from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.db.settings import set_app_setting
from app.models import AuditLog, McpDirectAuth, McpOAuthClient, User
from app.services.api_keys import create_api_key
from app.services.auth import create_session
from app.services.mcp_direct_auth import (
    DIRECT_AUTH_BEARER_KEY,
    DIRECT_AUTH_TRUSTED_NETWORK,
    create_named_direct_client,
)
from app.services.mcp_oauth import register_client
from app.services.mcp_permissions import (
    DEFAULT_MCP_TOOL_PERMISSIONS,
    MCP_TOOL_NAMES,
    MCP_TOOL_PERMISSIONS_KEY,
    McpToolPermissionDeniedError,
    authorize_mcp_tool,
)

# PARTPILOT:MCP_PERMISSION_ADMIN_SMOKE:V650


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def _database_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"MCP permission admin smoke requires SQLite, got {url!r}")
    return Path(url[len(prefix):]).resolve()


def _tool_map(payload: dict) -> dict[str, dict]:
    tools = payload.get("tools")
    if not isinstance(tools, list):
        fail("Permission response tools is not a list")
    result = {item.get("name"): item for item in tools if isinstance(item, dict)}
    if tuple(result) != MCP_TOOL_NAMES:
        fail(f"Permission response tool order/set changed: {tuple(result)}")
    return result


