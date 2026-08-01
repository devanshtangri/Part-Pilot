from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Literal

from starlette.responses import JSONResponse


LifecyclePhase = Literal[
    "ready",
    "maintenance",
    "stopping",
    "stopped",
]
PROBE_PATHS = frozenset(
    {
        "/health",
        "/api/health",
        "/ready",
        "/api/ready",
    }
)


class LifecycleStateError(RuntimeError):
    pass


@dataclass(frozen=True)
class LifecycleSnapshot:
    phase: LifecyclePhase
    reason: str | None
    active_requests: int
    accepting_requests: bool
    ready: bool
    generation: int


class ApplicationLifecycleState:
    def __init__(self) -> None:
        self._condition = threading.Condition(
            threading.RLock()
        )
        self._phase: LifecyclePhase = "ready"
        self._reason: str | None = None
        self._active_requests = 0
        self._accepting_requests = True
        self._ready = True
        self._generation = 0

    def _snapshot_locked(self) -> LifecycleSnapshot:
        return LifecycleSnapshot(
            phase=self._phase,
            reason=self._reason,
            active_requests=self._active_requests,
            accepting_requests=self._accepting_requests,
            ready=self._ready,
            generation=self._generation,
        )

    def snapshot(self) -> LifecycleSnapshot:
        with self._condition:
            return self._snapshot_locked()

    def mark_started(self) -> LifecycleSnapshot:
        with self._condition:
            if self._active_requests != 0:
                raise LifecycleStateError(
                    "Cannot mark the application ready while "
                    "requests are active."
                )
            self._phase = "ready"
            self._reason = None
            self._accepting_requests = True
            self._ready = True
            self._generation += 1
            self._condition.notify_all()
            return self._snapshot_locked()

    def try_start_request(self) -> bool:
        with self._condition:
            if not self._accepting_requests:
                return False
            self._active_requests += 1
            return True

    def finish_request(self) -> LifecycleSnapshot:
        with self._condition:
            if self._active_requests < 1:
                raise LifecycleStateError(
                    "Request accounting underflow."
                )
            self._active_requests -= 1
            self._condition.notify_all()
            return self._snapshot_locked()

    def begin_maintenance(
        self,
        reason: str,
    ) -> LifecycleSnapshot:
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise LifecycleStateError(
                "Maintenance reason cannot be empty."
            )
        with self._condition:
            if self._phase in {"stopping", "stopped"}:
                raise LifecycleStateError(
                    "Maintenance cannot begin while the "
                    "application is stopping or stopped."
                )
            self._phase = "maintenance"
            self._reason = normalized_reason
            self._accepting_requests = False
            self._ready = False
            self._generation += 1
            self._condition.notify_all()
            return self._snapshot_locked()

    def leave_maintenance(self) -> LifecycleSnapshot:
        with self._condition:
            if self._phase == "ready":
                return self._snapshot_locked()
            if self._phase != "maintenance":
                raise LifecycleStateError(
                    "Only maintenance mode can return to ready."
                )
            self._phase = "ready"
            self._reason = None
            self._accepting_requests = True
            self._ready = True
            self._generation += 1
            self._condition.notify_all()
            return self._snapshot_locked()

    def begin_shutdown(self) -> LifecycleSnapshot:
        with self._condition:
            self._phase = "stopping"
            self._reason = "application shutdown"
            self._accepting_requests = False
            self._ready = False
            self._generation += 1
            self._condition.notify_all()
            return self._snapshot_locked()

    def mark_stopped(self) -> LifecycleSnapshot:
        with self._condition:
            if self._active_requests != 0:
                raise LifecycleStateError(
                    "Cannot mark the application stopped while "
                    "requests remain active."
                )
            self._phase = "stopped"
            self._reason = "application stopped"
            self._accepting_requests = False
            self._ready = False
            self._generation += 1
            self._condition.notify_all()
            return self._snapshot_locked()

    def wait_for_drain(
        self,
        *,
        timeout: float,
        max_active_requests: int = 0,
    ) -> bool:
        if timeout < 0:
            raise LifecycleStateError(
                "Drain timeout cannot be negative."
            )
        if max_active_requests < 0:
            raise LifecycleStateError(
                "Maximum active requests cannot be negative."
            )

        deadline = time.monotonic() + timeout
        with self._condition:
            while (
                self._active_requests
                > max_active_requests
            ):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(timeout=remaining)
            return True


application_lifecycle = ApplicationLifecycleState()


class LifecycleRequestMiddleware:
    def __init__(
        self,
        app,
        *,
        state: ApplicationLifecycleState,
    ) -> None:
        self.app = app
        self.state = state

    async def __call__(
        self,
        scope,
        receive,
        send,
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "")
        if path in PROBE_PATHS:
            await self.app(scope, receive, send)
            return

        if not self.state.try_start_request():
            response = JSONResponse(
                status_code=503,
                content={
                    "detail": (
                        "Part Pilot is temporarily unavailable "
                        "while maintenance is in progress."
                    ),
                    "status": "maintenance",
                    "retryable": True,
                },
                headers={
                    "Cache-Control": "no-store, max-age=0",
                    "Pragma": "no-cache",
                    "Retry-After": "5",
                },
            )
            await response(scope, receive, send)
            return

        try:
            await self.app(scope, receive, send)
        finally:
            self.state.finish_request()
