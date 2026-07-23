from __future__ import annotations
import re

from collections import defaultdict

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.utils import slugify
from app.models import AuditLog, PartType, PartTypeField
from app.schemas.part_types import (
    PartTypeCollectionResponse,
    PartTypeCreateRequest,
    PartTypeFieldResponse,
    PartTypeResponse,
)
from sqlalchemy import select as management_select
from sqlalchemy.exc import IntegrityError as ManagementIntegrityError
from app.db.utils import (
    clean_text as management_clean_text,
    slugify as management_slugify,
)
from app.models import (
    AuditLog as ManagementAuditLog,
    PartFieldValue as ManagementPartFieldValue,
    PartType as ManagementPartType,
    PartTypeField as ManagementPartTypeField,
)
from app.schemas.part_types import (
    PartTypeUpdateRequest as ManagementPartTypeUpdateRequest,
)


def _field_response(field: PartTypeField) -> PartTypeFieldResponse:
    return PartTypeFieldResponse(
        id=field.id,
        field_key=field.field_key,
        label=field.label,
        field_type=field.field_type,
        is_required=field.is_required,
        sort_order=field.sort_order,
        options=field.options_json,
        default_unit=field.default_unit,
        help_text=field.help_text,
    )


def _type_response(
    part_type: PartType,
    fields: list[PartTypeField],
) -> PartTypeResponse:
    field_responses = [_field_response(field) for field in fields]
    return PartTypeResponse(
        id=part_type.id,
        name=part_type.name,
        slug=part_type.slug,
        description=part_type.description,
        is_builtin=part_type.is_builtin,
        is_active=part_type.is_active,
        template_version=part_type.template_version,
        field_count=len(field_responses),
        fields=field_responses,
    )


def list_part_types(db: Session) -> PartTypeCollectionResponse:
    part_types = list(
        db.execute(
            select(PartType).order_by(
                PartType.is_builtin.desc(),
                PartType.name.asc(),
            )
        ).scalars()
    )
    fields = list(
        db.execute(
            select(PartTypeField).order_by(
                PartTypeField.part_type_id.asc(),
                PartTypeField.sort_order.asc(),
                PartTypeField.id.asc(),
            )
        ).scalars()
    )

    fields_by_type: dict[int, list[PartTypeField]] = defaultdict(list)
    for field in fields:
        fields_by_type[field.part_type_id].append(field)

    responses = [
        _type_response(
            part_type,
            fields_by_type.get(part_type.id, []),
        )
        for part_type in part_types
    ]
    builtin_count = sum(1 for item in responses if item.is_builtin)

    return PartTypeCollectionResponse(
        total=len(responses),
        builtin_count=builtin_count,
        custom_count=len(responses) - builtin_count,
        total_fields=sum(item.field_count for item in responses),
        part_types=responses,
    )


def get_part_type(
    db: Session,
    part_type_id: int,
) -> PartTypeResponse | None:
    part_type = db.get(PartType, part_type_id)
    if part_type is None:
        return None

    fields = list(
        db.execute(
            select(PartTypeField)
            .where(PartTypeField.part_type_id == part_type_id)
            .order_by(
                PartTypeField.sort_order.asc(),
                PartTypeField.id.asc(),
            )
        ).scalars()
    )
    return _type_response(part_type, fields)


def create_custom_part_type(
    db: Session,
    payload: PartTypeCreateRequest,
    *,
    actor_user_id: int | None,
    commit: bool = True,
) -> PartTypeResponse:
    slug = slugify(payload.name)
    normalized_name = payload.name.casefold()

    existing_id = db.execute(
        select(PartType.id).where(
            or_(
                func.lower(PartType.name) == normalized_name,
                PartType.slug == slug,
            )
        )
    ).scalar_one_or_none()

    if existing_id is not None:
        raise ValueError("A part type with this name already exists")

    part_type = PartType(
        name=payload.name,
        slug=slug,
        description=payload.description,
        is_builtin=False,
        is_active=True,
        template_version=1,
    )
    db.add(part_type)
    db.flush()

    field_models: list[PartTypeField] = []
    for index, field_payload in enumerate(payload.fields):
        field = PartTypeField(
            part_type_id=part_type.id,
            field_key=field_payload.field_key,
            label=field_payload.label,
            field_type=field_payload.field_type,
            is_required=field_payload.is_required,
            sort_order=index,
            options_json=(
                field_payload.options
                if field_payload.field_type == "dropdown"
                else None
            ),
            default_unit=(
                field_payload.default_unit
                if field_payload.field_type == "unit_value"
                else None
            ),
            help_text=field_payload.help_text,
        )
        db.add(field)
        field_models.append(field)

    db.flush()
    response = _type_response(part_type, field_models)

    db.add(
        AuditLog(
            event_type="part_type.created",
            entity_type="part_type",
            entity_id=part_type.id,
            actor_type="user" if actor_user_id is not None else "system",
            actor_user_id=actor_user_id,
            summary=f"Created custom part type {part_type.name}",
            after_json=response.model_dump(mode="json"),
            metadata_json={"field_count": len(field_models)},
        )
    )

    if commit:
        db.commit()
        db.refresh(part_type)
        for field in field_models:
            db.refresh(field)
        response = _type_response(part_type, field_models)

    return response

