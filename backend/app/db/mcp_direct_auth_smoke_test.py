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
    DEFAULT_CUSTOM_HEADER_NAME,
    McpDirectAuthConfigurationError,
    McpDirectAuthDecryptionError,
    McpDirectAuthHeaderNameError,
    disable_direct_auth,
    reveal_bearer_key,
    reveal_custom_header_key,
    reveal_direct_key,
    rotate_bearer_key,
    rotate_custom_header_key,
    validate_bearer_key,
    validate_custom_header_key,
    validate_custom_header_name,
)


# PARTPILOT:MCP_DIRECT_AUTH_SMOKE:V497
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
        baseline_audit_id = int(
            db.execute(select(func.max(AuditLog.id))).scalar() or 0
        )
        actor = db.execute(
            select(User).where(User.is_active.is_(True)).order_by(User.id)
        ).scalars().first()
        if actor is None:
            fail("MCP direct-auth smoke requires one active user")
        if baseline_records != 0:
            fail("MCP direct-auth smoke requires an unconfigured copied database")

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

        if validate_custom_header_name(" X-PartPilot-MCP-Key ") != DEFAULT_CUSTOM_HEADER_NAME:
            fail("Custom header name was not canonicalized")
        for invalid_name in (
            "",
            "   ",
            "x bad header",
            "authorization",
            "cookie",
            "x-forwarded-for",
            "x-real-ip",
            "x" * 121,
        ):
            try:
                validate_custom_header_name(invalid_name)
            except McpDirectAuthHeaderNameError:
                pass
            else:
                fail(f"Unsafe custom header name was accepted: {invalid_name!r}")

        bearer = rotate_bearer_key(
            db,
            actor_user_id=actor.id,
            instance_secret=SECRET_A,
            commit=False,
        )
        bearer_key = bearer.plaintext_key
        if not bearer_key.startswith("pp_mcp_key_"):
            fail("Generated Bearer key prefix is incorrect")
        if bearer_key in (bearer.record.key_ciphertext or ""):
            fail("Plaintext Bearer key appears in ciphertext")
        if reveal_bearer_key(db, instance_secret=SECRET_A) != bearer_key:
            fail("Encrypted Bearer key did not round-trip")
        if reveal_direct_key(db, instance_secret=SECRET_A) != bearer_key:
            fail("Generic reveal rejected the Bearer mode")
        try:
            reveal_bearer_key(db, instance_secret=SECRET_B)
        except McpDirectAuthDecryptionError:
            pass
        else:
            fail("Wrong instance secret decrypted the Bearer key")
        if not validate_bearer_key(
            db,
            bearer_key,
            instance_secret=SECRET_A,
            touch=False,
            commit=False,
        ):
            fail("Correct Bearer key was rejected")

        custom = rotate_custom_header_key(
            db,
            actor_user_id=actor.id,
            header_name=" X-PartPilot-MCP-Key ",
            instance_secret=SECRET_A,
            commit=False,
        )
        custom_key = custom.plaintext_key
        if not custom_key.startswith("pp_mcp_header_"):
            fail("Generated custom-header key prefix is incorrect")
        if custom.record.mode != "custom_header":
            fail("Custom-header rotation stored the wrong mode")
        if custom.record.custom_header_name != DEFAULT_CUSTOM_HEADER_NAME:
            fail("Custom-header rotation stored the wrong header name")
        if custom_key in (custom.record.key_ciphertext or ""):
            fail("Plaintext custom-header key appears in ciphertext")
        if reveal_custom_header_key(db, instance_secret=SECRET_A) != custom_key:
            fail("Encrypted custom-header key did not round-trip")
        if reveal_direct_key(db, instance_secret=SECRET_A) != custom_key:
            fail("Generic reveal rejected custom-header mode")
        if validate_bearer_key(
            db,
            bearer_key,
            instance_secret=SECRET_A,
            touch=False,
            commit=False,
        ):
            fail("Switching modes did not invalidate the Bearer key")
        if validate_bearer_key(
            db,
            custom_key,
            instance_secret=SECRET_A,
            touch=False,
            commit=False,
        ):
            fail("Custom-header key was accepted by Bearer validation")
        if not validate_custom_header_key(
            db,
            custom_key,
            instance_secret=SECRET_A,
            touch=True,
            commit=False,
        ):
            fail("Correct custom-header key was rejected")
        if custom.record.last_used_at is None:
            fail("Custom-header validation did not touch last_used_at")
        if validate_custom_header_key(
            db,
            custom_key + "wrong",
            instance_secret=SECRET_A,
            touch=False,
            commit=False,
        ):
            fail("Wrong custom-header key was accepted")

        custom_two = rotate_custom_header_key(
            db,
            actor_user_id=actor.id,
            header_name="X-PartPilot-Lab-Key",
            instance_secret=SECRET_A,
            commit=False,
        )
        if custom_two.plaintext_key == custom_key:
            fail("Custom-header rotation reused old key material")
        if custom_two.record.custom_header_name != "x-partpilot-lab-key":
            fail("Custom-header rotation did not update the header name")
        if validate_custom_header_key(
            db,
            custom_key,
            instance_secret=SECRET_A,
            touch=False,
            commit=False,
        ):
            fail("Custom-header rotation did not invalidate the old key")

        bearer_two = rotate_bearer_key(
            db,
            actor_user_id=actor.id,
            instance_secret=SECRET_A,
            commit=False,
        )
        if not validate_bearer_key(
            db,
            bearer_two.plaintext_key,
            instance_secret=SECRET_A,
            touch=False,
            commit=False,
        ):
            fail("Bearer mode did not work after custom-header mode")
        if validate_custom_header_key(
            db,
            custom_two.plaintext_key,
            instance_secret=SECRET_A,
            touch=False,
            commit=False,
        ):
            fail("Switching back to Bearer did not invalidate custom-header key")

        audit_count_before_disable = int(db.query(AuditLog).count())
        if not disable_direct_auth(db, actor_user_id=actor.id, commit=False):
            fail("Configured direct auth was not disabled")
        if int(db.query(AuditLog).count()) != audit_count_before_disable + 1:
            fail("Disable did not create exactly one audit")
        if disable_direct_auth(db, actor_user_id=actor.id, commit=False):
            fail("Repeated disable was not a no-op")

        audits = db.execute(
            select(AuditLog)
            .where(AuditLog.id > baseline_audit_id)
            .order_by(AuditLog.id)
        ).scalars().all()
        events = [row.event_type for row in audits]
        expected_events = [
            "settings.mcp_direct_key_rotated",
            "settings.mcp_custom_header_key_rotated",
            "settings.mcp_custom_header_key_rotated",
            "settings.mcp_direct_key_rotated",
            "settings.mcp_direct_auth_disabled",
        ]
        if events != expected_events:
            fail(f"Unexpected direct-auth service audit events: {events}")
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
        for secret in (
            bearer_key,
            custom_key,
            custom_two.plaintext_key,
            bearer_two.plaintext_key,
        ):
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
