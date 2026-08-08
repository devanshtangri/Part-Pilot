from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import sqlite3
import tempfile

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal, dispose_database_engine
from app.models import (
    AuditLog,
    Part,
    PartType,
    PartTypeField,
    Project,
    ProjectItem,
    Reservation,
    ReservationItem,
    StockMovement,
)
from app.services.auth import create_session, create_user

# PARTPILOT:RECYCLE_BIN_SMOKE:V607


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def database_path() -> Path:
    from app.core.config import get_settings
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"SQLite required, got {url!r}")
    return Path(url[len(prefix):]).resolve()


def snapshot():
    connection = sqlite3.connect(database_path())
    connection.row_factory = sqlite3.Row
    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        rows = {
            table: [
                dict(row)
                for row in connection.execute(
                    f'SELECT * FROM "{table}" ORDER BY rowid'
                )
            ]
            for table in tables
        }
        sequence = []
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='sqlite_sequence'"
        ).fetchone():
            sequence = [
                tuple(row)
                for row in connection.execute(
                    "SELECT name,seq FROM sqlite_sequence ORDER BY name"
                )
            ]
        return rows, sequence
    finally:
        connection.close()


def backup() -> Path:
    fd, raw = tempfile.mkstemp(prefix="pp607_", suffix=".db")
    os.close(fd)
    target = Path(raw)
    source = sqlite3.connect(database_path())
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return target


def restore(source_path: Path) -> None:
    dispose_database_engine()
    for suffix in ("-wal", "-shm", "-journal"):
        Path(str(database_path()) + suffix).unlink(missing_ok=True)
    source = sqlite3.connect(source_path)
    destination = sqlite3.connect(database_path())
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    dispose_database_engine()


def check_only() -> None:
    from app.api.routes import part_types, parts
    from app.services import part_types as part_type_service
    from app.services import parts as part_service
    required = (
        "get_part_type_delete_dependencies",
        "purge_deleted_parts",
    )
    for name in required:
        if not hasattr(part_type_service, name) and not hasattr(part_service, name):
            fail(f"Missing recycle-bin service contract: {name}")
    if part_type_service.PART_TYPE_DEPENDENCY_PREVIEW_LIMIT != 5:
        fail("Part Type dependency preview limit must remain five parts")
    service_source = Path(part_type_service.__file__).read_text(encoding="utf-8")
    if ".limit(PART_TYPE_DEPENDENCY_PREVIEW_LIMIT)" not in service_source:
        fail("Part Type dependency preview query is not bounded")
    if not any(
        getattr(route, "path", "") == "/part-types/{part_type_id}/delete-dependencies"
        for route in part_types.router.routes
    ):
        fail("Missing part-type dependency route")
    if not any(
        getattr(route, "path", "") == "/parts/deleted/purge"
        for route in parts.router.routes
    ):
        fail("Missing permanent-purge route")
    print("[PASS] recycle-bin routes and services are present")


