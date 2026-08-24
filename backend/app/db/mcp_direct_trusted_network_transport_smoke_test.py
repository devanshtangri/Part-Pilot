from __future__ import annotations

import argparse
import asyncio
import copy
import os
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.db.settings import set_app_setting
from app.models import AppSetting, AuditLog, McpDirectAuth, Part, User
from app.services.mcp_direct_auth import (
    DIRECT_AUTH_SINGLETON_ID,
    configure_trusted_networks,
    disable_direct_auth,
    rotate_bearer_key,
)
from app.services.mcp_oauth import (
    MCP_ENABLED_KEY,
    MCP_READ_ENABLED_KEY,
    MCP_WRITE_ENABLED_KEY,
)


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


class PeerOverride:
    def __init__(self, target) -> None:
        self.target = target
        self.peer = "203.0.113.40"

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") == "http":
            scope = dict(scope)
            scope["client"] = (self.peer, 43125)
        await self.target(scope, receive, send)


def fail(message: str) -> None:
    raise SmokeFailure(message)


def sqlite_path() -> Path:
    value = get_settings().database_url
    prefix = "sqlite:///"
    if not value.startswith(prefix):
        fail(f"Trusted-network transport smoke requires SQLite, got {value!r}")
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
                fail("sqlite_sequence disappeared during trusted-network smoke")
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
                fail(f"Trusted-network smoke created sequence rows: {current}")
    finally:
        connection.close()


@contextmanager
def trusted_proxy_environment(value: str = "") -> Iterator[None]:
    key = "PARTPILOT_TRUSTED_PROXY_CIDRS"
    original = os.environ.get(key)
    try:
        os.environ[key] = value
        get_settings.cache_clear()
        yield
    finally:
        if original is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original
        get_settings.cache_clear()


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


