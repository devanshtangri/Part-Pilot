from __future__ import annotations

from starlette.responses import JSONResponse


RESTORE_VALIDATE_PATH = "/api/restores/validate"
DEFAULT_RESTORE_BODY_LIMIT_BYTES = (
    256 * 1024 * 1024
)


class RestoreUploadBodyTooLarge(RuntimeError):
    pass


def _content_length(
    scope,
) -> int | None:
    values = [
        value
        for key, value in scope.get("headers", ())
        if key.lower() == b"content-length"
    ]
    if not values:
        return None
    if len(values) != 1:
        raise ValueError(
            "Multiple Content-Length headers are not allowed."
        )
    try:
        parsed = int(values[0].decode("ascii"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(
            "Content-Length must be a non-negative integer."
        ) from exc
    if parsed < 0:
        raise ValueError(
            "Content-Length must be a non-negative integer."
        )
    return parsed


async def _send_limit_response(
    scope,
    receive,
    send,
    *,
    status_code: int,
    detail: str,
) -> None:
    response = JSONResponse(
        status_code=status_code,
        content={
            "detail": detail,
        },
        headers={
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )
    await response(scope, receive, send)


class RestoreUploadLimitMiddleware:
    def __init__(
        self,
        app,
        *,
        max_body_bytes: int = (
            DEFAULT_RESTORE_BODY_LIMIT_BYTES
        ),
    ) -> None:
        if max_body_bytes < 1:
            raise ValueError(
                "Restore upload body limit must be positive."
            )
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(
        self,
        scope,
        receive,
        send,
    ) -> None:
        if (
            scope.get("type") != "http"
            or scope.get("method") != "POST"
            or scope.get("path")
            != RESTORE_VALIDATE_PATH
        ):
            await self.app(scope, receive, send)
            return

        try:
            content_length = _content_length(scope)
        except ValueError:
            await _send_limit_response(
                scope,
                receive,
                send,
                status_code=400,
                detail="Invalid Content-Length header.",
            )
            return

        if (
            content_length is not None
            and content_length > self.max_body_bytes
        ):
            await _send_limit_response(
                scope,
                receive,
                send,
                status_code=413,
                detail="Restore upload exceeds the 256 MiB limit.",
            )
            return

        received = 0
        response_started = False

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(
                    message.get("body", b"")
                )
                if received > self.max_body_bytes:
                    raise RestoreUploadBodyTooLarge
            return message

        async def tracked_send(message):
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(
                scope,
                limited_receive,
                tracked_send,
            )
        except RestoreUploadBodyTooLarge:
            if response_started:
                raise
            await _send_limit_response(
                scope,
                receive,
                send,
                status_code=413,
                detail="Restore upload exceeds the 256 MiB limit.",
            )