def main() -> None:
    database_path = _database_path()
    before_bytes = database_path.read_bytes()
    db = SessionLocal()
    try:
        user = db.execute(
            select(User).where(User.is_active.is_(True)).order_by(User.id.asc())
        ).scalars().first()
        if user is None:
            fail("MCP permission admin smoke requires one active user")

        session = create_session(
            db,
            user=user,
            user_agent="Patch 650 MCP permission admin smoke",
            ip_address="127.0.0.1",
            commit=False,
        )
        api_key = create_api_key(
            db,
            actor_user_id=user.id,
            name="Patch 650 settings rejection",
            scopes=("inventory:read",),
            commit=False,
        )
        owned_oauth = register_client(
            db,
            client_name="Patch 650 owned OAuth",
            redirect_uris=("https://permission-admin.example/callback",),
            actor_user_id=user.id,
            registered_by_user_id=user.id,
            commit=False,
        ).client
        inaccessible_oauth = register_client(
            db,
            client_name="Patch 650 inaccessible OAuth",
            redirect_uris=("https://permission-inaccessible.example/callback",),
            actor_user_id=user.id,
            registered_by_user_id=None,
            commit=False,
        ).client
        direct = create_named_direct_client(
            db,
            actor_user_id=user.id,
            name="Patch 650 trusted direct",
            mode=DIRECT_AUTH_TRUSTED_NETWORK,
            networks=("203.0.113.252/30",),
            commit=False,
        )
        bearer = create_named_direct_client(
            db,
            actor_user_id=user.id,
            name="Patch 650 bearer rejection",
            mode=DIRECT_AUTH_BEARER_KEY,
            instance_secret=(
                "patch650-permission-admin-smoke-secret-0123456789-"
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            ),
            commit=False,
        )
        db.commit()
        direct_record = direct.record if hasattr(direct, "record") else direct
        bearer_record = bearer.record if hasattr(bearer, "record") else bearer
        bearer_key = bearer.plaintext_key
        set_app_setting(
            db,
            MCP_TOOL_PERMISSIONS_KEY,
            dict(DEFAULT_MCP_TOOL_PERMISSIONS),
            commit=False,
        )
        db.commit()

        existing_permission_audits = set(
            db.execute(
                select(AuditLog.id).where(
                    AuditLog.event_type.in_(
                        (
                            "settings.mcp_tool_permissions_updated",
                            "settings.mcp_oauth_client_permissions_updated",
                            "settings.mcp_direct_client_permissions_updated",
                        )
                    )
                )
            ).scalars()
        )
        session_headers = {"Authorization": f"Bearer {session.token}"}
        api_key_headers = {"Authorization": f"Bearer {api_key.plaintext_key}"}
        mcp_key_headers = {"Authorization": f"Bearer {bearer_key}"}

        from app.main import app

        with TestClient(app) as client:
            for method, path, kwargs in (
                ("get", "/api/settings/mcp/tool-permissions", {}),
                (
                    "patch",
                    "/api/settings/mcp/tool-permissions",
                    {"json": {"permissions": {"list_projects": False}}},
                ),
                (
                    "patch",
                    f"/api/settings/mcp/oauth-clients/{owned_oauth.id}/permissions",
                    {"json": {"denied_tools": ["search_parts"]}},
                ),
                (
                    "patch",
                    f"/api/settings/mcp/direct-clients/{direct_record.id}/permissions",
                    {"json": {"denied_tools": ["search_parts"]}},
                ),
            ):
                response = getattr(client, method)(path, **kwargs)
                if response.status_code != 401:
                    fail(f"Unauthenticated {method.upper()} {path} returned {response.status_code}")

            if client.get(
                "/api/settings/mcp/tool-permissions",
                headers=api_key_headers,
            ).status_code != 401:
                fail("Valid REST API key administered MCP permissions")
            if client.get(
                "/api/settings/mcp/tool-permissions",
                headers=mcp_key_headers,
            ).status_code != 401:
                fail("MCP direct credential administered MCP permissions")

            openapi = client.get("/openapi.json")
            if openapi.status_code != 200:
                fail("OpenAPI document is unavailable")
            paths = openapi.json().get("paths", {})
            expected_paths = {
                "/api/settings/mcp/tool-permissions": {"get", "patch"},
                "/api/settings/mcp/oauth-clients/{client_database_id}/permissions": {"patch"},
                "/api/settings/mcp/direct-clients/{client_id}/permissions": {"patch"},
            }
            for path, methods in expected_paths.items():
                if set(paths.get(path, {})) != methods:
                    fail(f"Unexpected permission OpenAPI methods for {path}: {paths.get(path)}")

            loaded = client.get(
                "/api/settings/mcp/tool-permissions",
                headers=session_headers,
            )
            if loaded.status_code != 200:
                fail(f"Global permission GET failed: {loaded.status_code} {loaded.text[:500]}")
            loaded_tools = _tool_map(loaded.json())
            for name, item in loaded_tools.items():
                capability = item.get("capability")
                if capability not in {"read", "write"}:
                    fail(f"Unexpected MCP tool capability for {name}: {capability}")
                expected_enabled = capability == "read"
                if item.get("enabled") is not expected_enabled:
                    fail(f"MCP default permission is unsafe for {name}: {item}")
            if sum(item.get("capability") == "read" for item in loaded_tools.values()) != 6:
                fail("Expected six MCP read permissions")
            if sum(item.get("capability") == "write" for item in loaded_tools.values()) != 8:
                fail("Expected eight MCP write permissions")

            invalid_global = client.patch(
                "/api/settings/mcp/tool-permissions",
                headers=session_headers,
                json={"permissions": {"not_a_tool": False}},
            )
            if invalid_global.status_code != 422:
                fail(f"Unknown global tool returned {invalid_global.status_code}")
            non_boolean = client.patch(
                "/api/settings/mcp/tool-permissions",
                headers=session_headers,
                json={"permissions": {"list_projects": "false"}},
            )
            if non_boolean.status_code != 422:
                fail("Non-boolean global permission was coerced instead of rejected")
            empty_global = client.patch(
                "/api/settings/mcp/tool-permissions",
                headers=session_headers,
                json={"permissions": {}},
            )
            if empty_global.status_code != 422:
                fail("Empty global permission PATCH was accepted")

            global_changed = client.patch(
                "/api/settings/mcp/tool-permissions",
                headers=session_headers,
                json={"permissions": {"list_projects": False}},
            )
            if global_changed.status_code != 200:
                fail(f"Global permission PATCH failed: {global_changed.status_code} {global_changed.text[:500]}")
            if _tool_map(global_changed.json())["list_projects"].get("enabled") is not False:
                fail("Global list_projects permission did not disable")
            global_unchanged = client.patch(
                "/api/settings/mcp/tool-permissions",
                headers=session_headers,
                json={"permissions": {"list_projects": False}},
            )
            if global_unchanged.status_code != 200:
                fail("No-op global permission PATCH failed")

            invalid_client_tool = client.patch(
                f"/api/settings/mcp/oauth-clients/{owned_oauth.id}/permissions",
                headers=session_headers,
                json={"denied_tools": ["missing_tool"]},
            )
            if invalid_client_tool.status_code != 422:
                fail("Unknown OAuth denied tool was accepted")
            inaccessible = client.patch(
                f"/api/settings/mcp/oauth-clients/{inaccessible_oauth.id}/permissions",
                headers=session_headers,
                json={"denied_tools": ["search_parts"]},
            )
            if inaccessible.status_code != 404:
                fail("Inaccessible OAuth client permission update was not hidden as 404")

            oauth_changed = client.patch(
                f"/api/settings/mcp/oauth-clients/{owned_oauth.id}/permissions",
                headers=session_headers,
                json={"denied_tools": ["search_parts"]},
            )
            if oauth_changed.status_code != 200:
                fail(f"OAuth permission PATCH failed: {oauth_changed.status_code} {oauth_changed.text[:500]}")
            oauth_tools = _tool_map(oauth_changed.json())
            if oauth_changed.json().get("denied_tools") != ["search_parts"]:
                fail("OAuth denied-tools response is not canonical")
            if oauth_tools["search_parts"].get("denied") is not True or oauth_tools["search_parts"].get("effective_enabled") is not False:
                fail("OAuth explicit deny did not become effective")
            if oauth_tools["list_projects"].get("denied") is not False or oauth_tools["list_projects"].get("global_enabled") is not False or oauth_tools["list_projects"].get("effective_enabled") is not False:
                fail("OAuth effective permission ignored global hard ceiling")
            if oauth_tools["get_part_details"].get("effective_enabled") is not True:
                fail("OAuth inherited globally-enabled tool was unexpectedly blocked")

            oauth_noop = client.patch(
                f"/api/settings/mcp/oauth-clients/{owned_oauth.id}/permissions",
                headers=session_headers,
                json={"denied_tools": ["search_parts", "search_parts"]},
            )
            if oauth_noop.status_code != 200 or oauth_noop.json().get("denied_tools") != ["search_parts"]:
                fail("OAuth no-op/canonicalization failed")

            manageable = client.get(
                "/api/settings/mcp/oauth-clients/manageable",
                headers=session_headers,
            )
            if manageable.status_code != 200:
                fail("Manageable OAuth clients endpoint failed")
            owned_summary = next(
                (row for row in manageable.json().get("clients", []) if row.get("database_id") == owned_oauth.id),
                None,
            )
            if owned_summary is None or owned_summary.get("denied_tools") != ["search_parts"]:
                fail("Manageable OAuth summary omitted denied tools")
            _tool_map({"tools": owned_summary.get("tool_permissions")})

            direct_changed = client.patch(
                f"/api/settings/mcp/direct-clients/{direct_record.id}/permissions",
                headers=session_headers,
                json={"denied_tools": ["get_part_details", "search_parts"]},
            )
            if direct_changed.status_code != 200:
                fail(f"Direct permission PATCH failed: {direct_changed.status_code} {direct_changed.text[:500]}")
            if direct_changed.json().get("denied_tools") != ["search_parts", "get_part_details"]:
                fail("Direct denied-tools order is not canonical")
            direct_tools = _tool_map(direct_changed.json())
            if direct_tools["search_parts"].get("effective_enabled") is not False:
                fail("Direct explicit deny did not become effective")

            direct_list = client.get(
                "/api/settings/mcp/direct-clients",
                headers=session_headers,
            )
            if direct_list.status_code != 200:
                fail("Direct clients list failed after permission update")
            direct_summary = next(
                (row for row in direct_list.json().get("clients", []) if row.get("id") == direct_record.id),
                None,
            )
            if direct_summary is None or direct_summary.get("denied_tools") != ["search_parts", "get_part_details"]:
                fail("Direct client summary omitted denied tools")
            _tool_map({"tools": direct_summary.get("tool_permissions")})

            # Immediate runtime policy effect does not require credential/token rotation.
            runtime_db = SessionLocal()
            try:
                oauth_principal = {
                    "auth_method": "oauth",
                    "actor_type": "mcp",
                    "actor_user_id": user.id,
                    "scopes": ["mcp:read"],
                    "resource_uri": "https://partpilot.example/mcp",
                    "oauth": {
                        "token_id": 1,
                        "client_database_id": owned_oauth.id,
                        "client_id": owned_oauth.client_id,
                    },
                }
                try:
                    authorize_mcp_tool(runtime_db, oauth_principal, "search_parts")
                except McpToolPermissionDeniedError:
                    pass
                else:
                    fail("OAuth deny did not affect runtime authorization immediately")
            finally:
                runtime_db.close()

            revoked_direct = client.delete(
                f"/api/settings/mcp/direct-clients/{direct_record.id}",
                headers=session_headers,
            )
            if revoked_direct.status_code != 200:
                fail("Direct fixture revocation failed")
            revoked_direct_update = client.patch(
                f"/api/settings/mcp/direct-clients/{direct_record.id}/permissions",
                headers=session_headers,
                json={"denied_tools": []},
            )
            if revoked_direct_update.status_code != 404:
                fail("Revoked direct client remained permission-editable")

            revoked_oauth = client.delete(
                f"/api/settings/mcp/oauth-clients/{owned_oauth.id}",
                headers=session_headers,
            )
            if revoked_oauth.status_code != 200:
                fail(f"OAuth fixture revocation failed: {revoked_oauth.status_code} {revoked_oauth.text[:500]}")
            revoked_oauth_update = client.patch(
                f"/api/settings/mcp/oauth-clients/{owned_oauth.id}/permissions",
                headers=session_headers,
                json={"denied_tools": []},
            )
            if revoked_oauth_update.status_code != 404:
                fail("Revoked OAuth client remained permission-editable")

        audit_db = SessionLocal()
        try:
            new_audits = list(
                audit_db.execute(
                    select(AuditLog).where(
                        AuditLog.event_type.in_(
                            (
                                "settings.mcp_tool_permissions_updated",
                                "settings.mcp_oauth_client_permissions_updated",
                                "settings.mcp_direct_client_permissions_updated",
                            )
                        )
                    ).order_by(AuditLog.id.asc())
                ).scalars()
            )
            new_audits = [row for row in new_audits if row.id not in existing_permission_audits]
            event_types = [row.event_type for row in new_audits]
            expected = [
                "settings.mcp_tool_permissions_updated",
                "settings.mcp_oauth_client_permissions_updated",
                "settings.mcp_direct_client_permissions_updated",
            ]
            if event_types != expected:
                fail(f"Permission audit/no-op contract changed: {event_types}")
            for row in new_audits:
                if row.actor_type != "user" or row.actor_user_id != user.id:
                    fail("Permission audit actor attribution is incorrect")
                serialized = str((row.before_json, row.after_json, row.metadata_json))
                if bearer_key in serialized or api_key.plaintext_key in serialized:
                    fail("Secret material leaked into permission audit")
        finally:
            audit_db.close()

        print(
            "[PASS] MCP permission administration is session-only, validates canonical tools, "
            "audits only real changes, enforces global hard ceilings and client denies immediately, "
            "exposes effective OAuth/direct state, hides inaccessible/revoked clients, and rejects REST/MCP credentials"
        )
    finally:
        db.rollback()
        db.close()
        engine.dispose()
        database_path.write_bytes(before_bytes)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(database_path) + suffix)
            if sidecar.exists():
                sidecar.unlink()
        if database_path.read_bytes() != before_bytes:
            fail("MCP permission admin smoke did not restore copied database bytes exactly")


if __name__ == "__main__":
    main()
