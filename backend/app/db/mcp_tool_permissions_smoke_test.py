from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.db.settings import get_app_setting, set_app_setting
from app.models import McpDirectAuth, McpOAuthClient, User
from app.services.mcp_direct_auth import DIRECT_AUTH_TRUSTED_NETWORK, create_named_direct_client
from app.services.mcp_oauth import MCP_ENABLED_KEY, MCP_READ_ENABLED_KEY, MCP_SCOPE_READ, MCP_WRITE_ENABLED_KEY, register_client
from app.services.mcp_permissions import (
    DEFAULT_MCP_TOOL_PERMISSIONS,
    MCP_TOOL_NAMES,
    MCP_TOOL_PERMISSIONS_KEY,
    McpToolPermissionConfigurationError,
    McpToolPermissionDeniedError,
    authorize_mcp_tool,
    get_global_tool_permissions,
    visible_mcp_tool_names,
)

# PARTPILOT:MCP_TOOL_PERMISSIONS_SMOKE:V644

class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def _database_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"MCP tool-permission smoke requires SQLite, got {url!r}")
    return Path(url[len(prefix):]).resolve()


def _expect_denied(db, principal, tool_name: str) -> None:
    try:
        authorize_mcp_tool(db, principal, tool_name)
    except McpToolPermissionDeniedError:
        return
    fail(f"Expected {tool_name} to be denied")


