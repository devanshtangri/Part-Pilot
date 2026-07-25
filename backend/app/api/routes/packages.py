from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db.session import get_db
from app.schemas.packages import (
    PackageCollectionResponse,
    PackageCreateRequest,
    PackageResponse,
)
from app.services.packages import (
    PackageConflictError,
    create_package,
    list_packages,
)


router = APIRouter(prefix="/packages", tags=["packages"])


@router.get("", response_model=PackageCollectionResponse)
def read_packages(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PackageCollectionResponse:
    del current_user
    return list_packages(db)


@router.post(
    "",
    response_model=PackageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_package_record(
    payload: PackageCreateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PackageResponse:
    try:
        return create_package(
            db,
            payload,
            actor_user_id=current_user.id,
            commit=True,
        )
    except PackageConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
