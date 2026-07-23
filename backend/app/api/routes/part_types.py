from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.schemas.part_types import (
    PartTypeCollectionResponse,
    PartTypeResponse,
)
from app.services.part_types import get_part_type, list_part_types

router = APIRouter(prefix="/part-types", tags=["part-types"])


@router.get("", response_model=PartTypeCollectionResponse)
def read_part_types(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PartTypeCollectionResponse:
    del current_user
    return list_part_types(db)


@router.get("/{part_type_id}", response_model=PartTypeResponse)
def read_part_type(
    part_type_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PartTypeResponse:
    del current_user

    part_type = get_part_type(db, part_type_id)
    if part_type is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Part type not found",
        )

    return part_type
