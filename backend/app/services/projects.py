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
    if project.status != PROJECT_STATUS_DRAFT:
        raise ProjectConflictError(
            "Only Draft Projects can be edited. "
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
        created_by=SOURCE_MANUAL,
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
                source=SOURCE_MANUAL,
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

        actor_type = "user" if actor_user_id is not None else "system"
        db.add(
            AuditLog(
                event_type="reservation.created",
                entity_type="reservation",
                entity_id=reservation.id,
                actor_type=actor_type,
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
                    "source": SOURCE_MANUAL,
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
                actor_type=actor_type,
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
                    "source": SOURCE_MANUAL,
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
