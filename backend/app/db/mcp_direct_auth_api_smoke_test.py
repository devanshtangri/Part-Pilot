from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AuditLog, McpDirectAuth, User, UserSession
from app.services.auth import create_session
from app.services.mcp_direct_auth import (
    validate_bearer_key,
    validate_custom_header_key,
)


# PARTPILOT:MCP_DIRECT_AUTH_API_SMOKE:V497
SECRET_FILE = Path("/data/.partpilot-instance-secret")


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def sqlite_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"SQLite required, got {url!r}")
    return Path(url[len(prefix) :]).resolve()


def snapshot() -> dict[str, object]:
    connection = sqlite3.connect(sqlite_path())
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
        has_sequence = connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='sqlite_sequence'"
        ).fetchone() is not None
        sequences = (
            [
                tuple(row)
                for row in connection.execute(
                    "SELECT name,seq FROM sqlite_sequence ORDER BY name"
                )
            ]
            if has_sequence
            else []
        )
        return {
            "rows": rows,
            "has_sequence": has_sequence,
            "sequences": sequences,
        }
    finally:
        connection.close()


def restore_direct_policy_rows(before: dict[str, object]) -> None:
    connection = sqlite3.connect(sqlite_path())
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("DELETE FROM mcp_direct_auth")
        for row in before["rows"]["mcp_direct_auth"]:
            columns = list(row)
            placeholders = ",".join("?" for _ in columns)
            connection.execute(
                f'INSERT INTO mcp_direct_auth ({",".join(columns)}) VALUES ({placeholders})',
                tuple(row[column] for column in columns),
            )
        keys = ("mcp.direct_clients_enabled", "mcp.direct_no_auth_enabled")
        connection.executemany("DELETE FROM app_settings WHERE key=?", [(key,) for key in keys])
        baseline_settings = [
            row
            for row in before["rows"]["app_settings"]
            if row["key"] in keys
        ]
        for row in baseline_settings:
            columns = list(row)
            placeholders = ",".join("?" for _ in columns)
            connection.execute(
                f'INSERT INTO app_settings ({",".join(columns)}) VALUES ({placeholders})',
                tuple(row[column] for column in columns),
            )
        connection.commit()
    finally:
        connection.close()


def restore_sequences(before: dict[str, object]) -> None:
    connection = sqlite3.connect(sqlite_path())
    try:
        has_sequence = connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='sqlite_sequence'"
        ).fetchone() is not None
        if before["has_sequence"]:
            if not has_sequence:
                fail("sqlite_sequence disappeared during smoke cleanup")
            connection.execute("DELETE FROM sqlite_sequence")
            connection.executemany(
                "INSERT INTO sqlite_sequence(name,seq) VALUES (?,?)",
                before["sequences"],
            )
            connection.commit()
        elif has_sequence:
            current = [
                tuple(row)
                for row in connection.execute(
                    "SELECT name,seq FROM sqlite_sequence ORDER BY name"
                )
            ]
            if current:
                fail(f"Smoke unexpectedly created sequence rows: {current}")
    finally:
        connection.close()


def assert_no_store(response) -> None:
    if (
        response.headers.get("cache-control") != "no-store"
        or response.headers.get("pragma") != "no-cache"
    ):
        fail("Direct-auth response is cacheable")


def assert_status_shape(
    payload: dict[str, object],
    *,
    mode: str,
    configured: bool,
    custom_header_name: str | None,
    trusted_networks: list[str] | None = None,
) -> None:
    if payload.get("mode") != mode:
        fail(f"Unexpected direct-auth mode: {payload}")
    if payload.get("configured") is not configured:
        fail(f"Unexpected direct-auth configured state: {payload}")
    if payload.get("custom_header_name") != custom_header_name:
        fail(f"Unexpected custom header name: {payload}")
    if payload.get("trusted_networks") != (trusted_networks or []):
        fail(f"Unexpected trusted networks: {payload}")


