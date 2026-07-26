from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.schemas.locations import (
    LocationCollectionResponse,
    LocationCreateRequest,
    LocationDeleteResponse,
    LocationResponse,
    LocationUpdateRequest,
)
from app.services.locations import (
    LocationConflictError,
    LocationInUseError,
    LocationNotFoundError,
    create_location,
    delete_location,
    list_locations,
    update_location,
)


# PATCH 156: reusable location catalogue routes
router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("", response_model=LocationCollectionResponse)
def read_locations(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LocationCollectionResponse:
    del current_user
    return list_locations(db)


@router.post(
    "",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_location_record(
    payload: LocationCreateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LocationResponse:
    try:
        return create_location(
            db,
            payload,
            actor_user_id=current_user.id,
            commit=True,
        )
    except LocationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.put(
    "/{location_id}",
    response_model=LocationResponse,
)
def update_location_record(
    location_id: int,
    payload: LocationUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LocationResponse:
    try:
        return update_location(
            db,
            location_id,
            payload,
            actor_user_id=current_user.id,
            commit=True,
        )
    except LocationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LocationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{location_id}",
    response_model=LocationDeleteResponse,
)
def delete_location_record(
    location_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LocationDeleteResponse:
    try:
        return delete_location(
            db,
            location_id,
            actor_user_id=current_user.id,
            commit=True,
        )
    except LocationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LocationInUseError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
