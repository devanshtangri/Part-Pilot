from __future__ import annotations

import argparse
import copy
import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.db.settings import set_app_setting
from app.models import AppSetting, AuditLog, User
from app.services.mcp_oauth import (
    MCP_ENABLED_KEY,
    MCP_READ_ENABLED_KEY,
    MCP_SCOPE_READ,
    MCP_WRITE_ENABLED_KEY,
    exchange_authorization_code,
    grant_consent,
    issue_authorization_code,
    pkce_s256_challenge,
    register_client,
)


# PARTPILOT:MCP_STREAMABLE_HTTP_SMOKE:V469
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
    if "oauth-protected-resource/mcp" not in challenge or "mcp:read" not in challenge:
        fail(f"Missing protected-resource challenge: {challenge!r}")
    if response.is_redirect:
        fail("/mcp redirected instead of serving the exact endpoint")


def check_only() -> None:
    from app.main import app

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
        "and safely rejects the non-MCP /mcp/ trailing-slash path"
    )


def full_flow() -> None:
    before = database_snapshot()
    db = SessionLocal()
    client_identifier: str | None = None
    audit_ids: list[int] = []
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
            client_name="Patch 469 Transport Smoke",
            redirect_uris=[REDIRECT],
            token_endpoint_auth_method="none",
            metadata={"fixture": "patch-469"},
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

        audit_ids = [
            int(value)
            for value in db.execute(
                select(AuditLog.id).where(
                    AuditLog.event_type.like("mcp.%"),
                    AuditLog.metadata_json["client_id"].as_string()
                    == client_identifier,
                )
            ).scalars()
        ]

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
            if listed != []:
                fail(f"Patch 469 must expose no tools, got {listed!r}")

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
        "gating, initialize, empty tools/list, and exact fixture cleanup"
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
