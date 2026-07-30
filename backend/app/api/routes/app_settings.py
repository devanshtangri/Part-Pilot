from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.schemas.app_settings import (
    ReservationSettingsResponse,
    ReservationSettingsUpdateRequest,
    SearchSettingsResponse,
    SearchSettingsUpdateRequest,
)
from app.services.app_settings import (
    get_reservation_settings,
    get_search_settings,
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
