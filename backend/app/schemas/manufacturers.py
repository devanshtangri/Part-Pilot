from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ManufacturerCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=180)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Manufacturer name is required")
        return cleaned


class ManufacturerResponse(BaseModel):
    id: int
    name: str
    is_builtin: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ManufacturerCollectionResponse(BaseModel):
    total: int
    builtin_count: int
    custom_count: int
    manufacturers: list[ManufacturerResponse]
