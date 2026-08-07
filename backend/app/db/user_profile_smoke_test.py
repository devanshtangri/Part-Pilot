from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal, dispose_database_engine
from app.models import AuditLog, User, UserSession
from app.services.auth import BUILTIN_AVATAR_IDS, create_session, create_user

# PARTPILOT:CURRENT_USER_PROFILE_SMOKE:V572


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def db_path() -> Path:
    from app.core.config import get_settings

    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"SQLite required, got {url!r}")
    return Path(url[len(prefix):]).resolve()


def snapshot():
    connection = sqlite3.connect(db_path())
    connection.row_factory = sqlite3.Row
    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
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
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='sqlite_sequence'"
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
    fd, raw = tempfile.mkstemp(prefix="pp572_", suffix=".db")
    os.close(fd)
    target = Path(raw)
    source = sqlite3.connect(db_path())
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
        Path(str(db_path()) + suffix).unlink(missing_ok=True)
    source = sqlite3.connect(source_path)
    destination = sqlite3.connect(db_path())
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    dispose_database_engine()


def check_only() -> None:
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/auth/profile")
        if response.status_code != 401:
            fail(f"unauthenticated profile GET returned {response.status_code}")
        response = client.put(
            "/api/auth/profile",
            json={
                "username": "x",
                "display_name": "X",
                "avatar_id": "initials",
            },
        )
        if response.status_code != 401:
            fail(f"unauthenticated profile PUT returned {response.status_code}")

        document = client.get("/openapi.json").json()
        profile = document["paths"].get("/api/auth/profile")
        if profile is None or set(profile) != {"get", "put"}:
            fail(f"profile OpenAPI methods unexpected: {profile}")
        serialized = json.dumps(document, sort_keys=True)
        for avatar_id in BUILTIN_AVATAR_IDS:
            if avatar_id not in serialized:
                fail(f"OpenAPI is missing avatar ID {avatar_id}")

    print("[PASS] protected profile API and avatar catalogue OpenAPI")


