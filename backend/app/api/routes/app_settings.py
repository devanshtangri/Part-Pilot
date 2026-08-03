from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.schemas.app_settings import (
    AppearanceSettingsResponse,
    AppearanceSettingsUpdateRequest,
    McpSettingsResponse,
    McpSettingsUpdateRequest,
    ReservationSettingsResponse,
    ReservationSettingsUpdateRequest,
    SearchSettingsResponse,
    SearchSettingsUpdateRequest,
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
