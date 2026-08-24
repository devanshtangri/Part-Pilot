from __future__ import annotations

import argparse
import asyncio
import copy
import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.db.settings import set_app_setting
from app.models import AppSetting, AuditLog, Part, User
from app.services.mcp_oauth import (
    MCP_ENABLED_KEY,
    MCP_READ_ENABLED_KEY,
    MCP_SCOPE_READ,
    MCP_WRITE_ENABLED_KEY,
    available_scopes,
    exchange_authorization_code,
    grant_consent,
    issue_authorization_code,
    pkce_s256_challenge,
    register_client,
)
from app.services.parts import get_part, list_parts


# PARTPILOT:MCP_STREAMABLE_HTTP_SMOKE:V471
RESOURCE = "https://partpilot.example/mcp"
REDIRECT = "https://client.example/callback"
VERIFIER = "v" * 64


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def sqlite_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"MCP transport smoke requires SQLite, got {url!r}")
    return Path(url[len(prefix):]).resolve()


def database_snapshot() -> dict[str, object]:
    path = sqlite_path()
    db = sqlite3.connect(path)
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
        rows: dict[str, list[dict[str, object]]] = {}
        for table in tables:
            values = [
                {key: row[key] for key in row.keys()}
                for row in db.execute(f'SELECT * FROM "{table}" ORDER BY rowid')
            ]
            rows[table] = values
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
    path = sqlite_path()
    db = sqlite3.connect(path)
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


def initialize_payload() -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "partpilot-smoke", "version": "1.0"},
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


def assert_unauthorized(client: TestClient) -> None:
    response = client.post(
        "/mcp",
        headers=request_headers(),
        json=initialize_payload(),
        follow_redirects=False,
    )
    if response.status_code != 401:
        fail(f"Expected unauthenticated /mcp to return 401, got {response.status_code}")
    challenge = response.headers.get("www-authenticate", "")
    db = SessionLocal()
    try:
        configured_scopes = sorted(available_scopes(db, require_enabled=False))
    finally:
        db.close()
    expected_scope = " ".join(configured_scopes or [MCP_SCOPE_READ])
    expected_scope_marker = f'scope="{expected_scope}"'
    if (
        "oauth-protected-resource/mcp" not in challenge
        or expected_scope_marker not in challenge
    ):
        fail(
            "Missing configured protected-resource scope challenge: "
            f"expected {expected_scope_marker!r}, got {challenge!r}"
        )
    if response.is_redirect:
        fail("/mcp redirected instead of serving the exact endpoint")


def check_only() -> None:
    from app.main import app
    from app.mcp.runtime import mcp_registered_tool_names

    names = asyncio.run(mcp_registered_tool_names())
    if names != (
        "adjust_part_quantity",
        "cancel_reservation",
        "consume_reservation",
        "create_part",
        "get_part_details",
        "get_project_details",
        "get_reservation_details",
        "list_projects",
        "list_reservations",
        "reserve_project",
        "search_parts",
        "update_part_metadata",
    ):
        fail(f"Unexpected registered MCP tools: {names!r}")

    with TestClient(app, base_url="https://partpilot.example") as client:
        assert_unauthorized(client)
        slash = client.post(
            "/mcp/",
            headers=request_headers(),
            json=initialize_payload(),
            follow_redirects=False,
        )
        if slash.status_code not in {307, 308, 401, 405}:
            fail(f"Unexpected /mcp/ response: {slash.status_code}")
    print(
        "[PASS] MCP Streamable HTTP route is exact, protected by OAuth discovery, "
        "safely rejects /mcp/, and registers six read and six safeguarded write tools"
    )


