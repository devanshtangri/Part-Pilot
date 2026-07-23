from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PartType, PartTypeField
from app.schemas.part_types import (
    PartTypeCollectionResponse,
    PartTypeFieldResponse,
    PartTypeResponse,
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
