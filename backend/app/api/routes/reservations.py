from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.routes.auth import (
    require_reservations_read,
    require_reservations_write,
)
from app.db.session import get_db
from app.schemas.reservations import (
    ReservationCollectionResponse,
    ReservationCreateRequest,
    ReservationDeleteRequest,
    ReservationDeleteResponse,
    ReservationUpdateRequest,
    ReservationResponse,
)
from app.services.reservations import (
    ReservationConflictError,
    ReservationNotFoundError,
    ReservationValidationError,
    cancel_reservation,
    consume_reservation,
    expire_reservation,
    create_reservation,
    delete_reservation,
    get_reservation,
    list_reservations,
    update_reservation,
)


router = APIRouter(
    prefix="/reservations",
    tags=["reservations"],
)


@router.get(
    "",
    response_model=ReservationCollectionResponse,
)
def read_reservations(
    status_filter: Literal[
        "active",
        "consumed",
        "cancelled",
        "expired",
    ] | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(require_reservations_read),
    db: Session = Depends(get_db),
) -> ReservationCollectionResponse:
    del current_user
    return list_reservations(
        db,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{reservation_id}",
    response_model=ReservationResponse,
)
def read_reservation(
    reservation_id: int,
    current_user=Depends(require_reservations_read),
    db: Session = Depends(get_db),
) -> ReservationResponse:
    del current_user
    try:
        return get_reservation(db, reservation_id)
    except ReservationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_reservation_record(
    payload: ReservationCreateRequest,
    current_user=Depends(require_reservations_write),
    db: Session = Depends(get_db),
) -> ReservationResponse:
    try:
        return create_reservation(
            db,
            payload,
            actor_user_id=current_user.id,
            commit=True,
        )
    except ReservationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ReservationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc




# PARTPILOT:RESERVATION_EDIT_ROUTE:V346
@router.put(
    "/{reservation_id}",
    response_model=ReservationResponse,
)
def update_reservation_record(
    reservation_id: int,
    payload: ReservationUpdateRequest,
    current_user=Depends(require_reservations_write),
    db: Session = Depends(get_db),
) -> ReservationResponse:
    try:
        return update_reservation(
            db,
            reservation_id,
            payload,
            actor_user_id=current_user.id,
            commit=True,
        )
    except ReservationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ReservationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ReservationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


# PARTPILOT:RESERVATION_DELETE_ROUTE:V351
@router.delete(
    "/{reservation_id}",
    response_model=ReservationDeleteResponse,
)
def delete_reservation_record(
    reservation_id: int,
    payload: ReservationDeleteRequest,
    current_user=Depends(require_reservations_write),
    db: Session = Depends(get_db),
) -> ReservationDeleteResponse:
    try:
        return delete_reservation(
            db,
            reservation_id,
            payload,
            actor_user_id=current_user.id,
            commit=True,
        )
    except ReservationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ReservationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ReservationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


# PARTPILOT:RESERVATION_CANCELLATION_ROUTE:V306
@router.post(
    "/{reservation_id}/cancel",
    response_model=ReservationResponse,
)
def cancel_reservation_record(
    reservation_id: int,
    current_user=Depends(require_reservations_write),
    db: Session = Depends(get_db),
) -> ReservationResponse:
    try:
        return cancel_reservation(
            db,
            reservation_id,
            actor_user_id=current_user.id,
            commit=True,
        )
    except ReservationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ReservationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


# PARTPILOT:RESERVATION_CONSUMPTION_ROUTE:V315
@router.post(
    "/{reservation_id}/consume",
    response_model=ReservationResponse,
)
def consume_reservation_record(
    reservation_id: int,
    current_user=Depends(require_reservations_write),
    db: Session = Depends(get_db),
) -> ReservationResponse:
    try:
        return consume_reservation(
            db,
            reservation_id,
            actor_user_id=current_user.id,
            commit=True,
        )
    except ReservationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ReservationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


# PARTPILOT:RESERVATION_EXPIRY_ROUTE:V320
@router.post(
    "/{reservation_id}/expire",
    response_model=ReservationResponse,
)
def expire_reservation_record(
    reservation_id: int,
    current_user=Depends(require_reservations_write),
    db: Session = Depends(get_db),
) -> ReservationResponse:
    try:
        return expire_reservation(
            db,
            reservation_id,
            actor_user_id=current_user.id,
            commit=True,
        )
    except ReservationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ReservationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


# PARTPILOT:RESERVATION_ACTIVITY_ROUTE:V338
from app.schemas.reservations import (
    ReservationActivityCollectionResponse,
)
from app.services.reservations import list_reservation_activity


@router.get(
    "/{reservation_id}/activity",
    response_model=ReservationActivityCollectionResponse,
)
def read_reservation_activity(
    reservation_id: int,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(require_reservations_read),
    db: Session = Depends(get_db),
) -> ReservationActivityCollectionResponse:
    del current_user
    try:
        return list_reservation_activity(
            db,
            reservation_id,
            limit=limit,
            offset=offset,
        )
    except ReservationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ReservationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
