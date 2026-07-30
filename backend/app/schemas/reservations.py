from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


ReservationStatus = Literal[
    "active",
    "consumed",
    "cancelled",
    "expired",
]


class ReservationItemCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part_id: int = Field(gt=0)
    quantity: int = Field(strict=True, gt=0)
    note: str | None = Field(default=None, max_length=5000)

    @field_validator("note")
    @classmethod
    def clean_optional_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


class ReservationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=180)
    notes: str | None = Field(default=None, max_length=10000)
    expiry_at: datetime | None = None
    items: list[ReservationItemCreateRequest] = Field(
        min_length=1,
        max_length=100,
    )

    @field_validator("label")
    @classmethod
    def clean_label(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Reservation label is required")
        return cleaned

    @field_validator("notes")
    @classmethod
    def clean_optional_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    @model_validator(mode="after")
    def validate_expiry(self) -> Self:
        if self.expiry_at is None:
            return self
        if (
            self.expiry_at.tzinfo is None
            or self.expiry_at.utcoffset() is None
        ):
            raise ValueError("Reservation expiry must include a timezone")
        if self.expiry_at.astimezone(timezone.utc) <= datetime.now(
            timezone.utc
        ):
            raise ValueError("Reservation expiry must be in the future")
        return self


# PARTPILOT:RESERVATION_EDIT_SCHEMA:V346
class ReservationUpdateRequest(ReservationCreateRequest):
    # Complete replacement payload for an existing active reservation.
    pass


class ReservationItemResponse(BaseModel):
    id: int
    reservation_id: int
    part_id: int | None = None
    part_number: str | None = None
    part_name: str | None = None
    quantity: int
    unit_price_snapshot: Decimal | None = None
    currency_snapshot: str | None = None
    note: str | None = None
    total_quantity: int | None = None
    reserved_quantity: int | None = None
    available_quantity: int | None = None


class ReservationResponse(BaseModel):
    id: int
    project_id: int | None = None
    label: str
    status: ReservationStatus
    notes: str | None = None
    created_by: str
    expiry_at: datetime | None = None
    estimated_reserved_value: Decimal | None = None
    currency_snapshot: str | None = None
    created_at: datetime
    updated_at: datetime
    items: list[ReservationItemResponse]


class ReservationCollectionResponse(BaseModel):
    total: int
    limit: int
    offset: int
    reservations: list[ReservationResponse]


# PARTPILOT:RESERVATION_DELETE_SCHEMA:V351
class ReservationDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation_label: str = Field(min_length=1, max_length=180)

    @field_validator("confirmation_label")
    @classmethod
    def clean_confirmation_label(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Reservation confirmation label is required")
        return cleaned


class ReservationDeleteResponse(BaseModel):
    id: int
    label: str
    previous_status: ReservationStatus
    deleted: bool
    removed_item_count: int
    detached_movement_count: int
    deleted_at: datetime


# PARTPILOT:RESERVATION_ACTIVITY_SCHEMA:V338
ReservationActivityKind = Literal["audit", "stock_movement"]


class ReservationActivityEntryResponse(BaseModel):
    key: str
    kind: ReservationActivityKind
    event_type: str
    occurred_at: datetime
    summary: str | None = None
    actor_type: str | None = None
    actor_user_id: int | None = None
    actor_display_name: str | None = None
    part_id: int | None = None
    part_number: str | None = None
    part_name: str | None = None
    movement_type: str | None = None
    quantity: int | None = None
    quantity_delta: int | None = None
    quantity_before: int | None = None
    quantity_after: int | None = None
    reserved_quantity_before: int | None = None
    reserved_quantity_after: int | None = None
    available_quantity_before: int | None = None
    available_quantity_after: int | None = None
    reason: str | None = None
    note: str | None = None
    source: str | None = None
    before_json: dict | list | None = None
    after_json: dict | list | None = None
    metadata_json: dict | list | None = None


class ReservationActivityCollectionResponse(BaseModel):
    reservation_id: int
    total: int
    limit: int
    offset: int
    activities: list[ReservationActivityEntryResponse]
