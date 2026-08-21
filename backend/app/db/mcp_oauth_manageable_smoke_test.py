from __future__ import annotations

import argparse
import copy
import sqlite3
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, or_, select, update

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.db.settings import set_app_setting
from app.main import app
from app.models import (
    AppSetting,
    AuditLog,
    McpOAuthAuthorizationCode,
    McpOAuthClient,
    McpOAuthConsent,
    McpOAuthToken,
    User,
    UserSession,
)
from app.services.auth import create_session
from app.services.mcp_oauth import (
    MCP_ENABLED_KEY,
    MCP_READ_ENABLED_KEY,
    MCP_SCOPE_READ,
    exchange_authorization_code,
    grant_consent,
    issue_authorization_code,
    pkce_s256_challenge,
    register_client,
)
from app.services.mcp_permissions import client_tool_permissions_response


REDIRECT = "https://client.example/callback"
RESOURCE = "https://partpilot.example/mcp"
VERIFIER = "v" * 64


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def sqlite_path():
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"SQLite required, got {url!r}")
    return url[len(prefix):]


def logical_snapshot():
    db = sqlite3.connect(sqlite_path())
    db.row_factory = sqlite3.Row
    try:
        tables = [
            row[0]
            for row in db.execute(
                "select name from sqlite_master where type='table' "
                "and name not like 'sqlite_%' order by name"
            )
        ]
        result = {}
        for table in tables:
            info = list(db.execute(f'pragma table_info("{table}")'))
            cols = [row[1] for row in info]
            primary = [row[1] for row in info if row[5]]
            order = primary or cols
            rows = db.execute(
                f'select * from "{table}" order by '
                + ",".join(f'"{column}"' for column in order)
            ).fetchall()
            result[table] = [dict(row) for row in rows]
        return result
    finally:
        db.close()


def require_no_store(response):
    if (
        response.headers.get("cache-control") != "no-store"
        or response.headers.get("pragma") != "no-cache"
    ):
        fail("no-store headers missing")


EXPECTED_FIELDS = {
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
    "registered_by_current_user",
    "denied_tools",
    "tool_permissions",
}
PERMISSION_FIELDS = {
    "name",
    "label",
    "capability",
    "global_enabled",
    "denied",
    "effective_enabled",
}


def validate_payload(payload):
    if set(payload) != {"clients", "total"}:
        fail(f"top-level fields wrong: {sorted(payload)}")
    if payload["total"] != len(payload["clients"]):
        fail("total mismatch")
    for item in payload["clients"]:
        if set(item) != EXPECTED_FIELDS:
            fail(f"manageable fields wrong: {sorted(set(item) ^ EXPECTED_FIELDS)}")
        for value in item.values():
            if isinstance(value, str) and value.startswith("pp_mcp_secret_"):
                fail("payload exposed plaintext client secret")
        if item["status"] not in {"registered", "connected", "revoked"}:
            fail(f"unexpected status {item['status']}")
        if not isinstance(item["denied_tools"], list) or any(
            not isinstance(name, str) for name in item["denied_tools"]
        ):
            fail("denied_tools shape wrong")
        if not isinstance(item["tool_permissions"], list):
            fail("tool_permissions shape wrong")
        for permission in item["tool_permissions"]:
            if not isinstance(permission, dict) or set(permission) != PERMISSION_FIELDS:
                fail("tool permission fields wrong")
            if not isinstance(permission["name"], str) or not isinstance(
                permission["label"], str
            ):
                fail("tool permission identity wrong")
            if permission["capability"] not in {"read", "write"}:
                fail("tool permission capability wrong")
            if not all(
                isinstance(permission[key], bool)
                for key in ("global_enabled", "denied", "effective_enabled")
            ):
                fail("tool permission booleans wrong")


def check_only():
    with TestClient(app) as client:
        response = client.get("/api/settings/mcp/oauth-clients/manageable")
        if response.status_code != 401:
            fail(f"unauth GET returned {response.status_code}")
        openapi = client.get("/openapi.json")
        if openapi.status_code != 200:
            fail("OpenAPI unavailable")
        methods = set(
            openapi.json()
            .get("paths", {})
            .get("/api/settings/mcp/oauth-clients/manageable", {})
        )
        if methods != {"get"}:
            fail(f"OpenAPI methods wrong: {methods}")
    print("[PASS] manageable OAuth GET is protected and registered in OpenAPI")