def request_headers(
    token: str | None = None,
    *,
    forwarded_for: str | None = None,
) -> dict[str, str]:
    values = {
        "Host": "partpilot.example",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if token is not None:
        values["Authorization"] = f"Bearer {token}"
    if forwarded_for is not None:
        values["X-Forwarded-For"] = forwarded_for
    return values


def initialize_payload(request_id: int) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {
                "name": "partpilot-trusted-network-smoke",
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


def configure(actor_user_id: int, networks: list[str]) -> None:
    db = SessionLocal()
    try:
        configure_trusted_networks(
            db,
            actor_user_id=actor_user_id,
            networks=networks,
            commit=True,
        )
    finally:
        db.close()


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
    peer = PeerOverride(app)
    with TestClient(peer, base_url="https://partpilot.example") as client:
        missing = client.post(
            "/mcp",
            headers=request_headers(),
            json=initialize_payload(1),
            follow_redirects=False,
        )
        assert_status(missing, 401, "Unconfigured trusted-network path")
        if "request source is not trusted" not in missing.text:
            fail("Unconfigured trusted-network path did not fail closed")
    print("MCP trusted-network transport check PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    arguments = parser.parse_args()
    if arguments.check_only:
        check_only()
        return

    before = database_snapshot()
    db = SessionLocal()
    original_settings: dict[str, tuple[object, object, object]] = {}
    baseline_audit_id = 0
    actor_user_id: int | None = None
    try:
        if db.query(McpDirectAuth).count() != 1:
            fail("Trusted-network smoke requires the migrated disabled legacy row")
        legacy = db.get(McpDirectAuth, 1)
        if legacy is None or legacy.mode != "disabled" or legacy.enabled:
            fail("Trusted-network migrated legacy row has unexpected state")
        user = db.execute(
            select(User).where(User.is_active.is_(True)).order_by(User.id)
        ).scalars().first()
        if user is None:
            fail("Trusted-network smoke requires one active user")
        actor_user_id = user.id
        baseline_audit_id = int(
            db.execute(select(func.max(AuditLog.id))).scalar() or 0
        )
        for key in (MCP_ENABLED_KEY, MCP_READ_ENABLED_KEY, MCP_WRITE_ENABLED_KEY):
            setting = db.execute(
                select(AppSetting).where(AppSetting.key == key)
            ).scalar_one()
            original_settings[key] = (
                copy.deepcopy(setting.value_json),
                setting.value_text,
                setting.updated_at,
            )
        part_id = db.execute(
            select(Part.id).where(Part.is_deleted.is_(False)).order_by(Part.id)
        ).scalars().first()
        if part_id is None:
            fail("Trusted-network smoke requires one active inventory part")
        db.close()
        db = None

        set_mcp_settings(enabled=True, read_enabled=True)
        configure(actor_user_id, ["198.51.100.0/24", "2001:db8:abcd::/64"])

        from app.main import app
        from app.mcp.runtime import mcp_registered_tool_names

        if set(asyncio.run(mcp_registered_tool_names())) != REGISTERED_TOOLS:
            fail("Registered MCP tool set changed")

        peer = PeerOverride(app)
        with TestClient(peer, base_url="https://partpilot.example") as client:
            with trusted_proxy_environment():
                peer.peer = "203.0.113.40"
                denied = client.post(
                    "/mcp",
                    headers=request_headers(),
                    json=initialize_payload(10),
                    follow_redirects=False,
                )
                assert_status(denied, 401, "Untrusted IPv4 peer")

                spoofed = client.post(
                    "/mcp",
                    headers=request_headers(forwarded_for="198.51.100.25"),
                    json=initialize_payload(11),
                    follow_redirects=False,
                )
                assert_status(spoofed, 401, "Spoofed untrusted forwarding")

                peer.peer = "198.51.100.25"
                invalid_explicit = client.post(
                    "/mcp",
                    headers=request_headers("not-a-real-oauth-token"),
                    json=initialize_payload(12),
                    follow_redirects=False,
                )
                assert_status(invalid_explicit, 401, "Invalid explicit credential")
                if "OAuth bearer token" not in invalid_explicit.text:
                    fail("Explicit invalid credential fell back to network trust")

                allowed = client.post(
                    "/mcp",
                    headers=request_headers(),
                    json=initialize_payload(13),
                    follow_redirects=False,
                )
                assert_status(allowed, 200, "Trusted IPv4 peer")

                tools = client.post(
                    "/mcp",
                    headers=request_headers(),
                    json=tools_payload(14),
                    follow_redirects=False,
                )
                assert_status(tools, 200, "Trusted-network tools/list")
                names = {
                    item.get("name")
                    for item in tools.json().get("result", {}).get("tools", [])
                    if isinstance(item, dict)
                }
                if names != EXPECTED_TOOLS:
                    fail(f"Trusted-network tools changed: {sorted(names)}")

                called = client.post(
                    "/mcp",
                    headers=request_headers(),
                    json=call_tool_payload(
                        15,
                        "get_part_details",
                        {"part_id": part_id},
                    ),
                    follow_redirects=False,
                )
                assert_status(called, 200, "Trusted-network tool call")
                result = called.json().get("result", {})
                if result.get("isError") is True:
                    fail(f"Trusted-network tool call failed: {result}")

                peer.peer = "2001:db8:abcd::25"
                allowed_v6 = client.post(
                    "/mcp",
                    headers=request_headers(),
                    json=initialize_payload(16),
                    follow_redirects=False,
                )
                assert_status(allowed_v6, 200, "Trusted IPv6 peer")

            with trusted_proxy_environment("10.0.0.0/24"):
                peer.peer = "10.0.0.5"
                proxied = client.post(
                    "/mcp",
                    headers=request_headers(forwarded_for="198.51.100.50"),
                    json=initialize_payload(20),
                    follow_redirects=False,
                )
                assert_status(proxied, 200, "Trusted proxy allowed client")

                denied_proxy = client.post(
                    "/mcp",
                    headers=request_headers(forwarded_for="203.0.113.50"),
                    json=initialize_payload(21),
                    follow_redirects=False,
                )
                assert_status(denied_proxy, 401, "Trusted proxy denied client")

            verify = SessionLocal()
            try:
                record = verify.get(McpDirectAuth, DIRECT_AUTH_SINGLETON_ID)
                if record is None or record.mode != "trusted_network":
                    fail("Trusted-network mode was not preserved")
                if record.last_used_at is None:
                    fail("Trusted-network access did not touch last_used_at")
                audits = verify.execute(
                    select(AuditLog)
                    .where(AuditLog.id > baseline_audit_id)
                    .order_by(AuditLog.id)
                ).scalars().all()
                tool_audits = [
                    row for row in audits if row.event_type == "mcp.tool_called"
                ]
                if not tool_audits:
                    fail("Trusted-network tool call produced no audit")
                if not any(
                    isinstance(row.metadata_json, dict)
                    and row.metadata_json.get("auth_method")
                    == "direct_trusted_network"
                    and row.metadata_json.get("client_ip") == "198.51.100.25"
                    and row.metadata_json.get("direct_auth_id")
                    == DIRECT_AUTH_SINGLETON_ID
                    for row in tool_audits
                ):
                    fail("Trusted-network audit omitted its resolved client IP")
            finally:
                verify.close()

            switch = SessionLocal()
            try:
                issued = rotate_bearer_key(
                    switch,
                    actor_user_id=actor_user_id,
                    commit=True,
                )
                bearer_key = issued.plaintext_key
            finally:
                switch.close()

            with trusted_proxy_environment():
                peer.peer = "198.51.100.25"
                network_after_switch = client.post(
                    "/mcp",
                    headers=request_headers(),
                    json=initialize_payload(30),
                    follow_redirects=False,
                )
                assert_status(
                    network_after_switch,
                    401,
                    "Network after Bearer switch",
                )
                bearer_after_switch = client.post(
                    "/mcp",
                    headers=request_headers(bearer_key),
                    json=initialize_payload(31),
                    follow_redirects=False,
                )
                assert_status(
                    bearer_after_switch,
                    200,
                    "Bearer after network switch",
                )

        cleanup = SessionLocal()
        try:
            disable_direct_auth(
                cleanup,
                actor_user_id=actor_user_id,
                commit=False,
            )
            cleanup.query(AuditLog).filter(AuditLog.id > baseline_audit_id).delete(
                synchronize_session=False
            )
            for key, (value_json, value_text, updated_at) in original_settings.items():
                setting = cleanup.execute(
                    select(AppSetting).where(AppSetting.key == key)
                ).scalar_one()
                setting.value_json = copy.deepcopy(value_json)
                setting.value_text = value_text
                setting.updated_at = updated_at
            cleanup.commit()
        finally:
            cleanup.close()

        restore_direct_baseline(before)
        restore_sequences(before)
        after = database_snapshot()
        if after != before:
            changed = [
                table
                for table in sorted(set(before["rows"]) | set(after["rows"]))
                if before["rows"].get(table) != after["rows"].get(table)
            ]
            fail(f"Trusted-network smoke changed copied database: {changed}")
    finally:
        if db is not None:
            db.rollback()
            db.close()

    print(
        "[PASS] MCP trusted-network authentication accepts canonical IPv4/IPv6 "
        "sources, resolves only explicitly trusted proxy chains, rejects spoofing, "
        "never falls back from invalid explicit credentials, preserves OAuth/Bearer "
        "precedence, touches last_used_at, audits the resolved client IP, exposes all "
        "six read-only tools, and restores the copied database exactly"
    )


if __name__ == "__main__":
    main()


# PARTPILOT:MCP_DIRECT_TRUSTED_NETWORK_TRANSPORT_SMOKE:V509
