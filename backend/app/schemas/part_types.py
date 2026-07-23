from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class PartTypeFieldResponse(BaseModel):
    id: int
    field_key: str
    label: str
    field_type: str
    is_required: bool
    sort_order: int
    options: list[Any] | dict[str, Any] | None = None
    default_unit: str | None = None
    help_text: str | None = None


class PartTypeResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    is_builtin: bool
    is_active: bool
    template_version: int
    field_count: int
    fields: list[PartTypeFieldResponse]


class PartTypeCollectionResponse(BaseModel):
    total: int
    builtin_count: int
    custom_count: int
    total_fields: int
    part_types: list[PartTypeResponse]
