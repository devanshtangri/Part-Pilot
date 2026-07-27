from __future__ import annotations

from datetime import datetime, timezone

from urllib.parse import urlparse

from sqlalchemy import String, case, cast, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.constants import (
    MOVEMENT_TYPE_ADJUST,
    MOVEMENT_TYPE_CONSUME,
    MOVEMENT_TYPE_RESTOCK,
    SOURCE_MANUAL,
)
from app.models import (
    AuditLog,
    Manufacturer,
    Part,
    PartAlias,
    PartFieldValue,
    PartTag,
    PartType,
    PartTypeField,
    StockMovement,
    Tag,
    Location,
)
from app.schemas.parts import (
    PartCollectionResponse,
    PartCreateRequest,
    PartFieldValueCreateRequest,
    PartFieldValueResponse,
    PartMovementCollectionResponse,
    PartQuantityAdjustmentRequest,
    PartQuantityAdjustmentResponse,
    PartResponse,
    PartUpdateRequest,
    StockMovementResponse,
    DeletedPartCollectionResponse,
    DeletedPartResponse,
    LowStockSummaryResponse,
)


class PartNotFoundError(LookupError):
    pass


class PartConflictError(ValueError):
    pass


class PartValidationError(ValueError):
    pass


def _has_submitted_value(value: PartFieldValueCreateRequest) -> bool:
    return (
        value.value_text is not None
        or value.value_number is not None
        or value.value_bool is not None
    )


