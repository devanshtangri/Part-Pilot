from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.constants import (
    MOVEMENT_TYPE_RESERVE,
    PROJECT_STATUSES,
    PROJECT_STATUS_DRAFT,
    PROJECT_STATUS_RESERVED,
    RESERVATION_STATUS_ACTIVE,
    SOURCE_MANUAL,
)
from app.db.settings import get_str_setting
from app.models import (
    AuditLog,
    Part,
    Project,
    ProjectItem,
    Reservation,
    ReservationItem,
    StockMovement,
)
from app.schemas.projects import (
    ProjectCollectionResponse,
    ProjectCreateRequest,
    ProjectItemCreateRequest,
    ProjectItemResponse,
    ProjectResponse,
    ProjectUpdateRequest,
)


class ProjectConflictError(ValueError):
    pass


class ProjectNotFoundError(LookupError):
    pass


class ProjectValidationError(ValueError):
    pass


@dataclass(frozen=True)
class _NormalisedProjectItem:
    part_id: int
    quantity: int
    note: str | None


def _normalise_items(
    items: list[ProjectItemCreateRequest],
) -> list[_NormalisedProjectItem]:
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
            raise ProjectValidationError(
                "Duplicate Project items for the same part must use "
                "the same note."
            )
        elif notes[item.part_id] is None:
            notes[item.part_id] = item.note

        quantities[item.part_id] += item.quantity

    return [
        _NormalisedProjectItem(
            part_id=part_id,
            quantity=quantities[part_id],
            note=notes[part_id],
        )
        for part_id in order
    ]


def _currency_snapshot(db: Session) -> str | None:
    value = get_str_setting(db, "currency.default", "").strip().upper()
    if len(value) == 3 and value.isalpha():
        return value
    return None


def _serialise_project_item(
    item: ProjectItem,
    part: Part | None,
) -> ProjectItemResponse:
    total_quantity = None if part is None else int(part.total_quantity)
    reserved_quantity = None if part is None else int(part.reserved_quantity)
    return ProjectItemResponse(
        id=item.id,
        project_id=item.project_id,
        part_id=item.part_id,
        part_number=None if part is None else part.part_number,
        part_name=None if part is None else part.name,
        part_is_deleted=None if part is None else bool(part.is_deleted),
        quantity=item.quantity,
        unit_price_snapshot=item.unit_price_snapshot,
        currency_snapshot=item.currency_snapshot,
        note=item.note,
        total_quantity=total_quantity,
        reserved_quantity=reserved_quantity,
        available_quantity=(
            None
            if total_quantity is None or reserved_quantity is None
            else total_quantity - reserved_quantity
        ),
    )


def _project_item_rows(
    db: Session,
    project_id: int,
) -> list[tuple[ProjectItem, Part | None]]:
    return list(
        db.execute(
            select(ProjectItem, Part)
            .outerjoin(Part, ProjectItem.part_id == Part.id)
            .where(ProjectItem.project_id == project_id)
            .order_by(ProjectItem.id.asc())
        ).all()
    )


def _serialise_project(
    db: Session,
    project: Project,
) -> ProjectResponse:
    items = [
        _serialise_project_item(item, part)
        for item, part in _project_item_rows(db, project.id)
    ]
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        notes=project.notes,
        created_by=project.created_by,
        estimated_total_value=project.estimated_total_value,
        currency_snapshot=project.currency_snapshot,
        created_at=project.created_at,
        updated_at=project.updated_at,
        item_count=len(items),
        total_units=sum(item.quantity for item in items),
        items=items,
    )


def get_project(
    db: Session,
    project_id: int,
) -> ProjectResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError("Project not found.")
    return _serialise_project(db, project)


