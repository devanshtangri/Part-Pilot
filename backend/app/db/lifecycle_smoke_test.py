from __future__ import annotations

import threading
import time

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.lifecycle import (
    ApplicationLifecycleState,
    LifecycleStateError,
    application_lifecycle,
)
from app.db.session import (
    SessionLocal,
    database_pool_status,
    dispose_database_engine,
)
from app.main import app as fastapi_app


class LifecycleSmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise LifecycleSmokeFailure(message)


def check_state_coordinator() -> None:
    state = ApplicationLifecycleState()
    initial = state.snapshot()
    if (
        initial.phase != "ready"
        or not initial.ready
        or not initial.accepting_requests
        or initial.active_requests != 0
    ):
        fail(
            f"Initial lifecycle state is incorrect: {initial}"
        )

    if not state.try_start_request():
        fail("Ready lifecycle state rejected a request.")
    active = state.snapshot()
    if active.active_requests != 1:
        fail(
            "Lifecycle request accounting did not increment."
        )

    maintenance = state.begin_maintenance(
        "lifecycle smoke"
    )
    if (
        maintenance.phase != "maintenance"
        or maintenance.ready
        or maintenance.accepting_requests
        or state.try_start_request()
    ):
        fail(
            "Maintenance did not close the request gate."
        )

    result: list[bool] = []

    def wait_for_drain() -> None:
        result.append(
            state.wait_for_drain(
                timeout=2.0,
                max_active_requests=0,
            )
        )

    thread = threading.Thread(
        target=wait_for_drain,
        daemon=True,
    )
    thread.start()
    time.sleep(0.05)
    if result:
        fail(
            "Drain completed before the active request ended."
        )
    state.finish_request()
    thread.join(timeout=3.0)
    if thread.is_alive() or result != [True]:
        fail(
            f"Lifecycle drain did not complete: {result}"
        )

    ready = state.leave_maintenance()
    if (
        ready.phase != "ready"
        or not ready.ready
        or not ready.accepting_requests
    ):
        fail(
            "Lifecycle did not return to ready state."
        )

    try:
        state.finish_request()
    except LifecycleStateError:
        pass
    else:
        fail(
            "Lifecycle request underflow was not rejected."
        )

    state.begin_shutdown()
    if state.try_start_request():
        fail("Stopping lifecycle accepted a request.")
    stopped = state.mark_stopped()
    if (
        stopped.phase != "stopped"
        or stopped.ready
        or stopped.accepting_requests
    ):
        fail(
            "Lifecycle stopped state is incorrect."
        )


def check_http_gate_and_readiness() -> None:
    with TestClient(fastapi_app) as client:
        paths = client.get(
            "/openapi.json"
        ).json().get("paths", {})
        if set(paths.get("/ready", {})) != {"get"}:
            fail(
                "Root readiness OpenAPI contract is incorrect."
            )
        if set(paths.get("/api/ready", {})) != {"get"}:
            fail(
                "API readiness OpenAPI contract is incorrect."
            )

        health = client.get("/api/health")
        if (
            health.status_code != 200
            or health.json().get("status") != "ok"
        ):
            fail(
                "Liveness endpoint changed unexpectedly."
            )

        ready = client.get("/api/ready")
        payload = ready.json()
        if (
            ready.status_code != 200
            or payload.get("status") != "ready"
            or payload.get("phase") != "ready"
            or payload.get("accepting_requests") is not True
            or payload.get("active_requests") != 0
            or ready.headers.get("cache-control")
            != "no-store, max-age=0"
        ):
            fail(
                f"Ready response is incorrect: "
                f"{ready.status_code} {payload}"
            )

        application_lifecycle.begin_maintenance(
            "lifecycle HTTP smoke"
        )
        try:
            blocked = client.get("/api/setup-status")
            if (
                blocked.status_code != 503
                or blocked.json().get("status")
                != "maintenance"
                or blocked.json().get("retryable") is not True
                or blocked.headers.get("retry-after") != "5"
                or blocked.headers.get("cache-control")
                != "no-store, max-age=0"
            ):
                fail(
                    "Maintenance middleware did not reject "
                    f"a new request correctly: "
                    f"{blocked.status_code} {blocked.text}"
                )

            not_ready = client.get("/api/ready")
            not_ready_payload = not_ready.json()
            if (
                not_ready.status_code != 503
                or not_ready_payload.get("status")
                != "not_ready"
                or not_ready_payload.get("phase")
                != "maintenance"
                or not_ready_payload.get(
                    "accepting_requests"
                )
                is not False
            ):
                fail(
                    "Readiness did not report maintenance."
                )

            live_during_maintenance = client.get(
                "/api/health"
            )
            if (
                live_during_maintenance.status_code != 200
                or live_during_maintenance.json().get(
                    "status"
                )
                != "ok"
            ):
                fail(
                    "Liveness was blocked during maintenance."
                )
        finally:
            application_lifecycle.leave_maintenance()

        recovered = client.get("/api/setup-status")
        if recovered.status_code == 503:
            fail(
                "Request gate did not reopen after maintenance."
            )
        final_ready = client.get("/api/ready")
        if (
            final_ready.status_code != 200
            or final_ready.json().get("phase")
            != "ready"
        ):
            fail(
                "Readiness did not recover after maintenance."
            )

    shutdown = application_lifecycle.snapshot()
    if (
        shutdown.phase != "stopped"
        or shutdown.active_requests != 0
        or shutdown.ready
        or shutdown.accepting_requests
    ):
        fail(
            f"Lifespan shutdown state is incorrect: {shutdown}"
        )


def check_engine_disposal_and_reconnect() -> None:
    application_lifecycle.mark_started()
    with SessionLocal() as db:
        if db.execute(text("SELECT 1")).scalar() != 1:
            fail(
                "Database was unavailable before disposal."
            )
    before_status = database_pool_status()
    dispose_database_engine()
    after_status = database_pool_status()

    with SessionLocal() as db:
        if db.execute(text("SELECT 1")).scalar() != 1:
            fail(
                "Database did not reconnect after disposal."
            )
        foreign_keys = db.execute(
            text("PRAGMA foreign_keys")
        ).scalar()
        if foreign_keys != 1:
            fail(
                "SQLite foreign-key listener was lost after "
                "engine disposal."
            )

    if not before_status or not after_status:
        fail(
            "Database pool status was not available."
        )


def main() -> None:
    check_state_coordinator()
    check_http_gate_and_readiness()
    check_engine_disposal_and_reconnect()
    print(
        "[PASS] Lifecycle foundation provides a thread-safe "
        "maintenance gate, bounded drain accounting, liveness/"
        "readiness separation, lifespan shutdown disposal, "
        "post-disposal database reconnection, and maintenance "
        "HTTP behavior without exposing restore controls"
    )


if __name__ == "__main__":
    main()