def main() -> None:
    before = snapshot()
    secret_before = SECRET_FILE.read_bytes() if SECRET_FILE.exists() else None
    db = SessionLocal()
    session_id = None
    baseline_audit_id = 0
    issued_keys: list[str] = []
    try:
        user = db.execute(
            select(User).where(User.is_active.is_(True)).order_by(User.id)
        ).scalars().first()
        if user is None:
            fail("One active user is required")
        baseline_audit_id = int(
            db.execute(select(func.max(AuditLog.id))).scalar() or 0
        )
        issued = create_session(
            db,
            user=user,
            user_agent="Patch 497 direct-auth API smoke",
            ip_address="127.0.0.1",
            commit=False,
        )
        session_id = issued.session.id
        db.commit()
        headers = {"Authorization": f"Bearer {issued.token}"}

        from app.main import app

        with TestClient(app) as client:
            protected = (
                ("get", "/api/settings/mcp/direct-auth", None),
                ("post", "/api/settings/mcp/direct-auth/bearer-key", None),
                ("post", "/api/settings/mcp/direct-auth/custom-header", {}),
                ("post", "/api/settings/mcp/direct-auth/reveal", None),
                ("delete", "/api/settings/mcp/direct-auth", None),
            )
            for method, path, body in protected:
                request = getattr(client, method)
                response = (
                    request(path)
                    if body is None
                    else request(path, json=body)
                )
                if response.status_code != 401:
                    fail(
                        f"Unauthenticated {method} {path}: "
                        f"{response.status_code}"
                    )

            initial = client.get(
                "/api/settings/mcp/direct-auth",
                headers=headers,
            )
            assert_no_store(initial)
            if initial.status_code != 200:
                fail(f"Initial status failed: {initial.status_code} {initial.text}")
            expected_initial = {
                "mode": "disabled",
                "configured": False,
                "masked_key": None,
                "custom_header_name": None,
                "trusted_networks": [],
                "rotated_at": None,
                "last_used_at": None,
            }
            if initial.json() != expected_initial:
                fail(f"Bad initial status: {initial.text}")

            for invalid_header in (
                "authorization",
                "x-forwarded-for",
                "x bad header",
            ):
                invalid = client.post(
                    "/api/settings/mcp/direct-auth/custom-header",
                    headers=headers,
                    json={"header_name": invalid_header},
                )
                assert_no_store(invalid)
                if invalid.status_code != 422:
                    fail(
                        f"Unsafe header {invalid_header!r} returned "
                        f"{invalid.status_code}: {invalid.text}"
                    )

            custom = client.post(
                "/api/settings/mcp/direct-auth/custom-header",
                headers=headers,
                json={"header_name": " X-PartPilot-MCP-Key "},
            )
            assert_no_store(custom)
            if custom.status_code != 200:
                fail(
                    f"Custom-header rotation failed: "
                    f"{custom.status_code} {custom.text}"
                )
            custom_body = custom.json()
            custom_key = custom_body.get("key")
            if (
                not isinstance(custom_key, str)
                or not custom_key.startswith("pp_mcp_header_")
            ):
                fail("Custom-header rotation returned an invalid key")
            issued_keys.append(custom_key)
            assert_status_shape(
                custom_body,
                mode="custom_header",
                configured=True,
                custom_header_name="x-partpilot-mcp-key",
            )
            if custom_key in str(custom_body.get("masked_key")):
                fail("Custom-header status leaked plaintext")

            verify_custom = SessionLocal()
            try:
                if not validate_custom_header_key(
                    verify_custom,
                    custom_key,
                    touch=False,
                    commit=False,
                ):
                    fail("Custom-header API key was rejected")
                if validate_bearer_key(
                    verify_custom,
                    custom_key,
                    touch=False,
                    commit=False,
                ):
                    fail("Custom-header API key was accepted as Bearer")
            finally:
                verify_custom.rollback()
                verify_custom.close()

            reveal_custom = client.post(
                "/api/settings/mcp/direct-auth/reveal",
                headers=headers,
            )
            assert_no_store(reveal_custom)
            if (
                reveal_custom.status_code != 200
                or reveal_custom.json().get("key") != custom_key
            ):
                fail(
                    f"Custom-header reveal failed: "
                    f"{reveal_custom.status_code} {reveal_custom.text}"
                )

            bearer = client.post(
                "/api/settings/mcp/direct-auth/bearer-key",
                headers=headers,
            )
            assert_no_store(bearer)
            if bearer.status_code != 200:
                fail(f"Bearer rotation failed: {bearer.status_code} {bearer.text}")
            bearer_body = bearer.json()
            bearer_key = bearer_body.get("key")
            if (
                not isinstance(bearer_key, str)
                or not bearer_key.startswith("pp_mcp_key_")
            ):
                fail("Bearer rotation returned an invalid key")
            issued_keys.append(bearer_key)
            assert_status_shape(
                bearer_body,
                mode="bearer_key",
                configured=True,
                custom_header_name=None,
            )

            verify_bearer = SessionLocal()
            try:
                if validate_custom_header_key(
                    verify_bearer,
                    custom_key,
                    touch=False,
                    commit=False,
                ):
                    fail("Custom-header key survived Bearer mode switch")
                if not validate_bearer_key(
                    verify_bearer,
                    bearer_key,
                    touch=False,
                    commit=False,
                ):
                    fail("New Bearer key was rejected")
            finally:
                verify_bearer.rollback()
                verify_bearer.close()

            custom_two = client.post(
                "/api/settings/mcp/direct-auth/custom-header",
                headers=headers,
                json={"header_name": "X-PartPilot-Lab-Key"},
            )
            assert_no_store(custom_two)
            if custom_two.status_code != 200:
                fail(
                    f"Second custom-header rotation failed: "
                    f"{custom_two.status_code} {custom_two.text}"
                )
            custom_two_body = custom_two.json()
            custom_key_two = custom_two_body.get("key")
            if not isinstance(custom_key_two, str) or custom_key_two == custom_key:
                fail("Second custom-header rotation did not issue a fresh key")
            issued_keys.append(custom_key_two)
            assert_status_shape(
                custom_two_body,
                mode="custom_header",
                configured=True,
                custom_header_name="x-partpilot-lab-key",
            )

            reveal_custom_two = client.post(
                "/api/settings/mcp/direct-auth/reveal",
                headers=headers,
            )
            assert_no_store(reveal_custom_two)
            if reveal_custom_two.json().get("key") != custom_key_two:
                fail("Generic reveal returned the wrong custom-header key")

            disabled = client.delete(
                "/api/settings/mcp/direct-auth",
                headers=headers,
            )
            assert_no_store(disabled)
            if disabled.status_code != 200:
                fail(f"Disable failed: {disabled.status_code} {disabled.text}")
            assert_status_shape(
                disabled.json(),
                mode="disabled",
                configured=False,
                custom_header_name=None,
            )
            repeated = client.delete(
                "/api/settings/mcp/direct-auth",
                headers=headers,
            )
            if repeated.status_code != 200:
                fail("Repeated disable failed")

        audits = db.execute(
            select(AuditLog)
            .where(AuditLog.id > baseline_audit_id)
            .order_by(AuditLog.id)
        ).scalars().all()
        events = [row.event_type for row in audits]
        expected_events = [
            "settings.mcp_custom_header_key_rotated",
            "settings.mcp_custom_header_key_revealed",
            "settings.mcp_direct_key_rotated",
            "settings.mcp_custom_header_key_rotated",
            "settings.mcp_custom_header_key_revealed",
            "settings.mcp_direct_auth_disabled",
        ]
        if events != expected_events:
            fail(f"Unexpected API audit events: {events}")
        payload = json.dumps(
            [
                {
                    "event": row.event_type,
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
        if any(key in payload for key in issued_keys):
            fail("API audit leaked a direct-auth credential")
        if any(
            row.actor_type != "user" or row.actor_user_id != user.id
            for row in audits
        ):
            fail("API audit actor mismatch")

        cleanup = SessionLocal()
        try:
            cleanup.query(AuditLog).filter(
                AuditLog.id > baseline_audit_id
            ).delete(synchronize_session=False)
            if session_id is not None:
                row = cleanup.get(UserSession, session_id)
                if row is not None:
                    cleanup.delete(row)
            cleanup.commit()
        finally:
            cleanup.close()
        restore_direct_policy_rows(before)
        restore_sequences(before)
        if snapshot() != before:
            fail("Database cleanup mismatch")
    finally:
        db.rollback()
        db.close()
        if secret_before is None:
            SECRET_FILE.unlink(missing_ok=True)
        else:
            SECRET_FILE.write_bytes(secret_before)
            os.chmod(SECRET_FILE, 0o600)

    print("MCP direct auth API smoke PASS")


if __name__ == "__main__":
    main()
