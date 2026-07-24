from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AuditLog, Manufacturer
from app.schemas.manufacturers import (
    ManufacturerCollectionResponse,
    ManufacturerCreateRequest,
    ManufacturerResponse,
)


class ManufacturerConflictError(ValueError):
    pass


def normalize_manufacturer_name(value: str) -> str:
    return " ".join(value.split()).casefold()


def serialize_manufacturer(
    manufacturer: Manufacturer,
) -> ManufacturerResponse:
    return ManufacturerResponse(
        id=manufacturer.id,
        name=manufacturer.name,
        is_builtin=manufacturer.is_builtin,
        is_active=manufacturer.is_active,
        created_at=manufacturer.created_at,
        updated_at=manufacturer.updated_at,
    )


def list_manufacturers(
    db: Session,
    *,
    active_only: bool = True,
) -> ManufacturerCollectionResponse:
    conditions = []
    if active_only:
        conditions.append(Manufacturer.is_active.is_(True))

    manufacturers = list(
        db.execute(
            select(Manufacturer)
            .where(*conditions)
            .order_by(
                func.lower(Manufacturer.name).asc(),
                Manufacturer.id.asc(),
            )
        ).scalars()
    )

    builtin_count = sum(
        1
        for manufacturer in manufacturers
        if manufacturer.is_builtin
    )

    return ManufacturerCollectionResponse(
        total=len(manufacturers),
        builtin_count=builtin_count,
        custom_count=len(manufacturers) - builtin_count,
        manufacturers=[
            serialize_manufacturer(manufacturer)
            for manufacturer in manufacturers
        ],
    )


def create_manufacturer(
    db: Session,
    payload: ManufacturerCreateRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> ManufacturerResponse:
    normalized_name = normalize_manufacturer_name(payload.name)

    existing = db.execute(
        select(Manufacturer).where(
            Manufacturer.normalized_name == normalized_name
        )
    ).scalar_one_or_none()

    if existing is not None:
        raise ManufacturerConflictError(
            f"{existing.name!r} already exists in the manufacturer "
            "catalogue."
        )

    manufacturer = Manufacturer(
        name=payload.name,
        normalized_name=normalized_name,
        is_builtin=False,
        is_active=True,
    )

    try:
        db.add(manufacturer)
        db.flush()

        db.add(
            AuditLog(
                event_type="manufacturer.created",
                entity_type="manufacturer",
                entity_id=manufacturer.id,
                actor_type=(
                    "user"
                    if actor_user_id is not None
                    else "system"
                ),
                actor_user_id=actor_user_id,
                summary=(
                    f"Created manufacturer {manufacturer.name}"
                ),
                before_json=None,
                after_json={
                    "id": manufacturer.id,
                    "name": manufacturer.name,
                    "is_builtin": manufacturer.is_builtin,
                    "is_active": manufacturer.is_active,
                },
                metadata_json=None,
            )
        )
        db.flush()

        if commit:
            db.commit()
            db.refresh(manufacturer)

    except IntegrityError as exc:
        db.rollback()
        raise ManufacturerConflictError(
            "A manufacturer with this name already exists."
        ) from exc
    except Exception:
        if commit:
            db.rollback()
        raise

    return serialize_manufacturer(manufacturer)