# PATCH 079: custom part type update service
class PartTypeUpdateNotFoundError(LookupError):
    pass


class PartTypeUpdateForbiddenError(PermissionError):
    pass


class PartTypeUpdateConflictError(ValueError):
    pass


class PartTypeUpdateValidationError(ValueError):
    pass


_MANAGEMENT_ALLOWED_FIELD_TYPES = {
    "text",
    "number",
    "boolean",
    "dropdown",
    "url",
    "unit_value",
}


def _management_field_snapshot(
    field: ManagementPartTypeField,
) -> dict[str, object]:
    return {
        "id": field.id,
        "field_key": field.field_key,
        "label": field.label,
        "field_type": field.field_type,
        "is_required": field.is_required,
        "sort_order": field.sort_order,
        "options": field.options_json,
        "default_unit": field.default_unit,
        "help_text": field.help_text,
    }


def _management_type_snapshot(
    part_type: ManagementPartType,
    fields: list[ManagementPartTypeField],
) -> dict[str, object]:
    return {
        "id": part_type.id,
        "name": part_type.name,
        "slug": part_type.slug,
        "description": part_type.description,
        "is_builtin": part_type.is_builtin,
        "is_active": part_type.is_active,
        "template_version": part_type.template_version,
        "fields": [
            _management_field_snapshot(field)
            for field in sorted(
                fields,
                key=lambda item: (item.sort_order, item.id or 0),
            )
        ],
    }


def _management_normalize_field_key(
    field_key: str | None,
    label: str,
) -> str:
    source = management_clean_text(field_key) or label
    normalized = management_slugify(source).replace("-", "_")
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if not normalized:
        raise PartTypeUpdateValidationError(
            "Every template field requires a valid field key."
        )
    if len(normalized) > 120:
        raise PartTypeUpdateValidationError(
            f"Field key {normalized!r} exceeds 120 characters."
        )
    return normalized


def _management_clean_options(
    raw_options: list[str] | None,
    field_label: str,
) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()

    for option in raw_options or []:
        value = management_clean_text(option)
        if value is None:
            continue
        key = value.casefold()
        if key in seen:
            raise PartTypeUpdateValidationError(
                f"Dropdown field {field_label!r} contains duplicate "
                f"option {value!r}."
            )
        seen.add(key)
        cleaned.append(value)

    if not cleaned:
        raise PartTypeUpdateValidationError(
            f"Dropdown field {field_label!r} requires at least one option."
        )

    return cleaned


def _management_prepare_fields(
    payload: ManagementPartTypeUpdateRequest,
) -> list[dict[str, object]]:
    if not payload.fields:
        raise PartTypeUpdateValidationError(
            "A custom part type must contain at least one template field."
        )
    if len(payload.fields) > 50:
        raise PartTypeUpdateValidationError(
            "A custom part type cannot contain more than 50 fields."
        )

    prepared: list[dict[str, object]] = []
    seen_keys: set[str] = set()
    seen_ids: set[int] = set()

    for index, field in enumerate(payload.fields):
        label = management_clean_text(field.label)
        if label is None:
            raise PartTypeUpdateValidationError(
                f"Field {index + 1} requires a label."
            )
        if len(label) > 160:
            raise PartTypeUpdateValidationError(
                f"Field label {label!r} exceeds 160 characters."
            )

        field_key = _management_normalize_field_key(
            field.field_key,
            label,
        )
        if field_key in seen_keys:
            raise PartTypeUpdateValidationError(
                f"Field key {field_key!r} is used more than once."
            )
        seen_keys.add(field_key)

        if field.id is not None:
            if field.id <= 0:
                raise PartTypeUpdateValidationError(
                    "Existing field IDs must be positive integers."
                )
            if field.id in seen_ids:
                raise PartTypeUpdateValidationError(
                    f"Field ID {field.id} appears more than once."
                )
            seen_ids.add(field.id)

        field_type = management_clean_text(field.field_type)
        if field_type not in _MANAGEMENT_ALLOWED_FIELD_TYPES:
            raise PartTypeUpdateValidationError(
                f"Unsupported field type {field.field_type!r}."
            )

        options: list[str] | None = None
        if field_type == "dropdown":
            options = _management_clean_options(
                field.options,
                label,
            )

        default_unit = management_clean_text(field.default_unit)
        if field_type != "unit_value":
            default_unit = None
        if default_unit is not None and len(default_unit) > 30:
            raise PartTypeUpdateValidationError(
                f"Default unit for {label!r} exceeds 30 characters."
            )

        help_text = management_clean_text(field.help_text)

        prepared.append(
            {
                "id": field.id,
                "field_key": field_key,
                "label": label,
                "field_type": field_type,
                "is_required": bool(field.is_required),
                "sort_order": index,
                "options_json": options,
                "default_unit": default_unit,
                "help_text": help_text,
            }
        )

    return prepared


