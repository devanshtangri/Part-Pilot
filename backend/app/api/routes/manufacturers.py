from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes.auth import (
    require_catalogues_read,
    require_catalogues_write,
)
from app.db.session import get_db
from app.schemas.manufacturers import (
    ManufacturerCollectionResponse,
    ManufacturerCreateRequest,
    ManufacturerResponse,
)
from app.services.manufacturers import (
    ManufacturerConflictError,
    create_manufacturer,
    list_manufacturers,
)


router = APIRouter(
    prefix="/manufacturers",
    tags=["manufacturers"],
)


@router.get(
    "",
    response_model=ManufacturerCollectionResponse,
)
def read_manufacturers(
    current_user=Depends(require_catalogues_read),
    db: Session = Depends(get_db),
) -> ManufacturerCollectionResponse:
    del current_user
    return list_manufacturers(db)


@router.post(
    "",
    response_model=ManufacturerResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_manufacturer_record(
    payload: ManufacturerCreateRequest,
    current_user=Depends(require_catalogues_write),
    db: Session = Depends(get_db),
) -> ManufacturerResponse:
    try:
        return create_manufacturer(
            db,
            payload,
            actor_user_id=current_user.id,
            commit=True,
        )
    except ManufacturerConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
