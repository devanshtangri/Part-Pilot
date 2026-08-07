from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal, dispose_database_engine
from app.models import (
    AuditLog,
    McpOAuthClient,
    McpOAuthConsent,
    McpOAuthToken,
    User,
)
from app.services.auth import create_session
from app.services.mcp_oauth import list_connected_oauth_clients


# PARTPILOT:MCP_OAUTH_CLIENT_ADMIN_SMOKE:V541
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


def create_database_backup() -> Path:
    descriptor, raw_path = tempfile.mkstemp(
        prefix="partpilot_patch541_oauth_admin_",
        suffix=".db",
    )
    os.close(descriptor)
    backup_path = Path(raw_path)
    source = sqlite3.connect(sqlite_path())
    destination = sqlite3.connect(backup_path)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return backup_path


def restore_database_backup(backup_path: Path) -> None:
    dispose_database_engine()
    database = sqlite_path()
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(str(database) + suffix)
        if sidecar.exists():
            sidecar.unlink()
    source = sqlite3.connect(backup_path)
    destination = sqlite3.connect(database)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    dispose_database_engine()


def expected_client_fields() -> set[str]:
    return {
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


def validate_payload(
    payload: dict[str, object],
    *,
    expected_names: list[str],
) -> None:
    if set(payload) != {"clients", "total"}:
        fail(f"Unexpected top-level fields: {sorted(payload)}")
    clients = payload.get("clients")
    if not isinstance(clients, list):
        fail(f"Connected-client collection is invalid: {clients!r}")
    if payload.get("total") != len(expected_names):
        fail(f"Unexpected connected-client total: {payload.get('total')!r}")
    names = [
        item.get("client_name")
        for item in clients
        if isinstance(item, dict)
    ]
    if names != expected_names:
        fail(f"Unexpected connected-client order/names: {names}")

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
    for item in clients:
        if not isinstance(item, dict):
            fail(f"OAuth administration client is not an object: {item!r}")
        if set(item) != expected_client_fields():
            fail(
                f"{item.get('client_name', 'Unknown')} has unexpected fields: "
                f"{sorted(set(item) ^ expected_client_fields())}"
            )
        name = str(item["client_name"])
        for field, expected_value in expected[name].items():
            if item.get(field) != expected_value:
                fail(
                    f"{name} field {field} expected {expected_value!r}, "
                    f"got {item.get(field)!r}"
                )
        if not str(item["client_id"]).startswith("pp_mcp_client_"):
            fail(f"{name} client ID is malformed")
        total_token_count = item.get("total_token_count")
        if (
            not isinstance(total_token_count, int)
            or isinstance(total_token_count, bool)
            or total_token_count < 1
        ):
            fail(f"{name} historical token count is invalid")
        for field in ("created_at", "connected_at"):
            if not isinstance(item.get(field), str) or not item[field]:
                fail(f"{name} is missing {field}")
        if item.get("last_used_at") is not None and not isinstance(
            item.get("last_used_at"),
            str,
        ):
            fail(f"{name} last_used_at has an invalid type")

    serialized = json.dumps(payload, sort_keys=True).casefold()
    for forbidden_path in (
        "/api/mcp/auth_callback",
        "/connector/oauth/",
    ):
        if forbidden_path in serialized:
            fail(f"Payload exposed a callback path: {forbidden_path!r}")


def require_no_store(response) -> None:
    if response.headers.get("cache-control") != "no-store":
        fail("OAuth administration response lacks Cache-Control no-store")
    if response.headers.get("pragma") != "no-cache":
        fail("OAuth administration response lacks Pragma no-cache")


def check_only() -> None:
    from app.main import app

    with TestClient(app) as client:
        get_response = client.get("/api/settings/mcp/oauth-clients")
        if get_response.status_code != 401:
            fail(f"Unauthenticated GET returned {get_response.status_code}")
        delete_response = client.delete(
            "/api/settings/mcp/oauth-clients/9"
        )
        if delete_response.status_code != 401:
            fail(
                "Unauthenticated OAuth client DELETE returned "
                f"{delete_response.status_code}"
            )
        openapi = client.get("/openapi.json")
        if openapi.status_code != 200:
            fail("OpenAPI document is unavailable")
        paths = openapi.json().get("paths", {})
        if set(paths.get("/api/settings/mcp/oauth-clients", {})) != {"get", "post"}:
            fail("OAuth client list OpenAPI contract changed")
        if set(
            paths.get(
                "/api/settings/mcp/oauth-clients/{client_database_id}",
                {},
            )
        ) != {"delete"}:
            fail("OAuth client revocation OpenAPI contract changed")

    print(
        "[PASS] OAuth client GET/POST/DELETE administration routes are protected "
        "and have exact OpenAPI methods"
    )


def full_flow() -> None:
    before = database_snapshot()
    backup_path = create_database_backup()
    try:
        db = SessionLocal()
        try:
            user = db.execute(
                select(User).order_by(User.id.asc())
            ).scalars().first()
            if user is None:
                fail("OAuth administration smoke requires one existing user")
            user_id = user.id
            canonical = list_connected_oauth_clients(db, user_id=user_id)
            validate_payload(
                canonical.model_dump(mode="json"),
                expected_names=["Claude", "ChatGPT"],
            )
            baseline_event_ids = set(
                db.execute(
                    select(AuditLog.id).where(
                        AuditLog.event_type == "mcp.oauth_client_revoked",
                        AuditLog.entity_id == 9,
                    )
                ).scalars()
            )
            session_token = create_session(
                db,
                user=user,
                user_agent="Patch 541 OAuth revocation smoke",
                ip_address="127.0.0.1",
                commit=True,
            )
            bearer = session_token.token
            claude_client_id = canonical.clients[0].client_id
        finally:
            db.close()

        from app.main import app

        headers = {"Authorization": f"Bearer {bearer}"}
        with TestClient(app) as client:
            missing = client.delete(
                "/api/settings/mcp/oauth-clients/999999",
                headers=headers,
            )
            if missing.status_code != 404:
                fail(f"Unknown OAuth client DELETE returned {missing.status_code}")
            require_no_store(missing)
            if missing.json() != {
                "detail": "Connected OAuth client was not found."
            }:
                fail(f"Unexpected not-found response: {missing.text[:500]}")

            revoked = client.delete(
                "/api/settings/mcp/oauth-clients/9",
                headers=headers,
            )
            if revoked.status_code != 200:
                fail(
                    f"Claude revocation failed: {revoked.status_code} "
                    f"{revoked.text[:500]}"
                )
            require_no_store(revoked)
            validate_payload(
                revoked.json(),
                expected_names=["ChatGPT"],
            )

            listed = client.get(
                "/api/settings/mcp/oauth-clients",
                headers=headers,
            )
            if listed.status_code != 200:
                fail(f"Post-revocation GET returned {listed.status_code}")
            require_no_store(listed)
            validate_payload(
                listed.json(),
                expected_names=["ChatGPT"],
            )

            repeated = client.delete(
                "/api/settings/mcp/oauth-clients/9",
                headers=headers,
            )
            if repeated.status_code != 404:
                fail(f"Repeated revocation returned {repeated.status_code}")
            require_no_store(repeated)

        verification = SessionLocal()
        try:
            claude = verification.get(McpOAuthClient, 9)
            chatgpt = verification.get(McpOAuthClient, 13)
            if claude is None or claude.revoked_at is None:
                fail("Claude client revocation marker is missing")
            if chatgpt is None or chatgpt.revoked_at is not None:
                fail("ChatGPT client was modified by Claude revocation")
            if verification.execute(
                select(McpOAuthToken).where(
                    McpOAuthToken.client_id == 9,
                    McpOAuthToken.revoked_at.is_(None),
                )
            ).scalars().first() is not None:
                fail("Claude retains an active OAuth token")
            claude_consent = verification.execute(
                select(McpOAuthConsent).where(
                    McpOAuthConsent.client_id == 9,
                    McpOAuthConsent.user_id == user_id,
                )
            ).scalar_one()
            if claude_consent.revoked_at is None:
                fail("Claude consent revocation marker is missing")
            event_rows = list(
                verification.execute(
                    select(AuditLog).where(
                        AuditLog.event_type == "mcp.oauth_client_revoked",
                        AuditLog.entity_id == 9,
                    )
                ).scalars()
            )
            new_events = [
                event
                for event in event_rows
                if event.id not in baseline_event_ids
            ]
            if len(new_events) != 1:
                fail(
                    "Expected one new Claude revocation audit, got "
                    f"{len(new_events)}"
                )
            event = new_events[0]
            if (
                event.actor_type != "user"
                or event.actor_user_id != user_id
                or event.metadata_json != {"client_id": claude_client_id}
            ):
                fail("Claude revocation audit metadata is incorrect")
            remaining = list_connected_oauth_clients(
                verification,
                user_id=user_id,
            )
            validate_payload(
                remaining.model_dump(mode="json"),
                expected_names=["ChatGPT"],
            )
        finally:
            verification.close()
    finally:
        restore_database_backup(backup_path)
        backup_path.unlink(missing_ok=True)

    if database_snapshot() != before:
        fail("OAuth revocation smoke did not restore the copied database exactly")

    print(
        "[PASS] OAuth client revocation is authenticated, current-user scoped, "
        "audited, idempotently hidden, preserves the other connection, and "
        "restores the copied database exactly"
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