def update_custom_part_type(
    db: Session,
    part_type_id: int,
    payload: ManagementPartTypeUpdateRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> PartTypeResponse:
    part_type = db.get(ManagementPartType, part_type_id)
    if part_type is None:
        raise PartTypeUpdateNotFoundError("Part type not found.")
    if part_type.is_builtin:
        raise PartTypeUpdateForbiddenError(
            "Built-in part types cannot be edited."
        )

    name = management_clean_text(payload.name)
    if name is None:
        raise PartTypeUpdateValidationError(
            "Part type name is required."
        )
    if len(name) > 120:
        raise PartTypeUpdateValidationError(
            "Part type name cannot exceed 120 characters."
        )

    description = management_clean_text(payload.description)
    slug = management_slugify(name)
    prepared_fields = _management_prepare_fields(payload)

    conflicting_name = db.execute(
        management_select(ManagementPartType.id).where(
            ManagementPartType.id != part_type_id,
            ManagementPartType.name == name,
        )
    ).scalar_one_or_none()
    if conflicting_name is not None:
        raise PartTypeUpdateConflictError(
            f"A part type named {name!r} already exists."
        )

    conflicting_slug = db.execute(
        management_select(ManagementPartType.id).where(
            ManagementPartType.id != part_type_id,
            ManagementPartType.slug == slug,
        )
    ).scalar_one_or_none()
    if conflicting_slug is not None:
        raise PartTypeUpdateConflictError(
            f"A part type using slug {slug!r} already exists."
        )

    existing_fields = list(
        db.execute(
            management_select(ManagementPartTypeField)
            .where(
                ManagementPartTypeField.part_type_id == part_type_id
            )
            .order_by(
                ManagementPartTypeField.sort_order.asc(),
                ManagementPartTypeField.id.asc(),
            )
        ).scalars()
    )
    existing_by_id = {
        field.id: field
        for field in existing_fields
    }

    requested_ids = {
        int(field["id"])
        for field in prepared_fields
        if field["id"] is not None
    }
    unknown_ids = requested_ids - set(existing_by_id)
    if unknown_ids:
        raise PartTypeUpdateValidationError(
            "One or more field IDs do not belong to this part type: "
            f"{sorted(unknown_ids)}"
        )

    removed_fields = [
        field
        for field in existing_fields
        if field.id not in requested_ids
    ]

    for removed in removed_fields:
        referenced_value = db.execute(
            management_select(ManagementPartFieldValue.id)
            .where(
                ManagementPartFieldValue.field_id == removed.id
            )
            .limit(1)
        ).scalar_one_or_none()
        if referenced_value is not None:
            raise PartTypeUpdateConflictError(
                f"Field {removed.label!r} is already used by inventory "
                "parts and cannot be removed."
            )

    before_snapshot = _management_type_snapshot(
        part_type,
        existing_fields,
    )

    try:
        part_type.name = name
        part_type.slug = slug
        part_type.description = description
        part_type.template_version = int(
            part_type.template_version or 0
        ) + 1

        for prepared in prepared_fields:
            field_id = prepared["id"]

            if field_id is None:
                field = ManagementPartTypeField(
                    part_type_id=part_type_id,
                )
                db.add(field)
            else:
                field = existing_by_id[int(field_id)]

            field.field_key = str(prepared["field_key"])
            field.label = str(prepared["label"])
            field.field_type = str(prepared["field_type"])
            field.is_required = bool(prepared["is_required"])
            field.sort_order = int(prepared["sort_order"])
            field.options_json = prepared["options_json"]
            field.default_unit = prepared["default_unit"]
            field.help_text = prepared["help_text"]

        for removed in removed_fields:
            db.delete(removed)

        db.flush()

        updated_fields = list(
            db.execute(
                management_select(ManagementPartTypeField)
                .where(
                    ManagementPartTypeField.part_type_id == part_type_id
                )
                .order_by(
                    ManagementPartTypeField.sort_order.asc(),
                    ManagementPartTypeField.id.asc(),
                )
            ).scalars()
        )

        after_snapshot = _management_type_snapshot(
            part_type,
            updated_fields,
        )

        db.add(
            ManagementAuditLog(
                event_type="part_type.updated",
                entity_type="part_type",
                entity_id=part_type.id,
                actor_type=(
                    "user"
                    if actor_user_id is not None
                    else "system"
                ),
                actor_user_id=actor_user_id,
                summary=f"Updated custom part type {part_type.name}",
                before_json=before_snapshot,
                after_json=after_snapshot,
                metadata_json={
                    "template_version": part_type.template_version,
                    "field_count": len(updated_fields),
                },
            )
        )

        if commit:
            db.commit()
        else:
            db.flush()

    except ManagementIntegrityError as exc:
        db.rollback()
        raise PartTypeUpdateConflictError(
            "The updated part type conflicts with existing data."
        ) from exc
    except Exception:
        if commit:
            db.rollback()
        raise

    result = get_part_type(db, part_type_id)
    if result is None:
        raise PartTypeUpdateNotFoundError(
            "Part type disappeared after update."
        )
    return result
