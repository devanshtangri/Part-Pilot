from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# PARTPILOT:SYSTEM_HISTORY_SCHEMA:V406
HistoryKind = Literal["audit", "stock_movement"]


class HistoryEntryResponse(BaseModel):
    key: str
    kind: HistoryKind
    event_type: str
    occurred_at: datetime
    summary: str | None = None

    entity_type: str | None = None
    entity_id: int | None = None
    entity_label: str | None = None

    actor_type: str | None = None
    actor_user_id: int | None = None
    actor_display_name: str | None = None

    part_id: int | None = None
    part_number: str | None = None
    part_name: str | None = None

    reservation_id: int | None = None
    reservation_label: str | None = None
    project_id: int | None = None
    project_label: str | None = None

    movement_type: str | None = None
    quantity: int | None = None
    quantity_delta: int | None = None
    quantity_before: int | None = None
    quantity_after: int | None = None
    reserved_quantity_before: int | None = None
    reserved_quantity_after: int | None = None
    available_quantity_before: int | None = None
    available_quantity_after: int | None = None
    unit_price_snapshot: str | None = None
    currency_snapshot: str | None = None
    reason: str | None = None
    note: str | None = None
    source: str | None = None

    before_json: dict | list | None = None
    after_json: dict | list | None = None
    metadata_json: dict | list | None = None


class HistoryCollectionResponse(BaseModel):
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    entries: list[HistoryEntryResponse]


class HistoryFacetValueResponse(BaseModel):
    value: str
    count: int = Field(ge=0)


class HistoryActorOptionResponse(BaseModel):
    user_id: int
    display_name: str
    count: int = Field(ge=0)


class HistoryFilterOptionsResponse(BaseModel):
    kinds: list[HistoryFacetValueResponse]
    entity_types: list[HistoryFacetValueResponse]
    event_types: list[HistoryFacetValueResponse]
    actor_types: list[HistoryFacetValueResponse]
    movement_types: list[HistoryFacetValueResponse]
    sources: list[HistoryFacetValueResponse]
    actors: list[HistoryActorOptionResponse]
    earliest_at: datetime | None = None
    latest_at: datetime | None = None
