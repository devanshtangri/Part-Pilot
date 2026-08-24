from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
from pathlib import Path
import sqlite3
import stat

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.db.settings import set_app_setting
from app.models import AppSetting, AuditLog, McpDirectAuth, Part, Project, Reservation, User
from app.services.mcp_direct_auth import (
    DEFAULT_CUSTOM_HEADER_NAME,
    DIRECT_AUTH_SINGLETON_ID,
    rotate_bearer_key,
    rotate_custom_header_key,
)
from app.services.mcp_oauth import (
    MCP_ENABLED_KEY,
    MCP_READ_ENABLED_KEY,
    MCP_WRITE_ENABLED_KEY,
)


# PARTPILOT:MCP_DIRECT_CUSTOM_HEADER_TRANSPORT_SMOKE:V499
RESOURCE = "https://partpilot.example/mcp"
EXPECTED_TOOLS = {
    "search_parts",
    "get_part_details",
    "list_projects",
    "get_project_details",
    "list_reservations",
    "get_reservation_details",
}
REGISTERED_TOOLS = EXPECTED_TOOLS | {
    "reserve_project",
    "consume_reservation",
    "cancel_reservation",
}


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def sqlite_path() -> Path:
    value = get_settings().database_url
    prefix = "sqlite:///"
    if not value.startswith(prefix):
        fail(f"Custom-header transport smoke requires SQLite, got {value!r}")
    return Path(value[len(prefix):]).resolve()


def database_snapshot() -> dict[str, object]:
    connection = sqlite3.connect(sqlite_path())
    connection.row_factory = sqlite3.Row
    try:
        tables = [
            str(row[0])
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
        has_sequences = connection.execute(
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
            if has_sequences
            else []
        )
        return {
            "rows": rows,
            "has_sequences": has_sequences,
            "sequences": sequences,
        }
    finally:
        connection.close()


def restore_sequences(before: dict[str, object]) -> None:
    connection = sqlite3.connect(sqlite_path())
    try:
        has_sequences = connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='sqlite_sequence'"
        ).fetchone() is not None
        if before["has_sequences"]:
            if not has_sequences:
                fail("sqlite_sequence disappeared during custom-header smoke")
            connection.execute("DELETE FROM sqlite_sequence")
            connection.executemany(
                "INSERT INTO sqlite_sequence(name,seq) VALUES (?,?)",
                before["sequences"],
            )
            connection.commit()
        elif has_sequences:
            current = [
                tuple(row)
                for row in connection.execute(
                    "SELECT name,seq FROM sqlite_sequence ORDER BY name"
                )
            ]
            if current:
                fail(f"Custom-header smoke created sequence rows: {current}")
    finally:
        connection.close()


def restore_direct_baseline(before: dict[str, object]) -> None:
    connection = sqlite3.connect(sqlite_path())
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("DELETE FROM mcp_direct_auth")
        for row in before["rows"]["mcp_direct_auth"]:
            columns = list(row)
            connection.execute(
                f'INSERT INTO mcp_direct_auth ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})',
                tuple(row[column] for column in columns),
            )
        keys = ("mcp.direct_clients_enabled", "mcp.direct_no_auth_enabled")
        connection.executemany("DELETE FROM app_settings WHERE key=?", [(key,) for key in keys])
        for row in before["rows"]["app_settings"]:
            if row["key"] not in keys:
                continue
            columns = list(row)
            connection.execute(
                f'INSERT INTO app_settings ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})',
                tuple(row[column] for column in columns),
            )
        connection.commit()
    finally:
        connection.close()


def base_headers() -> dict[str, str]:
    return {
        "Host": "partpilot.example",
        "X-Forwarded-Proto": "https",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }


def custom_headers(key: str, *, header_name: str = DEFAULT_CUSTOM_HEADER_NAME) -> dict[str, str]:
    headers = base_headers()
    headers[header_name] = key
    return headers


def initialize_payload(request_id: int) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {
                "name": "partpilot-custom-header-smoke",
                "version": "1.0",
            },
        },
    }


def tools_payload(request_id: int) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/list",
        "params": {},
    }


def call_tool_payload(
    request_id: int,
    name: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }


def assert_status(response, expected: int, label: str) -> None:
    if response.status_code != expected:
        fail(f"{label} returned {response.status_code}: {response.text[:800]}")


def set_mcp_settings(*, enabled: bool, read_enabled: bool) -> None:
    db = SessionLocal()
    try:
        set_app_setting(db, MCP_ENABLED_KEY, enabled, commit=False)
        set_app_setting(db, MCP_READ_ENABLED_KEY, read_enabled, commit=False)
        set_app_setting(db, MCP_WRITE_ENABLED_KEY, False, commit=False)
        db.commit()
    finally:
        db.close()


