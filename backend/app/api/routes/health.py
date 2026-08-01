from fastapi import APIRouter
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.core.lifecycle import application_lifecycle

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.env,
    }


# PARTPILOT:READINESS_ROUTE:V436
@router.get(
    "/ready",
    responses={
        503: {
            "description": (
                "Application is draining, in maintenance, "
                "stopping, or stopped."
            ),
        },
    },
)
def readiness_check():
    settings = get_settings()
    snapshot = application_lifecycle.snapshot()
    payload = {
        "status": (
            "ready" if snapshot.ready else "not_ready"
        ),
        "app": settings.app_name,
        "environment": settings.env,
        "phase": snapshot.phase,
        "accepting_requests": (
            snapshot.accepting_requests
        ),
        "active_requests": snapshot.active_requests,
    }
    headers = {
        "Cache-Control": "no-store, max-age=0",
        "Pragma": "no-cache",
    }
    if not snapshot.ready:
        return JSONResponse(
            status_code=503,
            content=payload,
            headers=headers,
        )
    return JSONResponse(
        status_code=200,
        content=payload,
        headers=headers,
    )
