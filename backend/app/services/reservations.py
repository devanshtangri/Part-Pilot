from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.constants import (
    MOVEMENT_TYPE_CONSUME,
    MOVEMENT_TYPE_RELEASE,
    MOVEMENT_TYPE_RESERVE,
    RESERVATION_STATUSES,
    RESERVATION_STATUS_ACTIVE,
    RESERVATION_STATUS_CANCELLED,
    RESERVATION_STATUS_CONSUMED,
    RESERVATION_STATUS_EXPIRED,
    SOURCE_MANUAL,
    SOURCE_SYSTEM,
)
from app.db.settings import get_str_setting
from app.models import (
    AuditLog,
    Part,
    Reservation,
    ReservationItem,
    StockMovement,
)
from app.schemas.reservations import (
    ReservationCollectionResponse,
    ReservationCreateRequest,
    ReservationDeleteRequest,
    ReservationDeleteResponse,
    ReservationUpdateRequest,
    ReservationItemCreateRequest,
    ReservationItemResponse,
    ReservationResponse,
)


class ReservationConflictError(ValueError):
    pass


class ReservationValidationError(ValueError):
    pass


@dataclass(frozen=True)
class _NormalisedReservationItem:
    part_id: int
    quantity: int
    note: str | None


def _normalise_items(
    items: list[ReservationItemCreateRequest],
) -> list[_NormalisedReservationItem]:
    quantities: dict[int, int] = {}
    notes: dict[int, str | None] = {}
    order: list[int] = []

    for item in items:
        if item.part_id not in quantities:
            quantities[item.part_id] = 0
            notes[item.part_id] = item.note
            order.append(item.part_id)
        elif (
            item.note is not None
            and notes[item.part_id] is not None
            and item.note != notes[item.part_id]
        ):
            raise ReservationValidationError(
                "Duplicate reservation items for the same part must use "
                "the same note."
            )
        elif notes[item.part_id] is None:
            notes[item.part_id] = item.note

        quantities[item.part_id] += item.quantity

    return [
        _NormalisedReservationItem(
            part_id=part_id,
            quantity=quantities[part_id],
            note=notes[part_id],
        )
        for part_id in order
    ]


