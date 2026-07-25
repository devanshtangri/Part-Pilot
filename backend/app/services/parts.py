from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import func, select
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
    PartFieldValue,
    PartType,
    PartTypeField,
    StockMovement,
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
    StockMovementResponse,
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


def _serialize_part(db: Session, part: Part) -> PartResponse:
    part_type = db.get(PartType, part.part_type_id)
    if part_type is None:
        raise PartNotFoundError("Part type not found.")

    manufacturer = (
        db.get(Manufacturer, part.manufacturer_id)
        if part.manufacturer_id is not None
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


def list_parts(
    db: Session,
    *,
    part_type_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PartCollectionResponse:
    conditions = [Part.is_deleted.is_(False)]
    if part_type_id is not None:
        conditions.append(Part.part_type_id == part_type_id)

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
                Part.created_at.desc(),
                Part.id.desc(),
            )
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
