from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# PATCH 156: reusable location catalogue schemas
class LocationCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    note: str | None = Field(default=None, max_length=4000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Location name is required")
        return cleaned

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class LocationUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    note: str | None = Field(default=None, max_length=4000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Location name is required")
        return cleaned

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class LocationResponse(BaseModel):
    id: int
    name: str
    note: str | None
    part_count: int
    active_part_count: int
    deleted_part_count: int
    created_at: datetime
    updated_at: datetime


class LocationCollectionResponse(BaseModel):
    total: int
    locations: list[LocationResponse]


class LocationDeleteResponse(BaseModel):
    id: int
    name: str
    deleted: bool