def _validate_url(value: str, label: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise PartValidationError(
            f"{label} must be a valid HTTP or HTTPS URL."
        )


def _validate_and_build_field_value(
    *,
    field: PartTypeField,
    submitted: PartFieldValueCreateRequest,
) -> PartFieldValue | None:
    if not _has_submitted_value(submitted):
        if field.is_required:
            raise PartValidationError(f"{field.label} is required.")
        return None

    value_text = submitted.value_text
    value_number = submitted.value_number
    value_bool = submitted.value_bool
    unit = submitted.unit

    if field.field_type in {"text", "dropdown", "url"}:
        if value_text is None:
            raise PartValidationError(
                f"{field.label} requires a text value."
            )
        if value_number is not None or value_bool is not None:
            raise PartValidationError(
                f"{field.label} received the wrong value type."
            )

        if field.field_type == "url":
            _validate_url(value_text, field.label)

        if field.field_type == "dropdown":
            options = (
                field.options_json
                if isinstance(field.options_json, list)
                else []
            )
            normalized_options = {
                str(option).casefold(): str(option)
                for option in options
            }
            if value_text.casefold() not in normalized_options:
                raise PartValidationError(
                    f"{field.label} must be one of: "
                    + ", ".join(str(option) for option in options)
                )
            value_text = normalized_options[value_text.casefold()]

        unit = None

    elif field.field_type == "number":
        if value_number is None:
            raise PartValidationError(
                f"{field.label} requires a numeric value."
            )
        if value_text is not None or value_bool is not None:
            raise PartValidationError(
                f"{field.label} received the wrong value type."
            )
        unit = None

    elif field.field_type == "unit_value":
        if value_number is None:
            raise PartValidationError(
                f"{field.label} requires a numeric value."
            )
        if value_text is not None or value_bool is not None:
            raise PartValidationError(
                f"{field.label} received the wrong value type."
            )
        unit = unit or field.default_unit
        if unit is not None:
            unit = " ".join(unit.split())[:30] or None

    elif field.field_type == "boolean":
        if value_bool is None:
            raise PartValidationError(
                f"{field.label} requires a yes/no value."
            )
        if value_text is not None or value_number is not None:
            raise PartValidationError(
                f"{field.label} received the wrong value type."
            )
        unit = None

    else:
        raise PartValidationError(
            f"{field.label} uses an unsupported field type "
            f"{field.field_type!r}."
        )

    return PartFieldValue(
        field_id=field.id,
        value_text=value_text,
        value_number=value_number,
        value_bool=value_bool,
        unit=unit,
    )


# PATCH 160: reusable part location assignment service
def _serialize_part(db: Session, part: Part) -> PartResponse:
    part_type = db.get(PartType, part.part_type_id)
    if part_type is None:
        raise PartNotFoundError("Part type not found.")

    manufacturer = (
        db.get(Manufacturer, part.manufacturer_id)
        if part.manufacturer_id is not None
        else None
    )

    location = (
        db.get(Location, part.location_id)
        if part.location_id is not None
        else None
    )
    fields = list(
        db.execute(
            select(PartTypeField)
            .where(PartTypeField.part_type_id == part.part_type_id)
            .order_by(
                PartTypeField.sort_order.asc(),
                PartTypeField.id.asc(),
            )
        ).scalars()
    )
    field_map = {field.id: field for field in fields}

    values = list(
        db.execute(
            select(PartFieldValue)
            .where(PartFieldValue.part_id == part.id)
            .order_by(PartFieldValue.id.asc())
        ).scalars()
    )

    field_values: list[PartFieldValueResponse] = []
    for value in values:
        field = field_map.get(value.field_id)
        if field is None:
            continue

        field_values.append(
            PartFieldValueResponse(
                id=value.id,
                field_id=field.id,
                field_key=field.field_key,
                label=field.label,
                field_type=field.field_type,
                is_required=field.is_required,
                value_text=value.value_text,
                value_number=value.value_number,
                value_bool=value.value_bool,
                unit=value.unit,
            )
        )

    available_quantity = part.total_quantity - part.reserved_quantity
    is_low_stock = bool(
        part.low_stock_enabled
        and part.low_stock_threshold is not None
        and available_quantity <= part.low_stock_threshold
    )

    return PartResponse(
        id=part.id,
        part_type_id=part.part_type_id,
        part_type_name=part_type.name,
        manufacturer_id=part.manufacturer_id,
        manufacturer_name=(
            manufacturer.name
            if manufacturer is not None
            else None
        ),
        location_id=part.location_id,
        location_name=(
            location.name
            if location is not None
            else None
        ),
        part_number=part.part_number,
        name=part.name,
        description=part.description,
        package=part.package,
        notes=part.notes,
        total_quantity=part.total_quantity,
        reserved_quantity=part.reserved_quantity,
        available_quantity=available_quantity,
        unit_price=part.unit_price,
        purchase_link=part.purchase_link,
        low_stock_enabled=part.low_stock_enabled,
        low_stock_threshold=part.low_stock_threshold,
        is_low_stock=is_low_stock,
        created_at=part.created_at,
        updated_at=part.updated_at,
        field_values=field_values,
    )


def create_part(
    db: Session,
    payload: PartCreateRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> PartResponse:
    part_type = db.get(PartType, payload.part_type_id)
    if part_type is None or not part_type.is_active:
        raise PartValidationError("Select an active part type.")

    manufacturer: Manufacturer | None = None
    if payload.manufacturer_id is not None:
        manufacturer = db.get(
            Manufacturer,
            payload.manufacturer_id,
        )
        if manufacturer is None or not manufacturer.is_active:
            raise PartValidationError(
                "Select an active manufacturer."
            )

    location: Location | None = None
    if payload.location_id is not None:
        location = db.get(Location, payload.location_id)
        if location is None:
            raise PartValidationError(
                "Select an existing location."
            )
    if payload.part_number:
        existing_id = db.execute(
            select(Part.id).where(
                Part.part_number == payload.part_number
            )
        ).scalar_one_or_none()
        if existing_id is not None:
            raise PartConflictError(
                "A part with this part number already exists."
            )

    fields = list(
        db.execute(
            select(PartTypeField)
            .where(
                PartTypeField.part_type_id == payload.part_type_id
            )
            .order_by(
                PartTypeField.sort_order.asc(),
                PartTypeField.id.asc(),
            )
        ).scalars()
    )
    field_map = {field.id: field for field in fields}
    submitted_map = {
        submitted.field_id: submitted
        for submitted in payload.field_values
    }

    if set(submitted_map) - set(field_map):
        raise PartValidationError(
            "One or more template fields do not belong to the "
            "selected part type."
        )

    pending_values: list[PartFieldValue] = []
    for field in fields:
        submitted = submitted_map.get(field.id)
        if submitted is None:
            if field.is_required:
                raise PartValidationError(
                    f"{field.label} is required."
                )
            continue

        value = _validate_and_build_field_value(
            field=field,
            submitted=submitted,
        )
        if value is not None:
            pending_values.append(value)

    part = Part(
        part_type_id=payload.part_type_id,
        manufacturer_id=payload.manufacturer_id,
        location_id=payload.location_id,
        part_number=payload.part_number,
        name=payload.name,
        description=payload.description,
        package=payload.package,
        notes=payload.notes,
        total_quantity=payload.total_quantity,
        reserved_quantity=0,
        unit_price=payload.unit_price,
        total_purchase_price=None,
        quantity_purchased=None,
        purchase_link=payload.purchase_link,
        purchase_date=None,
        price_note=None,
        low_stock_enabled=payload.low_stock_enabled,
        low_stock_threshold=payload.low_stock_threshold,
        is_deleted=False,
        deleted_at=None,
    )

    try:
        db.add(part)
        db.flush()

        for value in pending_values:
            value.part_id = part.id
            db.add(value)

        db.flush()

        db.add(
            AuditLog(
                event_type="part.created",
                entity_type="part",
                entity_id=part.id,
                actor_type=(
                    "user"
                    if actor_user_id is not None
                    else "system"
                ),
                actor_user_id=actor_user_id,
                summary=(
                    f"Created inventory part "
                    f"{part.name or part.part_number}"
                ),
                before_json=None,
                after_json={
                    "id": part.id,
                    "part_type_id": part.part_type_id,
                    "part_type_name": part_type.name,
                    "manufacturer_id": part.manufacturer_id,
                    "manufacturer_name": (
                        manufacturer.name
                        if manufacturer is not None
                        else None
                    ),
                    "location_id": part.location_id,
                    "location_name": (
                        location.name
                        if location is not None
                        else None
                    ),
                    "part_number": part.part_number,
                    "name": part.name,
                    "total_quantity": part.total_quantity,
                    "unit_price": (
                        str(part.unit_price)
                        if part.unit_price is not None
                        else None
                    ),
                    "field_value_count": len(pending_values),
                },
                metadata_json={
                    "part_type_id": part_type.id,
                    "part_type_name": part_type.name,
                },
            )
        )
        db.flush()

        if commit:
            db.commit()
            db.refresh(part)

    except IntegrityError as exc:
        db.rollback()
        raise PartConflictError(
            "This part conflicts with existing inventory data."
        ) from exc
    except Exception:
        if commit:
            db.rollback()
        raise

    return _serialize_part(db, part)


def get_part(db: Session, part_id: int) -> PartResponse:
    part = db.get(Part, part_id)
    if part is None or part.is_deleted:
        raise PartNotFoundError("Part not found.")
    return _serialize_part(db, part)


# PATCH 213: protected universal part search service
def _normalise_part_search(search: str | None) -> str | None:
    if search is None:
        return None
    normalised = " ".join(search.split()).casefold()
    return normalised or None


def _searchable_text(expression, term: str):
    return func.lower(func.coalesce(expression, "")).contains(
        term,
        autoescape=True,
    )


def _part_search_condition(term: str):
    custom_value_conditions = [
        _searchable_text(PartTypeField.field_key, term),
        _searchable_text(PartTypeField.label, term),
        _searchable_text(PartFieldValue.value_text, term),
        _searchable_text(cast(PartFieldValue.value_number, String), term),
        _searchable_text(cast(PartFieldValue.value_json, String), term),
        _searchable_text(PartFieldValue.unit, term),
    ]
    if term in {"true", "yes", "on", "enabled"}:
        custom_value_conditions.append(
            PartFieldValue.value_bool.is_(True)
        )
    elif term in {"false", "no", "off", "disabled"}:
        custom_value_conditions.append(
            PartFieldValue.value_bool.is_(False)
        )

    return or_(
        _searchable_text(Part.part_number, term),
        _searchable_text(Part.name, term),
        _searchable_text(Part.description, term),
        _searchable_text(Part.package, term),
        _searchable_text(Part.notes, term),
        exists(
            select(1)
            .select_from(PartType)
            .where(
                PartType.id == Part.part_type_id,
                or_(
                    _searchable_text(PartType.name, term),
                    _searchable_text(PartType.description, term),
                ),
            )
        ),
        exists(
            select(1)
            .select_from(Manufacturer)
            .where(
                Manufacturer.id == Part.manufacturer_id,
                _searchable_text(Manufacturer.name, term),
            )
        ),
        exists(
            select(1)
            .select_from(Location)
            .where(
                Location.id == Part.location_id,
                _searchable_text(Location.name, term),
            )
        ),
        exists(
            select(1)
            .select_from(PartAlias)
            .where(
                PartAlias.part_id == Part.id,
                _searchable_text(PartAlias.alias, term),
            )
        ),
        exists(
            select(1)
            .select_from(PartTag)
            .join(Tag, Tag.id == PartTag.tag_id)
            .where(
                PartTag.part_id == Part.id,
                or_(
                    _searchable_text(Tag.name, term),
                    _searchable_text(Tag.normalized_name, term),
                ),
            )
        ),
        exists(
            select(1)
            .select_from(PartFieldValue)
            .join(
                PartTypeField,
                PartTypeField.id == PartFieldValue.field_id,
            )
            .where(
                PartFieldValue.part_id == Part.id,
                or_(*custom_value_conditions),
            )
        ),
    )


def _part_search_order(term: str):
    part_number = func.lower(func.coalesce(Part.part_number, ""))
    name = func.lower(func.coalesce(Part.name, ""))
    available_quantity = Part.total_quantity - Part.reserved_quantity
    return (
        case((available_quantity > 0, 0), else_=1).asc(),
        case((part_number == term, 0), else_=1).asc(),
        case(
            (part_number.startswith(term, autoescape=True), 0),
            else_=1,
        ).asc(),
        case((name == term, 0), else_=1).asc(),
        case(
            (name.startswith(term, autoescape=True), 0),
            else_=1,
        ).asc(),
        Part.updated_at.desc(),
        Part.id.desc(),
    )


# PATCH 229: PARTPILOT_STORED_PARTS_STOCK_FILTER_V229
_PART_STOCK_STATUSES = {"all", "in", "low", "out"}


def _part_stock_conditions(stock_status: str):
    if stock_status not in _PART_STOCK_STATUSES:
        raise PartValidationError(
            f"Unsupported stock status filter: {stock_status!r}."
        )

    available_quantity = (
        Part.total_quantity - Part.reserved_quantity
    )
    low_stock_condition = (
        Part.low_stock_enabled.is_(True)
        & Part.low_stock_threshold.is_not(None)
        & (available_quantity <= Part.low_stock_threshold)
    )

    if stock_status == "all":
        return ()
    if stock_status == "out":
        return (available_quantity <= 0,)
    if stock_status == "low":
        return (
            available_quantity > 0,
            low_stock_condition,
        )
    return (
        available_quantity > 0,
        or_(
            Part.low_stock_enabled.is_(False),
            Part.low_stock_threshold.is_(None),
            available_quantity > Part.low_stock_threshold,
        ),
    )

# PATCH 267: PARTPILOT_STORED_PARTS_SORT_V267
_PART_SORT_FIELDS = {
    "default",
    "part",
    "type",
    "manufacturer",
    "location",
    "available",
    "total",
    "status",
}
_PART_SORT_DIRECTIONS = {"asc", "desc"}


def _part_sort_order(
    *,
    sort_by: str,
    sort_direction: str,
    search_term: str | None,
    stock_status: str,
):
    if sort_by not in _PART_SORT_FIELDS:
        raise PartValidationError(
            f"Unsupported part sort field: {sort_by!r}."
        )
    if sort_direction not in _PART_SORT_DIRECTIONS:
        raise PartValidationError(
            f"Unsupported part sort direction: {sort_direction!r}."
        )

    available_quantity = Part.total_quantity - Part.reserved_quantity
    available_group = case(
        (available_quantity > 0, 0),
        else_=1,
    ).asc()

    if sort_by == "default":
        if search_term is not None:
            return _part_search_order(search_term)
        return (
            available_group,
            Part.created_at.desc(),
            Part.id.desc(),
        )

    prefix = (available_group,) if stock_status == "all" else ()
    descending = sort_direction == "desc"

    def directed(expression):
        return expression.desc() if descending else expression.asc()

    if sort_by == "part":
        primary = func.lower(
            func.coalesce(Part.name, Part.part_number, "")
        )
        secondary = func.lower(func.coalesce(Part.part_number, ""))
        return (
            *prefix,
            directed(primary),
            directed(secondary),
            Part.id.asc(),
        )

    if sort_by == "type":
        expression = (
            select(func.lower(PartType.name))
            .where(PartType.id == Part.part_type_id)
            .scalar_subquery()
        )
        return (*prefix, directed(expression), Part.id.asc())

    if sort_by == "manufacturer":
        expression = (
            select(func.lower(Manufacturer.name))
            .where(Manufacturer.id == Part.manufacturer_id)
            .scalar_subquery()
        )
        missing = case(
            (Part.manufacturer_id.is_(None), 1),
            else_=0,
        ).asc()
        return (*prefix, missing, directed(expression), Part.id.asc())

    if sort_by == "location":
        expression = (
            select(func.lower(Location.name))
            .where(Location.id == Part.location_id)
            .scalar_subquery()
        )
        missing = case(
            (Part.location_id.is_(None), 1),
            else_=0,
        ).asc()
        return (*prefix, missing, directed(expression), Part.id.asc())

    if sort_by == "available":
        return (
            *prefix,
            directed(available_quantity),
            Part.id.asc(),
        )

    if sort_by == "total":
        return (
            *prefix,
            directed(Part.total_quantity),
            Part.id.asc(),
        )

    low_stock = (
        (available_quantity > 0)
        & Part.low_stock_enabled.is_(True)
        & Part.low_stock_threshold.is_not(None)
        & (available_quantity <= Part.low_stock_threshold)
    )
    status_rank = case(
        (available_quantity <= 0, 2),
        (low_stock, 1),
        else_=0,
    )
    return (*prefix, directed(status_rank), Part.id.asc())

def list_parts(
    db: Session,
    *,
    part_type_id: int | None = None,
    location_id: int | None = None,
    search: str | None = None,
    stock_status: str = "all",
    sort_by: str = "default",
    sort_direction: str = "asc",
    limit: int = 100,
    offset: int = 0,
) -> PartCollectionResponse:
    conditions = [Part.is_deleted.is_(False)]
    if part_type_id is not None:
        conditions.append(Part.part_type_id == part_type_id)
    if location_id is not None:
        conditions.append(Part.location_id == location_id)
    conditions.extend(_part_stock_conditions(stock_status))

    search_term = _normalise_part_search(search)
    if search_term is not None:
        conditions.append(_part_search_condition(search_term))

    total = int(
        db.execute(
            select(func.count(Part.id)).where(*conditions)
        ).scalar_one()
    )

    order_by = _part_sort_order(
        sort_by=sort_by,
        sort_direction=sort_direction,
        search_term=search_term,
        stock_status=stock_status,
    )
    parts = list(
        db.execute(
            select(Part)
            .where(*conditions)
            .order_by(*order_by)
            .limit(limit)
            .offset(offset)
        ).scalars()
    )
    return PartCollectionResponse(
        total=total,
        limit=limit,
        offset=offset,
        parts=[_serialize_part(db, part) for part in parts],
    )


# PATCH 182: dashboard-ready low-stock summary service
def list_low_stock_parts(
    db: Session,
    *,
    part_type_id: int | None = None,
    location_id: int | None = None,
    limit: int = 8,
) -> LowStockSummaryResponse:
    available_expression = (
        Part.total_quantity - Part.reserved_quantity
    )
    # PATCH 189: include every active zero-stock part
    # without a configured threshold. Positive stock still
    # requires an enabled threshold that is being reached.
    conditions = [
        Part.is_deleted.is_(False),
        (
            (available_expression <= 0)
            | (
                Part.low_stock_enabled.is_(True)
                & Part.low_stock_threshold.is_not(None)
                & (
                    available_expression
                    <= Part.low_stock_threshold
                )
            )
        ),
    ]

    if part_type_id is not None:
        conditions.append(Part.part_type_id == part_type_id)
    if location_id is not None:
        conditions.append(Part.location_id == location_id)

    total = int(
        db.execute(
            select(func.count(Part.id)).where(*conditions)
        ).scalar_one()
    )
    out_of_stock_count = int(
        db.execute(
            select(func.count(Part.id)).where(
                *conditions,
                available_expression <= 0,
            )
        ).scalar_one()
    )
    parts = list(
        db.execute(
            select(Part)
            .where(*conditions)
            .order_by(
                available_expression.asc(),
                Part.updated_at.desc(),
                Part.id.desc(),
            )
            .limit(limit)
        ).scalars()
    )

    return LowStockSummaryResponse(
        total=total,
        low_stock_count=total - out_of_stock_count,
        out_of_stock_count=out_of_stock_count,
        limit=limit,
        parts=[
            _serialize_part(db, part)
            for part in parts
        ],
    )




# PATCH 142: existing-part metadata update service
def _part_metadata_snapshot(response: PartResponse) -> dict[str, object]:
    return {
        "part_type_id": response.part_type_id,
        "part_type_name": response.part_type_name,
        "manufacturer_id": response.manufacturer_id,
        "manufacturer_name": response.manufacturer_name,
        "location_id": response.location_id,
        "location_name": response.location_name,
        "part_number": response.part_number,
        "name": response.name,
        "description": response.description,
        "package": response.package,
        "notes": response.notes,
        "unit_price": (
            str(response.unit_price)
            if response.unit_price is not None
            else None
        ),
        "purchase_link": response.purchase_link,
        "low_stock_enabled": response.low_stock_enabled,
        "low_stock_threshold": response.low_stock_threshold,
        "field_values": [
            {
                "field_id": value.field_id,
                "field_key": value.field_key,
                "label": value.label,
                "field_type": value.field_type,
                "is_required": value.is_required,
                "value_text": value.value_text,
                "value_number": (
                    str(value.value_number)
                    if value.value_number is not None
                    else None
                ),
                "value_bool": value.value_bool,
                "unit": value.unit,
            }
            for value in response.field_values
        ],
    }


def update_part_metadata(
    db: Session,
    part_id: int,
    payload: PartUpdateRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> PartResponse:
    part = db.execute(
        select(Part)
        .where(
            Part.id == part_id,
            Part.is_deleted.is_(False),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if part is None:
        raise PartNotFoundError("Part not found.")

    if payload.part_type_id != part.part_type_id:
        raise PartValidationError(
            "Changing a part's type is not supported in this edit workflow."
        )

    part_type = db.get(PartType, part.part_type_id)
    if part_type is None:
        raise PartNotFoundError("Part type not found.")

    manufacturer: Manufacturer | None = None
    if payload.manufacturer_id is not None:
        manufacturer = db.get(Manufacturer, payload.manufacturer_id)
        if manufacturer is None or not manufacturer.is_active:
            raise PartValidationError("Select an active manufacturer.")

    location: Location | None = None
    if payload.location_id is not None:
        location = db.get(Location, payload.location_id)
        if location is None:
            raise PartValidationError(
                "Select an existing location."
            )
    if payload.part_number:
        existing_id = db.execute(
            select(Part.id).where(
                Part.part_number == payload.part_number,
                Part.id != part.id,
            )
        ).scalar_one_or_none()
        if existing_id is not None:
            raise PartConflictError(
                "A part with this part number already exists."
            )

    fields = list(
        db.execute(
            select(PartTypeField)
            .where(PartTypeField.part_type_id == part.part_type_id)
            .order_by(
                PartTypeField.sort_order.asc(),
                PartTypeField.id.asc(),
            )
        ).scalars()
    )
    field_map = {field.id: field for field in fields}
    submitted_map = {
        submitted.field_id: submitted
        for submitted in payload.field_values
    }

    if set(submitted_map) - set(field_map):
        raise PartValidationError(
            "One or more template fields do not belong to this part type."
        )

    pending_values: list[PartFieldValue] = []
    for field in fields:
        submitted = submitted_map.get(field.id)
        if submitted is None:
            if field.is_required:
                raise PartValidationError(f"{field.label} is required.")
            continue

        value = _validate_and_build_field_value(
            field=field,
            submitted=submitted,
        )
        if value is not None:
            pending_values.append(value)

    before_response = _serialize_part(db, part)
    before_snapshot = _part_metadata_snapshot(before_response)
    total_quantity_before = part.total_quantity
    reserved_quantity_before = part.reserved_quantity
    existing_values = list(
        db.execute(
            select(PartFieldValue).where(
                PartFieldValue.part_id == part.id
            )
        ).scalars()
    )

    try:
        part.manufacturer_id = payload.manufacturer_id
        part.location_id = payload.location_id
        part.part_number = payload.part_number
        part.name = payload.name
        part.description = payload.description
        part.package = payload.package
        part.notes = payload.notes
        part.unit_price = payload.unit_price
        part.purchase_link = payload.purchase_link
        part.low_stock_enabled = payload.low_stock_enabled
        part.low_stock_threshold = payload.low_stock_threshold

        for existing_value in existing_values:
            db.delete(existing_value)
        db.flush()

        for value in pending_values:
            value.part_id = part.id
            db.add(value)
        db.flush()

        if (
            part.total_quantity != total_quantity_before
            or part.reserved_quantity != reserved_quantity_before
        ):
            raise PartValidationError(
                "Metadata editing cannot change stock quantities."
            )

        after_response = _serialize_part(db, part)
        after_snapshot = _part_metadata_snapshot(after_response)
        changed_fields = sorted(
            key
            for key in after_snapshot
            if before_snapshot.get(key) != after_snapshot.get(key)
        )
        display_name = (
            part.name
            or part.part_number
            or f"Part {part.id}"
        )

        db.add(
            AuditLog(
                event_type="part.metadata_updated",
                entity_type="part",
                entity_id=part.id,
                actor_type=(
                    "user" if actor_user_id is not None else "system"
                ),
                actor_user_id=actor_user_id,
                summary=f"Updated inventory metadata for {display_name}",
                before_json=before_snapshot,
                after_json=after_snapshot,
                metadata_json={
                    "part_type_id": part_type.id,
                    "part_type_name": part_type.name,
                    "manufacturer_id": payload.manufacturer_id,
                    "manufacturer_name": (
                        manufacturer.name
                        if manufacturer is not None
                        else None
                    ),
                    "location_id": payload.location_id,
                    "location_name": (
                        location.name
                        if location is not None
                        else None
                    ),
                    "changed_fields": changed_fields,
                    "field_value_count": len(pending_values),
                },
            )
        )
        db.flush()

        if commit:
            db.commit()
            db.refresh(part)
            after_response = _serialize_part(db, part)

    except IntegrityError as exc:
        db.rollback()
        raise PartConflictError(
            "This metadata update conflicts with existing inventory data."
        ) from exc
    except Exception:
        if commit:
            db.rollback()
        raise

    return after_response


# PATCH 134: stock quantity adjustment and movement history service
_ADJUSTMENT_MOVEMENT_TYPES = {
    "add": MOVEMENT_TYPE_RESTOCK,
    "remove": MOVEMENT_TYPE_ADJUST,
    "consume": MOVEMENT_TYPE_CONSUME,
    "correction": MOVEMENT_TYPE_ADJUST,
}

_DEFAULT_ADJUSTMENT_REASONS = {
    "add": "Manual stock addition",
    "remove": "Manual stock removal",
    "consume": "Manual stock consumption",
    "correction": "Manual stock correction",
}


def _adjustment_delta(payload: PartQuantityAdjustmentRequest) -> int:
    if payload.operation == "add":
        return payload.quantity
    if payload.operation in {"remove", "consume"}:
        return -payload.quantity
    return payload.quantity


def _serialize_stock_movement(
    movement: StockMovement,
) -> StockMovementResponse:
    return StockMovementResponse(
        id=movement.id,
        part_id=movement.part_id,
        movement_type=movement.movement_type,
        quantity_delta=movement.quantity_delta,
        quantity_before=movement.quantity_before,
        quantity_after=movement.quantity_after,
        unit_price_snapshot=movement.unit_price_snapshot,
        currency_snapshot=movement.currency_snapshot,
        reason=movement.reason,
        note=movement.note,
        source=movement.source,
        actor_user_id=movement.actor_user_id,
        created_at=movement.created_at,
    )


def adjust_part_quantity(
    db: Session,
    part_id: int,
    payload: PartQuantityAdjustmentRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> PartQuantityAdjustmentResponse:
    part = db.execute(
        select(Part)
        .where(
            Part.id == part_id,
            Part.is_deleted.is_(False),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if part is None:
        raise PartNotFoundError("Part not found.")

    quantity_before = int(part.total_quantity)
    quantity_delta = _adjustment_delta(payload)
    quantity_after = quantity_before + quantity_delta

    if quantity_after < 0:
        raise PartValidationError(
            "Quantity adjustment cannot reduce total stock below zero."
        )
    if quantity_after < part.reserved_quantity:
        raise PartValidationError(
            "Quantity adjustment cannot reduce total stock below the "
            "reserved quantity."
        )

    movement_type = _ADJUSTMENT_MOVEMENT_TYPES[payload.operation]
    reason = payload.reason or _DEFAULT_ADJUSTMENT_REASONS[payload.operation]
    display_name = part.name or part.part_number or f"Part {part.id}"
    available_before = quantity_before - part.reserved_quantity
    available_after = quantity_after - part.reserved_quantity

    movement = StockMovement(
        part_id=part.id,
        movement_type=movement_type,
        quantity_delta=quantity_delta,
        quantity_before=quantity_before,
        quantity_after=quantity_after,
        unit_price_snapshot=part.unit_price,
        currency_snapshot=None,
        reason=reason,
        note=payload.note,
        source=SOURCE_MANUAL,
        actor_user_id=actor_user_id,
    )

    try:
        part.total_quantity = quantity_after
        db.add(movement)
        db.flush()
        db.add(
            AuditLog(
                event_type="part.quantity_adjusted",
                entity_type="part",
                entity_id=part.id,
                actor_type=(
                    "user" if actor_user_id is not None else "system"
                ),
                actor_user_id=actor_user_id,
                summary=(
                    f"{payload.operation.title()} stock for {display_name}: "
                    f"{quantity_before} to {quantity_after}"
                ),
                before_json={
                    "total_quantity": quantity_before,
                    "reserved_quantity": part.reserved_quantity,
                    "available_quantity": available_before,
                },
                after_json={
                    "total_quantity": quantity_after,
                    "reserved_quantity": part.reserved_quantity,
                    "available_quantity": available_after,
                },
                metadata_json={
                    "operation": payload.operation,
                    "movement_type": movement_type,
                    "quantity_delta": quantity_delta,
                    "stock_movement_id": movement.id,
                    "source": SOURCE_MANUAL,
                    "reason": reason,
                },
            )
        )
        db.flush()
        if commit:
            db.commit()
            db.refresh(part)
            db.refresh(movement)
    except IntegrityError as exc:
        if commit:
            db.rollback()
        raise PartConflictError(
            "Quantity adjustment conflicted with current inventory data."
        ) from exc
    except Exception:
        if commit:
            db.rollback()
        raise

    return PartQuantityAdjustmentResponse(
        operation=payload.operation,
        part=_serialize_part(db, part),
        movement=_serialize_stock_movement(movement),
    )


def list_part_movements(
    db: Session,
    part_id: int,
    *,
    limit: int = 20,
) -> PartMovementCollectionResponse:
    part = db.execute(
        select(Part).where(
            Part.id == part_id,
            Part.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if part is None:
        raise PartNotFoundError("Part not found.")

    movements = list(
        db.execute(
            select(StockMovement)
            .where(StockMovement.part_id == part.id)
            .order_by(
                StockMovement.created_at.desc(),
                StockMovement.id.desc(),
            )
            .limit(limit)
        ).scalars()
    )
    return PartMovementCollectionResponse(
        part_id=part.id,
        movements=[
            _serialize_stock_movement(movement)
            for movement in movements
        ],
    )

# PATCH 152: part soft-delete and restoration service
def _serialize_deleted_part(
    db: Session,
    part: Part,
) -> DeletedPartResponse:
    if not part.is_deleted or part.deleted_at is None:
        raise PartValidationError("Part is not deleted.")

    active_shape = _serialize_part(db, part)
    return DeletedPartResponse(
        **active_shape.model_dump(),
        is_deleted=True,
        deleted_at=part.deleted_at,
    )


def _part_lifecycle_snapshot(
    db: Session,
    part: Part,
) -> dict[str, object]:
    response = _serialize_part(db, part)
    field_value_count = int(
        db.execute(
            select(func.count(PartFieldValue.id)).where(
                PartFieldValue.part_id == part.id
            )
        ).scalar_one()
    )
    movement_count = int(
        db.execute(
            select(func.count(StockMovement.id)).where(
                StockMovement.part_id == part.id
            )
        ).scalar_one()
    )
    return {
        "id": part.id,
        "part_type_id": response.part_type_id,
        "part_type_name": response.part_type_name,
        "manufacturer_id": response.manufacturer_id,
        "manufacturer_name": response.manufacturer_name,
        "location_id": response.location_id,
        "location_name": response.location_name,
        "part_number": response.part_number,
        "name": response.name,
        "total_quantity": response.total_quantity,
        "reserved_quantity": response.reserved_quantity,
        "available_quantity": response.available_quantity,
        "is_deleted": bool(part.is_deleted),
        "deleted_at": (
            part.deleted_at.isoformat()
            if part.deleted_at is not None
            else None
        ),
        "field_value_count": field_value_count,
        "movement_count": movement_count,
    }


def list_deleted_parts(
    db: Session,
    *,
    limit: int = 100,
    offset: int = 0,
) -> DeletedPartCollectionResponse:
    conditions = [Part.is_deleted.is_(True)]

    total = int(
        db.execute(
            select(func.count(Part.id)).where(*conditions)
        ).scalar_one()
    )
    parts = list(
        db.execute(
            select(Part)
            .where(*conditions)
            .order_by(
                Part.deleted_at.desc(),
                Part.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        ).scalars()
    )
    return DeletedPartCollectionResponse(
        total=total,
        limit=limit,
        offset=offset,
        parts=[
            _serialize_deleted_part(db, part)
            for part in parts
        ],
    )


def soft_delete_part(
    db: Session,
    part_id: int,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> DeletedPartResponse:
    part = db.execute(
        select(Part)
        .where(Part.id == part_id)
        .with_for_update()
    ).scalar_one_or_none()
    if part is None:
        raise PartNotFoundError("Part not found.")
    if part.is_deleted:
        raise PartConflictError("Part is already deleted.")

    before_snapshot = _part_lifecycle_snapshot(db, part)
    display_name = (
        part.name
        or part.part_number
        or f"Part {part.id}"
    )

    try:
        part.is_deleted = True
        part.deleted_at = datetime.now(timezone.utc)
        db.flush()

        after_snapshot = _part_lifecycle_snapshot(db, part)
        db.add(
            AuditLog(
                event_type="part.deleted",
                entity_type="part",
                entity_id=part.id,
                actor_type=(
                    "user"
                    if actor_user_id is not None
                    else "system"
                ),
                actor_user_id=actor_user_id,
                summary=f"Soft-deleted inventory part {display_name}",
                before_json=before_snapshot,
                after_json=after_snapshot,
                metadata_json={
                    "operation": "soft_delete",
                    "part_number_reserved": (
                        part.part_number is not None
                    ),
                    "field_value_count": after_snapshot[
                        "field_value_count"
                    ],
                    "movement_count": after_snapshot[
                        "movement_count"
                    ],
                    "total_quantity_preserved": part.total_quantity,
                    "reserved_quantity_preserved": (
                        part.reserved_quantity
                    ),
                },
            )
        )
        db.flush()

        if commit:
            db.commit()
            db.refresh(part)

    except IntegrityError as exc:
        db.rollback()
        raise PartConflictError(
            "Part deletion conflicted with current inventory data."
        ) from exc
    except Exception:
        if commit:
            db.rollback()
        raise

    return _serialize_deleted_part(db, part)


def restore_part(
    db: Session,
    part_id: int,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> PartResponse:
    part = db.execute(
        select(Part)
        .where(Part.id == part_id)
        .with_for_update()
    ).scalar_one_or_none()
    if part is None:
        raise PartNotFoundError("Part not found.")
    if not part.is_deleted:
        raise PartConflictError("Part is already active.")

    if part.part_number:
        conflicting_id = db.execute(
            select(Part.id).where(
                Part.part_number == part.part_number,
                Part.id != part.id,
            )
        ).scalar_one_or_none()
        if conflicting_id is not None:
            raise PartConflictError(
                "This part cannot be restored because its part number "
                "is already in use."
            )

    before_snapshot = _part_lifecycle_snapshot(db, part)
    display_name = (
        part.name
        or part.part_number
        or f"Part {part.id}"
    )

    try:
        part.is_deleted = False
        part.deleted_at = None
        db.flush()

        after_snapshot = _part_lifecycle_snapshot(db, part)
        db.add(
            AuditLog(
                event_type="part.restored",
                entity_type="part",
                entity_id=part.id,
                actor_type=(
                    "user"
                    if actor_user_id is not None
                    else "system"
                ),
                actor_user_id=actor_user_id,
                summary=f"Restored inventory part {display_name}",
                before_json=before_snapshot,
                after_json=after_snapshot,
                metadata_json={
                    "operation": "restore",
                    "part_number_conflict_checked": (
                        part.part_number is not None
                    ),
                    "field_value_count": after_snapshot[
                        "field_value_count"
                    ],
                    "movement_count": after_snapshot[
                        "movement_count"
                    ],
                    "total_quantity_preserved": part.total_quantity,
                    "reserved_quantity_preserved": (
                        part.reserved_quantity
                    ),
                },
            )
        )
        db.flush()

        if commit:
            db.commit()
            db.refresh(part)

    except IntegrityError as exc:
        db.rollback()
        raise PartConflictError(
            "This part cannot be restored because it conflicts with "
            "current inventory data."
        ) from exc
    except Exception:
        if commit:
            db.rollback()
        raise

    return _serialize_part(db, part)
