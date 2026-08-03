from __future__ import annotations

import argparse
import copy
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AppSetting, AuditLog, User, UserSession
from app.services.app_settings import get_mcp_settings
from app.services.auth import create_session
from app.services.mcp_oauth import MCP_SCOPE_READ, MCP_SCOPE_WRITE, available_scopes


# PARTPILOT:MCP_SETTINGS_SMOKE:V473
SETTING_KEYS = (
    "mcp.enabled",
    "mcp.read_tools_enabled",
    "mcp.write_tools_enabled",
)


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def sqlite_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"MCP settings smoke requires SQLite, got {url!r}")
    return Path(url[len(prefix):]).resolve()


def database_snapshot() -> dict[str, object]:
    db = sqlite3.connect(sqlite_path())
    db.row_factory = sqlite3.Row
    try:
        tables = [
            str(row[0])
            for row in db.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            )
        ]
        rows = {
            table: [
                {key: row[key] for key in row.keys()}
                for row in db.execute(
                    f'SELECT * FROM "{table}" ORDER BY rowid'
                )
            ]
            for table in tables
        }
        has_sequences = db.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='sqlite_sequence'"
        ).fetchone()
        sequences = (
            [
                tuple(row)
                for row in db.execute(
                    "SELECT name,seq FROM sqlite_sequence ORDER BY name"
                )
            ]
            if has_sequences
            else []
        )
        return {"rows": rows, "sequences": sequences}
    finally:
        db.close()


def restore_sequences(snapshot: dict[str, object]) -> None:
    db = sqlite3.connect(sqlite_path())
    try:
        has_sequences = db.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='sqlite_sequence'"
        ).fetchone()
        if has_sequences:
            db.execute("DELETE FROM sqlite_sequence")
            for name, sequence in snapshot["sequences"]:
                db.execute(
                    "INSERT INTO sqlite_sequence(name,seq) VALUES (?,?)",
                    (name, sequence),
                )
            db.commit()
    finally:
        db.close()


def check_only() -> None:
    from app.main import app

    with TestClient(app) as client:
        unauthenticated_get = client.get("/api/settings/mcp")
        if unauthenticated_get.status_code != 401:
            fail(
                "GET /api/settings/mcp should require authentication, "
                f"got {unauthenticated_get.status_code}"
            )
        unauthenticated_patch = client.patch(
            "/api/settings/mcp",
            json={
                "enabled": True,
                "read_tools_enabled": True,
                "write_tools_enabled": False,
            },
        )
        if unauthenticated_patch.status_code != 401:
            fail(
                "PATCH /api/settings/mcp should require authentication, "
                f"got {unauthenticated_patch.status_code}"
            )
        openapi = client.get("/openapi.json")
        if openapi.status_code != 200:
            fail("OpenAPI document is unavailable")
        methods = openapi.json().get("paths", {}).get(
            "/api/settings/mcp", {}
        )
        if set(methods) != {"get", "patch"}:
            fail(f"Unexpected MCP settings OpenAPI methods: {methods}")

    print(
        "[PASS] MCP settings GET/PATCH routes are protected and present in OpenAPI"
    )