def _normalise_expiry(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ReservationValidationError(
            "Reservation expiry must include a timezone."
        )
    normalised = value.astimezone(timezone.utc)
    if normalised <= datetime.now(timezone.utc):
        raise ReservationValidationError(
            "Reservation expiry must be in the future."
        )
    return normalised


def _currency_snapshot(db: Session) -> str | None:
    value = get_str_setting(db, "currency.default", "").strip().upper()
    if len(value) == 3 and value.isalpha():
        return value
    return None


def _serialise_created_reservation(
    reservation: Reservation,
    item_parts: list[tuple[ReservationItem, Part]],
) -> ReservationResponse:
    return ReservationResponse(
        id=reservation.id,
        project_id=reservation.project_id,
        label=reservation.label,
        status=reservation.status,
        notes=reservation.notes,
        created_by=reservation.created_by,
        expiry_at=reservation.expiry_at,
        estimated_reserved_value=reservation.estimated_reserved_value,
        currency_snapshot=reservation.currency_snapshot,
        created_at=reservation.created_at,
        updated_at=reservation.updated_at,
        items=[
            ReservationItemResponse(
                id=item.id,
                reservation_id=item.reservation_id,
                part_id=item.part_id,
                part_number=part.part_number,
                part_name=part.name,
                quantity=item.quantity,
                unit_price_snapshot=item.unit_price_snapshot,
                currency_snapshot=item.currency_snapshot,
                note=item.note,
                total_quantity=part.total_quantity,
                reserved_quantity=part.reserved_quantity,
                available_quantity=(
                    part.total_quantity - part.reserved_quantity
                ),
            )
            for item, part in item_parts
        ],
    )


def create_reservation(
    db: Session,
    payload: ReservationCreateRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> ReservationResponse:
    normalised_items = _normalise_items(payload.items)
    if not normalised_items:
        raise ReservationValidationError(
            "A reservation must contain at least one part."
        )

    part_ids = [item.part_id for item in normalised_items]
    parts = list(
        db.execute(
            select(Part).where(Part.id.in_(part_ids))
        ).scalars()
    )
    part_map = {part.id: part for part in parts}

    for item in normalised_items:
        part = part_map.get(item.part_id)
        if part is None or part.is_deleted:
            raise ReservationValidationError(
                f"Part {item.part_id} is not available for reservation."
            )

    currency = _currency_snapshot(db)
    expiry_at = _normalise_expiry(payload.expiry_at)

    all_prices_known = all(
        part_map[item.part_id].unit_price is not None
        for item in normalised_items
    )
    estimated_value = (
        sum(
            (
                Decimal(part_map[item.part_id].unit_price)
                * item.quantity
            )
            for item in normalised_items
        )
        if all_prices_known
        else None
    )

    reservation = Reservation(
        project_id=None,
        label=payload.label,
        status=RESERVATION_STATUS_ACTIVE,
        notes=payload.notes,
        created_by=SOURCE_MANUAL,
        expiry_at=expiry_at,
        estimated_reserved_value=estimated_value,
        currency_snapshot=currency,
    )

    item_parts: list[tuple[ReservationItem, Part]] = []
    movements: list[StockMovement] = []

    try:
        db.add(reservation)
        db.flush()

        for submitted in normalised_items:
            part = part_map[submitted.part_id]
            total_quantity = int(part.total_quantity)
            reserved_before = int(part.reserved_quantity)
            available_before = total_quantity - reserved_before

            if submitted.quantity > available_before:
                raise ReservationConflictError(
                    f"Part {part.id} has only {available_before} "
                    "available units."
                )

            reserved_after = reserved_before + submitted.quantity
            available_after = total_quantity - reserved_after
            changed_at = datetime.now(timezone.utc)

            result = db.execute(
                update(Part)
                .where(
                    Part.id == part.id,
                    Part.is_deleted.is_(False),
                    Part.reserved_quantity == reserved_before,
                    (
                        Part.total_quantity - Part.reserved_quantity
                        >= submitted.quantity
                    ),
                )
                .values(
                    reserved_quantity=reserved_after,
                    updated_at=changed_at,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                raise ReservationConflictError(
                    f"Part {part.id} stock changed while the "
                    "reservation was being created."
                )

            part.reserved_quantity = reserved_after
            part.updated_at = changed_at

            item = ReservationItem(
                reservation_id=reservation.id,
                part_id=part.id,
                quantity=submitted.quantity,
                unit_price_snapshot=part.unit_price,
                currency_snapshot=currency,
                note=submitted.note,
            )
            movement = StockMovement(
                part_id=part.id,
                reservation_id=reservation.id,
                movement_type=MOVEMENT_TYPE_RESERVE,
                quantity_delta=0,
                quantity_before=total_quantity,
                quantity_after=total_quantity,
                reserved_quantity_before=reserved_before,
                reserved_quantity_after=reserved_after,
                available_quantity_before=available_before,
                available_quantity_after=available_after,
                unit_price_snapshot=part.unit_price,
                currency_snapshot=currency,
                reason=(f"Reserved for {reservation.label}")[:180],
                note=submitted.note,
                source=SOURCE_MANUAL,
                actor_user_id=actor_user_id,
            )
            db.add(item)
            db.add(movement)
            item_parts.append((item, part))
            movements.append(movement)

        db.flush()

        audit_items = [
            {
                "reservation_item_id": item.id,
                "part_id": item.part_id,
                "quantity": item.quantity,
                "stock_movement_id": movement.id,
                "reserved_quantity_after": (
                    part.reserved_quantity
                ),
                "available_quantity_after": (
                    part.total_quantity - part.reserved_quantity
                ),
            }
            for (item, part), movement in zip(
                item_parts,
                movements,
                strict=True,
            )
        ]
        db.add(
            AuditLog(
                event_type="reservation.created",
                entity_type="reservation",
                entity_id=reservation.id,
                actor_type=(
                    "user"
                    if actor_user_id is not None
                    else "system"
                ),
                actor_user_id=actor_user_id,
                summary=(
                    f"Created reservation {reservation.label} "
                    f"with {len(item_parts)} parts"
                ),
                before_json=None,
                after_json={
                    "id": reservation.id,
                    "label": reservation.label,
                    "status": reservation.status,
                    "item_count": len(item_parts),
                    "total_reserved_units": sum(
                        item.quantity
                        for item, _part in item_parts
                    ),
                    "estimated_reserved_value": (
                        str(reservation.estimated_reserved_value)
                        if reservation.estimated_reserved_value is not None
                        else None
                    ),
                    "currency_snapshot": reservation.currency_snapshot,
                    "expiry_at": (
                        reservation.expiry_at.isoformat()
                        if reservation.expiry_at is not None
                        else None
                    ),
                    "items": audit_items,
                },
                metadata_json={
                    "source": SOURCE_MANUAL,
                    "movement_type": MOVEMENT_TYPE_RESERVE,
                    "project_id": None,
                },
            )
        )
        db.flush()

        if commit:
            db.commit()
            db.refresh(reservation)
            for item, part in item_parts:
                db.refresh(item)
                db.refresh(part)

    except IntegrityError as exc:
        db.rollback()
        raise ReservationConflictError(
            "Reservation conflicted with current inventory data."
        ) from exc
    except Exception:
        db.rollback()
        raise

    return _serialise_created_reservation(
        reservation,
        item_parts,
    )


class ReservationNotFoundError(LookupError):
    pass


def _serialise_reservation(
    db: Session,
    reservation: Reservation,
) -> ReservationResponse:
    items = list(
        db.execute(
            select(ReservationItem)
            .where(
                ReservationItem.reservation_id == reservation.id
            )
            .order_by(ReservationItem.id.asc())
        ).scalars()
    )
    part_ids = [
        item.part_id
        for item in items
        if item.part_id is not None
    ]
    parts = (
        list(
            db.execute(
                select(Part).where(Part.id.in_(part_ids))
            ).scalars()
        )
        if part_ids
        else []
    )
    part_map = {part.id: part for part in parts}

    return ReservationResponse(
        id=reservation.id,
        project_id=reservation.project_id,
        label=reservation.label,
        status=reservation.status,
        notes=reservation.notes,
        created_by=reservation.created_by,
        expiry_at=reservation.expiry_at,
        estimated_reserved_value=reservation.estimated_reserved_value,
        currency_snapshot=reservation.currency_snapshot,
        created_at=reservation.created_at,
        updated_at=reservation.updated_at,
        items=[
            ReservationItemResponse(
                id=item.id,
                reservation_id=item.reservation_id,
                part_id=item.part_id,
                part_number=(
                    part_map[item.part_id].part_number
                    if item.part_id in part_map
                    else None
                ),
                part_name=(
                    part_map[item.part_id].name
                    if item.part_id in part_map
                    else None
                ),
                quantity=item.quantity,
                unit_price_snapshot=item.unit_price_snapshot,
                currency_snapshot=item.currency_snapshot,
                note=item.note,
                total_quantity=(
                    part_map[item.part_id].total_quantity
                    if item.part_id in part_map
                    else None
                ),
                reserved_quantity=(
                    part_map[item.part_id].reserved_quantity
                    if item.part_id in part_map
                    else None
                ),
                available_quantity=(
                    part_map[item.part_id].total_quantity
                    - part_map[item.part_id].reserved_quantity
                    if item.part_id in part_map
                    else None
                ),
            )
            for item in items
        ],
    )


def get_reservation(
    db: Session,
    reservation_id: int,
) -> ReservationResponse:
    reservation = db.get(Reservation, reservation_id)
    if reservation is None:
        raise ReservationNotFoundError("Reservation not found.")
    return _serialise_reservation(db, reservation)


def list_reservations(
    db: Session,
    *,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ReservationCollectionResponse:
    if status_filter is not None and status_filter not in RESERVATION_STATUSES:
        raise ReservationValidationError(
            f"Unsupported reservation status: {status_filter}."
        )
    if limit < 1 or limit > 100:
        raise ReservationValidationError(
            "Reservation limit must be between 1 and 100."
        )
    if offset < 0:
        raise ReservationValidationError(
            "Reservation offset cannot be negative."
        )

    conditions = []
    if status_filter is not None:
        conditions.append(Reservation.status == status_filter)

    count_query = select(func.count()).select_from(Reservation)
    list_query = select(Reservation)
    if conditions:
        count_query = count_query.where(*conditions)
        list_query = list_query.where(*conditions)

    total = int(db.execute(count_query).scalar_one())
    reservations = list(
        db.execute(
            list_query
            .order_by(
                Reservation.created_at.desc(),
                Reservation.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        ).scalars()
    )
    return ReservationCollectionResponse(
        total=total,
        limit=limit,
        offset=offset,
        reservations=[
            _serialise_reservation(db, reservation)
            for reservation in reservations
        ],
    )




# PARTPILOT:RESERVATION_EDIT_SERVICE:V346
def _reservation_edit_expiry(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _reservation_edit_item_snapshot(
    item: ReservationItem,
) -> dict[str, object]:
    return {
        "reservation_item_id": item.id,
        "part_id": item.part_id,
        "quantity": int(item.quantity),
        "unit_price_snapshot": (
            str(item.unit_price_snapshot)
            if item.unit_price_snapshot is not None
            else None
        ),
        "currency_snapshot": item.currency_snapshot,
        "note": item.note,
    }


def update_reservation(
    db: Session,
    reservation_id: int,
    payload: ReservationUpdateRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> ReservationResponse:
    reservation = db.execute(
        select(Reservation)
        .where(Reservation.id == reservation_id)
        .with_for_update()
    ).scalar_one_or_none()
    if reservation is None:
        raise ReservationNotFoundError("Reservation not found.")
    if reservation.status != RESERVATION_STATUS_ACTIVE:
        raise ReservationConflictError(
            "Only active reservations can be edited. "
            f"Current status: {reservation.status}."
        )

    submitted_items = _normalise_items(payload.items)
    if not submitted_items:
        raise ReservationValidationError(
            "A reservation must contain at least one part."
        )
    expiry_at = _normalise_expiry(payload.expiry_at)

    existing_items = list(
        db.execute(
            select(ReservationItem)
            .where(ReservationItem.reservation_id == reservation.id)
            .order_by(ReservationItem.id.asc())
        ).scalars()
    )
    if not existing_items:
        raise ReservationConflictError(
            "Active reservation has no items to edit."
        )
    if any(item.part_id is None for item in existing_items):
        raise ReservationConflictError(
            "Reservation contains an item whose part no longer exists."
        )

    existing_by_part: dict[int, ReservationItem] = {}
    for item in existing_items:
        assert item.part_id is not None
        if item.part_id in existing_by_part:
            raise ReservationConflictError(
                "Reservation contains duplicate stored items for the same part."
            )
        existing_by_part[item.part_id] = item

    submitted_by_part = {
        item.part_id: item
        for item in submitted_items
    }
    all_part_ids = sorted(set(existing_by_part) | set(submitted_by_part))
    parts = list(
        db.execute(
            select(Part)
            .where(Part.id.in_(all_part_ids))
            .with_for_update()
        ).scalars()
    )
    part_map = {part.id: part for part in parts}

    for part_id in existing_by_part:
        part = part_map.get(part_id)
        if part is None or part.is_deleted:
            raise ReservationConflictError(
                f"Reservation part {part_id} is no longer editable."
            )
    for part_id in submitted_by_part:
        part = part_map.get(part_id)
        if part is None or part.is_deleted:
            raise ReservationValidationError(
                f"Part {part_id} is not available for reservation."
            )

    current_expiry = _reservation_edit_expiry(reservation.expiry_at)
    unchanged_items = (
        set(existing_by_part) == set(submitted_by_part)
        and all(
            int(existing_by_part[part_id].quantity)
            == int(submitted_by_part[part_id].quantity)
            and existing_by_part[part_id].note
            == submitted_by_part[part_id].note
            for part_id in existing_by_part
        )
    )
    if (
        reservation.label == payload.label
        and reservation.notes == payload.notes
        and current_expiry == expiry_at
        and unchanged_items
    ):
        return _serialise_reservation(db, reservation)

    before_items = [
        _reservation_edit_item_snapshot(item)
        for item in existing_items
    ]
    before_snapshot = {
        "id": reservation.id,
        "label": reservation.label,
        "status": reservation.status,
        "notes": reservation.notes,
        "expiry_at": (
            current_expiry.isoformat()
            if current_expiry is not None
            else None
        ),
        "estimated_reserved_value": (
            str(reservation.estimated_reserved_value)
            if reservation.estimated_reserved_value is not None
            else None
        ),
        "currency_snapshot": reservation.currency_snapshot,
        "total_reserved_units": sum(
            int(item.quantity) for item in existing_items
        ),
        "items": before_items,
    }

    movements: list[StockMovement] = []
    increased_part_ids: list[int] = []
    released_part_ids: list[int] = []
    retained_items: list[ReservationItem] = []

    try:
        for part_id in all_part_ids:
            part = part_map[part_id]
            existing = existing_by_part.get(part_id)
            submitted = submitted_by_part.get(part_id)
            old_quantity = int(existing.quantity) if existing is not None else 0
            new_quantity = int(submitted.quantity) if submitted is not None else 0
            delta = new_quantity - old_quantity
            total_quantity = int(part.total_quantity)
            reserved_before = int(part.reserved_quantity)
            available_before = total_quantity - reserved_before

            if existing is not None and reserved_before < old_quantity:
                raise ReservationConflictError(
                    f"Part {part.id} has only {reserved_before} reserved units, "
                    f"but reservation item {existing.id} requires {old_quantity}."
                )
            if delta > 0 and delta > available_before:
                raise ReservationConflictError(
                    f"Part {part.id} has only {available_before} available "
                    f"units; editing requires {delta} additional units."
                )

            reserved_after = reserved_before + delta
            if reserved_after < 0 or reserved_after > total_quantity:
                raise ReservationConflictError(
                    f"Part {part.id} stock cannot support the edited reservation."
                )

            if delta != 0:
                changed_at = datetime.now(timezone.utc)
                conditions = [
                    Part.id == part.id,
                    Part.is_deleted.is_(False),
                    Part.reserved_quantity == reserved_before,
                ]
                if delta > 0:
                    conditions.append(
                        Part.total_quantity - Part.reserved_quantity >= delta
                    )
                else:
                    conditions.append(Part.reserved_quantity >= -delta)
                result = db.execute(
                    update(Part)
                    .where(*conditions)
                    .values(
                        reserved_quantity=reserved_after,
                        updated_at=changed_at,
                    )
                    .execution_options(synchronize_session=False)
                )
                if result.rowcount != 1:
                    raise ReservationConflictError(
                        f"Part {part.id} stock changed while reservation "
                        f"{reservation.id} was being edited."
                    )
                part.reserved_quantity = reserved_after
                part.updated_at = changed_at

                movement_type = (
                    MOVEMENT_TYPE_RESERVE
                    if delta > 0
                    else MOVEMENT_TYPE_RELEASE
                )
                movement_note = (
                    submitted.note
                    if submitted is not None
                    else existing.note if existing is not None else None
                )
                movement = StockMovement(
                    part_id=part.id,
                    reservation_id=reservation.id,
                    movement_type=movement_type,
                    quantity_delta=0,
                    quantity_before=total_quantity,
                    quantity_after=total_quantity,
                    reserved_quantity_before=reserved_before,
                    reserved_quantity_after=reserved_after,
                    available_quantity_before=available_before,
                    available_quantity_after=(
                        total_quantity - reserved_after
                    ),
                    unit_price_snapshot=(
                        existing.unit_price_snapshot
                        if existing is not None
                        else part.unit_price
                    ),
                    currency_snapshot=reservation.currency_snapshot,
                    reason=(
                        (
                            f"Increased reservation for {payload.label}"
                            if delta > 0
                            else f"Released from reservation {payload.label}"
                        )[:180]
                    ),
                    note=movement_note,
                    source=SOURCE_MANUAL,
                    actor_user_id=actor_user_id,
                )
                db.add(movement)
                movements.append(movement)
                if delta > 0:
                    increased_part_ids.append(part.id)
                else:
                    released_part_ids.append(part.id)

        for submitted in submitted_items:
            existing = existing_by_part.get(submitted.part_id)
            if existing is None:
                part = part_map[submitted.part_id]
                existing = ReservationItem(
                    reservation_id=reservation.id,
                    part_id=part.id,
                    quantity=submitted.quantity,
                    unit_price_snapshot=part.unit_price,
                    currency_snapshot=reservation.currency_snapshot,
                    note=submitted.note,
                )
                db.add(existing)
            else:
                existing.quantity = submitted.quantity
                existing.note = submitted.note
            retained_items.append(existing)

        for part_id, existing in existing_by_part.items():
            if part_id not in submitted_by_part:
                db.delete(existing)

        all_prices_known = all(
            item.unit_price_snapshot is not None
            for item in retained_items
        )
        estimated_value = (
            sum(
                Decimal(item.unit_price_snapshot) * int(item.quantity)
                for item in retained_items
            )
            if all_prices_known
            else None
        )

        reservation.label = payload.label
        reservation.notes = payload.notes
        reservation.expiry_at = expiry_at
        reservation.estimated_reserved_value = estimated_value
        db.flush()

        after_items = [
            _reservation_edit_item_snapshot(item)
            for item in retained_items
        ]
        after_snapshot = {
            "id": reservation.id,
            "label": reservation.label,
            "status": reservation.status,
            "notes": reservation.notes,
            "expiry_at": (
                expiry_at.isoformat() if expiry_at is not None else None
            ),
            "estimated_reserved_value": (
                str(reservation.estimated_reserved_value)
                if reservation.estimated_reserved_value is not None
                else None
            ),
            "currency_snapshot": reservation.currency_snapshot,
            "total_reserved_units": sum(
                int(item.quantity) for item in retained_items
            ),
            "items": after_items,
        }

        db.add(
            AuditLog(
                event_type="reservation.updated",
                entity_type="reservation",
                entity_id=reservation.id,
                actor_type=(
                    "user" if actor_user_id is not None else "system"
                ),
                actor_user_id=actor_user_id,
                summary=(
                    f"Updated reservation {reservation.label} "
                    f"with {len(retained_items)} parts"
                ),
                before_json=before_snapshot,
                after_json=after_snapshot,
                metadata_json={
                    "source": SOURCE_MANUAL,
                    "movement_types": sorted(
                        {movement.movement_type for movement in movements}
                    ),
                    "movement_ids": [
                        movement.id for movement in movements
                    ],
                    "increased_part_ids": increased_part_ids,
                    "released_part_ids": released_part_ids,
                    "project_id": reservation.project_id,
                },
            )
        )
        db.flush()

        if commit:
            db.commit()
            db.refresh(reservation)

    except IntegrityError as exc:
        db.rollback()
        raise ReservationConflictError(
            "Reservation edit conflicted with current inventory data."
        ) from exc
    except Exception:
        db.rollback()
        raise

    return _serialise_reservation(db, reservation)


# PARTPILOT:RESERVATION_CANCELLATION_SERVICE:V306
def cancel_reservation(
    db: Session,
    reservation_id: int,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> ReservationResponse:
    reservation = db.execute(
        select(Reservation)
        .where(Reservation.id == reservation_id)
        .with_for_update()
    ).scalar_one_or_none()
    if reservation is None:
        raise ReservationNotFoundError("Reservation not found.")
    if reservation.status != RESERVATION_STATUS_ACTIVE:
        raise ReservationConflictError(
            "Only active reservations can be cancelled. "
            f"Current status: {reservation.status}."
        )

    items = list(
        db.execute(
            select(ReservationItem)
            .where(ReservationItem.reservation_id == reservation.id)
            .order_by(ReservationItem.id.asc())
        ).scalars()
    )
    if not items:
        raise ReservationConflictError(
            "Active reservation has no items to release."
        )

    part_ids = [item.part_id for item in items if item.part_id is not None]
    if len(part_ids) != len(items):
        raise ReservationConflictError(
            "Reservation contains an item whose part no longer exists."
        )

    parts = list(
        db.execute(
            select(Part)
            .where(Part.id.in_(part_ids))
            .with_for_update()
        ).scalars()
    )
    part_map = {part.id: part for part in parts}
    if len(part_map) != len(set(part_ids)):
        raise ReservationConflictError(
            "Reservation contains a part that no longer exists."
        )

    release_records: list[dict[str, int]] = []
    movements: list[StockMovement] = []

    try:
        for item in items:
            assert item.part_id is not None
            part = part_map[item.part_id]
            total_quantity = int(part.total_quantity)
            reserved_before = int(part.reserved_quantity)
            quantity = int(item.quantity)

            if reserved_before < quantity:
                raise ReservationConflictError(
                    f"Part {part.id} has only {reserved_before} reserved "
                    f"units, but reservation item {item.id} requires "
                    f"releasing {quantity}."
                )

            reserved_after = reserved_before - quantity
            available_before = total_quantity - reserved_before
            available_after = total_quantity - reserved_after
            changed_at = datetime.now(timezone.utc)

            result = db.execute(
                update(Part)
                .where(
                    Part.id == part.id,
                    Part.reserved_quantity == reserved_before,
                    Part.reserved_quantity >= quantity,
                )
                .values(
                    reserved_quantity=reserved_after,
                    updated_at=changed_at,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                raise ReservationConflictError(
                    f"Part {part.id} stock changed while reservation "
                    f"{reservation.id} was being cancelled."
                )

            movement = StockMovement(
                part_id=part.id,
                reservation_id=reservation.id,
                movement_type=MOVEMENT_TYPE_RELEASE,
                quantity_delta=0,
                quantity_before=total_quantity,
                quantity_after=total_quantity,
                reserved_quantity_before=reserved_before,
                reserved_quantity_after=reserved_after,
                available_quantity_before=available_before,
                available_quantity_after=available_after,
                unit_price_snapshot=item.unit_price_snapshot,
                currency_snapshot=item.currency_snapshot,
                reason=(f"Released from {reservation.label}")[:180],
                note=item.note,
                source=SOURCE_MANUAL,
                actor_user_id=actor_user_id,
            )
            db.add(movement)
            movements.append(movement)
            release_records.append(
                {
                    "reservation_item_id": item.id,
                    "part_id": part.id,
                    "quantity": quantity,
                    "total_quantity": total_quantity,
                    "reserved_quantity_before": reserved_before,
                    "reserved_quantity_after": reserved_after,
                    "available_quantity_before": available_before,
                    "available_quantity_after": available_after,
                }
            )
            db.expire(part, ["reserved_quantity", "updated_at"])

        changed_at = datetime.now(timezone.utc)
        status_result = db.execute(
            update(Reservation)
            .where(
                Reservation.id == reservation.id,
                Reservation.status == RESERVATION_STATUS_ACTIVE,
            )
            .values(
                status=RESERVATION_STATUS_CANCELLED,
                updated_at=changed_at,
            )
            .execution_options(synchronize_session=False)
        )
        if status_result.rowcount != 1:
            raise ReservationConflictError(
                "Reservation status changed while cancellation was in "
                "progress."
            )
        db.expire(reservation, ["status", "updated_at"])

        db.flush()
        for record, movement in zip(
            release_records,
            movements,
            strict=True,
        ):
            record["stock_movement_id"] = movement.id

        db.add(
            AuditLog(
                event_type="reservation.cancelled",
                entity_type="reservation",
                entity_id=reservation.id,
                actor_type=(
                    "user" if actor_user_id is not None else "system"
                ),
                actor_user_id=actor_user_id,
                summary=f"Cancelled reservation {reservation.label}",
                before_json={
                    "status": RESERVATION_STATUS_ACTIVE,
                    "items": [
                        {
                            "reservation_item_id": record[
                                "reservation_item_id"
                            ],
                            "part_id": record["part_id"],
                            "quantity": record["quantity"],
                            "reserved_quantity": record[
                                "reserved_quantity_before"
                            ],
                            "available_quantity": record[
                                "available_quantity_before"
                            ],
                        }
                        for record in release_records
                    ],
                },
                after_json={
                    "status": RESERVATION_STATUS_CANCELLED,
                    "released_units": sum(
                        record["quantity"] for record in release_records
                    ),
                    "items": release_records,
                },
                metadata_json={
                    "source": SOURCE_MANUAL,
                    "movement_type": MOVEMENT_TYPE_RELEASE,
                    "project_id": reservation.project_id,
                },
            )
        )
        db.flush()

        if commit:
            db.commit()
            db.refresh(reservation)

    except IntegrityError as exc:
        db.rollback()
        raise ReservationConflictError(
            "Reservation cancellation conflicted with current inventory "
            "data."
        ) from exc
    except Exception:
        db.rollback()
        raise

    return _serialise_reservation(db, reservation)


# PARTPILOT:RESERVATION_CONSUMPTION_SERVICE:V315
def consume_reservation(
    db: Session,
    reservation_id: int,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> ReservationResponse:
    reservation = db.execute(
        select(Reservation)
        .where(Reservation.id == reservation_id)
        .with_for_update()
    ).scalar_one_or_none()
    if reservation is None:
        raise ReservationNotFoundError("Reservation not found.")
    if reservation.status != RESERVATION_STATUS_ACTIVE:
        raise ReservationConflictError(
            "Only active reservations can be consumed. "
            f"Current status: {reservation.status}."
        )

    items = list(
        db.execute(
            select(ReservationItem)
            .where(ReservationItem.reservation_id == reservation.id)
            .order_by(ReservationItem.id.asc())
        ).scalars()
    )
    if not items:
        raise ReservationConflictError(
            "Active reservation has no items to consume."
        )

    part_ids = [
        item.part_id
        for item in items
        if item.part_id is not None
    ]
    if len(part_ids) != len(items):
        raise ReservationConflictError(
            "Reservation contains an item whose part no longer exists."
        )

    parts = list(
        db.execute(
            select(Part)
            .where(Part.id.in_(part_ids))
            .with_for_update()
        ).scalars()
    )
    part_map = {part.id: part for part in parts}
    if len(part_map) != len(set(part_ids)):
        raise ReservationConflictError(
            "Reservation contains a part that no longer exists."
        )

    consume_records: list[dict[str, int]] = []
    movements: list[StockMovement] = []

    try:
        for item in items:
            assert item.part_id is not None
            part = part_map[item.part_id]
            quantity = int(item.quantity)
            total_before = int(part.total_quantity)
            reserved_before = int(part.reserved_quantity)
            available_before = total_before - reserved_before

            if total_before < quantity:
                raise ReservationConflictError(
                    f"Part {part.id} has only {total_before} physical "
                    f"units, but reservation item {item.id} requires "
                    f"consuming {quantity}."
                )
            if reserved_before < quantity:
                raise ReservationConflictError(
                    f"Part {part.id} has only {reserved_before} reserved "
                    f"units, but reservation item {item.id} requires "
                    f"consuming {quantity}."
                )

            total_after = total_before - quantity
            reserved_after = reserved_before - quantity
            available_after = total_after - reserved_after
            if available_after != available_before:
                raise ReservationConflictError(
                    f"Part {part.id} available quantity would change "
                    "during reserved consumption."
                )

            changed_at = datetime.now(timezone.utc)
            result = db.execute(
                update(Part)
                .where(
                    Part.id == part.id,
                    Part.total_quantity == total_before,
                    Part.reserved_quantity == reserved_before,
                    Part.total_quantity >= quantity,
                    Part.reserved_quantity >= quantity,
                )
                .values(
                    total_quantity=total_after,
                    reserved_quantity=reserved_after,
                    updated_at=changed_at,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                raise ReservationConflictError(
                    f"Part {part.id} stock changed while reservation "
                    f"{reservation.id} was being consumed."
                )

            movement = StockMovement(
                part_id=part.id,
                reservation_id=reservation.id,
                movement_type=MOVEMENT_TYPE_CONSUME,
                quantity_delta=-quantity,
                quantity_before=total_before,
                quantity_after=total_after,
                reserved_quantity_before=reserved_before,
                reserved_quantity_after=reserved_after,
                available_quantity_before=available_before,
                available_quantity_after=available_after,
                unit_price_snapshot=item.unit_price_snapshot,
                currency_snapshot=item.currency_snapshot,
                reason=(f"Consumed from {reservation.label}")[:180],
                note=item.note,
                source=SOURCE_MANUAL,
                actor_user_id=actor_user_id,
            )
            db.add(movement)
            movements.append(movement)
            consume_records.append(
                {
                    "reservation_item_id": item.id,
                    "part_id": part.id,
                    "quantity": quantity,
                    "quantity_before": total_before,
                    "quantity_after": total_after,
                    "reserved_quantity_before": reserved_before,
                    "reserved_quantity_after": reserved_after,
                    "available_quantity_before": available_before,
                    "available_quantity_after": available_after,
                }
            )
            db.expire(
                part,
                ["total_quantity", "reserved_quantity", "updated_at"],
            )

        changed_at = datetime.now(timezone.utc)
        status_result = db.execute(
            update(Reservation)
            .where(
                Reservation.id == reservation.id,
                Reservation.status == RESERVATION_STATUS_ACTIVE,
            )
            .values(
                status=RESERVATION_STATUS_CONSUMED,
                updated_at=changed_at,
            )
            .execution_options(synchronize_session=False)
        )
        if status_result.rowcount != 1:
            raise ReservationConflictError(
                "Reservation status changed while consumption was in "
                "progress."
            )
        db.expire(reservation, ["status", "updated_at"])

        db.flush()
        for record, movement in zip(
            consume_records,
            movements,
            strict=True,
        ):
            record["stock_movement_id"] = movement.id

        db.add(
            AuditLog(
                event_type="reservation.consumed",
                entity_type="reservation",
                entity_id=reservation.id,
                actor_type=(
                    "user" if actor_user_id is not None else "system"
                ),
                actor_user_id=actor_user_id,
                summary=f"Consumed reservation {reservation.label}",
                before_json={
                    "status": RESERVATION_STATUS_ACTIVE,
                    "items": [
                        {
                            "reservation_item_id": record[
                                "reservation_item_id"
                            ],
                            "part_id": record["part_id"],
                            "quantity": record["quantity"],
                            "total_quantity": record["quantity_before"],
                            "reserved_quantity": record[
                                "reserved_quantity_before"
                            ],
                            "available_quantity": record[
                                "available_quantity_before"
                            ],
                        }
                        for record in consume_records
                    ],
                },
                after_json={
                    "status": RESERVATION_STATUS_CONSUMED,
                    "consumed_units": sum(
                        record["quantity"]
                        for record in consume_records
                    ),
                    "items": consume_records,
                },
                metadata_json={
                    "source": SOURCE_MANUAL,
                    "movement_type": MOVEMENT_TYPE_CONSUME,
                    "project_id": reservation.project_id,
                },
            )
        )
        db.flush()

        if commit:
            db.commit()
            db.refresh(reservation)

    except IntegrityError as exc:
        db.rollback()
        raise ReservationConflictError(
            "Reservation consumption conflicted with current inventory "
            "data."
        ) from exc
    except Exception:
        db.rollback()
        raise

    return _serialise_reservation(db, reservation)


# PARTPILOT:RESERVATION_EXPIRY_SERVICE:V320
def expire_reservation(
    db: Session,
    reservation_id: int,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> ReservationResponse:
    reservation = db.execute(
        select(Reservation)
        .where(Reservation.id == reservation_id)
        .with_for_update()
    ).scalar_one_or_none()
    if reservation is None:
        raise ReservationNotFoundError("Reservation not found.")
    if reservation.status != RESERVATION_STATUS_ACTIVE:
        raise ReservationConflictError(
            "Only active reservations can be expired. "
            f"Current status: {reservation.status}."
        )

    stored_expiry_at = reservation.expiry_at
    if stored_expiry_at is None:
        raise ReservationConflictError("Reservation has no expiry date.")

    expiry_at = stored_expiry_at
    if expiry_at.tzinfo is None or expiry_at.utcoffset() is None:
        expiry_at = expiry_at.replace(tzinfo=timezone.utc)
    else:
        expiry_at = expiry_at.astimezone(timezone.utc)
    if expiry_at > datetime.now(timezone.utc):
        raise ReservationConflictError(
            "Reservation is not due to expire yet."
        )

    items = list(
        db.execute(
            select(ReservationItem)
            .where(ReservationItem.reservation_id == reservation.id)
            .order_by(ReservationItem.id.asc())
        ).scalars()
    )
    if not items:
        raise ReservationConflictError(
            "Active reservation has no items to release."
        )

    part_ids = [
        item.part_id
        for item in items
        if item.part_id is not None
    ]
    if len(part_ids) != len(items):
        raise ReservationConflictError(
            "Reservation contains an item whose part no longer exists."
        )

    parts = list(
        db.execute(
            select(Part)
            .where(Part.id.in_(part_ids))
            .with_for_update()
        ).scalars()
    )
    part_map = {part.id: part for part in parts}
    if len(part_map) != len(set(part_ids)):
        raise ReservationConflictError(
            "Reservation contains a part that no longer exists."
        )

    records: list[dict[str, int]] = []
    movements: list[StockMovement] = []
    try:
        for item in items:
            assert item.part_id is not None
            part = part_map[item.part_id]
            quantity = int(item.quantity)
            total = int(part.total_quantity)
            reserved_before = int(part.reserved_quantity)
            available_before = total - reserved_before
            if reserved_before < quantity:
                raise ReservationConflictError(
                    f"Part {part.id} has only {reserved_before} reserved "
                    f"units, but reservation item {item.id} requires "
                    f"releasing {quantity}."
                )

            reserved_after = reserved_before - quantity
            available_after = total - reserved_after
            changed_at = datetime.now(timezone.utc)
            result = db.execute(
                update(Part)
                .where(
                    Part.id == part.id,
                    Part.total_quantity == total,
                    Part.reserved_quantity == reserved_before,
                    Part.reserved_quantity >= quantity,
                )
                .values(
                    reserved_quantity=reserved_after,
                    updated_at=changed_at,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                raise ReservationConflictError(
                    f"Part {part.id} stock changed while reservation "
                    f"{reservation.id} was being expired."
                )

            movement = StockMovement(
                part_id=part.id,
                reservation_id=reservation.id,
                movement_type=MOVEMENT_TYPE_RELEASE,
                quantity_delta=0,
                quantity_before=total,
                quantity_after=total,
                reserved_quantity_before=reserved_before,
                reserved_quantity_after=reserved_after,
                available_quantity_before=available_before,
                available_quantity_after=available_after,
                unit_price_snapshot=item.unit_price_snapshot,
                currency_snapshot=item.currency_snapshot,
                reason=(f"Expired reservation {reservation.label}")[:180],
                note=item.note,
                source=SOURCE_SYSTEM,
                actor_user_id=actor_user_id,
            )
            db.add(movement)
            movements.append(movement)
            records.append(
                {
                    "reservation_item_id": item.id,
                    "part_id": part.id,
                    "quantity": quantity,
                    "total_quantity": total,
                    "reserved_quantity_before": reserved_before,
                    "reserved_quantity_after": reserved_after,
                    "available_quantity_before": available_before,
                    "available_quantity_after": available_after,
                }
            )
            db.expire(part, ["reserved_quantity", "updated_at"])

        changed_at = datetime.now(timezone.utc)
        status_result = db.execute(
            update(Reservation)
            .where(
                Reservation.id == reservation.id,
                Reservation.status == RESERVATION_STATUS_ACTIVE,
                Reservation.expiry_at == stored_expiry_at,
            )
            .values(
                status=RESERVATION_STATUS_EXPIRED,
                updated_at=changed_at,
            )
            .execution_options(synchronize_session=False)
        )
        if status_result.rowcount != 1:
            raise ReservationConflictError(
                "Reservation status or expiry changed while expiry "
                "processing was in progress."
            )
        db.expire(reservation, ["status", "updated_at"])

        db.flush()
        for record, movement in zip(records, movements, strict=True):
            record["stock_movement_id"] = movement.id

        db.add(
            AuditLog(
                event_type="reservation.expired",
                entity_type="reservation",
                entity_id=reservation.id,
                actor_type=(
                    "user" if actor_user_id is not None else "system"
                ),
                actor_user_id=actor_user_id,
                summary=f"Expired reservation {reservation.label}",
                before_json={
                    "status": RESERVATION_STATUS_ACTIVE,
                    "expiry_at": expiry_at.isoformat(),
                    "items": [
                        {
                            "reservation_item_id": row[
                                "reservation_item_id"
                            ],
                            "part_id": row["part_id"],
                            "quantity": row["quantity"],
                            "reserved_quantity": row[
                                "reserved_quantity_before"
                            ],
                            "available_quantity": row[
                                "available_quantity_before"
                            ],
                        }
                        for row in records
                    ],
                },
                after_json={
                    "status": RESERVATION_STATUS_EXPIRED,
                    "expired_at": changed_at.isoformat(),
                    "released_units": sum(
                        row["quantity"] for row in records
                    ),
                    "items": records,
                },
                metadata_json={
                    "source": SOURCE_SYSTEM,
                    "movement_type": MOVEMENT_TYPE_RELEASE,
                    "project_id": reservation.project_id,
                },
            )
        )
        db.flush()
        if commit:
            db.commit()
            db.refresh(reservation)
    except IntegrityError as exc:
        db.rollback()
        raise ReservationConflictError(
            "Reservation expiry conflicted with current inventory data."
        ) from exc
    except Exception:
        db.rollback()
        raise

    return _serialise_reservation(db, reservation)


# PARTPILOT:RESERVATION_DELETE_SERVICE:V351
def _reservation_delete_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat()


def _reservation_delete_inventory_snapshot(db: Session) -> dict[str, int]:
    row = db.execute(
        select(
            func.count(Part.id),
            func.coalesce(func.sum(Part.total_quantity), 0),
            func.coalesce(func.sum(Part.reserved_quantity), 0),
            func.coalesce(
                func.sum(Part.total_quantity - Part.reserved_quantity),
                0,
            ),
        ).where(Part.is_deleted.is_(False))
    ).one()
    return {
        "active_parts": int(row[0]),
        "total_quantity": int(row[1]),
        "reserved_quantity": int(row[2]),
        "available_quantity": int(row[3]),
    }


def delete_reservation(
    db: Session,
    reservation_id: int,
    payload: ReservationDeleteRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> ReservationDeleteResponse:
    reservation = db.execute(
        select(Reservation)
        .where(Reservation.id == reservation_id)
        .with_for_update()
    ).scalar_one_or_none()
    if reservation is None:
        raise ReservationNotFoundError("Reservation not found.")
    if reservation.status == RESERVATION_STATUS_ACTIVE:
        raise ReservationConflictError(
            "Active reservations cannot be deleted. Cancel, consume, or "
            "expire the reservation first."
        )
    if reservation.status not in {
        RESERVATION_STATUS_CANCELLED,
        RESERVATION_STATUS_CONSUMED,
        RESERVATION_STATUS_EXPIRED,
    }:
        raise ReservationConflictError(
            f"Reservation status {reservation.status!r} cannot be deleted."
        )
    if payload.confirmation_label != reservation.label:
        raise ReservationValidationError(
            "Confirmation label does not match the reservation label."
        )

    items = list(
        db.execute(
            select(ReservationItem)
            .where(ReservationItem.reservation_id == reservation.id)
            .order_by(ReservationItem.id.asc())
        ).scalars()
    )
    movement_ids = list(
        db.execute(
            select(StockMovement.id)
            .where(StockMovement.reservation_id == reservation.id)
            .order_by(StockMovement.id.asc())
        ).scalars()
    )
    prior_audit_count = int(
        db.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.entity_type == "reservation",
                AuditLog.entity_id == reservation.id,
            )
        ).scalar_one()
    )
    inventory_before = _reservation_delete_inventory_snapshot(db)
    deleted_at = datetime.now(timezone.utc)
    previous_status = reservation.status
    snapshot = {
        "id": reservation.id,
        "project_id": reservation.project_id,
        "label": reservation.label,
        "status": reservation.status,
        "notes": reservation.notes,
        "created_by": reservation.created_by,
        "expiry_at": _reservation_delete_timestamp(reservation.expiry_at),
        "estimated_reserved_value": (
            str(reservation.estimated_reserved_value)
            if reservation.estimated_reserved_value is not None
            else None
        ),
        "currency_snapshot": reservation.currency_snapshot,
        "created_at": _reservation_delete_timestamp(reservation.created_at),
        "updated_at": _reservation_delete_timestamp(reservation.updated_at),
        "items": [
            {
                "id": item.id,
                "reservation_id": item.reservation_id,
                "part_id": item.part_id,
                "quantity": int(item.quantity),
                "unit_price_snapshot": (
                    str(item.unit_price_snapshot)
                    if item.unit_price_snapshot is not None
                    else None
                ),
                "currency_snapshot": item.currency_snapshot,
                "note": item.note,
                "created_at": _reservation_delete_timestamp(item.created_at),
                "updated_at": _reservation_delete_timestamp(item.updated_at),
            }
            for item in items
        ],
        "movement_ids": movement_ids,
        "prior_audit_count": prior_audit_count,
        "inventory": inventory_before,
    }
    response = ReservationDeleteResponse(
        id=reservation.id,
        label=reservation.label,
        previous_status=reservation.status,
        deleted=True,
        removed_item_count=len(items),
        detached_movement_count=len(movement_ids),
        deleted_at=deleted_at,
    )

    try:
        db.add(
            AuditLog(
                event_type="reservation.deleted",
                entity_type="reservation",
                entity_id=reservation.id,
                actor_type=(
                    "user" if actor_user_id is not None else "system"
                ),
                actor_user_id=actor_user_id,
                summary=f"Deleted {previous_status} reservation {reservation.label}",
                before_json=snapshot,
                after_json={
                    "id": response.id,
                    "label": response.label,
                    "previous_status": response.previous_status,
                    "deleted": True,
                    "removed_item_count": response.removed_item_count,
                    "detached_movement_count": response.detached_movement_count,
                    "deleted_at": deleted_at.isoformat(),
                },
                metadata_json={
                    "source": SOURCE_MANUAL,
                    "project_id": reservation.project_id,
                    "retained_prior_audit_count": prior_audit_count,
                    "retained_stock_movement_ids": movement_ids,
                    "inventory_unchanged": True,
                },
            )
        )
        deleted = db.execute(
            delete(Reservation).where(
                Reservation.id == reservation.id,
                Reservation.status == previous_status,
            )
        )
        if deleted.rowcount != 1:
            raise ReservationConflictError(
                "Reservation changed while deletion was in progress."
            )
        db.flush()

        if db.get(Reservation, response.id) is not None:
            raise ReservationConflictError(
                "Reservation row remained after deletion."
            )
        remaining_items = int(
            db.execute(
                select(func.count(ReservationItem.id)).where(
                    ReservationItem.reservation_id == response.id
                )
            ).scalar_one()
        )
        if remaining_items != 0:
            raise ReservationConflictError(
                "Reservation items remained after deletion."
            )
        if movement_ids:
            detached = list(
                db.execute(
                    select(
                        StockMovement.id,
                        StockMovement.reservation_id,
                    )
                    .where(StockMovement.id.in_(movement_ids))
                    .order_by(StockMovement.id.asc())
                ).all()
            )
            if (
                len(detached) != len(movement_ids)
                or [int(row[0]) for row in detached] != movement_ids
                or any(row[1] is not None for row in detached)
            ):
                raise ReservationConflictError(
                    "Reservation stock movements were not safely detached."
                )
        audit_count = int(
            db.execute(
                select(func.count(AuditLog.id)).where(
                    AuditLog.entity_type == "reservation",
                    AuditLog.entity_id == response.id,
                )
            ).scalar_one()
        )
        if audit_count != prior_audit_count + 1:
            raise ReservationConflictError(
                "Reservation audit history was not retained correctly."
            )
        if _reservation_delete_inventory_snapshot(db) != inventory_before:
            raise ReservationConflictError(
                "Reservation deletion attempted to change inventory."
            )

        if commit:
            db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ReservationConflictError(
            "Reservation deletion conflicted with current data."
        ) from exc
    except Exception:
        db.rollback()
        raise

    return response


# PARTPILOT:RESERVATION_ACTIVITY_SERVICE:V338
def _reservation_activity_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def list_reservation_activity(
    db: Session,
    reservation_id: int,
    *,
    limit: int = 100,
    offset: int = 0,
):
    from app.models import User
    from app.schemas.reservations import (
        ReservationActivityCollectionResponse,
        ReservationActivityEntryResponse,
    )

    reservation = db.get(Reservation, reservation_id)
    if reservation is None:
        raise ReservationNotFoundError("Reservation not found.")
    if limit < 1 or limit > 200:
        raise ReservationValidationError(
            "Reservation activity limit must be between 1 and 200."
        )
    if offset < 0:
        raise ReservationValidationError(
            "Reservation activity offset cannot be negative."
        )

    audits = list(
        db.execute(
            select(AuditLog)
            .where(
                AuditLog.entity_type == "reservation",
                AuditLog.entity_id == reservation_id,
            )
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        ).scalars()
    )
    movements = list(
        db.execute(
            select(StockMovement)
            .where(StockMovement.reservation_id == reservation_id)
            .order_by(
                StockMovement.created_at.desc(),
                StockMovement.id.desc(),
            )
        ).scalars()
    )

    actor_ids = {
        actor_id
        for actor_id in (
            [audit.actor_user_id for audit in audits]
            + [movement.actor_user_id for movement in movements]
        )
        if actor_id is not None
    }
    users = (
        list(
            db.execute(
                select(User).where(User.id.in_(actor_ids))
            ).scalars()
        )
        if actor_ids
        else []
    )
    actor_names = {
        user.id: (user.display_name.strip() or user.username)
        for user in users
    }

    part_ids = {
        movement.part_id
        for movement in movements
        if movement.part_id is not None
    }
    parts = (
        list(
            db.execute(
                select(Part).where(Part.id.in_(part_ids))
            ).scalars()
        )
        if part_ids
        else []
    )
    part_map = {part.id: part for part in parts}

    ordered: list[
        tuple[datetime, int, int, ReservationActivityEntryResponse]
    ] = []

    for audit in audits:
        occurred_at = _reservation_activity_timestamp(audit.created_at)
        ordered.append(
            (
                occurred_at,
                1,
                audit.id,
                ReservationActivityEntryResponse(
                    key=f"audit:{audit.id}",
                    kind="audit",
                    event_type=audit.event_type,
                    occurred_at=occurred_at,
                    summary=audit.summary,
                    actor_type=audit.actor_type,
                    actor_user_id=audit.actor_user_id,
                    actor_display_name=actor_names.get(
                        audit.actor_user_id
                    ),
                    before_json=audit.before_json,
                    after_json=audit.after_json,
                    metadata_json=audit.metadata_json,
                ),
            )
        )

    for movement in movements:
        occurred_at = _reservation_activity_timestamp(
            movement.created_at
        )
        part = (
            part_map.get(movement.part_id)
            if movement.part_id is not None
            else None
        )
        quantity = None
        if (
            movement.reserved_quantity_before is not None
            and movement.reserved_quantity_after is not None
        ):
            quantity = abs(
                int(movement.reserved_quantity_after)
                - int(movement.reserved_quantity_before)
            )
        if (
            not quantity
            and movement.quantity_delta is not None
        ):
            quantity = abs(int(movement.quantity_delta))

        ordered.append(
            (
                occurred_at,
                0,
                movement.id,
                ReservationActivityEntryResponse(
                    key=f"movement:{movement.id}",
                    kind="stock_movement",
                    event_type=(
                        f"stock.{movement.movement_type}"
                    ),
                    occurred_at=occurred_at,
                    summary=(
                        movement.reason
                        or (
                            f"{movement.movement_type.title()} "
                            "inventory movement"
                        )
                    ),
                    actor_type=(
                        "user"
                        if movement.actor_user_id is not None
                        else movement.source
                    ),
                    actor_user_id=movement.actor_user_id,
                    actor_display_name=actor_names.get(
                        movement.actor_user_id
                    ),
                    part_id=movement.part_id,
                    part_number=(
                        part.part_number if part is not None else None
                    ),
                    part_name=(
                        part.name if part is not None else None
                    ),
                    movement_type=movement.movement_type,
                    quantity=quantity,
                    quantity_delta=movement.quantity_delta,
                    quantity_before=movement.quantity_before,
                    quantity_after=movement.quantity_after,
                    reserved_quantity_before=(
                        movement.reserved_quantity_before
                    ),
                    reserved_quantity_after=(
                        movement.reserved_quantity_after
                    ),
                    available_quantity_before=(
                        movement.available_quantity_before
                    ),
                    available_quantity_after=(
                        movement.available_quantity_after
                    ),
                    reason=movement.reason,
                    note=movement.note,
                    source=movement.source,
                ),
            )
        )

    ordered.sort(
        key=lambda item: (item[0], item[1], item[2]),
        reverse=True,
    )
    total = len(ordered)
    selected = ordered[offset : offset + limit]

    return ReservationActivityCollectionResponse(
        reservation_id=reservation_id,
        total=total,
        limit=limit,
        offset=offset,
        activities=[item[3] for item in selected],
    )