def main() -> None:
    from app.mcp.runtime import mcp_registered_tool_names

    database_path = _database_path()
    before_bytes = database_path.read_bytes()
    db = SessionLocal()
    try:
        if asyncio.run(mcp_registered_tool_names()) != tuple(sorted(MCP_TOOL_NAMES)):
            fail("Permission catalogue differs from registered FastMCP tools")
        original_global_policy = get_global_tool_permissions(db)
        stored = get_app_setting(db, MCP_TOOL_PERMISSIONS_KEY, None)
        if stored != original_global_policy:
            fail("Persisted MCP global policy differs from the validated policy")
        if any((row.denied_tools_json or []) != [] for row in db.execute(select(McpOAuthClient)).scalars()):
            fail("0016 did not default existing OAuth clients to inherit-all")
        if any((row.denied_tools_json or []) != [] for row in db.execute(select(McpDirectAuth)).scalars()):
            fail("0016 did not default existing direct clients to inherit-all")

        user = db.execute(select(User).where(User.is_active.is_(True)).order_by(User.id)).scalars().first()
        if user is None:
            fail("MCP tool-permission smoke requires one active user")
        set_app_setting(db, MCP_ENABLED_KEY, True, commit=False)
        set_app_setting(db, MCP_READ_ENABLED_KEY, True, commit=False)
        set_app_setting(db, MCP_WRITE_ENABLED_KEY, False, commit=False)
        set_app_setting(
            db,
            MCP_TOOL_PERMISSIONS_KEY,
            dict(DEFAULT_MCP_TOOL_PERMISSIONS),
            commit=False,
        )

        registered = register_client(
            db,
            client_name="Patch 644 Permission Smoke OAuth",
            redirect_uris=["https://permission-smoke.example/callback"],
            actor_user_id=user.id,
            registered_by_user_id=user.id,
            commit=False,
        )
        oauth_row = db.get(McpOAuthClient, registered.client.id)
        if oauth_row is None:
            fail("Permission smoke OAuth client was not created")
        direct_created = create_named_direct_client(
            db,
            actor_user_id=user.id,
            name="Patch 644 Permission Smoke Direct",
            mode=DIRECT_AUTH_TRUSTED_NETWORK,
            networks=["203.0.113.248/30"],
            commit=False,
        )
        direct_row = direct_created.record if hasattr(direct_created, "record") else direct_created
        db.flush()

        oauth_principal = {
            "auth_method": "oauth",
            "actor_type": "mcp",
            "actor_user_id": user.id,
            "scopes": [MCP_SCOPE_READ],
            "resource_uri": "https://partpilot.example/mcp",
            "oauth": {"token_id": 1, "client_database_id": oauth_row.id, "client_id": oauth_row.client_id},
        }
        direct_principal = {
            "auth_method": "direct_trusted_network",
            "actor_type": "mcp",
            "actor_user_id": None,
            "scopes": [MCP_SCOPE_READ],
            "resource_uri": "https://partpilot.example/mcp",
            "direct_auth_id": direct_row.id,
            "direct_client_name": direct_row.name,
            "client_ip": "203.0.113.249",
        }
        noauth_principal = {
            "auth_method": "direct_no_auth",
            "actor_type": "mcp",
            "actor_user_id": None,
            "scopes": [MCP_SCOPE_READ],
            "resource_uri": "https://partpilot.example/mcp",
            "direct_auth_id": None,
            "direct_client_name": "No authentication",
            "client_ip": "203.0.113.250",
        }

        for name in MCP_TOOL_NAMES:
            authorize_mcp_tool(db, oauth_principal, name)
            authorize_mcp_tool(db, direct_principal, name)
            authorize_mcp_tool(db, noauth_principal, name)
        for principal in (oauth_principal, direct_principal, noauth_principal):
            if visible_mcp_tool_names(db, principal) != MCP_TOOL_NAMES:
                fail("Default visible MCP catalogue does not expose all six tools")

        global_policy = dict(DEFAULT_MCP_TOOL_PERMISSIONS)
        global_policy["search_parts"] = False
        set_app_setting(db, MCP_TOOL_PERMISSIONS_KEY, global_policy, commit=False)
        _expect_denied(db, oauth_principal, "search_parts")
        _expect_denied(db, direct_principal, "search_parts")
        _expect_denied(db, noauth_principal, "search_parts")
        authorize_mcp_tool(db, noauth_principal, "list_projects")
        for principal in (oauth_principal, direct_principal, noauth_principal):
            if "search_parts" in visible_mcp_tool_names(db, principal):
                fail("Globally denied search_parts remained in visible MCP catalogue")

        set_app_setting(db, MCP_TOOL_PERMISSIONS_KEY, dict(DEFAULT_MCP_TOOL_PERMISSIONS), commit=False)
        oauth_row.denied_tools_json = ["list_projects"]
        direct_row.denied_tools_json = ["search_parts"]
        db.flush()
        _expect_denied(db, oauth_principal, "list_projects")
        authorize_mcp_tool(db, oauth_principal, "search_parts")
        _expect_denied(db, direct_principal, "search_parts")
        authorize_mcp_tool(db, direct_principal, "list_projects")
        authorize_mcp_tool(db, noauth_principal, "list_projects")
        if "list_projects" in visible_mcp_tool_names(db, oauth_principal):
            fail("OAuth client-denied list_projects remained in visible catalogue")
        if "search_parts" in visible_mcp_tool_names(db, direct_principal):
            fail("Direct client-denied search_parts remained in visible catalogue")
        if visible_mcp_tool_names(db, noauth_principal) != MCP_TOOL_NAMES:
            fail("No-auth catalogue incorrectly inherited named-client denies")

        set_app_setting(db, MCP_TOOL_PERMISSIONS_KEY, {"search_parts": True}, commit=False)
        try:
            get_global_tool_permissions(db)
        except McpToolPermissionConfigurationError:
            pass
        else:
            fail("Malformed global tool policy did not fail closed")

        print("[PASS] MCP tool permissions enforce catalogue/global hard ceiling, OAuth/direct client denies, no-auth inheritance and malformed-policy fail-closed behavior")
    finally:
        db.rollback()
        db.close()
        engine.dispose()
        database_path.write_bytes(before_bytes)
        if database_path.read_bytes() != before_bytes:
            fail("MCP tool-permission smoke did not restore the copied database exactly")


if __name__ == "__main__":
    main()