def full_flow() -> None:
    before = database_snapshot()
    db = SessionLocal()
    session_id: int | None = None
    audit_ids: list[int] = []
    originals: dict[str, tuple[object, object, object]] = {}
    try:
        user = db.execute(select(User).order_by(User.id.asc())).scalars().first()
        if user is None:
            fail("MCP settings smoke requires one existing user")

        for key in SETTING_KEYS:
            setting = db.execute(
                select(AppSetting).where(AppSetting.key == key)
            ).scalar_one_or_none()
            if setting is None:
                fail(f"Required MCP setting is missing: {key}")
            originals[key] = (
                copy.deepcopy(setting.value_json),
                setting.value_text,
                setting.updated_at,
            )

        initial = get_mcp_settings(db)
        existing_audit_ids = set(
            db.execute(
                select(AuditLog.id).where(
                    AuditLog.event_type == "settings.mcp_updated"
                )
            ).scalars()
        )
        session_token = create_session(
            db,
            user=user,
            user_agent="Patch 473 MCP settings smoke",
            ip_address="127.0.0.1",
            commit=False,
        )
        session_id = session_token.session.id
        db.commit()
        headers = {"Authorization": f"Bearer {session_token.token}"}

        from app.main import app

        with TestClient(app) as client:
            loaded = client.get("/api/settings/mcp", headers=headers)
            if loaded.status_code != 200:
                fail(
                    f"GET /api/settings/mcp returned {loaded.status_code}: "
                    f"{loaded.text[:500]}"
                )
            if loaded.json() != initial.model_dump(mode="json"):
                fail("MCP settings GET differs from the canonical service")

            invalid = client.patch(
                "/api/settings/mcp",
                headers=headers,
                json={
                    "enabled": True,
                    "read_tools_enabled": True,
                    "write_tools_enabled": False,
                    "unexpected": True,
                },
            )
            if invalid.status_code != 422:
                fail(f"Extra MCP settings field returned {invalid.status_code}")

            enabled_payload = {
                "enabled": True,
                "read_tools_enabled": True,
                "write_tools_enabled": False,
            }
            enabled = client.patch(
                "/api/settings/mcp",
                headers=headers,
                json=enabled_payload,
            )
            if enabled.status_code != 200 or enabled.json() != enabled_payload:
                fail(
                    f"Enabling MCP failed: {enabled.status_code} "
                    f"{enabled.text[:500]}"
                )

            enabled_db = SessionLocal()
            try:
                scopes = available_scopes(enabled_db, require_enabled=True)
                if scopes != {MCP_SCOPE_READ}:
                    fail(f"Unexpected enabled MCP scopes: {sorted(scopes)}")
            finally:
                enabled_db.close()

            unchanged = client.patch(
                "/api/settings/mcp",
                headers=headers,
                json=enabled_payload,
            )
            if unchanged.status_code != 200:
                fail("Unchanged MCP settings PATCH failed")

            write_payload = {
                "enabled": True,
                "read_tools_enabled": True,
                "write_tools_enabled": True,
            }
            write_enabled = client.patch(
                "/api/settings/mcp",
                headers=headers,
                json=write_payload,
            )
            if (
                write_enabled.status_code != 200
                or write_enabled.json() != write_payload
            ):
                fail("Enabling MCP write authorization failed")

            write_db = SessionLocal()
            try:
                scopes = available_scopes(write_db, require_enabled=True)
                if scopes != {MCP_SCOPE_READ, MCP_SCOPE_WRITE}:
                    fail(f"Unexpected MCP read/write scopes: {sorted(scopes)}")
            finally:
                write_db.close()

            disabled_payload = {
                "enabled": False,
                "read_tools_enabled": True,
                "write_tools_enabled": False,
            }
            disabled = client.patch(
                "/api/settings/mcp",
                headers=headers,
                json=disabled_payload,
            )
            if disabled.status_code != 200 or disabled.json() != disabled_payload:
                fail("Restoring disabled MCP settings through the API failed")

        audit_db = SessionLocal()
        try:
            new_audits = list(
                audit_db.execute(
                    select(AuditLog)
                    .where(AuditLog.event_type == "settings.mcp_updated")
                    .order_by(AuditLog.id.asc())
                ).scalars()
            )
            new_audits = [
                row
                for row in new_audits
                if row.id not in existing_audit_ids
            ]
            if len(new_audits) != 3:
                fail(
                    "MCP settings should create one audit per real change; "
                    f"got {len(new_audits)}"
                )
            audit_ids = [row.id for row in new_audits]
            for row in new_audits:
                if row.actor_type != "user" or row.actor_user_id != user.id:
                    fail("MCP settings audit actor attribution is incorrect")
                if not isinstance(row.before_json, dict) or not isinstance(
                    row.after_json, dict
                ):
                    fail("MCP settings audit snapshots are missing")
                metadata = row.metadata_json
                if not isinstance(metadata, dict):
                    fail("MCP settings audit metadata is missing")
                if metadata.get("setting_keys") != list(SETTING_KEYS):
                    fail("MCP settings audit keys are incorrect")
                changed = metadata.get("changed_fields")
                if not isinstance(changed, list) or not changed:
                    fail("MCP settings audit changed_fields are missing")
        finally:
            audit_db.close()

        cleanup = SessionLocal()
        try:
            for key, (value_json, value_text, updated_at) in originals.items():
                setting = cleanup.execute(
                    select(AppSetting).where(AppSetting.key == key)
                ).scalar_one()
                setting.value_json = copy.deepcopy(value_json)
                setting.value_text = value_text
                setting.updated_at = updated_at
            if audit_ids:
                cleanup.query(AuditLog).filter(
                    AuditLog.id.in_(audit_ids)
                ).delete(synchronize_session=False)
            if session_id is not None:
                session = cleanup.get(UserSession, session_id)
                if session is not None:
                    cleanup.delete(session)
            cleanup.commit()
        finally:
            cleanup.close()

        restore_sequences(before)
        if database_snapshot() != before:
            fail("MCP settings smoke did not restore the exact database snapshot")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(
        "[PASS] MCP settings API persists enabled/read/write controls, enforces "
        "authentication, updates OAuth scopes immediately, audits real changes, "
        "and cleans up exactly"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if args.check_only:
        check_only()
    else:
        full_flow()


if __name__ == "__main__":
    main()