def full():
    before = logical_snapshot()
    client_ids: list[int] = []
    consent_ids: list[int] = []
    code_ids: list[int] = []
    token_ids: list[int] = []
    session_ids: list[int] = []
    created_setting_ids: list[int] = []
    setting_snapshots: dict[str, tuple | None] = {}
    audit_floor = 0
    uid = None
    registered_id = None
    registered_public_id = None
    connected_id = None
    connected_public_id = None
    expected_registered_permissions = None
    expected_connected_permissions = None
    bearer = None

    db = SessionLocal()
    try:
        user = db.execute(
            select(User).where(User.is_active.is_(True)).order_by(User.id.asc())
        ).scalars().first()
        if user is None:
            fail("existing active user required")
        uid = user.id
        audit_floor = int(
            db.execute(select(func.coalesce(func.max(AuditLog.id), 0))).scalar_one()
        )

        for key in (MCP_ENABLED_KEY, MCP_READ_ENABLED_KEY):
            setting = db.execute(
                select(AppSetting).where(AppSetting.key == key)
            ).scalar_one_or_none()
            if setting is None:
                setting_snapshots[key] = None
            else:
                setting_snapshots[key] = (
                    setting.id,
                    copy.deepcopy(setting.value_json),
                    setting.value_text,
                    setting.created_at,
                    setting.updated_at,
                )
            configured = set_app_setting(db, key, True, commit=False)
            if setting is None:
                created_setting_ids.append(configured.id)
        db.commit()

        registered = register_client(
            db,
            client_name="Patch 711 Registered " + uuid4().hex[:8],
            redirect_uris=[REDIRECT],
            grant_types=("authorization_code", "refresh_token"),
            response_types=("code",),
            token_endpoint_auth_method="none",
            metadata={"fixture": "patch-711-registered", "client_type": "public"},
            actor_user_id=uid,
            registered_by_user_id=uid,
            commit=True,
        )
        registered_id = registered.client.id
        registered_public_id = registered.client_id
        client_ids.append(registered_id)
        expected_registered_permissions = client_tool_permissions_response(
            db, registered.client.denied_tools_json
        ).model_dump(mode="json")

        connected = register_client(
            db,
            client_name="Patch 711 Connected " + uuid4().hex[:8],
            redirect_uris=[REDIRECT],
            grant_types=("authorization_code", "refresh_token"),
            response_types=("code",),
            token_endpoint_auth_method="none",
            metadata={"fixture": "patch-711-connected", "client_type": "public"},
            actor_user_id=uid,
            registered_by_user_id=uid,
            commit=True,
        )
        connected_id = connected.client.id
        connected_public_id = connected.client_id
        client_ids.append(connected_id)

        consent = grant_consent(
            db,
            user_id=uid,
            client_id=connected_public_id,
            scopes=[MCP_SCOPE_READ],
            commit=True,
        )
        consent_ids.append(consent.id)

        code = issue_authorization_code(
            db,
            client_id=connected_public_id,
            user_id=uid,
            redirect_uri=REDIRECT,
            scopes=[MCP_SCOPE_READ],
            code_challenge=pkce_s256_challenge(VERIFIER),
            code_challenge_method="S256",
            resource_uri=RESOURCE,
            commit=True,
        )
        code_ids.append(code.grant.id)

        tokens = exchange_authorization_code(
            db,
            code=code.code,
            client_id=connected_public_id,
            client_secret=None,
            redirect_uri=REDIRECT,
            code_verifier=VERIFIER,
            resource_uri=RESOURCE,
            commit=True,
        )
        token_ids.append(tokens.token.id)
        expected_connected_permissions = client_tool_permissions_response(
            db, connected.client.denied_tools_json
        ).model_dump(mode="json")

        session_token = create_session(
            db,
            user=user,
            user_agent="Patch 711 manageable smoke",
            ip_address="127.0.0.1",
            commit=True,
        )
        session_ids.append(session_token.session.id)
        bearer = session_token.token
    finally:
        db.close()

    try:
        if None in (
            registered_id,
            registered_public_id,
            connected_id,
            connected_public_id,
            expected_registered_permissions,
            expected_connected_permissions,
            bearer,
        ):
            fail("fixture setup incomplete")

        headers = {"Authorization": f"Bearer {bearer}"}
        with TestClient(app) as client:
            first = client.get(
                "/api/settings/mcp/oauth-clients/manageable", headers=headers
            )
            if first.status_code != 200:
                fail(f"first GET {first.status_code}: {first.text[:300]}")
            require_no_store(first)
            payload = first.json()
            validate_payload(payload)
            by = {item["database_id"]: item for item in payload["clients"]}

            registered_fixture = by.get(registered_id)
            if not registered_fixture:
                fail("registered fixture missing")
            if (
                registered_fixture["client_id"] != registered_public_id
                or registered_fixture["status"] != "registered"
                or not registered_fixture["registered_by_current_user"]
                or registered_fixture["connected_at"] is not None
                or registered_fixture["scopes"] != []
            ):
                fail("registered fixture identity/status wrong")
            if any(
                registered_fixture[key] != 0
                for key in (
                    "active_token_count",
                    "token_family_count",
                    "total_token_count",
                    "authorization_code_count",
                    "active_consent_count",
                )
            ):
                fail("registered fixture counters nonzero")
            if (
                registered_fixture["denied_tools"]
                != expected_registered_permissions["denied_tools"]
                or registered_fixture["tool_permissions"]
                != expected_registered_permissions["tools"]
            ):
                fail("registered fixture permissions wrong")

            connected_fixture = by.get(connected_id)
            if not connected_fixture:
                fail("connected fixture missing")
            if (
                connected_fixture["client_id"] != connected_public_id
                or connected_fixture["status"] != "connected"
                or not connected_fixture["registered_by_current_user"]
                or connected_fixture["connected_at"] is None
                or connected_fixture["last_used_at"] is not None
                or connected_fixture["scopes"] != [MCP_SCOPE_READ]
            ):
                fail("connected fixture identity/status/scopes wrong")
            expected_counts = {
                "active_token_count": 1,
                "token_family_count": 1,
                "total_token_count": 1,
                "authorization_code_count": 1,
                "active_consent_count": 1,
            }
            if any(
                connected_fixture[key] != expected
                for key, expected in expected_counts.items()
            ):
                fail(f"connected fixture counters wrong: {connected_fixture}")
            if (
                connected_fixture["denied_tools"]
                != expected_connected_permissions["denied_tools"]
                or connected_fixture["tool_permissions"]
                != expected_connected_permissions["tools"]
            ):
                fail("connected fixture permissions wrong")

            revoked = client.delete(
                f"/api/settings/mcp/oauth-clients/{registered_id}", headers=headers
            )
            if revoked.status_code != 200:
                fail(
                    "registered fixture DELETE returned "
                    f"{revoked.status_code}: {revoked.text[:300]}"
                )
            require_no_store(revoked)

            second = client.get(
                "/api/settings/mcp/oauth-clients/manageable", headers=headers
            )
            if second.status_code != 200:
                fail(f"second GET {second.status_code}: {second.text[:300]}")
            require_no_store(second)
            payload2 = second.json()
            validate_payload(payload2)
            by2 = {item["database_id"]: item for item in payload2["clients"]}
            revoked_fixture = by2.get(registered_id)
            connected_fixture2 = by2.get(connected_id)
            if (
                not revoked_fixture
                or revoked_fixture["status"] != "revoked"
                or not revoked_fixture["registered_by_current_user"]
            ):
                fail("revoked fixture wrong")
            if (
                not connected_fixture2
                or connected_fixture2["status"] != "connected"
                or connected_fixture2["client_id"] != connected_public_id
            ):
                fail("connected fixture changed during revoked-state coverage")
    finally:
        cleanup = SessionLocal()
        try:
            entity_pairs = []
            entity_pairs.extend(("mcp_oauth_client", row_id) for row_id in client_ids)
            entity_pairs.extend(("mcp_oauth_consent", row_id) for row_id in consent_ids)
            entity_pairs.extend(
                ("mcp_oauth_authorization_code", row_id) for row_id in code_ids
            )
            entity_pairs.extend(("mcp_oauth_token", row_id) for row_id in token_ids)
            audit_ids = []
            if entity_pairs:
                audit_ids = list(
                    cleanup.execute(
                        select(AuditLog.id).where(
                            AuditLog.id > audit_floor,
                            or_(
                                *(
                                    (AuditLog.entity_type == entity_type)
                                    & (AuditLog.entity_id == entity_id)
                                    for entity_type, entity_id in entity_pairs
                                )
                            ),
                        )
                    ).scalars()
                )

            if session_ids:
                cleanup.execute(
                    delete(UserSession).where(UserSession.id.in_(session_ids))
                )
            if audit_ids:
                cleanup.execute(delete(AuditLog).where(AuditLog.id.in_(audit_ids)))
            if token_ids:
                cleanup.execute(
                    delete(McpOAuthToken).where(McpOAuthToken.id.in_(token_ids))
                )
            if code_ids:
                cleanup.execute(
                    delete(McpOAuthAuthorizationCode).where(
                        McpOAuthAuthorizationCode.id.in_(code_ids)
                    )
                )
            if consent_ids:
                cleanup.execute(
                    delete(McpOAuthConsent).where(McpOAuthConsent.id.in_(consent_ids))
                )
            if client_ids:
                cleanup.execute(
                    delete(McpOAuthClient).where(McpOAuthClient.id.in_(client_ids))
                )

            for key, snapshot in setting_snapshots.items():
                if snapshot is None:
                    continue
                row_id, value_json, value_text, created_at, updated_at = snapshot
                cleanup.execute(
                    update(AppSetting)
                    .where(AppSetting.id == row_id, AppSetting.key == key)
                    .values(
                        value_json=copy.deepcopy(value_json),
                        value_text=value_text,
                        created_at=created_at,
                        updated_at=updated_at,
                    )
                )
            if created_setting_ids:
                cleanup.execute(
                    delete(AppSetting).where(AppSetting.id.in_(created_setting_ids))
                )
            cleanup.commit()
        except Exception:
            cleanup.rollback()
            raise
        finally:
            cleanup.close()

    after = logical_snapshot()
    if after != before:
        changed = sorted(
            key
            for key in set(before) | set(after)
            if before.get(key) != after.get(key)
        )
        fail(f"fixture cleanup did not restore logical database exactly: {changed}")
    print(
        "[PASS] manageable OAuth uses fixture-owned registered/connected/revoked "
        "coverage, validates exact counters/scopes/permissions, exposes no secret "
        "material and restores copied DB exactly"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    check_only() if args.check_only else full()


if __name__ == "__main__":
    main()
