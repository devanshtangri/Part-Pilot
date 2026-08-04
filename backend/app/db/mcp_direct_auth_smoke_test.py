from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal
from app.models import AuditLog, McpDirectAuth, User
from app.services.mcp_direct_auth import (
    McpDirectAuthConfigurationError,
    McpDirectAuthDecryptionError,
    disable_direct_auth,
    reveal_bearer_key,
    rotate_bearer_key,
    validate_bearer_key,
)


# PARTPILOT:MCP_DIRECT_AUTH_SMOKE:V482
EXPECTED_HEAD = "0009_mcp_direct_auth"
SECRET_A = "patch482-direct-auth-secret-A-0123456789-ABCDEFGHIJKLMN"
SECRET_B = "patch482-direct-auth-secret-B-0123456789-ABCDEFGHIJKLMN"


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def sqlite_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"MCP direct-auth smoke requires SQLite, got {url!r}")
    return Path(url[len(prefix):]).resolve()


def check_schema() -> None:
    db = sqlite3.connect(sqlite_path())
    try:
        head = db.execute("SELECT version_num FROM alembic_version").fetchone()
        if head is None or str(head[0]) != EXPECTED_HEAD:
            fail(f"Expected Alembic {EXPECTED_HEAD}, got {head}")
        if str(db.execute("PRAGMA integrity_check").fetchone()[0]).lower() != "ok":
            fail("SQLite integrity_check failed")
        violations = list(db.execute("PRAGMA foreign_key_check"))
        if violations:
            fail(f"Foreign-key violations: {violations[:20]}")
        expected = {
            "id", "mode", "key_ciphertext", "key_digest", "key_prefix",
            "custom_header_name", "rotated_at", "last_used_at",
            "created_at", "updated_at",
        }
        columns = {str(row[1]) for row in db.execute('PRAGMA table_info("mcp_direct_auth")')}
        if columns != expected:
            fail(f"Unexpected mcp_direct_auth columns: {sorted(columns)}")
        row = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='mcp_direct_auth'"
        ).fetchone()
        if row is None:
            fail("mcp_direct_auth table is missing")
        sql = str(row[0])
        for marker in (
            "ck_mcp_direct_auth_singleton",
            "ck_mcp_direct_auth_mode",
            "ck_mcp_direct_auth_key_bundle",
            "ck_mcp_direct_auth_mode_fields",
            "uq_mcp_direct_auth_key_digest",
        ):
            if marker not in sql:
                fail(f"mcp_direct_auth is missing {marker}")
        indexes = {str(row[1]) for row in db.execute('PRAGMA index_list("mcp_direct_auth")')}
        for marker in ("ix_mcp_direct_auth_mode", "ix_mcp_direct_auth_last_used_at"):
            if marker not in indexes:
                fail(f"mcp_direct_auth is missing {marker}")
        if "mcp_direct_auth" not in Base.metadata.tables:
            fail("ORM metadata is missing mcp_direct_auth")
        if set(Base.metadata.tables["mcp_direct_auth"].columns.keys()) != expected:
            fail("ORM/database direct-auth columns differ")
    finally:
        db.close()


def check_service() -> None:
    db = SessionLocal()
    try:
        baseline_records = int(db.query(McpDirectAuth).count())
        baseline_audits = int(db.query(AuditLog).count())
        baseline_audit_id = int(db.execute(select(func.max(AuditLog.id))).scalar() or 0)
        actor = db.execute(
            select(User).where(User.is_active.is_(True)).order_by(User.id)
        ).scalars().first()
        if actor is None:
            fail("MCP direct-auth smoke requires one active user")
        if baseline_records != 0:
            fail("Live MCP direct-auth table must be empty before configuration")
        try:
            rotate_bearer_key(
                db,
                actor_user_id=actor.id,
                instance_secret="too-short",
                commit=False,
            )
        except McpDirectAuthConfigurationError:
            pass
        else:
            fail("Short instance secret was accepted")
        first = rotate_bearer_key(
            db,
            actor_user_id=actor.id,
            instance_secret=SECRET_A,
            commit=False,
        )
        if not first.plaintext_key.startswith("pp_mcp_key_"):
            fail("Generated key prefix is incorrect")
        if first.plaintext_key in (first.record.key_ciphertext or ""):
            fail("Plaintext key appears in ciphertext")
        if reveal_bearer_key(db, instance_secret=SECRET_A) != first.plaintext_key:
            fail("Encrypted key did not round-trip")
        try:
            reveal_bearer_key(db, instance_secret=SECRET_B)
        except McpDirectAuthDecryptionError:
            pass
        else:
            fail("Wrong instance secret decrypted the key")
        if not validate_bearer_key(
            db, first.plaintext_key, instance_secret=SECRET_A, touch=False, commit=False
        ):
            fail("Correct direct key was rejected")
        if validate_bearer_key(
            db, first.plaintext_key + "wrong", instance_secret=SECRET_A, touch=False, commit=False
        ):
            fail("Wrong direct key was accepted")
        first_key = first.plaintext_key
        first_digest = first.record.key_digest
        second = rotate_bearer_key(
            db,
            actor_user_id=actor.id,
            instance_secret=SECRET_A,
            commit=False,
        )
        if second.plaintext_key == first_key or second.record.key_digest == first_digest:
            fail("Rotation reused old key material")
        if validate_bearer_key(
            db, first_key, instance_secret=SECRET_A, touch=False, commit=False
        ):
            fail("Rotation did not invalidate the old key")
        if not validate_bearer_key(
            db, second.plaintext_key, instance_secret=SECRET_A, touch=True, commit=False
        ):
            fail("Rotated key was rejected")
        if second.record.last_used_at is None:
            fail("Successful validation did not touch last_used_at")
        audit_count_before_disable = int(db.query(AuditLog).count())
        if not disable_direct_auth(db, actor_user_id=actor.id, commit=False):
            fail("Configured direct auth was not disabled")
        if int(db.query(AuditLog).count()) != audit_count_before_disable + 1:
            fail("Disable did not create exactly one audit")
        if disable_direct_auth(db, actor_user_id=actor.id, commit=False):
            fail("Repeated disable was not a no-op")
        audits = db.execute(
            select(AuditLog).where(AuditLog.id > baseline_audit_id).order_by(AuditLog.id)
        ).scalars().all()
        payload = json.dumps(
            [
                {
                    "event_type": row.event_type,
                    "summary": row.summary,
                    "before": row.before_json,
                    "after": row.after_json,
                    "metadata": row.metadata_json,
                }
                for row in audits
            ],
            sort_keys=True,
            default=str,
        )
        for secret in (first_key, second.plaintext_key):
            if secret in payload:
                fail("Plaintext direct key leaked into audit content")
    finally:
        db.rollback()
        db.close()
    verify = SessionLocal()
    try:
        if int(verify.query(McpDirectAuth).count()) != baseline_records:
            fail("Direct-auth smoke left credential rows behind")
        if int(verify.query(AuditLog).count()) != baseline_audits:
            fail("Direct-auth smoke left audit rows behind")
    finally:
        verify.close()


def main() -> None:
    check_schema()
    check_service()
    print("MCP direct auth smoke PASS")


if __name__ == "__main__":
    main()
