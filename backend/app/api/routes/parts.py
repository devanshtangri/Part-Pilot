from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.schemas.parts import (
    PartCollectionResponse,
    PartCreateRequest,
    PartMovementCollectionResponse,
    PartQuantityAdjustmentRequest,
    PartQuantityAdjustmentResponse,
    PartResponse,
    PartUpdateRequest,
    DeletedPartCollectionResponse,
    DeletedPartResponse,
    LowStockSummaryResponse,
)
from app.services.parts import (
    PartConflictError,
    PartNotFoundError,
    PartValidationError,
    adjust_part_quantity,
    create_part,
    get_part,
    list_part_movements,
    list_parts,
    update_part_metadata,
    list_deleted_parts,
    restore_part,
    soft_delete_part,
    list_low_stock_parts,
)


router = APIRouter(prefix="/parts", tags=["parts"])


@router.get("", response_model=PartCollectionResponse)
# PATCH 213: protected universal part search query
def read_parts(
    part_type_id: int | None = Query(default=None, gt=0),
    location_id: int | None = Query(default=None, gt=0),
    search: str | None = Query(default=None, max_length=180),
    # PATCH 229: PARTPILOT_STORED_PARTS_STOCK_FILTER_V229
    stock_status: Literal["all", "in", "low", "out"] = Query(
        default="all"
    ),
    limit: int = Query(default=100, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PartCollectionResponse:
    del current_user
    return list_parts(
        db,
        part_type_id=part_type_id,
        location_id=location_id,
        search=search,
        stock_status=stock_status,
        limit=limit,
        offset=offset,
    )


# PATCH 182: protected low-stock summary route
@router.get(
    "/low-stock",
    response_model=LowStockSummaryResponse,
)
def read_low_stock_parts(
    part_type_id: int | None = Query(default=None, gt=0),
    location_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=8, ge=1, le=50),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LowStockSummaryResponse:
    del current_user
    return list_low_stock_parts(
        db,
        part_type_id=part_type_id,
        location_id=location_id,
        limit=limit,
    )




@router.post(
    "",
    response_model=PartResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_inventory_part(
    payload: PartCreateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PartResponse:
    try:
        return create_part(
            db,
            payload,
            actor_user_id=current_user.id,
            commit=True,
        )
    except PartConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except PartValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


# PATCH 152: part soft-delete and restoration routes
@router.get(
    "/deleted",
    response_model=DeletedPartCollectionResponse,
)
def read_deleted_parts(
    limit: int = Query(default=100, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeletedPartCollectionResponse:
    del current_user
    return list_deleted_parts(
        db,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{part_id}/restore",
    response_model=PartResponse,
)
def restore_inventory_part(
    part_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PartResponse:
    try:
        return restore_part(
            db,
            part_id,
            actor_user_id=current_user.id,
            commit=True,
        )
    except PartNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PartConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{part_id}",
    response_model=DeletedPartResponse,
)
def delete_inventory_part(
    part_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeletedPartResponse:
    try:
        return soft_delete_part(
            db,
            part_id,
            actor_user_id=current_user.id,
            commit=True,
        )
    except PartNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PartConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


# PATCH 134: stock quantity adjustment and movement history routes
@router.post(
    "/{part_id}/quantity-adjustments",
    response_model=PartQuantityAdjustmentResponse,
)
def create_part_quantity_adjustment(
    part_id: int,
    payload: PartQuantityAdjustmentRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PartQuantityAdjustmentResponse:
    try:
        return adjust_part_quantity(
            db,
            part_id,
            payload,
            actor_user_id=current_user.id,
            commit=True,
        )
    except PartNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PartConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except PartValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/{part_id}/movements",
    response_model=PartMovementCollectionResponse,
)
def read_part_movements(
    part_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PartMovementCollectionResponse:
    del current_user
    try:
        return list_part_movements(db, part_id, limit=limit)
    except PartNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc



# PATCH 142: existing-part metadata update route
@router.put("/{part_id}", response_model=PartResponse)
def update_inventory_part(
    part_id: int,
    payload: PartUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PartResponse:
    try:
        return update_part_metadata(
            db,
            part_id,
            payload,
            actor_user_id=current_user.id,
            commit=True,
        )
    except PartNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PartConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except PartValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get("/{part_id}", response_model=PartResponse)
def read_part(
    part_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PartResponse:
    del current_user
    try:
        return get_part(db, part_id)
    except PartNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
