from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.utils import normalize_location_name
from app.models import AuditLog, Location, Part
from app.schemas.locations import (
    LocationCollectionResponse,
    LocationCreateRequest,
    LocationDeleteResponse,
    LocationResponse,
    LocationUpdateRequest,
)


# PATCH 156: reusable location catalogue service
class LocationNotFoundError(LookupError):
    pass


class LocationConflictError(ValueError):
    pass


class LocationInUseError(ValueError):
    pass


UsageCounts = tuple[int, int, int]


def _snapshot_location(
    location: Location,
    *,
    counts: UsageCounts,
) -> dict[str, object]:
    total, active, deleted = counts
    return {
        "id": location.id,
        "name": location.name,
        "note": location.note,
        "part_count": total,
        "active_part_count": active,
        "deleted_part_count": deleted,
    }


def _usage_counts_for_ids(
    db: Session,
    location_ids: Iterable[int],
) -> dict[int, UsageCounts]:
    identifiers = sorted({int(value) for value in location_ids})
    if not identifiers:
        return {}

    rows = db.execute(
        select(
            Part.location_id,
            Part.is_deleted,
            func.count(Part.id),
        )
        .where(Part.location_id.in_(identifiers))
        .group_by(Part.location_id, Part.is_deleted)
    ).all()

    mutable: dict[int, list[int]] = {
        identifier: [0, 0, 0]
        for identifier in identifiers
    }
    for location_id, is_deleted, count in rows:
        if location_id is None:
            continue
        count_value = int(count)
        values = mutable[int(location_id)]
        values[0] += count_value
        if bool(is_deleted):
            values[2] += count_value
        else:
            values[1] += count_value

    return {
        identifier: (values[0], values[1], values[2])
        for identifier, values in mutable.items()
    }


def _usage_counts_for_location(
    db: Session,
    location_id: int,
) -> UsageCounts:
    return _usage_counts_for_ids(db, [location_id]).get(
        location_id,
        (0, 0, 0),
    )


def serialize_location(
    location: Location,
    *,
    counts: UsageCounts = (0, 0, 0),
) -> LocationResponse:
    total, active, deleted = counts
    return LocationResponse(
        id=location.id,
        name=location.name,
        note=location.note,
        part_count=total,
        active_part_count=active,
        deleted_part_count=deleted,
        created_at=location.created_at,
        updated_at=location.updated_at,
    )


def list_locations(db: Session) -> LocationCollectionResponse:
    locations = list(
        db.execute(
            select(Location).order_by(
                func.lower(Location.name).asc(),
                Location.id.asc(),
            )
        ).scalars()
    )
    counts_by_id = _usage_counts_for_ids(
        db,
        (location.id for location in locations),
    )
    return LocationCollectionResponse(
        total=len(locations),
        locations=[
            serialize_location(
                location,
                counts=counts_by_id.get(location.id, (0, 0, 0)),
            )
            for location in locations
        ],
    )


def _get_location_model(db: Session, location_id: int) -> Location:
    location = db.get(Location, location_id)
    if location is None:
        raise LocationNotFoundError(
            f"Location {location_id} was not found."
        )
    return location


def create_location(
    db: Session,
    payload: LocationCreateRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> LocationResponse:
    normalized_name = normalize_location_name(payload.name)
    existing = db.execute(
        select(Location).where(
            Location.normalized_name == normalized_name
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise LocationConflictError(
            f"{existing.name!r} already exists in the location catalogue."
        )

    location = Location(
        name=payload.name,
        normalized_name=normalized_name,
        note=payload.note,
    )

    try:
        db.add(location)
        db.flush()
        after_snapshot = _snapshot_location(
            location,
            counts=(0, 0, 0),
        )
        db.add(
            AuditLog(
                event_type="location.created",
                entity_type="location",
                entity_id=location.id,
                actor_type=(
                    "user" if actor_user_id is not None else "system"
                ),
                actor_user_id=actor_user_id,
                summary=f"Created location {location.name}",
                before_json=None,
                after_json=after_snapshot,
                metadata_json={
                    "normalized_name": location.normalized_name,
                },
            )
        )
        db.flush()
        if commit:
            db.commit()
            db.refresh(location)
    except IntegrityError as exc:
        db.rollback()
        raise LocationConflictError(
            "A location with this name already exists."
        ) from exc
    except Exception:
        if commit:
            db.rollback()
        raise

    return serialize_location(location)


def update_location(
    db: Session,
    location_id: int,
    payload: LocationUpdateRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> LocationResponse:
    location = _get_location_model(db, location_id)
    counts = _usage_counts_for_location(db, location.id)
    before_snapshot = _snapshot_location(location, counts=counts)

    normalized_name = normalize_location_name(payload.name)
    duplicate = db.execute(
        select(Location).where(
            Location.normalized_name == normalized_name,
            Location.id != location.id,
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise LocationConflictError(
            f"{duplicate.name!r} already exists in the location catalogue."
        )

    changed_fields: list[str] = []
    if location.name != payload.name:
        changed_fields.append("name")
    if location.note != payload.note:
        changed_fields.append("note")

    location.name = payload.name
    location.normalized_name = normalized_name
    location.note = payload.note

    try:
        db.flush()
        after_snapshot = _snapshot_location(location, counts=counts)
        db.add(
            AuditLog(
                event_type="location.updated",
                entity_type="location",
                entity_id=location.id,
                actor_type=(
                    "user" if actor_user_id is not None else "system"
                ),
                actor_user_id=actor_user_id,
                summary=f"Updated location {location.name}",
                before_json=before_snapshot,
                after_json=after_snapshot,
                metadata_json={
                    "changed_fields": changed_fields,
                    "normalized_name": location.normalized_name,
                },
            )
        )
        db.flush()
        if commit:
            db.commit()
            db.refresh(location)
    except IntegrityError as exc:
        db.rollback()
        raise LocationConflictError(
            "A location with this name already exists."
        ) from exc
    except Exception:
        if commit:
            db.rollback()
        raise

    return serialize_location(location, counts=counts)


def delete_location(
    db: Session,
    location_id: int,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> LocationDeleteResponse:
    location = _get_location_model(db, location_id)
    counts = _usage_counts_for_location(db, location.id)
    total_count, active_count, deleted_count = counts
    if total_count > 0:
        raise LocationInUseError(
            f"{location.name!r} is assigned to {total_count} part(s) "
            f"({active_count} active, {deleted_count} deleted) and cannot "
            "be deleted."
        )

    before_snapshot = _snapshot_location(location, counts=counts)
    response = LocationDeleteResponse(
        id=location.id,
        name=location.name,
        deleted=True,
    )

    try:
        db.delete(location)
        db.flush()
        db.add(
            AuditLog(
                event_type="location.deleted",
                entity_type="location",
                entity_id=response.id,
                actor_type=(
                    "user" if actor_user_id is not None else "system"
                ),
                actor_user_id=actor_user_id,
                summary=f"Deleted unused location {response.name}",
                before_json=before_snapshot,
                after_json={
                    "id": response.id,
                    "name": response.name,
                    "deleted": True,
                },
                metadata_json={
                    "part_count": 0,
                    "safe_delete_check": True,
                },
            )
        )
        db.flush()
        if commit:
            db.commit()
    except Exception:
        if commit:
            db.rollback()
        raise

    return response
