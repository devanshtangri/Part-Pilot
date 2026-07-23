from __future__ import annotations

import re
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator


PartTypeFieldKind = Literal[
    "text",
    "number",
    "boolean",
    "dropdown",
    "url",
    "unit_value",
]

_FIELD_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class PartTypeFieldCreateRequest(BaseModel):
    field_key: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=160)
    field_type: PartTypeFieldKind = "text"
    is_required: bool = False
    options: list[str] = Field(default_factory=list)
    default_unit: str | None = Field(default=None, max_length=30)
    help_text: str | None = Field(default=None, max_length=1000)

    @field_validator("field_key")
    @classmethod
    def validate_field_key(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not _FIELD_KEY_RE.fullmatch(cleaned):
            raise ValueError(
                "Field keys must start with a letter and contain only "
                "lowercase letters, numbers, and underscores"
            )
        return cleaned

    @field_validator("label")
    @classmethod
    def clean_label(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Field label is required")
        return cleaned

    @field_validator("default_unit", "help_text")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    @model_validator(mode="after")
    def validate_field_configuration(self) -> Self:
        cleaned_options: list[str] = []
        seen: set[str] = set()

        for raw_option in self.options:
            option = " ".join(raw_option.split())
            if not option:
                continue
            key = option.casefold()
            if key in seen:
                continue
            seen.add(key)
            cleaned_options.append(option)

        if len(cleaned_options) > 50:
            raise ValueError("Dropdown fields support at most 50 options")

        if self.field_type == "dropdown":
            if len(cleaned_options) < 2:
                raise ValueError(
                    "Dropdown fields require at least two unique options"
                )
            self.options = cleaned_options
        else:
            self.options = []

        if self.field_type != "unit_value":
            self.default_unit = None

        return self


class PartTypeCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    fields: list[PartTypeFieldCreateRequest] = Field(
        default_factory=list,
        max_length=40,
    )

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("Part type name must contain at least 2 characters")
        return cleaned

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    @model_validator(mode="after")
    def validate_unique_field_keys(self) -> Self:
        seen: set[str] = set()
        duplicates: set[str] = set()

        for field in self.fields:
            if field.field_key in seen:
                duplicates.add(field.field_key)
            seen.add(field.field_key)

        if duplicates:
            raise ValueError(
                "Field keys must be unique: " + ", ".join(sorted(duplicates))
            )

        return self


# PATCH 079: custom part type update schemas
class PartTypeFieldUpdateRequest(BaseModel):
    id: int | None = None
    field_key: str
    label: str
    field_type: str
    is_required: bool = False
    options: list[str] | None = None
    default_unit: str | None = None
    help_text: str | None = None


class PartTypeUpdateRequest(BaseModel):
    name: str
    description: str | None = None
    fields: list[PartTypeFieldUpdateRequest]

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
