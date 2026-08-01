from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import Text, cast, false, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    AppSetting,
    AuditLog,
    Location,
    Manufacturer,
    PackageOption,
    Part,
    PartType,
    Project,
    Reservation,
    StockMovement,
    User,
)
from app.schemas.history import (
    HistoryActorOptionResponse,
    HistoryCollectionResponse,
    HistoryEntryResponse,
    HistoryFacetValueResponse,
    HistoryFilterOptionsResponse,
    HistoryKind,
)


# PARTPILOT:SYSTEM_HISTORY_SERVICE:V406
class HistoryValidationError(ValueError):
    pass


def _history_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _query_timestamp(value: datetime) -> datetime:
    return _history_timestamp(value).replace(tzinfo=None)


def _clean_filter(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _literal_like_pattern(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    return f"%{escaped}%"


def _display_part(part: Part | None, part_id: int | None) -> str | None:
    if part is not None:
        return (
            part.part_number
            or part.name
            or f"Part #{part.id}"
        )
    return f"Part #{part_id}" if part_id is not None else None


def _json_mapping(value: dict | list | None) -> dict:
    return value if isinstance(value, dict) else {}


def _json_int(*values: object) -> int | None:
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.isdigit():
            parsed = int(value)
            if parsed > 0:
                return parsed
    return None


def _related_id(audit: AuditLog, key: str) -> int | None:
    metadata = _json_mapping(audit.metadata_json)
    after = _json_mapping(audit.after_json)
    before = _json_mapping(audit.before_json)
    return _json_int(
        metadata.get(key),
        after.get(key),
        before.get(key),
    )


def _facet_rows(rows: Iterable[tuple[object, object]]) -> list[
    HistoryFacetValueResponse
]:
    return [
        HistoryFacetValueResponse(
            value=str(value),
            count=int(count),
        )
        for value, count in rows
        if value is not None and str(value).strip()
    ]


def _audit_query(
    *,
    entity_type: str | None,
    event_type: str | None,
    actor_type: str | None,
    actor_user_id: int | None,
    from_time: datetime | None,
    to_time: datetime | None,
    query: str | None,
):
    statement = (
        select(AuditLog)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
    )
    conditions = []
    if entity_type is not None:
        conditions.append(AuditLog.entity_type == entity_type)
    if event_type is not None:
        conditions.append(AuditLog.event_type == event_type)
    if actor_type is not None:
        conditions.append(AuditLog.actor_type == actor_type)
    if actor_user_id is not None:
        conditions.append(
            AuditLog.actor_user_id == actor_user_id
        )
    if from_time is not None:
        conditions.append(
            AuditLog.created_at >= _query_timestamp(from_time)
        )
    if to_time is not None:
        conditions.append(
            AuditLog.created_at <= _query_timestamp(to_time)
        )
    if query is not None:
        pattern = _literal_like_pattern(query)
        conditions.append(
            or_(
                AuditLog.event_type.ilike(pattern, escape="\\"),
                AuditLog.entity_type.ilike(pattern, escape="\\"),
                AuditLog.summary.ilike(pattern, escape="\\"),
                cast(AuditLog.before_json, Text).ilike(
                    pattern,
                    escape="\\",
                ),
                cast(AuditLog.after_json, Text).ilike(
                    pattern,
                    escape="\\",
                ),
                cast(AuditLog.metadata_json, Text).ilike(
                    pattern,
                    escape="\\",
                ),
                User.username.ilike(pattern, escape="\\"),
                User.display_name.ilike(pattern, escape="\\"),
            )
        )
    if conditions:
        statement = statement.where(*conditions)
    return statement


def _movement_query(
    *,
    entity_type: str | None,
    event_type: str | None,
    actor_type: str | None,
    actor_user_id: int | None,
    movement_type: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
    query: str | None,
):
    statement = (
        select(StockMovement)
        .outerjoin(Part, Part.id == StockMovement.part_id)
        .outerjoin(
            Reservation,
            Reservation.id == StockMovement.reservation_id,
        )
        .outerjoin(Project, Project.id == Reservation.project_id)
        .outerjoin(User, User.id == StockMovement.actor_user_id)
    )
    conditions = []
    if entity_type is not None:
        conditions.append(
            StockMovement.part_id.is_not(None)
            if entity_type == "part"
            else false()
        )
    if event_type is not None:
        if event_type.startswith("stock.") and len(event_type) > 6:
            conditions.append(
                StockMovement.movement_type == event_type[6:]
            )
        else:
            conditions.append(false())
    if actor_type is not None:
        if actor_type == "user":
            conditions.append(
                StockMovement.actor_user_id.is_not(None)
            )
        else:
            conditions.extend(
                (
                    StockMovement.actor_user_id.is_(None),
                    StockMovement.source == actor_type,
                )
            )
    if actor_user_id is not None:
        conditions.append(
            StockMovement.actor_user_id == actor_user_id
        )
    if movement_type is not None:
        conditions.append(
            StockMovement.movement_type == movement_type
        )
    if from_time is not None:
        conditions.append(
            StockMovement.created_at >= _query_timestamp(from_time)
        )
    if to_time is not None:
        conditions.append(
            StockMovement.created_at <= _query_timestamp(to_time)
        )
    if query is not None:
        pattern = _literal_like_pattern(query)
        conditions.append(
            or_(
                StockMovement.movement_type.ilike(
                    pattern,
                    escape="\\",
                ),
                StockMovement.source.ilike(pattern, escape="\\"),
                StockMovement.reason.ilike(pattern, escape="\\"),
                StockMovement.note.ilike(pattern, escape="\\"),
                Part.part_number.ilike(pattern, escape="\\"),
                Part.name.ilike(pattern, escape="\\"),
                Reservation.label.ilike(pattern, escape="\\"),
                Project.name.ilike(pattern, escape="\\"),
                User.username.ilike(pattern, escape="\\"),
                User.display_name.ilike(pattern, escape="\\"),
            )
        )
    if conditions:
        statement = statement.where(*conditions)
    return statement


def _entity_labels(
    db: Session,
    audits: list[AuditLog],
) -> dict[tuple[str, int], str]:
    grouped: dict[str, set[int]] = {}
    for audit in audits:
        if (
            audit.entity_type is None
            or audit.entity_id is None
        ):
            continue
        grouped.setdefault(audit.entity_type, set()).add(
            audit.entity_id
        )

    labels: dict[tuple[str, int], str] = {}

    def load(
        entity_type: str,
        model,
        label_builder,
    ) -> None:
        ids = grouped.get(entity_type, set())
        if not ids:
            return
        rows = list(
            db.execute(
                select(model).where(model.id.in_(ids))
            ).scalars()
        )
        for row in rows:
            labels[(entity_type, row.id)] = label_builder(row)

    load(
        "part",
        Part,
        lambda row: (
            row.part_number
            or row.name
            or f"Part #{row.id}"
        ),
    )
    load("project", Project, lambda row: row.name)
    load("reservation", Reservation, lambda row: row.label)
    load("part_type", PartType, lambda row: row.name)
    load("location", Location, lambda row: row.name)
    load("manufacturer", Manufacturer, lambda row: row.name)
    load("package", PackageOption, lambda row: row.name)
    load("app_setting", AppSetting, lambda row: row.key)

    for entity_type, ids in grouped.items():
        for entity_id in ids:
            labels.setdefault(
                (entity_type, entity_id),
                f"{entity_type.replace('_', ' ').title()} "
                f"#{entity_id}",
            )
    return labels


def _load_page_context(
    db: Session,
    audits: list[AuditLog],
    movements: list[StockMovement],
) -> tuple[
    dict[int, str],
    dict[int, Part],
    dict[int, Reservation],
    dict[int, Project],
    dict[tuple[str, int], str],
]:
    actor_ids = {
        actor_id
        for actor_id in (
            [audit.actor_user_id for audit in audits]
            + [
                movement.actor_user_id
                for movement in movements
            ]
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

    reservation_ids = {
        movement.reservation_id
        for movement in movements
        if movement.reservation_id is not None
    }
    for audit in audits:
        if (
            audit.entity_type == "reservation"
            and audit.entity_id is not None
        ):
            reservation_ids.add(audit.entity_id)
        related = _related_id(audit, "reservation_id")
        if related is not None:
            reservation_ids.add(related)

    reservations = (
        list(
            db.execute(
                select(Reservation).where(
                    Reservation.id.in_(reservation_ids)
                )
            ).scalars()
        )
        if reservation_ids
        else []
    )
    reservation_map = {
        reservation.id: reservation
        for reservation in reservations
    }

    project_ids = {
        reservation.project_id
        for reservation in reservations
        if reservation.project_id is not None
    }
    for audit in audits:
        if (
            audit.entity_type == "project"
            and audit.entity_id is not None
        ):
            project_ids.add(audit.entity_id)
        related = _related_id(audit, "project_id")
        if related is not None:
            project_ids.add(related)

    projects = (
        list(
            db.execute(
                select(Project).where(Project.id.in_(project_ids))
            ).scalars()
        )
        if project_ids
        else []
    )
    project_map = {
        project.id: project
        for project in projects
    }

    return (
        actor_names,
        part_map,
        reservation_map,
        project_map,
        _entity_labels(db, audits),
    )


def _audit_entry(
    audit: AuditLog,
    *,
    actor_names: dict[int, str],
    reservation_map: dict[int, Reservation],
    project_map: dict[int, Project],
    entity_labels: dict[tuple[str, int], str],
) -> HistoryEntryResponse:
    reservation_id = (
        audit.entity_id
        if audit.entity_type == "reservation"
        else _related_id(audit, "reservation_id")
    )
    reservation = (
        reservation_map.get(reservation_id)
        if reservation_id is not None
        else None
    )
    project_id = (
        audit.entity_id
        if audit.entity_type == "project"
        else _related_id(audit, "project_id")
    )
    if project_id is None and reservation is not None:
        project_id = reservation.project_id
    project = (
        project_map.get(project_id)
        if project_id is not None
        else None
    )

    metadata = _json_mapping(audit.metadata_json)
    source = metadata.get("source")
    if not isinstance(source, str):
        source = None

    part_id = (
        audit.entity_id
        if audit.entity_type == "part"
        else _related_id(audit, "part_id")
    )

    return HistoryEntryResponse(
        key=f"audit:{audit.id}",
        kind="audit",
        event_type=audit.event_type,
        occurred_at=_history_timestamp(audit.created_at),
        summary=audit.summary,
        entity_type=audit.entity_type,
        entity_id=audit.entity_id,
        entity_label=(
            entity_labels.get(
                (audit.entity_type, audit.entity_id)
            )
            if (
                audit.entity_type is not None
                and audit.entity_id is not None
            )
            else None
        ),
        actor_type=audit.actor_type,
        actor_user_id=audit.actor_user_id,
        actor_display_name=actor_names.get(
            audit.actor_user_id
        ),
        part_id=part_id,
        reservation_id=reservation_id,
        reservation_label=(
            reservation.label
            if reservation is not None
            else None
        ),
        project_id=project_id,
        project_label=(
            project.name if project is not None else None
        ),
        source=source,
        before_json=audit.before_json,
        after_json=audit.after_json,
        metadata_json=audit.metadata_json,
    )


def _movement_quantity(movement: StockMovement) -> int | None:
    if (
        movement.reserved_quantity_before is not None
        and movement.reserved_quantity_after is not None
    ):
        delta = abs(
            int(movement.reserved_quantity_after)
            - int(movement.reserved_quantity_before)
        )
        if delta:
            return delta
    if movement.quantity_delta:
        return abs(int(movement.quantity_delta))
    return None


def _movement_entry(
    movement: StockMovement,
    *,
    actor_names: dict[int, str],
    part_map: dict[int, Part],
    reservation_map: dict[int, Reservation],
    project_map: dict[int, Project],
) -> HistoryEntryResponse:
    part = (
        part_map.get(movement.part_id)
        if movement.part_id is not None
        else None
    )
    reservation = (
        reservation_map.get(movement.reservation_id)
        if movement.reservation_id is not None
        else None
    )
    project = (
        project_map.get(reservation.project_id)
        if (
            reservation is not None
            and reservation.project_id is not None
        )
        else None
    )
    actor_type = (
        "user"
        if movement.actor_user_id is not None
        else movement.source
    )
    return HistoryEntryResponse(
        key=f"movement:{movement.id}",
        kind="stock_movement",
        event_type=f"stock.{movement.movement_type}",
        occurred_at=_history_timestamp(movement.created_at),
        summary=(
            movement.reason
            or f"{movement.movement_type.title()} "
            "inventory movement"
        ),
        entity_type="part",
        entity_id=movement.part_id,
        entity_label=_display_part(part, movement.part_id),
        actor_type=actor_type,
        actor_user_id=movement.actor_user_id,
        actor_display_name=actor_names.get(
            movement.actor_user_id
        ),
        part_id=movement.part_id,
        part_number=(
            part.part_number if part is not None else None
        ),
        part_name=part.name if part is not None else None,
        reservation_id=movement.reservation_id,
        reservation_label=(
            reservation.label
            if reservation is not None
            else None
        ),
        project_id=(
            reservation.project_id
            if reservation is not None
            else None
        ),
        project_label=(
            project.name if project is not None else None
        ),
        movement_type=movement.movement_type,
        quantity=_movement_quantity(movement),
        quantity_delta=int(movement.quantity_delta),
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
        unit_price_snapshot=(
            str(movement.unit_price_snapshot)
            if movement.unit_price_snapshot is not None
            else None
        ),
        currency_snapshot=movement.currency_snapshot,
        reason=movement.reason,
        note=movement.note,
        source=movement.source,
    )


def list_history(
    db: Session,
    *,
    kind: HistoryKind | None = None,
    entity_type: str | None = None,
    event_type: str | None = None,
    actor_type: str | None = None,
    actor_user_id: int | None = None,
    movement_type: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> HistoryCollectionResponse:
    if limit < 1 or limit > 100:
        raise HistoryValidationError(
            "History limit must be between 1 and 100."
        )
    if offset < 0:
        raise HistoryValidationError(
            "History offset cannot be negative."
        )
    if actor_user_id is not None and actor_user_id < 1:
        raise HistoryValidationError(
            "History actor_user_id must be positive."
        )

    entity_type = _clean_filter(entity_type)
    event_type = _clean_filter(event_type)
    actor_type = _clean_filter(actor_type)
    movement_type = _clean_filter(movement_type)
    query = _clean_filter(query)

    if query is not None and len(query) > 200:
        raise HistoryValidationError(
            "History search cannot exceed 200 characters."
        )
    if (
        from_time is not None
        and to_time is not None
        and _query_timestamp(from_time)
        > _query_timestamp(to_time)
    ):
        raise HistoryValidationError(
            "History from time must not be after to time."
        )

    include_audits = kind in (None, "audit")
    include_movements = kind in (None, "stock_movement")
    if movement_type is not None:
        include_audits = False

    candidate_limit = offset + limit
    audit_total = 0
    movement_total = 0
    audits: list[AuditLog] = []
    movements: list[StockMovement] = []

    if include_audits:
        audit_statement = _audit_query(
            entity_type=entity_type,
            event_type=event_type,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            from_time=from_time,
            to_time=to_time,
            query=query,
        )
        audit_total = int(
            db.execute(
                select(func.count()).select_from(
                    audit_statement.subquery()
                )
            ).scalar_one()
        )
        audits = list(
            db.execute(
                audit_statement.order_by(
                    AuditLog.created_at.desc(),
                    AuditLog.id.desc(),
                ).limit(candidate_limit)
            ).scalars()
        )

    if include_movements:
        movement_statement = _movement_query(
            entity_type=entity_type,
            event_type=event_type,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            movement_type=movement_type,
            from_time=from_time,
            to_time=to_time,
            query=query,
        )
        movement_total = int(
            db.execute(
                select(func.count()).select_from(
                    movement_statement.subquery()
                )
            ).scalar_one()
        )
        movements = list(
            db.execute(
                movement_statement.order_by(
                    StockMovement.created_at.desc(),
                    StockMovement.id.desc(),
                ).limit(candidate_limit)
            ).scalars()
        )

    ordered: list[
        tuple[datetime, int, int, Literal["audit", "stock_movement"], object]
    ] = []
    ordered.extend(
        (
            _history_timestamp(audit.created_at),
            1,
            audit.id,
            "audit",
            audit,
        )
        for audit in audits
    )
    ordered.extend(
        (
            _history_timestamp(movement.created_at),
            0,
            movement.id,
            "stock_movement",
            movement,
        )
        for movement in movements
    )
    ordered.sort(
        key=lambda item: (item[0], item[1], item[2]),
        reverse=True,
    )
    page = ordered[offset:offset + limit]

    page_audits = [
        item[4]
        for item in page
        if item[3] == "audit"
    ]
    page_movements = [
        item[4]
        for item in page
        if item[3] == "stock_movement"
    ]
    (
        actor_names,
        part_map,
        reservation_map,
        project_map,
        entity_labels,
    ) = _load_page_context(
        db,
        page_audits,
        page_movements,
    )

    entries: list[HistoryEntryResponse] = []
    for _timestamp, _rank, _id, entry_kind, record in page:
        if entry_kind == "audit":
            entries.append(
                _audit_entry(
                    record,
                    actor_names=actor_names,
                    reservation_map=reservation_map,
                    project_map=project_map,
                    entity_labels=entity_labels,
                )
            )
        else:
            entries.append(
                _movement_entry(
                    record,
                    actor_names=actor_names,
                    part_map=part_map,
                    reservation_map=reservation_map,
                    project_map=project_map,
                )
            )

    return HistoryCollectionResponse(
        total=audit_total + movement_total,
        limit=limit,
        offset=offset,
        entries=entries,
    )


def list_history_filter_options(
    db: Session,
) -> HistoryFilterOptionsResponse:
    audit_count = int(
        db.execute(
            select(func.count()).select_from(AuditLog)
        ).scalar_one()
    )
    movement_count = int(
        db.execute(
            select(func.count()).select_from(StockMovement)
        ).scalar_one()
    )

    entity_counts: dict[str, int] = {
        str(value): int(count)
        for value, count in db.execute(
            select(
                AuditLog.entity_type,
                func.count(AuditLog.id),
            )
            .where(AuditLog.entity_type.is_not(None))
            .group_by(AuditLog.entity_type)
        ).all()
    }
    entity_counts["part"] = (
        entity_counts.get("part", 0) + movement_count
    )

    event_counts: dict[str, int] = {
        str(value): int(count)
        for value, count in db.execute(
            select(
                AuditLog.event_type,
                func.count(AuditLog.id),
            ).group_by(AuditLog.event_type)
        ).all()
    }
    movement_type_rows = db.execute(
        select(
            StockMovement.movement_type,
            func.count(StockMovement.id),
        ).group_by(StockMovement.movement_type)
    ).all()
    for value, count in movement_type_rows:
        event_counts[f"stock.{value}"] = int(count)

    actor_counts: dict[str, int] = {
        str(value): int(count)
        for value, count in db.execute(
            select(
                AuditLog.actor_type,
                func.count(AuditLog.id),
            ).group_by(AuditLog.actor_type)
        ).all()
    }
    movement_user_count = int(
        db.execute(
            select(func.count(StockMovement.id)).where(
                StockMovement.actor_user_id.is_not(None)
            )
        ).scalar_one()
    )
    if movement_user_count:
        actor_counts["user"] = (
            actor_counts.get("user", 0)
            + movement_user_count
        )
    for value, count in db.execute(
        select(
            StockMovement.source,
            func.count(StockMovement.id),
        )
        .where(StockMovement.actor_user_id.is_(None))
        .group_by(StockMovement.source)
    ).all():
        actor_counts[str(value)] = (
            actor_counts.get(str(value), 0)
            + int(count)
        )

    source_rows = db.execute(
        select(
            StockMovement.source,
            func.count(StockMovement.id),
        ).group_by(StockMovement.source)
    ).all()

    actor_user_counts: dict[int, int] = {}
    for actor_id, count in db.execute(
        select(
            AuditLog.actor_user_id,
            func.count(AuditLog.id),
        )
        .where(AuditLog.actor_user_id.is_not(None))
        .group_by(AuditLog.actor_user_id)
    ).all():
        actor_user_counts[int(actor_id)] = int(count)
    for actor_id, count in db.execute(
        select(
            StockMovement.actor_user_id,
            func.count(StockMovement.id),
        )
        .where(StockMovement.actor_user_id.is_not(None))
        .group_by(StockMovement.actor_user_id)
    ).all():
        actor_user_counts[int(actor_id)] = (
            actor_user_counts.get(int(actor_id), 0)
            + int(count)
        )

    users = (
        list(
            db.execute(
                select(User).where(
                    User.id.in_(actor_user_counts)
                )
            ).scalars()
        )
        if actor_user_counts
        else []
    )
    actors = sorted(
        (
            HistoryActorOptionResponse(
                user_id=user.id,
                display_name=(
                    user.display_name.strip()
                    or user.username
                ),
                count=actor_user_counts[user.id],
            )
            for user in users
        ),
        key=lambda item: (
            item.display_name.casefold(),
            item.user_id,
        ),
    )

    audit_min = db.execute(
        select(AuditLog.created_at)
        .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
        .limit(1)
    ).scalar_one_or_none()
    audit_max = db.execute(
        select(AuditLog.created_at)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    movement_min = db.execute(
        select(StockMovement.created_at)
        .order_by(
            StockMovement.created_at.asc(),
            StockMovement.id.asc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    movement_max = db.execute(
        select(StockMovement.created_at)
        .order_by(
            StockMovement.created_at.desc(),
            StockMovement.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    minimums = [
        _history_timestamp(value)
        for value in (audit_min, movement_min)
        if value is not None
    ]
    maximums = [
        _history_timestamp(value)
        for value in (audit_max, movement_max)
        if value is not None
    ]

    return HistoryFilterOptionsResponse(
        kinds=[
            HistoryFacetValueResponse(
                value="audit",
                count=audit_count,
            ),
            HistoryFacetValueResponse(
                value="stock_movement",
                count=movement_count,
            ),
        ],
        entity_types=[
            HistoryFacetValueResponse(
                value=value,
                count=count,
            )
            for value, count in sorted(entity_counts.items())
        ],
        event_types=[
            HistoryFacetValueResponse(
                value=value,
                count=count,
            )
            for value, count in sorted(event_counts.items())
        ],
        actor_types=[
            HistoryFacetValueResponse(
                value=value,
                count=count,
            )
            for value, count in sorted(actor_counts.items())
        ],
        movement_types=_facet_rows(
            sorted(
                movement_type_rows,
                key=lambda row: str(row[0]),
            )
        ),
        sources=_facet_rows(
            sorted(
                source_rows,
                key=lambda row: str(row[0]),
            )
        ),
        actors=actors,
        earliest_at=min(minimums) if minimums else None,
        latest_at=max(maximums) if maximums else None,
    )
