from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Self
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PartFieldValueCreateRequest(BaseModel):
    field_id: int = Field(gt=0)
    value_text: str | None = Field(default=None, max_length=5000)
    value_number: Decimal | None = None
    value_bool: bool | None = None
    unit: str | None = Field(default=None, max_length=30)

    @field_validator("value_text", "unit")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    @model_validator(mode="after")
    def validate_one_typed_value(self) -> Self:
        present = sum(
            value is not None
            for value in (
                self.value_text,
                self.value_number,
                self.value_bool,
            )
        )
        if present > 1:
            raise ValueError(
                "A template field value must use only one typed value"
            )
        return self


# PATCH 160: reusable part location assignment schemas
class PartCreateRequest(BaseModel):
    part_type_id: int = Field(gt=0)
    manufacturer_id: int | None = Field(default=None, gt=0)
    location_id: int | None = Field(default=None, gt=0)
    part_number: str | None = Field(default=None, max_length=160)
    name: str | None = Field(default=None, max_length=220)
    description: str | None = Field(default=None, max_length=5000)
    package: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=10000)
    total_quantity: int = Field(default=0, ge=0)
    unit_price: Decimal | None = Field(default=None, ge=0)
    purchase_link: str | None = Field(default=None, max_length=2000)
    low_stock_enabled: bool = False
    low_stock_threshold: int | None = Field(default=None, ge=0)
    field_values: list[PartFieldValueCreateRequest] = Field(
        default_factory=list,
        max_length=100,
    )

    @field_validator(
        "part_number",
        "name",
        "description",
        "package",
        "notes",
        "purchase_link",
    )
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    @model_validator(mode="after")
    def validate_part(self) -> Self:
        if not self.name and not self.part_number:
            raise ValueError(
                "Enter at least a part name or part number"
            )

        if self.low_stock_enabled and self.low_stock_threshold is None:
            raise ValueError(
                "Low-stock threshold is required when alerts are enabled"
            )

        if not self.low_stock_enabled:
            self.low_stock_threshold = None

        if self.purchase_link:
            parsed = urlparse(self.purchase_link)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(
                    "Purchase link must be a valid HTTP or HTTPS URL"
                )

        field_ids = [item.field_id for item in self.field_values]
        if len(field_ids) != len(set(field_ids)):
            raise ValueError(
                "Each template field may be submitted only once"
            )

        return self