def full_flow() -> None:
    before = database_snapshot()
    db = SessionLocal()
    client_identifier: str | None = None
    audit_ids: list[int] = []
    expected_part_id: int | None = None
    original_settings: dict[str, tuple[object, object, object]] = {}
    try:
        user = db.execute(select(User).order_by(User.id.asc())).scalars().first()
        if user is None:
            fail("MCP transport smoke requires one existing user")

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

        set_app_setting(db, MCP_ENABLED_KEY, True, commit=False)
        set_app_setting(db, MCP_READ_ENABLED_KEY, True, commit=False)
        set_app_setting(db, MCP_WRITE_ENABLED_KEY, False, commit=False)

        registered = register_client(
            db,
            client_name="Patch 471 Workspace Registry Smoke",
            redirect_uris=[REDIRECT],
            token_endpoint_auth_method="none",
            metadata={"fixture": "patch-471-registry"},
            actor_user_id=user.id,
            commit=False,
        )
        client_identifier = registered.client_id
        grant_consent(
            db,
            user_id=user.id,
            client_id=client_identifier,
            scopes=[MCP_SCOPE_READ],
            commit=False,
        )
        code = issue_authorization_code(
            db,
            client_id=client_identifier,
            user_id=user.id,
            redirect_uri=REDIRECT,
            scopes=[MCP_SCOPE_READ],
            code_challenge=pkce_s256_challenge(VERIFIER),
            code_challenge_method="S256",
            resource_uri=RESOURCE,
            commit=False,
        )
        issued = exchange_authorization_code(
            db,
            code=code.code,
            client_id=client_identifier,
            client_secret=None,
            redirect_uri=REDIRECT,
            code_verifier=VERIFIER,
            resource_uri=RESOURCE,
            commit=False,
        )
        db.commit()

        expected_part_id = db.execute(
            select(Part.id)
            .where(Part.is_deleted.is_(False))
            .order_by(Part.id.asc())
        ).scalars().first()
        if expected_part_id is None:
            fail("MCP part tool smoke requires one active inventory part")
        expected_search = list_parts(db, limit=3, offset=0)
        expected_detail = get_part(db, expected_part_id)

        from app.main import app

        with TestClient(app, base_url="https://partpilot.example") as client:
            assert_unauthorized(client)

            invalid = client.post(
                "/mcp",
                headers=request_headers("not-a-real-token"),
                json=initialize_payload(),
                follow_redirects=False,
            )
            if invalid.status_code != 401:
                fail(f"Invalid bearer token returned {invalid.status_code}")

            bad_origin_headers = request_headers(issued.access_token)
            bad_origin_headers["Origin"] = "https://attacker.example"
            bad_origin = client.post(
                "/mcp",
                headers=bad_origin_headers,
                json=initialize_payload(),
                follow_redirects=False,
            )
            if bad_origin.status_code != 403:
                fail(f"Invalid Origin returned {bad_origin.status_code}")

            initialized = client.post(
                "/mcp",
                headers=request_headers(issued.access_token),
                json=initialize_payload(),
                follow_redirects=False,
            )
            if initialized.status_code != 200:
                fail(
                    "Authenticated initialize failed: "
                    f"{initialized.status_code} {initialized.text[:500]}"
                )
            body = initialized.json()
            if body.get("jsonrpc") != "2.0" or body.get("id") != 1:
                fail(f"Unexpected initialize response: {body}")
            result = body.get("result")
            if not isinstance(result, dict):
                fail(f"Initialize response has no result: {body}")
            server_info = result.get("serverInfo", {})
            if server_info.get("name") != "Part Pilot":
                fail(f"Unexpected MCP server info: {server_info}")

            tools = client.post(
                "/mcp",
                headers=request_headers(issued.access_token),
                json=tools_payload(),
                follow_redirects=False,
            )
            if tools.status_code != 200:
                fail(f"tools/list failed: {tools.status_code} {tools.text[:500]}")
            tools_body = tools.json()
            listed = tools_body.get("result", {}).get("tools")
            if not isinstance(listed, list):
                fail(f"tools/list returned no tool list: {tools_body}")
            listed_by_name = {
                item.get("name"): item
                for item in listed
                if isinstance(item, dict)
            }
            if set(listed_by_name) != {
                "search_parts",
                "get_part_details",
                "list_projects",
                "get_project_details",
                "list_reservations",
                "get_reservation_details",
            }:
                fail(f"Unexpected MCP tools: {sorted(listed_by_name)}")
            for name, item in listed_by_name.items():
                annotations = item.get("annotations") or {}
                if annotations.get("readOnlyHint") is not True:
                    fail(f"{name} is not marked read-only: {annotations}")
                if annotations.get("destructiveHint") is not False:
                    fail(f"{name} is not marked non-destructive: {annotations}")
                if not isinstance(item.get("outputSchema"), dict):
                    fail(f"{name} has no structured output schema")

            search_response = client.post(
                "/mcp",
                headers=request_headers(issued.access_token),
                json=call_tool_payload(3, "search_parts", {"limit": 3}),
                follow_redirects=False,
            )
            if search_response.status_code != 200:
                fail(
                    "search_parts failed: "
                    f"{search_response.status_code} {search_response.text[:500]}"
                )
            search_rpc = search_response.json()
            search_result = search_rpc.get("result", {})
            if search_result.get("isError") is True:
                fail(f"search_parts returned a tool error: {search_result}")
            search_data = search_result.get("structuredContent")
            if not isinstance(search_data, dict):
                fail(f"search_parts returned no structured content: {search_result}")
            expected_ids = [part.id for part in expected_search.parts]
            actual_rows = search_data.get("parts")
            if not isinstance(actual_rows, list):
                fail(f"search_parts returned no compact rows: {search_data}")
            actual_ids = [row.get("id") for row in actual_rows if isinstance(row, dict)]
            if actual_ids != expected_ids:
                fail(f"search_parts IDs differ: {actual_ids} != {expected_ids}")
            if search_data.get("total") != expected_search.total:
                fail("search_parts total differs from the inventory service")
            if search_data.get("returned") != len(expected_search.parts):
                fail("search_parts returned count is incorrect")
            content = search_result.get("content")
            if (
                not isinstance(content, list)
                or not content
                or not isinstance(content[0], dict)
                or content[0].get("type") != "text"
                or "summary" not in str(content[0].get("text", ""))
            ):
                fail("search_parts has no structured-compatible text fallback")

            detail_response = client.post(
                "/mcp",
                headers=request_headers(issued.access_token),
                json=call_tool_payload(
                    4,
                    "get_part_details",
                    {"part_id": expected_part_id},
                ),
                follow_redirects=False,
            )
            if detail_response.status_code != 200:
                fail(
                    "get_part_details failed: "
                    f"{detail_response.status_code} {detail_response.text[:500]}"
                )
            detail_result = detail_response.json().get("result", {})
            if detail_result.get("isError") is True:
                fail(f"get_part_details returned a tool error: {detail_result}")
            detail_data = detail_result.get("structuredContent")
            if not isinstance(detail_data, dict):
                fail("get_part_details returned no structured content")
            if detail_data.get("part") != expected_detail.model_dump(mode="json"):
                fail("get_part_details differs from the canonical part service")

            audit_check = SessionLocal()
            try:
                tool_audits = list(
                    audit_check.execute(
                        select(AuditLog)
                        .where(AuditLog.event_type == "mcp.tool_called")
                        .order_by(AuditLog.id.asc())
                    ).scalars()
                )
                tool_audits = [
                    row
                    for row in tool_audits
                    if isinstance(row.metadata_json, dict)
                    and row.metadata_json.get("client_id") == client_identifier
                ]
                if len(tool_audits) != 2:
                    fail(f"Expected two MCP tool audits, got {len(tool_audits)}")
                if {row.metadata_json.get("tool") for row in tool_audits} != {
                    "search_parts",
                    "get_part_details",
                }:
                    fail("MCP tool audit names are incorrect")
                for row in tool_audits:
                    if row.actor_type != "mcp" or row.actor_user_id != user.id:
                        fail("MCP tool audit actor attribution is incorrect")
                    if row.metadata_json.get("success") is not True:
                        fail("Successful MCP tool call was audited as failed")
                    serialized = json.dumps(row.metadata_json, sort_keys=True)
                    for secret in (
                        issued.access_token,
                        issued.refresh_token,
                        code.code,
                    ):
                        if secret and secret in serialized:
                            fail("MCP tool audit leaked an OAuth secret")
            finally:
                audit_check.close()

            disabled_db = SessionLocal()
            try:
                set_app_setting(disabled_db, MCP_ENABLED_KEY, False, commit=True)
            finally:
                disabled_db.close()
            disabled = client.post(
                "/mcp",
                headers=request_headers(issued.access_token),
                json=initialize_payload(),
                follow_redirects=False,
            )
            if disabled.status_code != 503:
                fail(f"Disabled MCP returned {disabled.status_code}")

        cleanup = SessionLocal()
        try:
            for key, (value_json, value_text, updated_at) in original_settings.items():
                setting = cleanup.execute(
                    select(AppSetting).where(AppSetting.key == key)
                ).scalar_one()
                setting.value_json = copy.deepcopy(value_json)
                setting.value_text = value_text
                setting.updated_at = updated_at

            if client_identifier is not None:
                audit_ids = [
                    row.id
                    for row in cleanup.execute(
                        select(AuditLog).where(AuditLog.event_type.like("mcp.%"))
                    ).scalars()
                    if isinstance(row.metadata_json, dict)
                    and row.metadata_json.get("client_id") == client_identifier
                ]
                from app.models import McpOAuthClient

                client_row = cleanup.execute(
                    select(McpOAuthClient).where(
                        McpOAuthClient.client_id == client_identifier
                    )
                ).scalar_one_or_none()
                if client_row is not None:
                    cleanup.delete(client_row)
            if audit_ids:
                cleanup.query(AuditLog).filter(AuditLog.id.in_(audit_ids)).delete(
                    synchronize_session=False
                )
            cleanup.commit()
        finally:
            cleanup.close()
        restore_sequences(before)
        after = database_snapshot()
        if after != before:
            fail("MCP transport smoke did not restore the exact database snapshot")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(
        "[PASS] MCP Streamable HTTP supports exact /mcp routing, OAuth bearer "
        "validation, protected-resource challenges, Origin rejection, disabled "
        "gating, six read-only workspace tools, secret-free audits, and exact cleanup"
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
