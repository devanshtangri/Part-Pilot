from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.constants import (
    MOVEMENT_TYPE_RESERVE,
    RESERVATION_STATUSES,
    RESERVATION_STATUS_ACTIVE,
    SOURCE_MANUAL,
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
