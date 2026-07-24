from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Self
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator


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


class PartCreateRequest(BaseModel):
    part_type_id: int = Field(gt=0)
    manufacturer_id: int | None = Field(default=None, gt=0)
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