def full() -> None:
    before = snapshot()
    backup_path = backup()
    try:
        db = SessionLocal()
        try:
            user = db.execute(select(User).order_by(User.id)).scalars().first()
            if user is None:
                fail("existing user required")
            user_id = user.id
            original_username = user.username
            original_display_name = user.display_name
            original_avatar = user.avatar_id
            original_password_hash = user.password_hash
            original_sessions = {
                row.id: (
                    row.user_id,
                    row.token_hash,
                    row.expires_at,
                    row.revoked_at,
                    row.user_agent,
                    row.ip_address,
                )
                for row in db.execute(select(UserSession)).scalars()
            }
            audit_floor = (
                db.execute(
                    select(AuditLog.id).order_by(AuditLog.id.desc()).limit(1)
                ).scalar_one_or_none()
                or 0
            )
            token = create_session(
                db,
                user=user,
                user_agent="Patch 572 profile smoke",
                ip_address="127.0.0.1",
                commit=True,
            ).token
            conflict = create_user(
                db,
                username="patch572_conflict",
                display_name="Patch 572 Conflict",
                password="Patch572-conflict-password",
                commit=True,
            )
            conflict_id = conflict.id
        finally:
            db.close()

        headers = {"Authorization": f"Bearer {token}"}
        from app.main import app

        with TestClient(app) as client:
            current = client.get("/api/auth/profile", headers=headers)
            if current.status_code != 200:
                fail(f"profile GET failed: {current.status_code} {current.text[:300]}")
            body = current.json()
            if body.get("id") != user_id:
                fail("profile GET returned wrong user")
            if body.get("avatar_id") != original_avatar:
                fail("profile GET returned wrong avatar")
            if body.get("available_avatar_ids") != list(BUILTIN_AVATAR_IDS):
                fail("profile GET avatar catalogue mismatch")

            invalid = client.put(
                "/api/auth/profile",
                headers=headers,
                json={
                    "username": original_username,
                    "display_name": original_display_name,
                    "avatar_id": "not-a-real-avatar",
                },
            )
            if invalid.status_code != 422:
                fail(
                    f"invalid avatar returned {invalid.status_code}: "
                    f"{invalid.text[:200]}"
                )

            conflict_response = client.put(
                "/api/auth/profile",
                headers=headers,
                json={
                    "username": "PATCH572_CONFLICT",
                    "display_name": "Still Me",
                    "avatar_id": "chip",
                },
            )
            if conflict_response.status_code != 409:
                fail(
                    f"username conflict returned {conflict_response.status_code}: "
                    f"{conflict_response.text[:200]}"
                )

            changed = client.put(
                "/api/auth/profile",
                headers=headers,
                json={
                    "username": " PATCH572.Profile ",
                    "display_name": " Patch 572 Profile ",
                    "avatar_id": "circuit",
                },
            )
            if changed.status_code != 200:
                fail(
                    f"profile PUT failed: {changed.status_code} "
                    f"{changed.text[:300]}"
                )
            changed_body = changed.json()
            if (
                changed_body.get("username") != "patch572.profile"
                or changed_body.get("display_name") != "Patch 572 Profile"
                or changed_body.get("avatar_id") != "circuit"
            ):
                fail(f"profile normalization/update mismatch: {changed_body}")

            me = client.get("/api/auth/me", headers=headers)
            if me.status_code != 200:
                fail(f"/auth/me failed after profile update: {me.status_code}")
            if (
                me.json().get("username") != "patch572.profile"
                or me.json().get("display_name") != "Patch 572 Profile"
                or me.json().get("avatar_id") != "circuit"
            ):
                fail("/auth/me did not reflect profile update")

        db = SessionLocal()
        try:
            user = db.get(User, user_id)
            if user is None:
                fail("updated user disappeared")
            if user.password_hash != original_password_hash:
                fail("profile update changed password hash")

            preexisting_sessions = {
                row.id: (
                    row.user_id,
                    row.token_hash,
                    row.expires_at,
                    row.revoked_at,
                    row.user_agent,
                    row.ip_address,
                )
                for row in db.execute(
                    select(UserSession).where(UserSession.id.in_(original_sessions))
                ).scalars()
            }
            if preexisting_sessions != original_sessions:
                fail("profile update changed pre-existing sessions")

            audits = list(
                db.execute(
                    select(AuditLog).where(
                        AuditLog.id > audit_floor,
                        AuditLog.event_type == "auth.profile_updated",
                        AuditLog.entity_type == "user",
                        AuditLog.entity_id == user_id,
                    )
                ).scalars()
            )
            if len(audits) != 1:
                fail(f"expected one profile audit, found {len(audits)}")
            audit = audits[0]
            if audit.actor_type != "user" or audit.actor_user_id != user_id:
                fail("profile audit attribution is incorrect")
            if sorted(audit.metadata_json.get("changed_fields", [])) != [
                "avatar_id",
                "display_name",
                "username",
            ]:
                fail(f"profile audit changed_fields unexpected: {audit.metadata_json}")
            serialized = json.dumps(
                {
                    "summary": audit.summary,
                    "before": audit.before_json,
                    "after": audit.after_json,
                    "metadata": audit.metadata_json,
                },
                sort_keys=True,
            ).casefold()
            if "password" in serialized or "token_hash" in serialized:
                fail("profile audit exposed credential-shaped data")

            if db.get(User, conflict_id) is None:
                fail("conflict fixture unexpectedly disappeared")
        finally:
            db.close()
    finally:
        restore(backup_path)
        backup_path.unlink(missing_ok=True)

    if snapshot() != before:
        fail("exact logical restore failed")

    print(
        "[PASS] profile read/update, normalization, conflict handling, avatar "
        "validation, audit, /me refresh, password/session preservation and exact restore"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    check_only() if args.check_only else full()


if __name__ == "__main__":
    main()