def list_projects(
    db: Session,
    *,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ProjectCollectionResponse:
    if status_filter is not None and status_filter not in PROJECT_STATUSES:
        raise ProjectValidationError(
            f"Unsupported Project status: {status_filter}."
        )
    if limit < 1 or limit > 100:
        raise ProjectValidationError(
            "Project limit must be between 1 and 100."
        )
    if offset < 0:
        raise ProjectValidationError(
            "Project offset cannot be negative."
        )

    conditions = []
    if status_filter is not None:
        conditions.append(Project.status == status_filter)

    count_query = select(func.count()).select_from(Project)
    list_query = select(Project)
    if conditions:
        count_query = count_query.where(*conditions)
        list_query = list_query.where(*conditions)

    total = int(db.execute(count_query).scalar_one())
    projects = list(
        db.execute(
            list_query
            .order_by(Project.created_at.desc(), Project.id.desc())
            .limit(limit)
            .offset(offset)
        ).scalars()
    )
    return ProjectCollectionResponse(
        total=total,
        limit=limit,
        offset=offset,
        projects=[_serialise_project(db, project) for project in projects],
    )


def create_project(
    db: Session,
    payload: ProjectCreateRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> ProjectResponse:
    normalised_items = _normalise_items(payload.items)
    if not normalised_items:
        raise ProjectValidationError(
            "A Project must contain at least one part."
        )

    part_ids = [item.part_id for item in normalised_items]
    parts = list(
        db.execute(select(Part).where(Part.id.in_(part_ids))).scalars()
    )
    part_map = {part.id: part for part in parts}
    for item in normalised_items:
        part = part_map.get(item.part_id)
        if part is None or part.is_deleted:
            raise ProjectValidationError(
                f"Part {item.part_id} is not available for a Project."
            )

    currency = _currency_snapshot(db)
    all_prices_known = all(
        part_map[item.part_id].unit_price is not None
        for item in normalised_items
    )
    estimated_total = (
        sum(
            (
                Decimal(part_map[item.part_id].unit_price)
                * item.quantity
                for item in normalised_items
            ),
            Decimal("0"),
        )
        if all_prices_known
        else None
    )

    project = Project(
        name=payload.name,
        description=payload.description,
        status=PROJECT_STATUS_DRAFT,
        notes=payload.notes,
        created_by=SOURCE_MANUAL,
        estimated_total_value=estimated_total,
        currency_snapshot=currency,
    )
    project_items: list[ProjectItem] = []

    try:
        db.add(project)
        db.flush()

        for submitted in normalised_items:
            part = part_map[submitted.part_id]
            item = ProjectItem(
                project_id=project.id,
                part_id=part.id,
                quantity=submitted.quantity,
                unit_price_snapshot=part.unit_price,
                currency_snapshot=currency,
                note=submitted.note,
            )
            db.add(item)
            project_items.append(item)
        db.flush()

        audit_items = [
            {
                "project_item_id": item.id,
                "part_id": item.part_id,
                "quantity": item.quantity,
                "unit_price_snapshot": (
                    str(item.unit_price_snapshot)
                    if item.unit_price_snapshot is not None
                    else None
                ),
                "currency_snapshot": item.currency_snapshot,
                "note": item.note,
            }
            for item in project_items
        ]
        db.add(
            AuditLog(
                event_type="project.created",
                entity_type="project",
                entity_id=project.id,
                actor_type=(
                    "user" if actor_user_id is not None else "system"
                ),
                actor_user_id=actor_user_id,
                summary=(
                    f"Created Project {project.name} with "
                    f"{len(project_items)} parts"
                ),
                before_json=None,
                after_json={
                    "id": project.id,
                    "name": project.name,
                    "status": project.status,
                    "item_count": len(project_items),
                    "total_units": sum(
                        item.quantity for item in project_items
                    ),
                    "estimated_total_value": (
                        str(project.estimated_total_value)
                        if project.estimated_total_value is not None
                        else None
                    ),
                    "currency_snapshot": project.currency_snapshot,
                    "items": audit_items,
                },
                metadata_json={"source": SOURCE_MANUAL},
            )
        )
        db.flush()

        if commit:
            db.commit()
            db.refresh(project)
            for item in project_items:
                db.refresh(item)
    except IntegrityError as exc:
        db.rollback()
        raise ProjectConflictError(
            "Project conflicted with current part data."
        ) from exc
    except Exception:
        db.rollback()
        raise

    return _serialise_project(db, project)

# PARTPILOT:PROJECT_DRAFT_UPDATE_SERVICE:V379
def _project_item_audit_snapshot(item: ProjectItem) -> dict[str, object]:
    return {
        "project_item_id": item.id,
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


def _project_audit_snapshot(
    project: Project,
    items: list[ProjectItem],
) -> dict[str, object]:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "notes": project.notes,
        "item_count": len(items),
        "total_units": sum(int(item.quantity) for item in items),
        "estimated_total_value": (
            str(project.estimated_total_value)
            if project.estimated_total_value is not None
            else None
        ),
        "currency_snapshot": project.currency_snapshot,
        "items": [_project_item_audit_snapshot(item) for item in items],
    }



# PARTPILOT:PROJECT_RESERVED_UPDATE_SERVICE:V400
def _update_reserved_project(
    db: Session,
    project: Project,
    payload: ProjectUpdateRequest,
    *,
    actor_user_id: int | None,
    commit: bool,
) -> ProjectResponse:
    from app.schemas.reservations import ReservationUpdateRequest
    from app.services.reservations import (
        ReservationConflictError,
        ReservationNotFoundError,
        ReservationValidationError,
        update_reservation,
    )

    submitted_items = _normalise_items(payload.items)
    if not submitted_items:
        raise ProjectValidationError(
            "A Project must contain at least one part."
        )

    existing_items = list(
        db.execute(
            select(ProjectItem)
            .where(ProjectItem.project_id == project.id)
            .order_by(ProjectItem.id.asc())
            .with_for_update()
        ).scalars()
    )
    if not existing_items:
        raise ProjectConflictError(
            "Reserved Project has no stored items to edit."
        )
    if any(item.part_id is None for item in existing_items):
        raise ProjectConflictError(
            "Reserved Project contains an item whose part no longer exists."
        )

    existing_by_part: dict[int, ProjectItem] = {}
    for item in existing_items:
        assert item.part_id is not None
        if item.part_id in existing_by_part:
            raise ProjectConflictError(
                "Reserved Project contains duplicate stored items for the "
                "same part."
            )
        existing_by_part[item.part_id] = item

    linked_reservations = list(
        db.execute(
            select(Reservation)
            .where(Reservation.project_id == project.id)
            .order_by(Reservation.id.asc())
            .with_for_update()
        ).scalars()
    )
    if len(linked_reservations) != 1:
        raise ProjectConflictError(
            "Reserved Project must have exactly one linked Reservation "
            "before it can be edited."
        )
    reservation = linked_reservations[0]
    if reservation.status != RESERVATION_STATUS_ACTIVE:
        raise ProjectConflictError(
            "The linked Reservation must be active before the Reserved "
            f"Project can be edited. Current status: {reservation.status}."
        )

    reservation_items = list(
        db.execute(
            select(ReservationItem)
            .where(ReservationItem.reservation_id == reservation.id)
            .order_by(ReservationItem.id.asc())
            .with_for_update()
        ).scalars()
    )
    if any(item.part_id is None for item in reservation_items):
        raise ProjectConflictError(
            "Linked Reservation contains an item whose part no longer exists."
        )
    reservation_by_part = {
        int(item.part_id): item
        for item in reservation_items
        if item.part_id is not None
    }
    if (
        len(reservation_by_part) != len(reservation_items)
        or set(reservation_by_part) != set(existing_by_part)
        or any(
            int(reservation_by_part[part_id].quantity)
            != int(existing_by_part[part_id].quantity)
            or reservation_by_part[part_id].note
            != existing_by_part[part_id].note
            for part_id in existing_by_part
        )
    ):
        raise ProjectConflictError(
            "Reserved Project and linked Reservation item plans are not "
            "synchronised."
        )

    submitted_by_part = {
        item.part_id: item
        for item in submitted_items
    }
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
    reservation_aligned = (
        reservation.label == payload.name
        and reservation.notes == payload.notes
        and unchanged_items
    )
    if (
        project.name == payload.name
        and project.description == payload.description
        and project.notes == payload.notes
        and unchanged_items
        and reservation_aligned
    ):
        return _serialise_project(db, project)

    before_snapshot = _project_audit_snapshot(project, existing_items)
    existing_movement_ids = set(
        db.execute(
            select(StockMovement.id).where(
                StockMovement.reservation_id == reservation.id
            )
        ).scalars()
    )
    expiry_at = reservation.expiry_at
    if (
        expiry_at is not None
        and (expiry_at.tzinfo is None or expiry_at.utcoffset() is None)
    ):
        expiry_at = expiry_at.replace(tzinfo=timezone.utc)

    reservation_payload = ReservationUpdateRequest(
        label=payload.name,
        notes=payload.notes,
        expiry_at=expiry_at,
        items=[
            {
                "part_id": item.part_id,
                "quantity": item.quantity,
                "note": item.note,
            }
            for item in submitted_items
        ],
    )

    try:
        try:
            updated_reservation = update_reservation(
                db,
                reservation.id,
                reservation_payload,
                actor_user_id=actor_user_id,
                commit=False,
                sync_linked_project=False,
            )
        except ReservationNotFoundError as exc:
            raise ProjectConflictError(
                "Linked Reservation no longer exists."
            ) from exc
        except ReservationConflictError as exc:
            raise ProjectConflictError(
                f"Linked Reservation could not be edited: {exc}"
            ) from exc
        except ReservationValidationError as exc:
            raise ProjectValidationError(str(exc)) from exc

        if updated_reservation.status != RESERVATION_STATUS_ACTIVE:
            raise ProjectConflictError(
                "Linked Reservation did not remain active after the edit."
            )

        updated_reservation_by_part = {
            int(item.part_id): item
            for item in updated_reservation.items
            if item.part_id is not None
        }
        if (
            len(updated_reservation_by_part)
            != len(updated_reservation.items)
            or set(updated_reservation_by_part) != set(submitted_by_part)
        ):
            raise ProjectConflictError(
                "Linked Reservation response did not match the submitted "
                "Project item plan."
            )

        project.name = payload.name
        project.description = payload.description
        project.notes = payload.notes
        project.estimated_total_value = (
            updated_reservation.estimated_reserved_value
        )
        project.currency_snapshot = updated_reservation.currency_snapshot
        project.updated_at = datetime.now(timezone.utc)

        for existing in existing_items:
            assert existing.part_id is not None
            submitted = submitted_by_part.get(existing.part_id)
            if submitted is None:
                db.delete(existing)
                continue
            response_item = updated_reservation_by_part[existing.part_id]
            existing.quantity = submitted.quantity
            existing.note = submitted.note
            existing.unit_price_snapshot = response_item.unit_price_snapshot
            existing.currency_snapshot = response_item.currency_snapshot

        for submitted in submitted_items:
            if submitted.part_id in existing_by_part:
                continue
            response_item = updated_reservation_by_part[submitted.part_id]
            db.add(
                ProjectItem(
                    project_id=project.id,
                    part_id=submitted.part_id,
                    quantity=submitted.quantity,
                    unit_price_snapshot=response_item.unit_price_snapshot,
                    currency_snapshot=response_item.currency_snapshot,
                    note=submitted.note,
                )
            )

        db.flush()
        updated_items = list(
            db.execute(
                select(ProjectItem)
                .where(ProjectItem.project_id == project.id)
                .order_by(ProjectItem.id.asc())
            ).scalars()
        )
        after_snapshot = _project_audit_snapshot(project, updated_items)

        all_movements = list(
            db.execute(
                select(StockMovement)
                .where(StockMovement.reservation_id == reservation.id)
                .order_by(StockMovement.id.asc())
            ).scalars()
        )
        new_movements = [
            movement
            for movement in all_movements
            if movement.id not in existing_movement_ids
        ]

        db.add(
            AuditLog(
                event_type="project.updated",
                entity_type="project",
                entity_id=project.id,
                actor_type=(
                    "user" if actor_user_id is not None else "system"
                ),
                actor_user_id=actor_user_id,
                summary=(
                    f"Updated Reserved Project {project.name} with "
                    f"{len(updated_items)} parts"
                ),
                before_json=before_snapshot,
                after_json=after_snapshot,
                metadata_json={
                    "source": SOURCE_MANUAL,
                    "origin": "reserved_project.edit",
                    "reservation_id": reservation.id,
                    "movement_ids": [
                        movement.id for movement in new_movements
                    ],
                    "movement_types": sorted(
                        {
                            movement.movement_type
                            for movement in new_movements
                        }
                    ),
                },
            )
        )
        db.flush()

        if commit:
            db.commit()
            db.refresh(project)
            db.refresh(reservation)
    except IntegrityError as exc:
        db.rollback()
        raise ProjectConflictError(
            "Reserved Project update conflicted with current inventory "
            "data."
        ) from exc
    except Exception:
        db.rollback()
        raise

    return _serialise_project(db, project)


def update_project(
    db: Session,
    project_id: int,
    payload: ProjectUpdateRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> ProjectResponse:
    project = db.execute(
        select(Project)
        .where(Project.id == project_id)
        .with_for_update()
    ).scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError("Project not found.")
    if project.status == PROJECT_STATUS_RESERVED:
        return _update_reserved_project(
            db,
            project,
            payload,
            actor_user_id=actor_user_id,
            commit=commit,
        )
    if project.status != PROJECT_STATUS_DRAFT:
        raise ProjectConflictError(
            "Only Draft or Reserved Projects can be edited. "
            f"Current status: {project.status}."
        )

    submitted_items = _normalise_items(payload.items)
    if not submitted_items:
        raise ProjectValidationError(
            "A Project must contain at least one part."
        )

    existing_items = list(
        db.execute(
            select(ProjectItem)
            .where(ProjectItem.project_id == project.id)
            .order_by(ProjectItem.id.asc())
            .with_for_update()
        ).scalars()
    )
    existing_by_part: dict[int, ProjectItem] = {}
    for item in existing_items:
        if item.part_id is None:
            continue
        if item.part_id in existing_by_part:
            raise ProjectConflictError(
                "Project contains duplicate stored items for the same part."
            )
        existing_by_part[item.part_id] = item

    submitted_by_part = {item.part_id: item for item in submitted_items}
    part_ids = sorted(submitted_by_part)
    parts = list(
        db.execute(
            select(Part)
            .where(Part.id.in_(part_ids))
            .with_for_update()
        ).scalars()
    )
    part_map = {part.id: part for part in parts}
    for part_id in part_ids:
        part = part_map.get(part_id)
        if part is None or part.is_deleted:
            raise ProjectValidationError(
                f"Part {part_id} is not available for a Project."
            )

    unchanged_items = (
        len(existing_items) == len(existing_by_part)
        and set(existing_by_part) == set(submitted_by_part)
        and all(
            int(existing_by_part[part_id].quantity)
            == int(submitted_by_part[part_id].quantity)
            and existing_by_part[part_id].note
            == submitted_by_part[part_id].note
            for part_id in existing_by_part
        )
    )
    if (
        project.name == payload.name
        and project.description == payload.description
        and project.notes == payload.notes
        and unchanged_items
    ):
        return _serialise_project(db, project)

    before_snapshot = _project_audit_snapshot(project, existing_items)
    currency = _currency_snapshot(db)
    all_prices_known = all(
        part_map[item.part_id].unit_price is not None
        for item in submitted_items
    )
    estimated_total = (
        sum(
            (
                Decimal(part_map[item.part_id].unit_price) * item.quantity
                for item in submitted_items
            ),
            Decimal("0"),
        )
        if all_prices_known
        else None
    )

    try:
        project.name = payload.name
        project.description = payload.description
        project.notes = payload.notes
        project.estimated_total_value = estimated_total
        project.currency_snapshot = currency

        retained_items: list[ProjectItem] = []
        for existing in existing_items:
            submitted = (
                None
                if existing.part_id is None
                else submitted_by_part.get(existing.part_id)
            )
            if submitted is None:
                db.delete(existing)
                continue
            part = part_map[submitted.part_id]
            existing.quantity = submitted.quantity
            existing.note = submitted.note
            existing.unit_price_snapshot = part.unit_price
            existing.currency_snapshot = currency
            retained_items.append(existing)

        for submitted in submitted_items:
            if submitted.part_id in existing_by_part:
                continue
            part = part_map[submitted.part_id]
            item = ProjectItem(
                project_id=project.id,
                part_id=part.id,
                quantity=submitted.quantity,
                unit_price_snapshot=part.unit_price,
                currency_snapshot=currency,
                note=submitted.note,
            )
            db.add(item)
            retained_items.append(item)

        db.flush()
        updated_items = list(
            db.execute(
                select(ProjectItem)
                .where(ProjectItem.project_id == project.id)
                .order_by(ProjectItem.id.asc())
            ).scalars()
        )
        after_snapshot = _project_audit_snapshot(project, updated_items)
        db.add(
            AuditLog(
                event_type="project.updated",
                entity_type="project",
                entity_id=project.id,
                actor_type=(
                    "user" if actor_user_id is not None else "system"
                ),
                actor_user_id=actor_user_id,
                summary=(
                    f"Updated Draft Project {project.name} with "
                    f"{len(updated_items)} parts"
                ),
                before_json=before_snapshot,
                after_json=after_snapshot,
                metadata_json={"source": SOURCE_MANUAL},
            )
        )
        db.flush()

        if commit:
            db.commit()
            db.refresh(project)
    except IntegrityError as exc:
        db.rollback()
        raise ProjectConflictError(
            "Project update conflicted with current part data."
        ) from exc
    except Exception:
        db.rollback()
        raise

    return _serialise_project(db, project)
# PARTPILOT:PROJECT_RESERVATION_SERVICE:V383
def reserve_project(
    db: Session,
    project_id: int,
    *,
    actor_user_id: int | None = None,
    actor_type: str | None = None,
    source: str = SOURCE_MANUAL,
    commit: bool = True,
) -> ProjectResponse:
    project = db.execute(
        select(Project).where(Project.id == project_id).with_for_update()
    ).scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError("Project not found.")
    if project.status != PROJECT_STATUS_DRAFT:
        raise ProjectConflictError(
            "Only Draft Projects can be reserved. "
            f"Current status: {project.status}."
        )

    rows = list(
        db.execute(
            select(ProjectItem, Part)
            .outerjoin(Part, ProjectItem.part_id == Part.id)
            .where(ProjectItem.project_id == project.id)
            .order_by(ProjectItem.id.asc())
            .with_for_update()
        ).all()
    )
    if not rows:
        raise ProjectValidationError(
            "A Project must contain at least one part before reservation."
        )

    seen_part_ids: set[int] = set()
    for item, part in rows:
        if item.part_id is None or part is None or part.is_deleted:
            raise ProjectValidationError(
                f"Project item {item.id} is not linked to an available part."
            )
        if part.id in seen_part_ids:
            raise ProjectValidationError(
                f"Project contains duplicate rows for part {part.id}."
            )
        seen_part_ids.add(part.id)

    reservation = Reservation(
        project_id=project.id,
        label=project.name,
        status=RESERVATION_STATUS_ACTIVE,
        notes=project.notes,
        created_by=source,
        expiry_at=None,
        estimated_reserved_value=project.estimated_total_value,
        currency_snapshot=project.currency_snapshot,
    )
    item_parts: list[tuple[ReservationItem, Part]] = []
    movements: list[StockMovement] = []

    try:
        db.add(reservation)
        db.flush()

        for project_item, part in rows:
            quantity = int(project_item.quantity)
            total_quantity = int(part.total_quantity)
            reserved_before = int(part.reserved_quantity)
            available_before = total_quantity - reserved_before
            if quantity > available_before:
                raise ProjectConflictError(
                    f"Part {part.id} has only {available_before} available units."
                )

            reserved_after = reserved_before + quantity
            available_after = total_quantity - reserved_after
            changed_at = datetime.now(timezone.utc)
            result = db.execute(
                update(Part)
                .where(
                    Part.id == part.id,
                    Part.is_deleted.is_(False),
                    Part.reserved_quantity == reserved_before,
                    Part.total_quantity - Part.reserved_quantity >= quantity,
                )
                .values(
                    reserved_quantity=reserved_after,
                    updated_at=changed_at,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                raise ProjectConflictError(
                    f"Part {part.id} stock changed while the Project "
                    "was being reserved."
                )

            part.reserved_quantity = reserved_after
            part.updated_at = changed_at
            reservation_item = ReservationItem(
                reservation_id=reservation.id,
                part_id=part.id,
                quantity=quantity,
                unit_price_snapshot=project_item.unit_price_snapshot,
                currency_snapshot=project_item.currency_snapshot,
                note=project_item.note,
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
                unit_price_snapshot=project_item.unit_price_snapshot,
                currency_snapshot=project_item.currency_snapshot,
                reason=(f"Reserved for Project {project.name}")[:180],
                note=project_item.note,
                source=source,
                actor_user_id=actor_user_id,
            )
            db.add(reservation_item)
            db.add(movement)
            item_parts.append((reservation_item, part))
            movements.append(movement)

        project.status = PROJECT_STATUS_RESERVED
        project.updated_at = datetime.now(timezone.utc)
        db.flush()

        audit_items = [
            {
                "reservation_item_id": reservation_item.id,
                "project_item_id": project_item.id,
                "part_id": part.id,
                "quantity": reservation_item.quantity,
                "stock_movement_id": movement.id,
                "reserved_quantity_after": int(part.reserved_quantity),
                "available_quantity_after": (
                    int(part.total_quantity) - int(part.reserved_quantity)
                ),
            }
            for (project_item, _),
            (reservation_item, part),
            movement in zip(rows, item_parts, movements, strict=True)
        ]

        resolved_actor_type = actor_type or (
            "user" if actor_user_id is not None else "system"
        )
        db.add(
            AuditLog(
                event_type="reservation.created",
                entity_type="reservation",
                entity_id=reservation.id,
                actor_type=resolved_actor_type,
                actor_user_id=actor_user_id,
                summary=(
                    f"Created Project reservation {reservation.label} "
                    f"with {len(item_parts)} parts"
                ),
                before_json=None,
                after_json={
                    "id": reservation.id,
                    "project_id": project.id,
                    "label": reservation.label,
                    "status": reservation.status,
                    "item_count": len(item_parts),
                    "total_reserved_units": sum(
                        item.quantity for item, _part in item_parts
                    ),
                    "estimated_reserved_value": (
                        str(reservation.estimated_reserved_value)
                        if reservation.estimated_reserved_value is not None
                        else None
                    ),
                    "currency_snapshot": reservation.currency_snapshot,
                    "items": audit_items,
                },
                metadata_json={
                    "source": source,
                    "movement_type": MOVEMENT_TYPE_RESERVE,
                    "project_id": project.id,
                },
            )
        )
        db.add(
            AuditLog(
                event_type="project.reserved",
                entity_type="project",
                entity_id=project.id,
                actor_type=resolved_actor_type,
                actor_user_id=actor_user_id,
                summary=(
                    f"Reserved Project {project.name} with "
                    f"{len(item_parts)} parts"
                ),
                before_json={
                    "status": PROJECT_STATUS_DRAFT,
                    "reservation_id": None,
                },
                after_json={
                    "status": PROJECT_STATUS_RESERVED,
                    "reservation_id": reservation.id,
                    "item_count": len(item_parts),
                    "total_reserved_units": sum(
                        item.quantity for item, _part in item_parts
                    ),
                    "stock_movement_ids": [
                        movement.id for movement in movements
                    ],
                },
                metadata_json={
                    "source": source,
                    "movement_type": MOVEMENT_TYPE_RESERVE,
                    "reservation_id": reservation.id,
                },
            )
        )
        db.flush()

        if commit:
            db.commit()
            db.refresh(project)
            db.refresh(reservation)
            for reservation_item, part in item_parts:
                db.refresh(reservation_item)
                db.refresh(part)
            for movement in movements:
                db.refresh(movement)
    except IntegrityError as exc:
        db.rollback()
        raise ProjectConflictError(
            "Project reservation conflicted with current inventory data."
        ) from exc
    except Exception:
        db.rollback()
        raise

    return _serialise_project(db, project)

# PARTPILOT:PROJECT_TERMINAL_MOVEMENT_DELTA:V402
def _reservation_movement_ids(
    db: Session,
    reservation_id: int,
) -> set[int]:
    return set(
        db.execute(
            select(StockMovement.id).where(
                StockMovement.reservation_id == reservation_id
            )
        ).scalars()
    )


def _new_reservation_movements(
    db: Session,
    reservation_id: int,
    movement_type: str,
    existing_movement_ids: set[int],
) -> list[StockMovement]:
    conditions = [
        StockMovement.reservation_id == reservation_id,
        StockMovement.movement_type == movement_type,
    ]
    if existing_movement_ids:
        conditions.append(
            StockMovement.id.not_in(existing_movement_ids)
        )
    return list(
        db.execute(
            select(StockMovement)
            .where(*conditions)
            .order_by(StockMovement.id.asc())
        ).scalars()
    )


# PARTPILOT:PROJECT_CONSUMPTION_SERVICE:V394
def consume_project(
    db: Session,
    project_id: int,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> ProjectResponse:
    from app.db.constants import (
        MOVEMENT_TYPE_CONSUME,
        PROJECT_STATUS_CONSUMED,
        RESERVATION_STATUS_CONSUMED,
    )
    from app.services.reservations import (
        ReservationConflictError,
        ReservationNotFoundError,
        consume_reservation,
    )

    project = db.execute(
        select(Project)
        .where(Project.id == project_id)
        .with_for_update()
    ).scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError("Project not found.")
    if project.status != PROJECT_STATUS_RESERVED:
        raise ProjectConflictError(
            "Only Reserved Projects can be consumed. "
            f"Current status: {project.status}."
        )

    linked_reservations = list(
        db.execute(
            select(Reservation)
            .where(Reservation.project_id == project.id)
            .order_by(Reservation.id.asc())
            .with_for_update()
        ).scalars()
    )
    if not linked_reservations:
        raise ProjectConflictError(
            "Reserved Project has no linked Reservation to consume."
        )
    if len(linked_reservations) != 1:
        raise ProjectConflictError(
            "Reserved Project has multiple linked Reservations and cannot "
            "be consumed safely."
        )

    reservation = linked_reservations[0]
    if reservation.status != RESERVATION_STATUS_ACTIVE:
        raise ProjectConflictError(
            "The linked Reservation must be active before Project "
            f"consumption. Current status: {reservation.status}."
        )

    reservation_items = list(
        db.execute(
            select(ReservationItem)
            .where(ReservationItem.reservation_id == reservation.id)
            .order_by(ReservationItem.id.asc())
        ).scalars()
    )
    if not reservation_items:
        raise ProjectConflictError(
            "The linked Reservation has no items to consume."
        )

    existing_movement_ids = _reservation_movement_ids(
        db,
        reservation.id,
    )

    try:
        try:
            consumed_reservation = consume_reservation(
                db,
                reservation.id,
                actor_user_id=actor_user_id,
                commit=False,
                sync_linked_project=False,
            )
        except (ReservationConflictError, ReservationNotFoundError) as exc:
            raise ProjectConflictError(
                f"Linked Reservation could not be consumed: {exc}"
            ) from exc

        if consumed_reservation.status != RESERVATION_STATUS_CONSUMED:
            raise ProjectConflictError(
                "Linked Reservation did not transition to consumed."
            )

        changed_at = datetime.now(timezone.utc)
        project_status_result = db.execute(
            update(Project)
            .where(
                Project.id == project.id,
                Project.status == PROJECT_STATUS_RESERVED,
            )
            .values(
                status=PROJECT_STATUS_CONSUMED,
                updated_at=changed_at,
            )
            .execution_options(synchronize_session=False)
        )
        if project_status_result.rowcount != 1:
            raise ProjectConflictError(
                "Project status changed while consumption was in progress."
            )
        db.expire(project, ["status", "updated_at"])

        db.flush()
        consume_movements = _new_reservation_movements(
            db,
            reservation.id,
            MOVEMENT_TYPE_CONSUME,
            existing_movement_ids,
        )
        if len(consume_movements) != len(reservation_items):
            raise ProjectConflictError(
                "Project consumption did not create one consume movement "
                "for every linked Reservation item."
            )

        consumed_units = sum(
            int(item.quantity) for item in reservation_items
        )
        db.add(
            AuditLog(
                event_type="project.consumed",
                entity_type="project",
                entity_id=project.id,
                actor_type=(
                    "user" if actor_user_id is not None else "system"
                ),
                actor_user_id=actor_user_id,
                summary=(
                    f"Consumed Project {project.name} with "
                    f"{len(reservation_items)} parts"
                ),
                before_json={
                    "status": PROJECT_STATUS_RESERVED,
                    "reservation_id": reservation.id,
                    "reservation_status": RESERVATION_STATUS_ACTIVE,
                    "total_units": consumed_units,
                },
                after_json={
                    "status": PROJECT_STATUS_CONSUMED,
                    "reservation_id": reservation.id,
                    "reservation_status": RESERVATION_STATUS_CONSUMED,
                    "consumed_units": consumed_units,
                    "stock_movement_ids": [
                        movement.id for movement in consume_movements
                    ],
                },
                metadata_json={
                    "source": SOURCE_MANUAL,
                    "movement_type": MOVEMENT_TYPE_CONSUME,
                    "reservation_id": reservation.id,
                },
            )
        )
        db.flush()

        if commit:
            db.commit()
            db.refresh(project)
            db.refresh(reservation)
    except IntegrityError as exc:
        db.rollback()
        raise ProjectConflictError(
            "Project consumption conflicted with current inventory data."
        ) from exc
    except Exception:
        db.rollback()
        raise

    return _serialise_project(db, project)

# PARTPILOT:PROJECT_CANCELLATION_SERVICE:V397
def cancel_project(
    db: Session,
    project_id: int,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> ProjectResponse:
    from app.db.constants import (
        MOVEMENT_TYPE_RELEASE,
        PROJECT_STATUS_CANCELLED,
        RESERVATION_STATUS_CANCELLED,
    )
    from app.services.reservations import (
        ReservationConflictError,
        ReservationNotFoundError,
        cancel_reservation,
    )

    project = db.execute(
        select(Project)
        .where(Project.id == project_id)
        .with_for_update()
    ).scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError("Project not found.")
    if project.status != PROJECT_STATUS_RESERVED:
        raise ProjectConflictError(
            "Only Reserved Projects can be cancelled. "
            f"Current status: {project.status}."
        )

    linked_reservations = list(
        db.execute(
            select(Reservation)
            .where(Reservation.project_id == project.id)
            .order_by(Reservation.id.asc())
            .with_for_update()
        ).scalars()
    )
    if not linked_reservations:
        raise ProjectConflictError(
            "Reserved Project has no linked Reservation to cancel."
        )
    if len(linked_reservations) != 1:
        raise ProjectConflictError(
            "Reserved Project has multiple linked Reservations and cannot "
            "be cancelled safely."
        )

    reservation = linked_reservations[0]
    if reservation.status != RESERVATION_STATUS_ACTIVE:
        raise ProjectConflictError(
            "The linked Reservation must be active before Project "
            f"cancellation. Current status: {reservation.status}."
        )

    reservation_items = list(
        db.execute(
            select(ReservationItem)
            .where(ReservationItem.reservation_id == reservation.id)
            .order_by(ReservationItem.id.asc())
        ).scalars()
    )
    if not reservation_items:
        raise ProjectConflictError(
            "The linked Reservation has no items to release."
        )

    existing_movement_ids = _reservation_movement_ids(
        db,
        reservation.id,
    )

    try:
        try:
            cancelled_reservation = cancel_reservation(
                db,
                reservation.id,
                actor_user_id=actor_user_id,
                commit=False,
                sync_linked_project=False,
            )
        except (ReservationConflictError, ReservationNotFoundError) as exc:
            raise ProjectConflictError(
                f"Linked Reservation could not be cancelled: {exc}"
            ) from exc

        if cancelled_reservation.status != RESERVATION_STATUS_CANCELLED:
            raise ProjectConflictError(
                "Linked Reservation did not transition to cancelled."
            )

        changed_at = datetime.now(timezone.utc)
        project_status_result = db.execute(
            update(Project)
            .where(
                Project.id == project.id,
                Project.status == PROJECT_STATUS_RESERVED,
            )
            .values(
                status=PROJECT_STATUS_CANCELLED,
                updated_at=changed_at,
            )
            .execution_options(synchronize_session=False)
        )
        if project_status_result.rowcount != 1:
            raise ProjectConflictError(
                "Project status changed while cancellation was in progress."
            )
        db.expire(project, ["status", "updated_at"])

        db.flush()
        release_movements = _new_reservation_movements(
            db,
            reservation.id,
            MOVEMENT_TYPE_RELEASE,
            existing_movement_ids,
        )
        if len(release_movements) != len(reservation_items):
            raise ProjectConflictError(
                "Project cancellation did not create one release movement "
                "for every linked Reservation item."
            )

        released_units = sum(
            int(item.quantity) for item in reservation_items
        )
        db.add(
            AuditLog(
                event_type="project.cancelled",
                entity_type="project",
                entity_id=project.id,
                actor_type=(
                    "user" if actor_user_id is not None else "system"
                ),
                actor_user_id=actor_user_id,
                summary=(
                    f"Cancelled Project {project.name} and released "
                    f"{released_units} reserved units"
                ),
                before_json={
                    "status": PROJECT_STATUS_RESERVED,
                    "reservation_id": reservation.id,
                    "reservation_status": RESERVATION_STATUS_ACTIVE,
                    "total_units": released_units,
                },
                after_json={
                    "status": PROJECT_STATUS_CANCELLED,
                    "reservation_id": reservation.id,
                    "reservation_status": RESERVATION_STATUS_CANCELLED,
                    "released_units": released_units,
                    "stock_movement_ids": [
                        movement.id for movement in release_movements
                    ],
                },
                metadata_json={
                    "source": SOURCE_MANUAL,
                    "movement_type": MOVEMENT_TYPE_RELEASE,
                    "reservation_id": reservation.id,
                },
            )
        )
        db.flush()

        if commit:
            db.commit()
            db.refresh(project)
            db.refresh(reservation)
    except IntegrityError as exc:
        db.rollback()
        raise ProjectConflictError(
            "Project cancellation conflicted with current inventory data."
        ) from exc
    except Exception:
        db.rollback()
        raise

    return _serialise_project(db, project)
