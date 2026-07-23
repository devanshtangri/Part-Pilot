from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.schemas.part_types import (
    PartTypeCollectionResponse,
    PartTypeCreateRequest,
    PartTypeResponse,
)
from app.services.part_types import (
    create_custom_part_type,
    get_part_type,
    list_part_types,
)
from app.schemas.part_types import (
    PartTypeUpdateRequest as ManagementPartTypeUpdateRequest,
)
from app.services.part_types import (
    PartTypeUpdateConflictError,
    PartTypeUpdateForbiddenError,
    PartTypeUpdateNotFoundError,
    PartTypeUpdateValidationError,
    update_custom_part_type,
)


router = APIRouter(prefix="/part-types", tags=["part-types"])


@router.get("", response_model=PartTypeCollectionResponse)
def read_part_types(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PartTypeCollectionResponse:
    del current_user
    return list_part_types(db)


@router.post(
    "",
    response_model=PartTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_part_type(
    payload: PartTypeCreateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PartTypeResponse:
    try:
        return create_custom_part_type(
            db,
            payload,
            actor_user_id=current_user.id,
            commit=True,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A part type or field with these values already exists",
        ) from exc
    except Exception:
        db.rollback()
        raise


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

# PATCH 079: custom part type update route
@router.put(
    "/{part_type_id}",
    response_model=PartTypeResponse,
)
def update_part_type(
    part_type_id: int,
    payload: ManagementPartTypeUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PartTypeResponse:
    try:
        return update_custom_part_type(
            db,
            part_type_id,
            payload,
            actor_user_id=current_user.id,
            commit=True,
        )
    except PartTypeUpdateNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PartTypeUpdateForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except PartTypeUpdateConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except PartTypeUpdateValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