# PATCH 142: existing-part metadata update schema
class PartUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part_type_id: int = Field(gt=0)
    manufacturer_id: int | None = Field(default=None, gt=0)
    location_id: int | None = Field(default=None, gt=0)
    part_number: str | None = Field(default=None, max_length=160)
    name: str | None = Field(default=None, max_length=220)
    description: str | None = Field(default=None, max_length=5000)
    package: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=10000)
    unit_price: Decimal | None = Field(default=None, ge=0)
    purchase_link: str | None = Field(default=None, max_length=2000)
    low_stock_enabled: bool = False
    low_stock_threshold: int | None = Field(default=None, ge=0)
    field_values: list[PartFieldValueCreateRequest] = Field(
        default_factory=list,
        max_length=100,
    )

    @field_validator(
        "part_number",
        "name",
        "description",
        "package",
        "notes",
        "purchase_link",
    )
    @classmethod
    def clean_optional_metadata_text(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    @model_validator(mode="after")
    def validate_metadata(self) -> Self:
        if not self.name and not self.part_number:
            raise ValueError(
                "Enter at least a part name or part number"
            )

        if self.low_stock_enabled and self.low_stock_threshold is None:
            raise ValueError(
                "Low-stock threshold is required when alerts are enabled"
            )

        if not self.low_stock_enabled:
            self.low_stock_threshold = None

        if self.purchase_link:
            parsed = urlparse(self.purchase_link)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(
                    "Purchase link must be a valid HTTP or HTTPS URL"
                )

        field_ids = [item.field_id for item in self.field_values]
        if len(field_ids) != len(set(field_ids)):
            raise ValueError(
                "Each template field may be submitted only once"
            )

        return self


class PartFieldValueResponse(BaseModel):
    id: int
    field_id: int
    field_key: str
    label: str
    field_type: str
    is_required: bool
    value_text: str | None = None
    value_number: Decimal | None = None
    value_bool: bool | None = None
    unit: str | None = None


class PartResponse(BaseModel):
    id: int
    part_type_id: int
    part_type_name: str
    manufacturer_id: int | None = None
    manufacturer_name: str | None = None
    location_id: int | None = None
    location_name: str | None = None
    part_number: str | None = None
    name: str | None = None
    description: str | None = None
    package: str | None = None
    notes: str | None = None
    total_quantity: int
    reserved_quantity: int
    available_quantity: int
    unit_price: Decimal | None = None
    purchase_link: str | None = None
    low_stock_enabled: bool
    low_stock_threshold: int | None = None
    is_low_stock: bool
    created_at: datetime
    updated_at: datetime
    field_values: list[PartFieldValueResponse]


class PartCollectionResponse(BaseModel):
    total: int
    limit: int
    offset: int
    parts: list[PartResponse]


# PARTPILOT:WHOLE_INVENTORY_METRICS_SCHEMA:V724
class InventoryMetricsResponse(BaseModel):
    active_part_count: int = Field(ge=0)
    physical_quantity: int = Field(ge=0)
    reserved_quantity: int = Field(ge=0)
    available_quantity: int = Field(ge=0)
    priced_part_count: int = Field(ge=0)
    inventory_value: Decimal = Field(ge=0)
    stock_alert_count: int = Field(ge=0)
    low_stock_count: int = Field(ge=0)
    out_of_stock_count: int = Field(ge=0)


# PATCH 182: dashboard-ready low-stock summary schema
class LowStockSummaryResponse(BaseModel):
    total: int
    low_stock_count: int
    out_of_stock_count: int
    limit: int
    parts: list[PartResponse]

# PATCH 152: part soft-delete and restoration schemas
class DeletedPartResponse(PartResponse):
    is_deleted: bool
    deleted_at: datetime


class DeletedPartCollectionResponse(BaseModel):
    total: int
    limit: int
    offset: int
    parts: list[DeletedPartResponse]


# PARTPILOT:PERMANENT_PART_PURGE_SCHEMA:V607
class DeletedPartPurgeRequest(BaseModel):
    part_ids: list[int] = Field(min_length=1, max_length=250)
    confirmation: Literal["DELETE"]

    @field_validator("part_ids")
    @classmethod
    def validate_part_ids(cls, value: list[int]) -> list[int]:
        if any(part_id <= 0 for part_id in value):
            raise ValueError("Part IDs must be positive integers")
        if len(set(value)) != len(value):
            raise ValueError("Part IDs must be unique")
        return value


class DeletedPartPurgeResponse(BaseModel):
    purged_count: int
    purged_ids: list[int]
    detached_movement_count: int
    detached_project_item_count: int
    detached_reservation_item_count: int

# PATCH 134: stock quantity adjustment and movement history schemas
class PartQuantityAdjustmentRequest(BaseModel):
    operation: Literal["add", "remove", "consume", "correction"]
    quantity: int = Field(
        strict=True,
        description=(
            "Positive units for add, remove, and consume. Correction accepts "
            "a signed non-zero delta."
        ),
    )
    reason: str | None = Field(default=None, max_length=180)
    note: str | None = Field(default=None, max_length=5000)

    @field_validator("reason", "note")
    @classmethod
    def clean_optional_adjustment_text(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    @model_validator(mode="after")
    def validate_adjustment(self) -> Self:
        if self.quantity == 0:
            raise ValueError("Quantity adjustment cannot be zero")
        if (
            self.operation in {"add", "remove", "consume"}
            and self.quantity < 0
        ):
            raise ValueError(
                "Add, remove, and consume quantities must be positive"
            )
        if self.operation == "correction" and self.reason is None:
            raise ValueError("Correction reason is required")
        return self


class StockMovementResponse(BaseModel):
    id: int
    part_id: int | None = None
    movement_type: str
    quantity_delta: int
    quantity_before: int | None = None
    quantity_after: int | None = None
    reserved_quantity_before: int | None = None
    reserved_quantity_after: int | None = None
    available_quantity_before: int | None = None
    available_quantity_after: int | None = None
    unit_price_snapshot: Decimal | None = None
    currency_snapshot: str | None = None
    reason: str | None = None
    note: str | None = None
    source: str
    actor_user_id: int | None = None
    created_at: datetime


class PartQuantityAdjustmentResponse(BaseModel):
    operation: Literal["add", "remove", "consume", "correction"]
    part: PartResponse
    movement: StockMovementResponse


class PartMovementCollectionResponse(BaseModel):
    part_id: int
    movements: list[StockMovementResponse]