def check_only() -> None:
    from app.main import app
    from app.mcp.runtime import mcp_registered_tool_names

    if set(asyncio.run(mcp_registered_tool_names())) != REGISTERED_TOOLS:
        fail("Registered MCP tool set changed")
    with TestClient(app, base_url="https://partpilot.example") as client:
        response = client.post(
            "/mcp",
            headers=custom_headers("pp_mcp_header_missing"),
            json=initialize_payload(1),
            follow_redirects=False,
        )
        assert_status(response, 401, "Unconfigured live custom-header path")
        if "pp_mcp_header_missing" in response.text:
            fail("Live custom-header check leaked the supplied credential")
    print("MCP custom-header transport check PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    arguments = parser.parse_args()
    if arguments.check_only:
        check_only()
        return

    before = database_snapshot()
    secret_path = Path(get_settings().instance_secret_file)
    secret_before = secret_path.read_bytes() if secret_path.exists() else None
    secret_mode_before = (
        stat.S_IMODE(secret_path.stat().st_mode)
        if secret_path.exists()
        else None
    )
    db = SessionLocal()
    baseline_audit_id = 0
    original_settings: dict[str, tuple[object, object, object]] = {}
    secrets_seen: list[str] = []
    try:
        if db.query(McpDirectAuth).count() != 1:
            fail("Custom-header smoke requires the migrated disabled legacy row")
        legacy = db.get(McpDirectAuth, 1)
        if legacy is None or legacy.mode != "disabled" or legacy.enabled:
            fail("Custom-header migrated legacy row has unexpected state")
        user = db.execute(
            select(User).where(User.is_active.is_(True)).order_by(User.id)
        ).scalars().first()
        if user is None:
            fail("Custom-header smoke requires one active user")
        baseline_audit_id = int(
            db.execute(select(func.max(AuditLog.id))).scalar() or 0
        )
        for setting_key in (
            MCP_ENABLED_KEY,
            MCP_READ_ENABLED_KEY,
            MCP_WRITE_ENABLED_KEY,
        ):
            setting = db.execute(
                select(AppSetting).where(AppSetting.key == setting_key)
            ).scalar_one()
            original_settings[setting_key] = (
                copy.deepcopy(setting.value_json),
                setting.value_text,
                setting.updated_at,
            )
        part_id = db.execute(
            select(Part.id).where(Part.is_deleted.is_(False)).order_by(Part.id)
        ).scalars().first()
        project_id = db.execute(select(Project.id).order_by(Project.id)).scalars().first()
        reservation_id = db.execute(
            select(Reservation.id).order_by(Reservation.id)
        ).scalars().first()
        if part_id is None or project_id is None or reservation_id is None:
            fail("Custom-header smoke requires inventory, Project and Reservation data")
        db.close()
        db = None

        set_mcp_settings(enabled=True, read_enabled=True)
        setup = SessionLocal()
        try:
            first = rotate_custom_header_key(
                setup,
                actor_user_id=user.id,
                header_name="X-PartPilot-MCP-Key",
                commit=True,
            )
            key1 = first.plaintext_key
            secrets_seen.extend(
                [
                    key1,
                    first.record.key_ciphertext or "",
                    first.record.key_digest or "",
                ]
            )
            if first.record.custom_header_name != DEFAULT_CUSTOM_HEADER_NAME:
                fail("Custom-header name was not canonicalized")
        finally:
            setup.close()

        from app.main import app
        from app.mcp.runtime import mcp_registered_tool_names

        if set(asyncio.run(mcp_registered_tool_names())) != REGISTERED_TOOLS:
            fail("Registered MCP tool set changed")

        with TestClient(app, base_url="https://partpilot.example") as client:
            missing = client.post(
                "/mcp",
                headers=base_headers(),
                json=initialize_payload(1),
                follow_redirects=False,
            )
            assert_status(missing, 401, "Missing custom header")

            wrong = client.post(
                "/mcp",
                headers=custom_headers("pp_mcp_header_wrong"),
                json=initialize_payload(2),
                follow_redirects=False,
            )
            assert_status(wrong, 401, "Wrong custom key")
            if "custom-header key" not in wrong.text:
                fail("Wrong custom key did not use the custom-header path")

            empty = client.post(
                "/mcp",
                headers=custom_headers("   "),
                json=initialize_payload(3),
                follow_redirects=False,
            )
            assert_status(empty, 401, "Empty custom key")

            valid = client.post(
                "/mcp",
                headers=custom_headers(key1, header_name="X-PartPilot-MCP-Key"),
                json=initialize_payload(4),
                follow_redirects=False,
            )
            assert_status(valid, 200, "Case-insensitive custom header")

            duplicate_headers = list(base_headers().items()) + [
                ("X-PartPilot-MCP-Key", key1),
                ("x-partpilot-mcp-key", key1),
            ]
            duplicate = client.post(
                "/mcp",
                headers=duplicate_headers,
                json=initialize_payload(5),
                follow_redirects=False,
            )
            assert_status(duplicate, 400, "Duplicate custom headers")
            if "Duplicate MCP custom credential headers" not in duplicate.text:
                fail("Duplicate custom headers were not rejected explicitly")

            mixed_headers = custom_headers(key1)
            mixed_headers["Authorization"] = "Bearer not-a-real-oauth-token"
            mixed = client.post(
                "/mcp",
                headers=mixed_headers,
                json=initialize_payload(6),
                follow_redirects=False,
            )
            assert_status(mixed, 400, "Mixed credentials")
            if "exactly one authentication credential" not in mixed.text:
                fail("Mixed credentials were not rejected as ambiguous")

            duplicate_auth_headers = list(custom_headers(key1).items()) + [
                ("Authorization", "Bearer one"),
                ("authorization", "Bearer two"),
            ]
            duplicate_auth = client.post(
                "/mcp",
                headers=duplicate_auth_headers,
                json=initialize_payload(7),
                follow_redirects=False,
            )
            assert_status(duplicate_auth, 400, "Duplicate Authorization")

            bad_origin_headers = custom_headers(key1)
            bad_origin_headers["Origin"] = "https://attacker.example"
            bad_origin = client.post(
                "/mcp",
                headers=bad_origin_headers,
                json=initialize_payload(8),
                follow_redirects=False,
            )
            assert_status(bad_origin, 403, "Invalid Origin")

            saved_secret = secret_path.read_bytes()
            saved_mode = stat.S_IMODE(secret_path.stat().st_mode)
            secret_path.unlink()
            try:
                missing_secret = client.post(
                    "/mcp",
                    headers=custom_headers(key1),
                    json=initialize_payload(9),
                    follow_redirects=False,
                )
                assert_status(missing_secret, 401, "Missing instance secret")
                if key1 in missing_secret.text:
                    fail("Missing-secret response leaked the custom key")
            finally:
                secret_path.write_bytes(saved_secret)
                os.chmod(secret_path, saved_mode)

            rotate = SessionLocal()
            try:
                second = rotate_custom_header_key(
                    rotate,
                    actor_user_id=user.id,
                    header_name=DEFAULT_CUSTOM_HEADER_NAME,
                    commit=True,
                )
                key2 = second.plaintext_key
                secrets_seen.extend(
                    [
                        key2,
                        second.record.key_ciphertext or "",
                        second.record.key_digest or "",
                    ]
                )
            finally:
                rotate.close()

            old_key = client.post(
                "/mcp",
                headers=custom_headers(key1),
                json=initialize_payload(10),
                follow_redirects=False,
            )
            assert_status(old_key, 401, "Rotated old custom key")
            new_key = client.post(
                "/mcp",
                headers=custom_headers(key2),
                json=initialize_payload(11),
                follow_redirects=False,
            )
            assert_status(new_key, 200, "Rotated custom key")

            switch = SessionLocal()
            try:
                bearer = rotate_bearer_key(
                    switch,
                    actor_user_id=user.id,
                    commit=True,
                )
                bearer_key = bearer.plaintext_key
                secrets_seen.extend(
                    [
                        bearer_key,
                        bearer.record.key_ciphertext or "",
                        bearer.record.key_digest or "",
                    ]
                )
            finally:
                switch.close()

            stale_custom = client.post(
                "/mcp",
                headers=custom_headers(key2),
                json=initialize_payload(12),
                follow_redirects=False,
            )
            assert_status(stale_custom, 401, "Custom key after Bearer switch")
            bearer_headers = base_headers()
            bearer_headers["Authorization"] = f"Bearer {bearer_key}"
            bearer_valid = client.post(
                "/mcp",
                headers=bearer_headers,
                json=initialize_payload(13),
                follow_redirects=False,
            )
            assert_status(bearer_valid, 200, "Bearer compatibility")

            switch_back = SessionLocal()
            try:
                third = rotate_custom_header_key(
                    switch_back,
                    actor_user_id=user.id,
                    header_name=DEFAULT_CUSTOM_HEADER_NAME,
                    commit=True,
                )
                key3 = third.plaintext_key
                secrets_seen.extend(
                    [
                        key3,
                        third.record.key_ciphertext or "",
                        third.record.key_digest or "",
                    ]
                )
            finally:
                switch_back.close()

            set_mcp_settings(enabled=False, read_enabled=True)
            disabled = client.post(
                "/mcp",
                headers=custom_headers(key3),
                json=initialize_payload(14),
                follow_redirects=False,
            )
            assert_status(disabled, 503, "MCP disabled")

            set_mcp_settings(enabled=True, read_enabled=False)
            read_disabled = client.post(
                "/mcp",
                headers=custom_headers(key3),
                json=initialize_payload(15),
                follow_redirects=False,
            )
            assert_status(read_disabled, 403, "Read tools disabled")

            set_mcp_settings(enabled=True, read_enabled=True)
            initialized = client.post(
                "/mcp",
                headers=custom_headers(key3),
                json=initialize_payload(16),
                follow_redirects=False,
            )
            assert_status(initialized, 200, "Final custom initialize")
            listed = client.post(
                "/mcp",
                headers=custom_headers(key3),
                json=tools_payload(17),
                follow_redirects=False,
            )
            assert_status(listed, 200, "Custom tools/list")
            tool_names = {
                item.get("name")
                for item in listed.json().get("result", {}).get("tools", [])
                if isinstance(item, dict)
            }
            if tool_names != EXPECTED_TOOLS:
                fail(f"Custom-header tools/list changed: {sorted(tool_names)}")

            calls = (
                ("search_parts", {"limit": 3, "offset": 0}),
                ("get_part_details", {"part_id": part_id}),
                ("list_projects", {"limit": 3, "offset": 0}),
                ("get_project_details", {"project_id": project_id}),
                ("list_reservations", {"limit": 3, "offset": 0}),
                ("get_reservation_details", {"reservation_id": reservation_id}),
            )
            for request_id, (tool_name, arguments) in enumerate(calls, start=20):
                response = client.post(
                    "/mcp",
                    headers=custom_headers(key3),
                    json=call_tool_payload(request_id, tool_name, arguments),
                    follow_redirects=False,
                )
                assert_status(response, 200, f"Custom tool {tool_name}")
                result = response.json().get("result")
                if not isinstance(result, dict) or result.get("isError") is True:
                    fail(f"Custom tool {tool_name} failed: {response.text[:800]}")

        verify = SessionLocal()
        try:
            tool_audits = verify.execute(
                select(AuditLog)
                .where(
                    AuditLog.id > baseline_audit_id,
                    AuditLog.event_type == "mcp.tool_called",
                )
                .order_by(AuditLog.id)
            ).scalars().all()
            if len(tool_audits) != 6:
                fail(f"Expected six custom-header tool audits, got {len(tool_audits)}")
            for audit in tool_audits:
                metadata = audit.metadata_json or {}
                if (
                    audit.actor_type != "mcp"
                    or audit.actor_user_id is not None
                    or metadata.get("auth_method") != "direct_custom_header"
                    or metadata.get("direct_auth_id") != DIRECT_AUTH_SINGLETON_ID
                    or "client_id" in metadata
                    or "token_id" in metadata
                ):
                    fail(f"Invalid custom-header tool audit identity: {metadata}")
            payload = json.dumps(
                [
                    {
                        "event": row.event_type,
                        "summary": row.summary,
                        "before": row.before_json,
                        "after": row.after_json,
                        "metadata": row.metadata_json,
                    }
                    for row in verify.execute(
                        select(AuditLog)
                        .where(AuditLog.id > baseline_audit_id)
                        .order_by(AuditLog.id)
                    ).scalars()
                ],
                sort_keys=True,
                default=str,
            )
            for value in secrets_seen:
                if value and value in payload:
                    fail("Custom-header credential material leaked into audits")
        finally:
            verify.close()
    finally:
        if db is not None:
            db.rollback()
            db.close()
        cleanup = SessionLocal()
        try:
            cleanup.query(AuditLog).filter(
                AuditLog.id > baseline_audit_id
            ).delete(synchronize_session=False)
            for setting_key, values in original_settings.items():
                setting = cleanup.execute(
                    select(AppSetting).where(AppSetting.key == setting_key)
                ).scalar_one()
                setting.value_json, setting.value_text, setting.updated_at = values
            cleanup.commit()
        finally:
            cleanup.close()
        restore_direct_baseline(before)
        restore_sequences(before)
        if secret_before is None:
            secret_path.unlink(missing_ok=True)
        else:
            secret_path.write_bytes(secret_before)
            os.chmod(secret_path, secret_mode_before or 0o600)
        if database_snapshot() != before:
            fail("Custom-header transport smoke did not restore the database exactly")
        current_secret = secret_path.read_bytes() if secret_path.exists() else None
        current_mode = (
            stat.S_IMODE(secret_path.stat().st_mode)
            if secret_path.exists()
            else None
        )
        if current_secret != secret_before or current_mode != secret_mode_before:
            fail("Custom-header transport smoke did not restore the instance secret")

    print(
        "[PASS] MCP custom-header authentication rejects missing, wrong, empty, "
        "duplicate and mixed credentials; preserves Origin, MCP/read gates and "
        "Bearer fallback; supports all six read tools; writes identity-safe "
        "audits; and restores the copied database and secret exactly"
    )


if __name__ == "__main__":
    main()
