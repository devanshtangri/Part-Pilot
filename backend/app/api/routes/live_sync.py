from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import StreamingResponse

from app.api.routes.auth import get_current_user
from app.core.lifecycle import application_lifecycle
from app.db.session import SessionLocal
from app.schemas.live_sync import LiveSyncStateResponse
from app.services.live_sync import (
    encode_sse_delivery,
    live_sync_broker,
)


router = APIRouter(
    prefix="/live",
    tags=["live-sync"],
)

STREAM_POLL_SECONDS = 0.10
STREAM_HEARTBEAT_SECONDS = 15.0


def require_live_sync_user_id(
    authorization: str | None = Header(default=None),
) -> int:
    # A streaming response must not keep a SQLAlchemy dependency/session
    # open for the lifetime of the connection. Validate the same browser
    # Bearer session contract, copy only the primitive user id, then close
    # the database session before StreamingResponse begins.
    with SessionLocal() as db:
        user = get_current_user(
            authorization=authorization,
            db=db,
        )
        return int(user.id)


@router.get(
    "/state",
    response_model=LiveSyncStateResponse,
)
def live_sync_state(
    response: Response,
    _user_id: int = Depends(require_live_sync_user_id),
) -> LiveSyncStateResponse:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return LiveSyncStateResponse.model_validate(
        live_sync_broker.state()
    )


async def _stream_events(
    request: Request,
    *,
    last_event_id: str | None,
):
    subscription_token, initial = live_sync_broker.subscribe(
        last_event_id
    )
    next_heartbeat = time.monotonic() + STREAM_HEARTBEAT_SECONDS
    try:
        if application_lifecycle.snapshot().phase != "ready":
            return

        for delivery in initial:
            yield encode_sse_delivery(delivery)

        while application_lifecycle.snapshot().phase == "ready":
            if await request.is_disconnected():
                break

            delivery = live_sync_broker.poll(
                subscription_token
            )
            if delivery is not None:
                yield encode_sse_delivery(delivery)
                continue

            now = time.monotonic()
            if now >= next_heartbeat:
                yield ": keepalive\n\n"
                next_heartbeat = now + STREAM_HEARTBEAT_SECONDS

            await asyncio.sleep(STREAM_POLL_SECONDS)
    finally:
        live_sync_broker.unsubscribe(subscription_token)


# PARTPILOT:AUTHENTICATED_LIVE_SYNC_STREAM:V687
@router.get(
    "/events",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Authenticated live invalidation stream",
            "content": {
                "text/event-stream": {},
            },
        },
    },
)
def live_sync_events(
    request: Request,
    last_event_id: str | None = Header(
        default=None,
        alias="Last-Event-ID",
    ),
    _user_id: int = Depends(require_live_sync_user_id),
) -> StreamingResponse:
    return StreamingResponse(
        _stream_events(
            request,
            last_event_id=last_event_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": (
                "no-store, no-cache, must-revalidate, max-age=0"
            ),
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
