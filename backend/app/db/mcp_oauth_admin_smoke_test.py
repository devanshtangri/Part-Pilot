from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import User, UserSession
from app.services.auth import create_session
from app.services.mcp_oauth import list_connected_oauth_clients


# PARTPILOT:MCP_OAUTH_CLIENT_ADMIN_SMOKE:V540
class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def sqlite_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"OAuth administration smoke requires SQLite, got {url!r}")
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
        unauthenticated = client.get("/api/settings/mcp/oauth-clients")
        if unauthenticated.status_code != 401:
            fail(
                "GET /api/settings/mcp/oauth-clients should require "
                f"authentication, got {unauthenticated.status_code}"
            )

        openapi = client.get("/openapi.json")
        if openapi.status_code != 200:
            fail("OpenAPI document is unavailable")
        methods = openapi.json().get("paths", {}).get(
            "/api/settings/mcp/oauth-clients",
            {},
        )
        if set(methods) != {"get"}:
            fail(
                "Unexpected OAuth administration OpenAPI methods: "
                f"{sorted(methods)}"
            )

    print(
        "[PASS] Connected OAuth client administration GET route is protected "
        "and present in OpenAPI"
    )


def validate_payload(payload: dict[str, object]) -> None:
    if payload.get("total") != 2:
        fail(f"Expected two connected clients, got {payload.get('total')!r}")
    clients = payload.get("clients")
    if not isinstance(clients, list) or len(clients) != 2:
        fail(f"Unexpected connected-client collection: {clients!r}")

    names = [item.get("client_name") for item in clients]
    if names != ["Claude", "ChatGPT"]:
        fail(f"Unexpected connected-client order/names: {names}")

    by_name = {
        str(item["client_name"]): item
        for item in clients
        if isinstance(item, dict)
    }
    expected = {
        "Claude": {
            "database_id": 9,
            "status": "connected",
            "client_type": "confidential",
            "token_endpoint_auth_method": "client_secret_post",
            "redirect_origins": ["https://claude.ai"],
            "scopes": ["mcp:read"],
            "active_token_count": 1,
            "token_family_count": 1,
            "authorization_code_count": 1,
            "active_consent_count": 1,
        },
        "ChatGPT": {
            "database_id": 13,
            "status": "connected",
            "client_type": "public",
            "token_endpoint_auth_method": "none",
            "redirect_origins": ["https://chatgpt.com"],
            "scopes": ["mcp:read"],
            "active_token_count": 1,
            "token_family_count": 1,
            "authorization_code_count": 1,
            "active_consent_count": 1,
        },
    }
    for name, expected_fields in expected.items():
        item = by_name.get(name)
        if item is None:
            fail(f"Missing connected client {name}")
        for field, expected_value in expected_fields.items():
            if item.get(field) != expected_value:
                fail(
                    f"{name} field {field} expected {expected_value!r}, "
                    f"got {item.get(field)!r}"
                )
        if not isinstance(item.get("client_id"), str) or not str(
            item["client_id"]
        ).startswith("pp_mcp_client_"):
            fail(f"{name} client ID is missing or malformed")
        for field in ("created_at", "connected_at"):
            if not isinstance(item.get(field), str) or not item[field]:
                fail(f"{name} is missing {field}")
        if item.get("last_used_at") is not None and not isinstance(
            item.get("last_used_at"),
            str,
        ):
            fail(f"{name} last_used_at has an invalid type")
        total_token_count = item.get("total_token_count")
        if (
            not isinstance(total_token_count, int)
            or isinstance(total_token_count, bool)
            or total_token_count < 1
        ):
            fail(
                f"{name} total_token_count must be a positive integer, "
                f"got {total_token_count!r}"
            )

    expected_top_level_fields = {"clients", "total"}
    if set(payload) != expected_top_level_fields:
        fail(
            "OAuth administration payload has unexpected top-level fields: "
            f"{sorted(payload)}"
        )

    expected_client_fields = {
        "database_id",
        "client_id",
        "client_name",
        "status",
        "client_type",
        "token_endpoint_auth_method",
        "redirect_origins",
        "scopes",
        "created_at",
        "connected_at",
        "last_used_at",
        "active_token_count",
        "token_family_count",
        "total_token_count",
        "authorization_code_count",
        "active_consent_count",
    }
    for item in clients:
        if not isinstance(item, dict):
            fail(f"OAuth administration client is not an object: {item!r}")
        actual_fields = set(item)
        if actual_fields != expected_client_fields:
            fail(
                f"{item.get('client_name', 'Unknown')} has unexpected fields: "
                f"missing={sorted(expected_client_fields - actual_fields)}, "
                f"extra={sorted(actual_fields - expected_client_fields)}"
            )

    serialized = json.dumps(payload, sort_keys=True).casefold()
    for forbidden_path in (
        "/api/mcp/auth_callback",
        "/connector/oauth/",
    ):
        if forbidden_path in serialized:
            fail(
                "OAuth administration payload exposed a callback path: "
                f"{forbidden_path!r}"
            )


def full_flow() -> None:
    before = database_snapshot()
    db = SessionLocal()
    session_id: int | None = None
    try:
        user = db.execute(
            select(User).order_by(User.id.asc())
        ).scalars().first()
        if user is None:
            fail("OAuth administration smoke requires one existing user")

        canonical = list_connected_oauth_clients(
            db,
            user_id=user.id,
        )
        validate_payload(canonical.model_dump(mode="json"))

        session_token = create_session(
            db,
            user=user,
            user_agent="Patch 540 OAuth administration smoke",
            ip_address="127.0.0.1",
            commit=False,
        )
        session_id = session_token.session.id
        db.commit()

        headers = {"Authorization": f"Bearer {session_token.token}"}

        from app.main import app

        with TestClient(app) as client:
            response = client.get(
                "/api/settings/mcp/oauth-clients",
                headers=headers,
            )
            if response.status_code != 200:
                fail(
                    "Connected OAuth client GET failed: "
                    f"{response.status_code} {response.text[:500]}"
                )
            if response.headers.get("cache-control") != "no-store":
                fail("Connected OAuth client response lacks Cache-Control no-store")
            if response.headers.get("pragma") != "no-cache":
                fail("Connected OAuth client response lacks Pragma no-cache")
            payload = response.json()
            validate_payload(payload)
            if payload != canonical.model_dump(mode="json"):
                fail(
                    "Connected OAuth client API differs from the canonical "
                    "service response"
                )

        cleanup = SessionLocal()
        try:
            if session_id is not None:
                session = cleanup.get(UserSession, session_id)
                if session is not None:
                    cleanup.delete(session)
            cleanup.commit()
        finally:
            cleanup.close()

        restore_sequences(before)
        if database_snapshot() != before:
            fail(
                "OAuth administration smoke did not restore the exact "
                "database snapshot"
            )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(
        "[PASS] Connected OAuth client administration returns only the current "
        "user's live Claude/ChatGPT connections, exposes safe metadata, sends "
        "no-store headers, and restores the copied database exactly"
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
