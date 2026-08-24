from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import sqlite3
import stat
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.db.settings import set_app_setting
from app.models import (
    AppSetting,
    AuditLog,
    McpDirectAuth,
    Part,
    Project,
    Reservation,
    User,
)
from app.services.mcp_direct_auth import (
    DIRECT_AUTH_SINGLETON_ID,
    disable_direct_auth,
    rotate_bearer_key,
)
from app.services.mcp_oauth import (
    MCP_ENABLED_KEY,
    MCP_READ_ENABLED_KEY,
    MCP_WRITE_ENABLED_KEY,
)
from app.services.parts import get_part, list_parts
from app.services.projects import get_project, list_projects as list_project_records
from app.services.reservations import (
    get_reservation,
    list_reservations as list_reservation_records,
)


# PARTPILOT:MCP_DIRECT_BEARER_TRANSPORT_SMOKE:V488
RESOURCE = "https://partpilot.example/mcp"
DIRECT_PREFIX = "pp_mcp_key_"
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
    "adjust_part_quantity",
    "create_part",
    "update_part_metadata",
}


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def sqlite_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"MCP direct-Bearer smoke requires SQLite, got {url!r}")
    return Path(url[len(prefix):]).resolve()


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
                fail("sqlite_sequence disappeared during direct-Bearer smoke")
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
                fail(f"Direct-Bearer smoke created sequence rows: {current}")
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


def request_headers(token: str | None = None) -> dict[str, str]:
    headers = {
        "Host": "partpilot.example",
        "X-Forwarded-Proto": "https",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def initialize_payload(request_id: int = 1) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {
                "name": "partpilot-direct-bearer-smoke",
                "version": "1.0",
            },
        },
    }


def tools_payload() -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": 2,
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
        fail(
            f"{label} returned {response.status_code}: "
            f"{response.text[:800]}"
        )


def set_mcp_settings(*, enabled: bool, read_enabled: bool) -> None:
    db = SessionLocal()
    try:
        set_app_setting(db, MCP_ENABLED_KEY, enabled, commit=False)
        set_app_setting(db, MCP_READ_ENABLED_KEY, read_enabled, commit=False)
        set_app_setting(db, MCP_WRITE_ENABLED_KEY, False, commit=False)
        db.commit()
    finally:
        db.close()


def rotate_key(actor_user_id: int) -> tuple[str, str, str]:
    db = SessionLocal()
    try:
        issued = rotate_bearer_key(
            db,
            actor_user_id=actor_user_id,
            commit=True,
        )
        record = db.get(McpDirectAuth, DIRECT_AUTH_SINGLETON_ID)
        if record is None or not record.key_ciphertext or not record.key_digest:
            fail("Direct-key rotation did not persist its protected key bundle")
        return issued.plaintext_key, record.key_ciphertext, record.key_digest
    finally:
        db.close()


def disable_key(actor_user_id: int) -> None:
    db = SessionLocal()
    try:
        if not disable_direct_auth(
            db,
            actor_user_id=actor_user_id,
            commit=True,
        ):
            fail("Configured direct authentication was not disabled")
    finally:
        db.close()


def parse_tool_result(response, label: str) -> dict[str, object]:
    assert_status(response, 200, label)
    rpc = response.json()
    result = rpc.get("result")
    if not isinstance(result, dict):
        fail(f"{label} returned no JSON-RPC result: {rpc}")
    if result.get("isError") is True:
        fail(f"{label} returned a tool error: {result}")
    structured = result.get("structuredContent")
    if not isinstance(structured, dict):
        fail(f"{label} returned no structuredContent: {result}")
    return structured


def check_only() -> None:
    from app.main import app
    from app.mcp.runtime import mcp_registered_tool_names

    names = set(asyncio.run(mcp_registered_tool_names()))
    if names != REGISTERED_TOOLS:
        fail(f"Unexpected registered tools: {sorted(names)}")
    with TestClient(app, base_url="https://partpilot.example") as client:
        oauth_invalid = client.post(
            "/mcp",
            headers=request_headers("not-a-real-oauth-token"),
            json=initialize_payload(),
            follow_redirects=False,
        )
        assert_status(oauth_invalid, 401, "Non-prefixed OAuth fallback")
        if "OAuth bearer token" not in oauth_invalid.text:
            fail("Non-prefixed Bearer value did not remain on the OAuth path")

        direct_invalid = client.post(
            "/mcp",
            headers=request_headers(DIRECT_PREFIX + "missing"),
            json=initialize_payload(2),
            follow_redirects=False,
        )
        assert_status(direct_invalid, 401, "Unconfigured direct Bearer")
        if "direct Bearer key" not in direct_invalid.text:
            fail("Prefixed Bearer value did not use the direct-key path")
    print("MCP direct Bearer transport check PASS")


