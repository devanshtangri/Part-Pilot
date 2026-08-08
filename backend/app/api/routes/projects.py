from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.routes.auth import (
    require_projects_read,
    require_projects_write,
)
from app.db.session import get_db
from app.schemas.projects import (
    ProjectCollectionResponse,
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.services.projects import (
    ProjectConflictError,
    ProjectNotFoundError,
    ProjectValidationError,
    create_project,
    get_project,
    list_projects,
    reserve_project,
    update_project,
)


router = APIRouter(
    prefix="/projects",
    tags=["projects"],
)


@router.get(
    "",
    response_model=ProjectCollectionResponse,
)
def read_projects(
    status_filter: Literal[
        "draft",
        "reserved",
        "consumed",
        "cancelled",
    ] | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(require_projects_read),
    db: Session = Depends(get_db),
) -> ProjectCollectionResponse:
    del current_user
    return list_projects(
        db,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
)
def read_project(
    project_id: int,
    current_user=Depends(require_projects_read),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    del current_user
    try:
        return get_project(db, project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_record(
    payload: ProjectCreateRequest,
    current_user=Depends(require_projects_write),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    try:
        return create_project(
            db,
            payload,
            actor_user_id=current_user.id,
            commit=True,
        )
    except ProjectConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ProjectValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

# PARTPILOT:PROJECT_DRAFT_UPDATE_ROUTE:V379
@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
)
def update_project_record(
    project_id: int,
    payload: ProjectUpdateRequest,
    current_user=Depends(require_projects_write),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    try:
        return update_project(
            db,
            project_id,
            payload,
            actor_user_id=current_user.id,
            commit=True,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ProjectConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ProjectValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
# PARTPILOT:PROJECT_RESERVATION_ROUTE:V383
@router.post(
    "/{project_id}/reserve",
    response_model=ProjectResponse,
)
def reserve_project_record(
    project_id: int,
    current_user=Depends(require_projects_write),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    try:
        return reserve_project(
            db,
            project_id,
            actor_user_id=current_user.id,
            commit=True,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ProjectConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ProjectValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

# PARTPILOT:PROJECT_CONSUMPTION_ROUTE:V394
@router.post(
    "/{project_id}/consume",
    response_model=ProjectResponse,
)
def consume_project_record(
    project_id: int,
    current_user=Depends(require_projects_write),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    from app.services.projects import consume_project

    try:
        return consume_project(
            db,
            project_id,
            actor_user_id=current_user.id,
            commit=True,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ProjectConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

# PARTPILOT:PROJECT_CANCELLATION_ROUTE:V397
@router.post(
    "/{project_id}/cancel",
    response_model=ProjectResponse,
)
def cancel_project_record(
    project_id: int,
    current_user=Depends(require_projects_write),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    from app.services.projects import cancel_project

    try:
        return cancel_project(
            db,
            project_id,
            actor_user_id=current_user.id,
            commit=True,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ProjectConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
