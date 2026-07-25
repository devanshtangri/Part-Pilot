from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class PackageCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Package or form-factor name is required")
        return cleaned


class PackageResponse(BaseModel):
    id: int
    name: str
    is_builtin: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PackageCollectionResponse(BaseModel):
    total: int
    builtin_count: int
    custom_count: int
    packages: list[PackageResponse]