def full_flow() -> None:
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
    keys: list[str] = []
    protected_material: list[str] = []
    try:
        if db.query(McpDirectAuth).count() != 1:
            fail("Direct-Bearer smoke requires the migrated disabled legacy row")
        legacy = db.get(McpDirectAuth, 1)
        if legacy is None or legacy.mode != "disabled" or legacy.enabled:
            fail("Direct-Bearer migrated legacy row has unexpected state")
        user = db.execute(
            select(User).where(User.is_active.is_(True)).order_by(User.id)
        ).scalars().first()
        if user is None:
            fail("Direct-Bearer smoke requires one active user")
        baseline_audit_id = int(
            db.execute(select(func.max(AuditLog.id))).scalar() or 0
        )
        for key in (MCP_ENABLED_KEY, MCP_READ_ENABLED_KEY, MCP_WRITE_ENABLED_KEY):
            setting = db.execute(
                select(AppSetting).where(AppSetting.key == key)
            ).scalar_one_or_none()
            if setting is None:
                fail(f"Required MCP setting is missing: {key}")
            original_settings[key] = (
                copy.deepcopy(setting.value_json),
                setting.value_text,
                setting.updated_at,
            )
        expected_part_id = db.execute(
            select(Part.id)
            .where(Part.is_deleted.is_(False))
            .order_by(Part.id)
        ).scalars().first()
        expected_project_id = db.execute(
            select(Project.id).order_by(Project.id)
        ).scalars().first()
        expected_reservation_id = db.execute(
            select(Reservation.id).order_by(Reservation.id)
        ).scalars().first()
        if expected_part_id is None:
            fail("Direct-Bearer smoke requires one active part")
        if expected_project_id is None:
            fail("Direct-Bearer smoke requires one Project")
        if expected_reservation_id is None:
            fail("Direct-Bearer smoke requires one Reservation")
        expected_parts = list_parts(db, limit=3, offset=0)
        expected_part = get_part(db, expected_part_id)
        expected_projects = list_project_records(db, limit=3, offset=0)
        expected_project = get_project(db, expected_project_id)
        expected_reservations = list_reservation_records(db, limit=3, offset=0)
        expected_reservation = get_reservation(db, expected_reservation_id)
        db.close()
        db = None

        set_mcp_settings(enabled=True, read_enabled=True)
        key1, ciphertext1, digest1 = rotate_key(user.id)
        keys.append(key1)
        protected_material.extend((ciphertext1, digest1))
        if not key1.startswith(DIRECT_PREFIX):
            fail("First direct key has the wrong prefix")
        if not secret_path.is_file() or secret_path.is_symlink():
            fail("First direct-key rotation did not create a safe instance secret")
        if stat.S_IMODE(secret_path.stat().st_mode) != 0o600:
            fail("Instance-secret file is not mode 0600")

        from app.main import app

        with TestClient(app, base_url="https://partpilot.example") as client:
            oauth_invalid = client.post(
                "/mcp",
                headers=request_headers("not-a-real-oauth-token"),
                json=initialize_payload(10),
                follow_redirects=False,
            )
            assert_status(oauth_invalid, 401, "OAuth fallback invalid token")
            if "OAuth bearer token" not in oauth_invalid.text:
                fail("Non-prefixed Bearer value did not preserve OAuth handling")

            wrong = client.post(
                "/mcp",
                headers=request_headers(DIRECT_PREFIX + "wrong"),
                json=initialize_payload(11),
                follow_redirects=False,
            )
            assert_status(wrong, 401, "Wrong direct key")
            if "direct Bearer key" not in wrong.text:
                fail("Wrong prefixed key was not rejected by direct authentication")

            valid = client.post(
                "/mcp",
                headers=request_headers(key1),
                json=initialize_payload(12),
                follow_redirects=False,
            )
            assert_status(valid, 200, "Valid direct key")

            bad_origin_headers = request_headers(key1)
            bad_origin_headers["Origin"] = "https://attacker.example"
            bad_origin = client.post(
                "/mcp",
                headers=bad_origin_headers,
                json=initialize_payload(13),
                follow_redirects=False,
            )
            assert_status(bad_origin, 403, "Direct-key invalid Origin")

            saved_secret = secret_path.read_bytes()
            saved_mode = stat.S_IMODE(secret_path.stat().st_mode)
            secret_path.unlink()
            try:
                missing_secret = client.post(
                    "/mcp",
                    headers=request_headers(key1),
                    json=initialize_payload(14),
                    follow_redirects=False,
                )
                assert_status(missing_secret, 401, "Absent instance secret")
                if key1 in missing_secret.text:
                    fail("Absent-secret response leaked the supplied direct key")
            finally:
                secret_path.write_bytes(saved_secret)
                os.chmod(secret_path, saved_mode)

            key2, ciphertext2, digest2 = rotate_key(user.id)
            keys.append(key2)
            protected_material.extend((ciphertext2, digest2))
            if key2 == key1:
                fail("Direct-key rotation reused plaintext material")
            rotated_old = client.post(
                "/mcp",
                headers=request_headers(key1),
                json=initialize_payload(15),
                follow_redirects=False,
            )
            assert_status(rotated_old, 401, "Rotated old direct key")
            rotated_new = client.post(
                "/mcp",
                headers=request_headers(key2),
                json=initialize_payload(16),
                follow_redirects=False,
            )
            assert_status(rotated_new, 200, "Rotated new direct key")

            disable_key(user.id)
            disabled_auth = client.post(
                "/mcp",
                headers=request_headers(key2),
                json=initialize_payload(17),
                follow_redirects=False,
            )
            assert_status(disabled_auth, 401, "Disabled direct authentication")

            key3, ciphertext3, digest3 = rotate_key(user.id)
            keys.append(key3)
            protected_material.extend((ciphertext3, digest3))

            set_mcp_settings(enabled=False, read_enabled=True)
            mcp_disabled = client.post(
                "/mcp",
                headers=request_headers(key3),
                json=initialize_payload(18),
                follow_redirects=False,
            )
            assert_status(mcp_disabled, 503, "MCP disabled gate")

            set_mcp_settings(enabled=True, read_enabled=False)
            read_disabled = client.post(
                "/mcp",
                headers=request_headers(key3),
                json=initialize_payload(19),
                follow_redirects=False,
            )
            assert_status(read_disabled, 403, "Read-tools disabled gate")

            set_mcp_settings(enabled=True, read_enabled=True)
            initialized = client.post(
                "/mcp",
                headers=request_headers(key3),
                json=initialize_payload(20),
                follow_redirects=False,
            )
            assert_status(initialized, 200, "Final direct-key initialize")
            initialized_body = initialized.json()
            if initialized_body.get("jsonrpc") != "2.0":
                fail(f"Unexpected initialize response: {initialized_body}")

            listed = client.post(
                "/mcp",
                headers=request_headers(key3),
                json=tools_payload(),
                follow_redirects=False,
            )
            assert_status(listed, 200, "Direct-key tools/list")
            listed_tools = listed.json().get("result", {}).get("tools")
            if not isinstance(listed_tools, list):
                fail("Direct-key tools/list returned no tools")
            names = {
                item.get("name")
                for item in listed_tools
                if isinstance(item, dict)
            }
            if names != EXPECTED_TOOLS:
                fail(f"Unexpected direct-key tool registry: {sorted(names)}")

            search_data = parse_tool_result(
                client.post(
                    "/mcp",
                    headers=request_headers(key3),
                    json=call_tool_payload(30, "search_parts", {"limit": 3}),
                    follow_redirects=False,
                ),
                "search_parts",
            )
            expected_part_ids = [part.id for part in expected_parts.parts]
            actual_part_ids = [
                row.get("id")
                for row in search_data.get("parts", [])
                if isinstance(row, dict)
            ]
            if actual_part_ids != expected_part_ids:
                fail(
                    f"search_parts IDs differ: {actual_part_ids} != {expected_part_ids}"
                )
            if search_data.get("total") != expected_parts.total:
                fail("search_parts total differs from the canonical service")

            part_data = parse_tool_result(
                client.post(
                    "/mcp",
                    headers=request_headers(key3),
                    json=call_tool_payload(
                        31,
                        "get_part_details",
                        {"part_id": expected_part_id},
                    ),
                    follow_redirects=False,
                ),
                "get_part_details",
            )
            if part_data.get("part") != expected_part.model_dump(mode="json"):
                fail("get_part_details differs from the canonical part service")

            projects_data = parse_tool_result(
                client.post(
                    "/mcp",
                    headers=request_headers(key3),
                    json=call_tool_payload(32, "list_projects", {"limit": 3}),
                    follow_redirects=False,
                ),
                "list_projects",
            )
            if projects_data.get("total") != expected_projects.total:
                fail("list_projects total differs from the canonical service")

            project_data = parse_tool_result(
                client.post(
                    "/mcp",
                    headers=request_headers(key3),
                    json=call_tool_payload(
                        33,
                        "get_project_details",
                        {"project_id": expected_project_id},
                    ),
                    follow_redirects=False,
                ),
                "get_project_details",
            )
            if project_data.get("project") != expected_project.model_dump(mode="json"):
                fail("get_project_details differs from the canonical Project service")

            reservations_data = parse_tool_result(
                client.post(
                    "/mcp",
                    headers=request_headers(key3),
                    json=call_tool_payload(34, "list_reservations", {"limit": 3}),
                    follow_redirects=False,
                ),
                "list_reservations",
            )
            if reservations_data.get("total") != expected_reservations.total:
                fail("list_reservations total differs from the canonical service")

            reservation_data = parse_tool_result(
                client.post(
                    "/mcp",
                    headers=request_headers(key3),
                    json=call_tool_payload(
                        35,
                        "get_reservation_details",
                        {"reservation_id": expected_reservation_id},
                    ),
                    follow_redirects=False,
                ),
                "get_reservation_details",
            )
            if reservation_data.get("reservation") != expected_reservation.model_dump(mode="json"):
                fail(
                    "get_reservation_details differs from the canonical Reservation service"
                )

        audit_db = SessionLocal()
        try:
            tool_audits = list(
                audit_db.execute(
                    select(AuditLog)
                    .where(
                        AuditLog.id > baseline_audit_id,
                        AuditLog.event_type == "mcp.tool_called",
                    )
                    .order_by(AuditLog.id)
                ).scalars()
            )
            direct_audits = [
                row
                for row in tool_audits
                if isinstance(row.metadata_json, dict)
                and row.metadata_json.get("auth_method") == "direct_bearer"
            ]
            if len(direct_audits) != 6:
                fail(
                    f"Expected six direct-key tool audits, got {len(direct_audits)}"
                )
            if {
                row.metadata_json.get("tool")
                for row in direct_audits
            } != EXPECTED_TOOLS:
                fail("Direct-key tool audit names are incomplete")
            for row in direct_audits:
                metadata = row.metadata_json
                if row.actor_type != "mcp" or row.actor_user_id is not None:
                    fail("Direct-key tool audit fabricated a user identity")
                if metadata.get("direct_auth_id") != DIRECT_AUTH_SINGLETON_ID:
                    fail("Direct-key tool audit lacks direct-auth attribution")
                if "client_id" in metadata or "token_id" in metadata:
                    fail("Direct-key tool audit fabricated OAuth attribution")
                if metadata.get("success") is not True:
                    fail("Successful direct-key tool call was audited as failed")
            serialized = json.dumps(
                [
                    {
                        "event_type": row.event_type,
                        "summary": row.summary,
                        "metadata": row.metadata_json,
                    }
                    for row in direct_audits
                ],
                sort_keys=True,
                default=str,
            )
            for secret in [*keys, *protected_material]:
                if secret and secret in serialized:
                    fail("Direct-key tool audit leaked key material")
            if "authorization" in serialized.casefold():
                fail("Direct-key tool audit included an Authorization header")
        finally:
            audit_db.close()

        cleanup = SessionLocal()
        try:
            for key, (value_json, value_text, updated_at) in original_settings.items():
                setting = cleanup.execute(
                    select(AppSetting).where(AppSetting.key == key)
                ).scalar_one()
                setting.value_json = copy.deepcopy(value_json)
                setting.value_text = value_text
                setting.updated_at = updated_at
            cleanup.query(AuditLog).filter(
                AuditLog.id > baseline_audit_id
            ).delete(synchronize_session=False)
            cleanup.commit()
        finally:
            cleanup.close()
        restore_direct_baseline(before)
        restore_sequences(before)
        if database_snapshot() != before:
            fail("Direct-Bearer transport smoke did not restore the exact database")
    finally:
        if db is not None:
            db.rollback()
            db.close()
        if secret_before is None:
            secret_path.unlink(missing_ok=True)
        else:
            secret_path.write_bytes(secret_before)
            os.chmod(secret_path, secret_mode_before or 0o600)
    print(
        "[PASS] MCP direct Bearer authentication validates only pp_mcp_key_ "
        "credentials, preserves OAuth fallback and Host/Origin checks, enforces "
        "MCP/read gates, supports all six read tools, rejects wrong/rotated/disabled "
        "keys and missing secrets, records identity-safe audits, and restores the "
        "copied database and secret state exactly"
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
