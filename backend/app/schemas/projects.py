from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ProjectStatus = Literal[
    "draft",
    "reserved",
    "consumed",
    "cancelled",
]


class ProjectItemCreateRequest(BaseModel):
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


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=5000)
    notes: str | None = Field(default=None, max_length=10000)
    items: list[ProjectItemCreateRequest] = Field(
        min_length=1,
        max_length=100,
    )

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Project name is required")
        return cleaned

    @field_validator("description", "notes")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


class ProjectUpdateRequest(ProjectCreateRequest):
    """Replace the editable fields and item plan for a Draft Project."""


class ProjectItemResponse(BaseModel):
    id: int
    project_id: int
    part_id: int | None = None
    part_number: str | None = None
    part_name: str | None = None
    part_is_deleted: bool | None = None
    quantity: int
    unit_price_snapshot: Decimal | None = None
    currency_snapshot: str | None = None
    note: str | None = None
    total_quantity: int | None = None
    reserved_quantity: int | None = None
    available_quantity: int | None = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    status: ProjectStatus
    notes: str | None = None
    created_by: str
    estimated_total_value: Decimal | None = None
    currency_snapshot: str | None = None
    created_at: datetime
    updated_at: datetime
    item_count: int
    total_units: int
    items: list[ProjectItemResponse]


class ProjectCollectionResponse(BaseModel):
    total: int
    limit: int
    offset: int
    projects: list[ProjectResponse]
