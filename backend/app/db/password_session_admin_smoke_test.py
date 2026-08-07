from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import sqlite3
import tempfile

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import verify_password
from app.db.session import SessionLocal, dispose_database_engine
from app.models import AuditLog, User, UserSession
from app.services.auth import create_session, create_user, is_session_active

# PARTPILOT:PASSWORD_SESSION_ADMIN_SMOKE:V584


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
    fd, raw = tempfile.mkstemp(prefix="pp584_", suffix=".db")
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


def check_safe_session_shape(body: dict, expected_current_id: int | None = None) -> None:
    expected = {
        "id",
        "is_current",
        "is_active",
        "created_at",
        "updated_at",
        "expires_at",
        "revoked_at",
        "user_agent",
        "ip_address",
    }
    sessions = body.get("sessions")
    if not isinstance(sessions, list):
        fail(f"sessions response is not a list: {body}")
    for item in sessions:
        if set(item) != expected:
            fail(f"unsafe or incomplete session response fields: {sorted(item)}")
        serialized = json.dumps(item, sort_keys=True).casefold()
        if "token_hash" in serialized or '"token"' in serialized:
            fail("session response exposed token-shaped material")
    if expected_current_id is not None:
        if not sessions or sessions[0].get("id") != expected_current_id:
            fail("current session is not sorted first")
        current_rows = [item for item in sessions if item.get("is_current")]
        if len(current_rows) != 1 or current_rows[0].get("id") != expected_current_id:
            fail("session response current-session marker is incorrect")


def check_only() -> None:
    from app.main import app

    valid_password = {
        "current_password": "Patch584-current-password",
        "new_password": "Patch584-new-password",
    }
    probes = [
        ("post", "/api/auth/change-password", valid_password),
        ("get", "/api/auth/sessions", None),
        ("post", "/api/auth/sessions/revoke-all-other", None),
        ("delete", "/api/auth/sessions/999999", None),
    ]
    with TestClient(app) as client:
        for method, path, payload in probes:
            response = client.request(method, path, json=payload)
            if response.status_code != 401:
                fail(
                    f"unauthenticated {method.upper()} {path} returned "
                    f"{response.status_code}: {response.text[:200]}"
                )

        document = client.get("/openapi.json").json()
        expected = {
            "/api/auth/change-password": {"post"},
            "/api/auth/sessions": {"get"},
            "/api/auth/sessions/revoke-all-other": {"post"},
            "/api/auth/sessions/{session_id}": {"delete"},
        }
        for path, methods in expected.items():
            actual = set(document.get("paths", {}).get(path, {}))
            if actual != methods:
                fail(f"OpenAPI methods for {path} are {actual}, expected {methods}")

        serialized = json.dumps(document, sort_keys=True).casefold()
        for required in (
            "passwordchangerequest",
            "sessionresponse",
            "revoked_other_sessions",
            "revoke-all-other",
        ):
            if required not in serialized:
                fail(f"OpenAPI missing password/session marker {required}")

    print("[PASS] protected password/session APIs and OpenAPI contract")