def full() -> None:
    before = snapshot()
    backup_path = backup()
    suffix = secrets.token_hex(5)
    username = f"patch607_recycle_{suffix}"
    password = "Patch607-recycle-bin-password"
    try:
        db = SessionLocal()
        try:
            user = create_user(
                db,
                username=username,
                display_name="Patch 607 Recycle Bin",
                password=password,
                commit=True,
            )
            token = create_session(db, user=user, commit=True).token
            part_type = PartType(
                name=f"Patch 607 Type {suffix}",
                slug=f"patch-607-type-{suffix}",
                description="Recycle-bin dependency smoke",
                is_builtin=False,
                is_active=True,
                template_version=1,
            )
            db.add(part_type)
            db.flush()
            field = PartTypeField(
                part_type_id=part_type.id,
                field_key="variant",
                label="Variant",
                field_type="text",
                is_required=False,
                sort_order=0,
            )
            db.add(field)
            db.flush()
            type_id = int(part_type.id)

            active = Part(
                part_type_id=type_id,
                part_number=f"PP607-A-{suffix}",
                name="Patch 607 active part",
                total_quantity=1,
                reserved_quantity=0,
                is_deleted=False,
                deleted_at=None,
            )
            deleted = Part(
                part_type_id=type_id,
                part_number=f"PP607-D-{suffix}",
                name="Patch 607 deleted part",
                total_quantity=3,
                reserved_quantity=0,
                is_deleted=True,
                deleted_at=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ),
            )
            db.add_all([active, deleted])
            db.flush()
            active_id = int(active.id)
            deleted_id = int(deleted.id)
            db.commit()
        finally:
            db.close()

        from app.main import app
        headers = {"Authorization": f"Bearer {token}"}
        with TestClient(app) as client:
            unauth = client.post(
                "/api/parts/deleted/purge",
                json={"part_ids": [deleted_id], "confirmation": "DELETE"},
            )
            if unauth.status_code not in {401, 403}:
                fail(f"purge should require auth, got {unauth.status_code}")

            dependencies = client.get(
                f"/api/part-types/{type_id}/delete-dependencies",
                headers=headers,
            )
            if dependencies.status_code != 200:
                fail(f"dependency check failed: {dependencies.text}")
            dep = dependencies.json()
            if (
                dep.get("active_part_count") != 1
                or dep.get("deleted_part_count") != 1
                or dep.get("active_part_names") != ["Patch 607 active part"]
                or dep.get("deleted_part_names") != ["Patch 607 deleted part"]
                or dep.get("can_delete") is not False
            ):
                fail(f"unexpected mixed dependencies: {dep}")

            blocked_type = client.delete(
                f"/api/part-types/{type_id}",
                headers=headers,
            )
            if blocked_type.status_code != 409:
                fail(f"type delete should be blocked: {blocked_type.text}")
            detail = str(blocked_type.json().get("detail", ""))
            if "active inventory" not in detail or "Deleted items" not in detail:
                fail(f"type delete message lacks dependency classes: {detail}")

            active_delete = client.delete(
                f"/api/parts/{active_id}",
                headers=headers,
            )
            if active_delete.status_code != 200:
                fail(f"soft delete failed: {active_delete.text}")

            dependencies = client.get(
                f"/api/part-types/{type_id}/delete-dependencies",
                headers=headers,
            ).json()
            if (
                dependencies.get("active_part_count") != 0
                or dependencies.get("deleted_part_count") != 2
                or dependencies.get("active_part_names") != []
                or dependencies.get("deleted_part_names")
                != ["Patch 607 active part", "Patch 607 deleted part"]
                or dependencies.get("can_delete") is not False
            ):
                fail(f"unexpected deleted-only dependencies: {dependencies}")

            blocked_type = client.delete(
                f"/api/part-types/{type_id}",
                headers=headers,
            )
            if blocked_type.status_code != 409 or "Deleted items" not in str(
                blocked_type.json().get("detail", "")
            ):
                fail("deleted-only dependency should block type deletion")

            invalid_confirmation = client.post(
                "/api/parts/deleted/purge",
                headers=headers,
                json={"part_ids": [deleted_id], "confirmation": "NO"},
            )
            if invalid_confirmation.status_code != 422:
                fail("purge must require exact DELETE confirmation")

            db = SessionLocal()
            try:
                blocked = db.get(Part, active_id)
                if blocked is None:
                    fail("soft-deleted active fixture disappeared")
                blocked.reserved_quantity = 1
                project = Project(
                    name=f"Patch 607 consumed project {suffix}",
                    status="consumed",
                    created_by="manual",
                )
                reservation = Reservation(
                    label=f"Patch 607 cancelled reservation {suffix}",
                    status="cancelled",
                    created_by="manual",
                )
                db.add_all([project, reservation])
                db.flush()
                db.add(
                    ProjectItem(
                        project_id=project.id,
                        part_id=deleted_id,
                        quantity=1,
                    )
                )
                db.add(
                    ReservationItem(
                        reservation_id=reservation.id,
                        part_id=deleted_id,
                        quantity=1,
                    )
                )
                db.add(
                    StockMovement(
                        part_id=deleted_id,
                        movement_type="adjust",
                        quantity_delta=1,
                        quantity_before=2,
                        quantity_after=3,
                        source="manual",
                    )
                )
                db.commit()
            finally:
                db.close()

            atomic_block = client.post(
                "/api/parts/deleted/purge",
                headers=headers,
                json={
                    "part_ids": [deleted_id, active_id],
                    "confirmation": "DELETE",
                },
            )
            if atomic_block.status_code != 409:
                fail(f"reserved purge should block atomically: {atomic_block.text}")

            db = SessionLocal()
            try:
                if db.get(Part, deleted_id) is None or db.get(Part, active_id) is None:
                    fail("atomic purge removed rows despite a blocker")
                blocked = db.get(Part, active_id)
                blocked.reserved_quantity = 0
                db.commit()
            finally:
                db.close()

            purge = client.post(
                "/api/parts/deleted/purge",
                headers=headers,
                json={
                    "part_ids": [deleted_id, active_id],
                    "confirmation": "DELETE",
                },
            )
            if purge.status_code != 200:
                fail(f"permanent purge failed: {purge.status_code} {purge.text}")
            purged = purge.json()
            if purged.get("purged_count") != 2 or set(purged.get("purged_ids", [])) != {
                deleted_id,
                active_id,
            }:
                fail(f"unexpected purge response: {purged}")
            if (
                purged.get("detached_movement_count") != 1
                or purged.get("detached_project_item_count") != 1
                or purged.get("detached_reservation_item_count") != 1
            ):
                fail(f"historical detach counts incorrect: {purged}")

            dependencies = client.get(
                f"/api/part-types/{type_id}/delete-dependencies",
                headers=headers,
            ).json()
            if dependencies.get("can_delete") is not True:
                fail(f"type did not unlock after purge: {dependencies}")

            type_delete = client.delete(
                f"/api/part-types/{type_id}",
                headers=headers,
            )
            if type_delete.status_code != 200:
                fail(f"type delete after purge failed: {type_delete.text}")

        db = SessionLocal()
        try:
            movement = db.execute(
                select(StockMovement).where(StockMovement.part_id.is_(None))
                .order_by(StockMovement.id.desc())
            ).scalars().first()
            if movement is None:
                fail("historical movement was not retained/detached")
            project_item = db.execute(
                select(ProjectItem).where(ProjectItem.part_id.is_(None))
                .order_by(ProjectItem.id.desc())
            ).scalars().first()
            reservation_item = db.execute(
                select(ReservationItem).where(ReservationItem.part_id.is_(None))
                .order_by(ReservationItem.id.desc())
            ).scalars().first()
            if project_item is None or reservation_item is None:
                fail("terminal Project/Reservation history was not retained/detached")
            purge_audits = list(
                db.execute(
                    select(AuditLog).where(
                        AuditLog.event_type == "part.purged",
                        AuditLog.entity_id.in_((active_id, deleted_id)),
                    )
                ).scalars()
            )
            if len(purge_audits) != 2:
                fail(f"expected two purge audits, found {len(purge_audits)}")
        finally:
            db.close()
    finally:
        restore(backup_path)
        backup_path.unlink(missing_ok=True)

    if snapshot() != before:
        fail("exact logical restore failed after recycle-bin smoke")

    print(
        "[PASS] recycle bin preserves restore dependencies, bulk purge is atomic, "
        "historical terminal links detach safely and part-type deletion unlocks"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    check_only() if args.check_only else full()


if __name__ == "__main__":
    main()
