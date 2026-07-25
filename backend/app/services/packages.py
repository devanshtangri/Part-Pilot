from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AuditLog, PackageOption
from app.schemas.packages import (
    PackageCollectionResponse,
    PackageCreateRequest,
    PackageResponse,
)


class PackageConflictError(ValueError):
    pass


def normalize_package_name(value: str) -> str:
    return " ".join(value.split()).casefold()


def serialize_package(package: PackageOption) -> PackageResponse:
    return PackageResponse(
        id=package.id,
        name=package.name,
        is_builtin=package.is_builtin,
        is_active=package.is_active,
        created_at=package.created_at,
        updated_at=package.updated_at,
    )


def list_packages(
    db: Session,
    *,
    active_only: bool = True,
) -> PackageCollectionResponse:
    conditions = []
    if active_only:
        conditions.append(PackageOption.is_active.is_(True))

    packages = list(
        db.execute(
            select(PackageOption)
            .where(*conditions)
            .order_by(
                func.lower(PackageOption.name).asc(),
                PackageOption.id.asc(),
            )
        ).scalars()
    )
    builtin_count = sum(
        1 for package in packages if package.is_builtin
    )

    return PackageCollectionResponse(
        total=len(packages),
        builtin_count=builtin_count,
        custom_count=len(packages) - builtin_count,
        packages=[serialize_package(package) for package in packages],
    )


def create_package(
    db: Session,
    payload: PackageCreateRequest,
    *,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> PackageResponse:
    normalized_name = normalize_package_name(payload.name)
    existing = db.execute(
        select(PackageOption).where(
            PackageOption.normalized_name == normalized_name
        )
    ).scalar_one_or_none()

    if existing is not None:
        raise PackageConflictError(
            f"{existing.name!r} already exists in the package catalogue."
        )

    package = PackageOption(
        name=payload.name,
        normalized_name=normalized_name,
        is_builtin=False,
        is_active=True,
    )

    try:
        db.add(package)
        db.flush()
        db.add(
            AuditLog(
                event_type="package.created",
                entity_type="package",
                entity_id=package.id,
                actor_type=(
                    "user" if actor_user_id is not None else "system"
                ),
                actor_user_id=actor_user_id,
                summary=(
                    f"Created package or form factor {package.name}"
                ),
                before_json=None,
                after_json={
                    "id": package.id,
                    "name": package.name,
                    "is_builtin": package.is_builtin,
                    "is_active": package.is_active,
                },
                metadata_json=None,
            )
        )
        db.flush()

        if commit:
            db.commit()
            db.refresh(package)
    except IntegrityError as exc:
        db.rollback()
        raise PackageConflictError(
            "A package or form factor with this name already exists."
        ) from exc
    except Exception:
        if commit:
            db.rollback()
        raise

    return serialize_package(package)
