from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.schemas.app_settings import (
    AppearanceSettingsResponse,
    AppearanceSettingsUpdateRequest,
    McpDirectAuthKeyResponse,
    McpDirectAuthStatusResponse,
    McpSettingsResponse,
    McpSettingsUpdateRequest,
    ReservationSettingsResponse,
    ReservationSettingsUpdateRequest,
    SearchSettingsResponse,
    SearchSettingsUpdateRequest,
)
from app.services.mcp_direct_auth import (
    DIRECT_AUTH_BEARER_KEY,
    DIRECT_AUTH_DISABLED,
    McpDirectAuthConfigurationError,
    McpDirectAuthDecryptionError,
    McpDirectAuthNotConfiguredError,
    disable_direct_auth,
    get_direct_auth,
    reveal_bearer_key,
    rotate_bearer_key,
)

from app.services.app_settings import (
    AppearanceThemeUnavailableError,
    get_appearance_settings,
    get_mcp_settings,
    get_reservation_settings,
    get_search_settings,
    update_appearance_settings,
    update_mcp_settings,
    update_reservation_settings,
    update_search_settings,
)


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/search", response_model=SearchSettingsResponse)
def read_search_settings(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchSettingsResponse:
    del current_user
    return get_search_settings(db)


@router.patch("/search", response_model=SearchSettingsResponse)
def patch_search_settings(
    payload: SearchSettingsUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchSettingsResponse:
    return update_search_settings(
        db,
        payload,
        actor_user_id=current_user.id,
        commit=True,
    )


# PARTPILOT:RESERVATION_SETTINGS_ROUTE:V361
@router.get("/reservations", response_model=ReservationSettingsResponse)
def read_reservation_settings(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReservationSettingsResponse:
    del current_user
    return get_reservation_settings(db)


@router.patch("/reservations", response_model=ReservationSettingsResponse)
def patch_reservation_settings(
    payload: ReservationSettingsUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReservationSettingsResponse:
    return update_reservation_settings(
        db,
        payload,
        actor_user_id=current_user.id,
        commit=True,
    )


# PARTPILOT:APPEARANCE_SETTINGS_ROUTE:V411
@router.get(
    "/appearance",
    response_model=AppearanceSettingsResponse,
)
def read_appearance_settings(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppearanceSettingsResponse:
    del current_user
    return get_appearance_settings(db)


@router.patch(
    "/appearance",
    response_model=AppearanceSettingsResponse,
)
def patch_appearance_settings(
    payload: AppearanceSettingsUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppearanceSettingsResponse:
    try:
        return update_appearance_settings(
            db,
            payload,
            actor_user_id=current_user.id,
            commit=True,
        )
    except AppearanceThemeUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


# PARTPILOT:MCP_SETTINGS_ROUTE:V473
@router.get("/mcp", response_model=McpSettingsResponse)
def read_mcp_settings(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpSettingsResponse:
    del current_user
    return get_mcp_settings(db)


@router.patch("/mcp", response_model=McpSettingsResponse)
def patch_mcp_settings(
    payload: McpSettingsUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpSettingsResponse:
    return update_mcp_settings(
        db,
        payload,
        actor_user_id=current_user.id,
        commit=True,
    )


# PARTPILOT:MCP_DIRECT_AUTH_API_ROUTE:V485
def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"

def _direct_auth_status(db: Session) -> McpDirectAuthStatusResponse:
    record = get_direct_auth(db)
    configured = bool(
        record is not None
        and record.mode == DIRECT_AUTH_BEARER_KEY
        and record.key_ciphertext
        and record.key_digest
        and record.key_prefix
    )
    return McpDirectAuthStatusResponse(
        mode=record.mode if record is not None else DIRECT_AUTH_DISABLED,
        configured=configured,
        masked_key=(f"{record.key_prefix}••••••••" if configured and record is not None else None),
        rotated_at=record.rotated_at if record is not None else None,
        last_used_at=record.last_used_at if record is not None else None,
    )

@router.get("/mcp/direct-auth", response_model=McpDirectAuthStatusResponse)
def read_mcp_direct_auth(response: Response, current_user=Depends(get_current_user), db: Session=Depends(get_db)) -> McpDirectAuthStatusResponse:
    del current_user
    _no_store(response)
    return _direct_auth_status(db)

@router.post("/mcp/direct-auth/bearer-key", response_model=McpDirectAuthKeyResponse)
def rotate_mcp_direct_key(response: Response, current_user=Depends(get_current_user), db: Session=Depends(get_db)) -> McpDirectAuthKeyResponse:
    _no_store(response)
    try:
        issued=rotate_bearer_key(db,actor_user_id=current_user.id,commit=True)
    except McpDirectAuthConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
            headers={
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        ) from exc
    current=_direct_auth_status(db)
    return McpDirectAuthKeyResponse(**current.model_dump(),key=issued.plaintext_key)

@router.post("/mcp/direct-auth/reveal", response_model=McpDirectAuthKeyResponse)
def reveal_mcp_direct_key(response: Response, current_user=Depends(get_current_user), db: Session=Depends(get_db)) -> McpDirectAuthKeyResponse:
    _no_store(response)
    try:
        key=reveal_bearer_key(db,actor_user_id=current_user.id,commit=True)
    except (McpDirectAuthConfigurationError,McpDirectAuthDecryptionError,McpDirectAuthNotConfiguredError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
            headers={
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        ) from exc
    current=_direct_auth_status(db)
    return McpDirectAuthKeyResponse(**current.model_dump(),key=key)

@router.delete("/mcp/direct-auth", response_model=McpDirectAuthStatusResponse)
def delete_mcp_direct_auth(response: Response, current_user=Depends(get_current_user), db: Session=Depends(get_db)) -> McpDirectAuthStatusResponse:
    _no_store(response)
    disable_direct_auth(db,actor_user_id=current_user.id,commit=True)
    return _direct_auth_status(db)
