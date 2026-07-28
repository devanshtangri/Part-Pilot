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
