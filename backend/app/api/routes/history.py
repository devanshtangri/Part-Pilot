from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.routes.auth import (
    require_history_read,
)
from app.db.session import get_db
from app.schemas.history import (
    HistoryCollectionResponse,
    HistoryFilterOptionsResponse,
)
from app.services.history import (
    HistoryValidationError,
    list_history,
    list_history_filter_options,
)


# PARTPILOT:SYSTEM_HISTORY_ROUTE:V406
router = APIRouter(
    prefix="/history",
    tags=["history"],
)


@router.get(
    "/filter-options",
    response_model=HistoryFilterOptionsResponse,
)
def read_history_filter_options(
    current_user=Depends(require_history_read),
    db: Session = Depends(get_db),
) -> HistoryFilterOptionsResponse:
    del current_user
    return list_history_filter_options(db)


@router.get(
    "",
    response_model=HistoryCollectionResponse,
)
def read_history(
    kind: Literal["audit", "stock_movement"] | None = Query(
        default=None
    ),
    entity_type: str | None = Query(
        default=None,
        max_length=80,
    ),
    event_type: str | None = Query(
        default=None,
        max_length=80,
    ),
    actor_type: str | None = Query(
        default=None,
        max_length=40,
    ),
    actor_user_id: int | None = Query(
        default=None,
        ge=1,
    ),
    movement_type: str | None = Query(
        default=None,
        max_length=60,
    ),
    from_time: datetime | None = Query(
        default=None,
        alias="from",
    ),
    to_time: datetime | None = Query(
        default=None,
        alias="to",
    ),
    query: str | None = Query(
        default=None,
        alias="q",
        max_length=200,
    ),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(require_history_read),
    db: Session = Depends(get_db),
) -> HistoryCollectionResponse:
    del current_user
    try:
        return list_history(
            db,
            kind=kind,
            entity_type=entity_type,
            event_type=event_type,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            movement_type=movement_type,
            from_time=from_time,
            to_time=to_time,
            query=query,
            limit=limit,
            offset=offset,
        )
    except HistoryValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