def full() -> None:
    before = snapshot()
    backup_path = backup()
    suffix = secrets.token_hex(5)
    username = f"patch584_security_{suffix}"
    foreign_username = f"patch584_foreign_{suffix}"
    old_password = "Patch584-current-password"
    new_password = "Patch584-new-password"
    later_password = "Patch584-later-password"

    try:
        db = SessionLocal()
        try:
            user = create_user(
                db,
                username=username,
                display_name="Patch 584 Security Fixture",
                password=old_password,
                commit=False,
            )
            foreign_user = create_user(
                db,
                username=foreign_username,
                display_name="Patch 584 Foreign Fixture",
                password="Patch584-foreign-password",
                commit=False,
            )
            db.flush()

            current = create_session(
                db,
                user=user,
                user_agent="Patch 584 current browser",
                ip_address="127.0.0.81",
                commit=False,
            )
            other_one = create_session(
                db,
                user=user,
                user_agent="Patch 584 other one",
                ip_address="127.0.0.82",
                commit=False,
            )
            other_two = create_session(
                db,
                user=user,
                user_agent="Patch 584 other two",
                ip_address="127.0.0.83",
                commit=False,
            )
            expired = create_session(
                db,
                user=user,
                user_agent="Patch 584 expired",
                ip_address="127.0.0.84",
                commit=False,
            )
            expired.session.expires_at = naive_now() - timedelta(hours=2)
            already_revoked = create_session(
                db,
                user=user,
                user_agent="Patch 584 already revoked",
                ip_address="127.0.0.85",
                commit=False,
            )
            already_revoked.session.revoked_at = naive_now() - timedelta(hours=1)
            foreign = create_session(
                db,
                user=foreign_user,
                user_agent="Patch 584 foreign",
                ip_address="127.0.0.86",
                commit=False,
            )
            db.flush()

            user_id = user.id
            current_id = current.session.id
            other_one_id = other_one.session.id
            other_two_id = other_two.session.id
            expired_id = expired.session.id
            revoked_id = already_revoked.session.id
            foreign_id = foreign.session.id
            current_token = current.token
            other_one_token = other_one.token
            other_two_token = other_two.token
            foreign_token = foreign.token
            initial_hash = user.password_hash
            audit_floor = (
                db.execute(
                    select(AuditLog.id).order_by(AuditLog.id.desc()).limit(1)
                ).scalar_one_or_none()
                or 0
            )
            db.commit()
        finally:
            db.close()

        headers = {"Authorization": f"Bearer {current_token}"}
        from app.main import app

        with TestClient(app) as client:
            listed = client.get("/api/auth/sessions", headers=headers)
            if listed.status_code != 200:
                fail(f"initial session list failed: {listed.status_code} {listed.text[:300]}")
            check_safe_session_shape(listed.json(), current_id)
            listed_ids = {item["id"] for item in listed.json()["sessions"]}
            if listed_ids != {
                current_id,
                other_one_id,
                other_two_id,
                expired_id,
                revoked_id,
            }:
                fail(f"session list ownership/history mismatch: {listed_ids}")
            if foreign_id in listed_ids:
                fail("session list leaked another user's session")

            wrong = client.post(
                "/api/auth/change-password",
                headers=headers,
                json={
                    "current_password": "Patch584-wrong-password",
                    "new_password": new_password,
                },
            )
            if wrong.status_code != 400 or "incorrect" not in wrong.text.casefold():
                fail(f"wrong current password was not rejected safely: {wrong.status_code} {wrong.text}")

            reused = client.post(
                "/api/auth/change-password",
                headers=headers,
                json={
                    "current_password": old_password,
                    "new_password": old_password,
                },
            )
            if reused.status_code != 422 or "different" not in reused.text.casefold():
                fail(f"password reuse was not rejected: {reused.status_code} {reused.text}")

            too_short = client.post(
                "/api/auth/change-password",
                headers=headers,
                json={
                    "current_password": old_password,
                    "new_password": "short",
                },
            )
            if too_short.status_code != 422:
                fail(f"short new password returned {too_short.status_code}")

            db = SessionLocal()
            try:
                unchanged = db.get(User, user_id)
                if unchanged is None or unchanged.password_hash != initial_hash:
                    fail("failed password changes mutated the stored password")
                for sid in (other_one_id, other_two_id):
                    row = db.get(UserSession, sid)
                    if row is None or not is_session_active(row):
                        fail("failed password changes mutated another active session")
                premature_audits = list(
                    db.execute(
                        select(AuditLog).where(
                            AuditLog.id > audit_floor,
                            AuditLog.event_type == "auth.password_changed",
                        )
                    ).scalars()
                )
                if premature_audits:
                    fail("failed password changes created a password-change audit")
            finally:
                db.close()

            changed = client.post(
                "/api/auth/change-password",
                headers=headers,
                json={
                    "current_password": old_password,
                    "new_password": new_password,
                },
            )
            if changed.status_code != 200 or changed.json() != {
                "ok": True,
                "revoked_other_sessions": 2,
            }:
                fail(f"password change response mismatch: {changed.status_code} {changed.text}")

            current_still_valid = client.get("/api/auth/profile", headers=headers)
            if current_still_valid.status_code != 200:
                fail("password change unexpectedly revoked the current browser session")

            for old_token in (other_one_token, other_two_token):
                old_session = client.get(
                    "/api/auth/profile",
                    headers={"Authorization": f"Bearer {old_token}"},
                )
                if old_session.status_code != 401:
                    fail("password change did not revoke another active session")

            foreign_still_valid = client.get(
                "/api/auth/profile",
                headers={"Authorization": f"Bearer {foreign_token}"},
            )
            if foreign_still_valid.status_code != 200:
                fail("password change affected another user's session")

            db = SessionLocal()
            try:
                user_row = db.get(User, user_id)
                if user_row is None:
                    fail("fixture user disappeared after password change")
                if not verify_password(new_password, user_row.password_hash):
                    fail("new password hash does not verify")
                if verify_password(old_password, user_row.password_hash):
                    fail("old password still verifies after password change")
                current_row = db.get(UserSession, current_id)
                if current_row is None or not is_session_active(current_row):
                    fail("current session is not active after password change")
                if db.get(UserSession, expired_id).revoked_at is not None:
                    fail("password change rewrote an already-expired session")
                original_revoked_at = db.get(UserSession, revoked_id).revoked_at
                if original_revoked_at is None:
                    fail("pre-revoked fixture unexpectedly became unrevoked")

                password_audits = list(
                    db.execute(
                        select(AuditLog).where(
                            AuditLog.id > audit_floor,
                            AuditLog.event_type == "auth.password_changed",
                            AuditLog.entity_type == "user",
                            AuditLog.entity_id == user_id,
                        )
                    ).scalars()
                )
                if len(password_audits) != 1:
                    fail(f"expected one password-change audit, found {len(password_audits)}")
                audit = password_audits[0]
                if audit.actor_type != "user" or audit.actor_user_id != user_id:
                    fail("password-change audit attribution is incorrect")
                if audit.before_json is not None or audit.after_json is not None:
                    fail("password-change audit should not contain credential snapshots")
                if audit.metadata_json != {
                    "revoked_other_sessions": 2,
                    "preserved_current_session_id": current_id,
                }:
                    fail(f"password-change audit metadata mismatch: {audit.metadata_json}")
                secret_probe = json.dumps(
                    {
                        "summary": audit.summary,
                        "before": audit.before_json,
                        "after": audit.after_json,
                        "metadata": audit.metadata_json,
                    },
                    sort_keys=True,
                )
                for secret_value in (
                    old_password,
                    new_password,
                    current_token,
                    initial_hash,
                ):
                    if secret_value in secret_probe:
                        fail("password-change audit exposed credential material")
                if "password_hash" in secret_probe or "token_hash" in secret_probe:
                    fail("password-change audit exposed credential field names")
            finally:
                db.close()

            current_target = client.delete(
                f"/api/auth/sessions/{current_id}",
                headers=headers,
            )
            if current_target.status_code != 409 or "logout" not in current_target.text.casefold():
                fail(f"targeted current-session revoke was not rejected: {current_target.status_code} {current_target.text}")

            foreign_target = client.delete(
                f"/api/auth/sessions/{foreign_id}",
                headers=headers,
            )
            if foreign_target.status_code != 404:
                fail(f"cross-user session revoke returned {foreign_target.status_code}")

            missing_target = client.delete(
                "/api/auth/sessions/999999999",
                headers=headers,
            )
            if missing_target.status_code != 404:
                fail(f"missing session revoke returned {missing_target.status_code}")

            db = SessionLocal()
            try:
                user_row = db.get(User, user_id)
                target = create_session(
                    db,
                    user=user_row,
                    user_agent="Patch 584 targeted revoke",
                    ip_address="127.0.0.87",
                    commit=True,
                )
                target_id = target.session.id
                target_token = target.token
            finally:
                db.close()

            targeted = client.delete(
                f"/api/auth/sessions/{target_id}",
                headers=headers,
            )
            if targeted.status_code != 200 or targeted.json() != {
                "ok": True,
                "revoked": True,
            }:
                fail(f"targeted revoke failed: {targeted.status_code} {targeted.text}")
            targeted_again = client.delete(
                f"/api/auth/sessions/{target_id}",
                headers=headers,
            )
            if targeted_again.status_code != 200 or targeted_again.json() != {
                "ok": True,
                "revoked": False,
            }:
                fail(f"targeted revoke is not idempotent: {targeted_again.status_code} {targeted_again.text}")
            target_invalid = client.get(
                "/api/auth/profile",
                headers={"Authorization": f"Bearer {target_token}"},
            )
            if target_invalid.status_code != 401:
                fail("targeted revoked token still authenticates")

            db = SessionLocal()
            try:
                target_audits = list(
                    db.execute(
                        select(AuditLog).where(
                            AuditLog.id > audit_floor,
                            AuditLog.event_type == "auth.session_revoked",
                            AuditLog.entity_type == "session",
                            AuditLog.entity_id == target_id,
                        )
                    ).scalars()
                )
                if len(target_audits) != 1:
                    fail(f"targeted revoke should audit once, found {len(target_audits)}")
                if target_audits[0].metadata_json != {
                    "target_session_id": target_id,
                    "was_active": True,
                }:
                    fail(f"targeted revoke audit metadata mismatch: {target_audits[0].metadata_json}")

                user_row = db.get(User, user_id)
                bulk_one = create_session(
                    db,
                    user=user_row,
                    user_agent="Patch 584 bulk one",
                    ip_address="127.0.0.88",
                    commit=False,
                )
                bulk_two = create_session(
                    db,
                    user=user_row,
                    user_agent="Patch 584 bulk two",
                    ip_address="127.0.0.89",
                    commit=False,
                )
                db.commit()
                bulk_tokens = (bulk_one.token, bulk_two.token)
            finally:
                db.close()

            bulk = client.post(
                "/api/auth/sessions/revoke-all-other",
                headers=headers,
            )
            if bulk.status_code != 200 or bulk.json() != {
                "ok": True,
                "revoked_sessions": 2,
            }:
                fail(f"revoke-all-other failed: {bulk.status_code} {bulk.text}")
            bulk_again = client.post(
                "/api/auth/sessions/revoke-all-other",
                headers=headers,
            )
            if bulk_again.status_code != 200 or bulk_again.json() != {
                "ok": True,
                "revoked_sessions": 0,
            }:
                fail(f"revoke-all-other is not idempotent: {bulk_again.status_code} {bulk_again.text}")

            for bulk_token in bulk_tokens:
                response = client.get(
                    "/api/auth/profile",
                    headers={"Authorization": f"Bearer {bulk_token}"},
                )
                if response.status_code != 401:
                    fail("revoke-all-other left another active session usable")

            current_after_bulk = client.get("/api/auth/profile", headers=headers)
            if current_after_bulk.status_code != 200:
                fail("revoke-all-other revoked the exact current session")

            final_list = client.get("/api/auth/sessions", headers=headers)
            if final_list.status_code != 200:
                fail(f"final session list failed: {final_list.status_code} {final_list.text}")
            check_safe_session_shape(final_list.json(), current_id)
            active_rows = [item for item in final_list.json()["sessions"] if item["is_active"]]
            if [item["id"] for item in active_rows] != [current_id]:
                fail(f"unexpected active sessions after revoke-all-other: {active_rows}")
            if foreign_id in {item["id"] for item in final_list.json()["sessions"]}:
                fail("final session list leaked foreign ownership")

            db = SessionLocal()
            try:
                bulk_audits = list(
                    db.execute(
                        select(AuditLog).where(
                            AuditLog.id > audit_floor,
                            AuditLog.event_type == "auth.other_sessions_revoked",
                            AuditLog.entity_type == "user",
                            AuditLog.entity_id == user_id,
                        )
                    ).scalars()
                )
                if len(bulk_audits) != 1:
                    fail(f"revoke-all-other should audit once, found {len(bulk_audits)}")
                if bulk_audits[0].metadata_json != {
                    "revoked_sessions": 2,
                    "preserved_current_session_id": current_id,
                }:
                    fail(f"revoke-all-other audit metadata mismatch: {bulk_audits[0].metadata_json}")

                all_new_audits = list(
                    db.execute(select(AuditLog).where(AuditLog.id > audit_floor)).scalars()
                )
                serialized = json.dumps(
                    [
                        {
                            "event_type": row.event_type,
                            "summary": row.summary,
                            "before": row.before_json,
                            "after": row.after_json,
                            "metadata": row.metadata_json,
                        }
                        for row in all_new_audits
                    ],
                    sort_keys=True,
                )
                for secret_value in (
                    old_password,
                    new_password,
                    later_password,
                    current_token,
                    other_one_token,
                    other_two_token,
                    target_token,
                    initial_hash,
                ):
                    if secret_value in serialized:
                        fail("session/password audits exposed credential material")
                if "token_hash" in serialized or "password_hash" in serialized:
                    fail("session/password audits exposed credential field names")
            finally:
                db.close()

    finally:
        restore(backup_path)
        backup_path.unlink(missing_ok=True)

    if snapshot() != before:
        fail("exact logical restore failed after password/session smoke")

    print(
        "[PASS] password verification/reuse rules, atomic other-session revocation, "
        "current-session preservation, safe owned session listing, targeted and bulk "
        "idempotent revocation, secret-free audits and exact copied-database restore"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    check_only() if args.check_only else full()


if __name__ == "__main__":
    main()
