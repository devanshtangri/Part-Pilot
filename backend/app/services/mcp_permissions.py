from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.settings import get_app_setting, get_bool_setting, set_app_setting
from app.models import (
    AuditLog,
    McpDirectAuth,
    McpOAuthClient,
    McpOAuthConsent,
    McpOAuthToken,
    User,
)
from app.schemas.app_settings import (
    McpClientToolPermissionItemResponse,
    McpClientToolPermissionsResponse,
    McpToolPermissionItemResponse,
    McpToolPermissionsResponse,
)


# PARTPILOT:MCP_TOOL_PERMISSIONS_SERVICE:V650
MCP_TOOL_PERMISSIONS_KEY = "mcp.tool_permissions"
MCP_ENABLED_KEY = "mcp.enabled"
MCP_READ_ENABLED_KEY = "mcp.read_tools_enabled"
MCP_WRITE_ENABLED_KEY = "mcp.write_tools_enabled"
MCP_SCOPE_READ = "mcp:read"
MCP_SCOPE_WRITE = "mcp:write"
MCP_TOOL_CAPABILITY_READ = "read"
MCP_TOOL_CAPABILITY_WRITE = "write"


@dataclass(frozen=True)
class McpToolPermissionDefinition:
    name: str
    label: str
    capability: str


# PARTPILOT:MCP_WRITE_TOOL_CATALOGUE:V734
MCP_TOOL_CATALOGUE = (
    McpToolPermissionDefinition("search_parts", "Search parts", MCP_TOOL_CAPABILITY_READ),
    McpToolPermissionDefinition("get_part_details", "Get part details", MCP_TOOL_CAPABILITY_READ),
    McpToolPermissionDefinition("list_projects", "List Projects", MCP_TOOL_CAPABILITY_READ),
    McpToolPermissionDefinition("get_project_details", "Get Project details", MCP_TOOL_CAPABILITY_READ),
    McpToolPermissionDefinition("list_reservations", "List Reservations", MCP_TOOL_CAPABILITY_READ),
    McpToolPermissionDefinition("get_reservation_details", "Get Reservation details", MCP_TOOL_CAPABILITY_READ),
    McpToolPermissionDefinition("reserve_project", "Reserve Project", MCP_TOOL_CAPABILITY_WRITE),
    McpToolPermissionDefinition("consume_reservation", "Consume Reservation", MCP_TOOL_CAPABILITY_WRITE),
    McpToolPermissionDefinition("cancel_reservation", "Cancel Reservation", MCP_TOOL_CAPABILITY_WRITE),
    McpToolPermissionDefinition("adjust_part_quantity", "Adjust part quantity", MCP_TOOL_CAPABILITY_WRITE),
    McpToolPermissionDefinition("create_part", "Create inventory part", MCP_TOOL_CAPABILITY_WRITE),
    McpToolPermissionDefinition("update_part_metadata", "Update part metadata", MCP_TOOL_CAPABILITY_WRITE),
    McpToolPermissionDefinition("soft_delete_part", "Move part to Deleted items", MCP_TOOL_CAPABILITY_WRITE),
    McpToolPermissionDefinition("restore_part", "Restore inventory part", MCP_TOOL_CAPABILITY_WRITE),
)
MCP_TOOL_NAMES = tuple(item.name for item in MCP_TOOL_CATALOGUE)
MCP_TOOL_DEFINITIONS = {item.name: item for item in MCP_TOOL_CATALOGUE}
DEFAULT_MCP_TOOL_PERMISSIONS = {
    item.name: item.capability == MCP_TOOL_CAPABILITY_READ
    for item in MCP_TOOL_CATALOGUE
}


class McpToolPermissionError(RuntimeError):
    pass


class McpToolPermissionConfigurationError(McpToolPermissionError):
    pass


class McpToolPermissionDeniedError(McpToolPermissionError):
    pass


class McpToolPermissionTargetNotFoundError(McpToolPermissionError):
    pass


def _naive_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _canonical_tool_name(tool_name: str) -> str:
    if not isinstance(tool_name, str) or tool_name not in MCP_TOOL_DEFINITIONS:
        raise McpToolPermissionConfigurationError("Unknown MCP tool permission target.")
    return tool_name


def normalize_denied_tools(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise McpToolPermissionConfigurationError(
            "MCP client denied-tools policy must be a JSON array."
        )
    denied: set[str] = set()
    for raw in value:
        if not isinstance(raw, str) or raw not in MCP_TOOL_DEFINITIONS:
            raise McpToolPermissionConfigurationError(
                "MCP client denied-tools policy contains an unknown tool."
            )
        denied.add(raw)
    return [name for name in MCP_TOOL_NAMES if name in denied]


def normalize_global_permission_updates(value: Any) -> dict[str, bool]:
    if not isinstance(value, dict) or not value:
        raise McpToolPermissionConfigurationError(
            "At least one MCP tool permission must be supplied."
        )
    if len(value) > len(MCP_TOOL_NAMES):
        raise McpToolPermissionConfigurationError(
            "MCP tool-permissions update contains too many entries."
        )
    result: dict[str, bool] = {}
    for raw_name, raw_value in value.items():
        name = _canonical_tool_name(raw_name)
        if type(raw_value) is not bool:
            raise McpToolPermissionConfigurationError(
                "MCP tool-permissions values must be booleans."
            )
        result[name] = raw_value
    return result


def get_global_tool_permissions(db: Session) -> dict[str, bool]:
    raw = get_app_setting(db, MCP_TOOL_PERMISSIONS_KEY, None)
    if raw is None:
        return dict(DEFAULT_MCP_TOOL_PERMISSIONS)
    if not isinstance(raw, dict) or set(raw) != set(MCP_TOOL_NAMES):
        raise McpToolPermissionConfigurationError(
            "MCP global tool-permissions policy is malformed."
        )
    result: dict[str, bool] = {}
    for name in MCP_TOOL_NAMES:
        value = raw.get(name)
        if type(value) is not bool:
            raise McpToolPermissionConfigurationError(
                "MCP global tool-permissions policy is malformed."
            )
        result[name] = value
    return result


def global_tool_permissions_response(db: Session) -> McpToolPermissionsResponse:
    policy = get_global_tool_permissions(db)
    return McpToolPermissionsResponse(
        tools=[
            McpToolPermissionItemResponse(
                name=item.name,
                label=item.label,
                capability=item.capability,
                enabled=policy[item.name],
            )
            for item in MCP_TOOL_CATALOGUE
        ]
    )


def client_tool_permissions_response(
    db: Session,
    denied_tools: Any,
) -> McpClientToolPermissionsResponse:
    denied = normalize_denied_tools(denied_tools)
    denied_set = set(denied)
    global_policy = get_global_tool_permissions(db)
    return McpClientToolPermissionsResponse(
        denied_tools=denied,
        tools=[
            McpClientToolPermissionItemResponse(
                name=item.name,
                label=item.label,
                capability=item.capability,
                global_enabled=global_policy[item.name],
                denied=item.name in denied_set,
                effective_enabled=(
                    global_policy[item.name] and item.name not in denied_set
                ),
            )
            for item in MCP_TOOL_CATALOGUE
        ],
    )


def _changed_tool_names(before: set[str], after: set[str]) -> list[str]:
    changed = before.symmetric_difference(after)
    return [name for name in MCP_TOOL_NAMES if name in changed]


def update_global_tool_permissions(
    db: Session,
    updates: Any,
    *,
    actor_user_id: int,
    commit: bool = True,
) -> McpToolPermissionsResponse:
    canonical_updates = normalize_global_permission_updates(updates)
    before = get_global_tool_permissions(db)
    after = dict(before)
    after.update(canonical_updates)
    changed = [name for name in MCP_TOOL_NAMES if before[name] != after[name]]
    if not changed:
        return global_tool_permissions_response(db)

    try:
        setting = set_app_setting(db, MCP_TOOL_PERMISSIONS_KEY, after, commit=False)
        db.add(
            AuditLog(
                event_type="settings.mcp_tool_permissions_updated",
                entity_type="app_setting",
                entity_id=setting.id,
                actor_type="user",
                actor_user_id=actor_user_id,
                summary="Updated MCP global tool permissions",
                before_json={"permissions": before},
                after_json={"permissions": after},
                metadata_json={"changed_tools": changed},
            )
        )
        db.flush()
        if commit:
            db.commit()
    except Exception:
        if commit:
            db.rollback()
        raise
    return global_tool_permissions_response(db)


def _manageable_oauth_client(
    db: Session,
    *,
    user_id: int,
    client_database_id: int,
) -> McpOAuthClient:
    client = db.get(McpOAuthClient, client_database_id)
    if client is None or client.revoked_at is not None:
        raise McpToolPermissionTargetNotFoundError(
            "Manageable MCP OAuth client was not found."
        )
    if client.registered_by_user_id == user_id:
        return client

    consent = db.execute(
        select(McpOAuthConsent.id).where(
            McpOAuthConsent.client_id == client.id,
            McpOAuthConsent.user_id == user_id,
            McpOAuthConsent.revoked_at.is_(None),
        )
    ).first()
    now = _naive_utc_now()
    token = db.execute(
        select(McpOAuthToken.id).where(
            McpOAuthToken.client_id == client.id,
            McpOAuthToken.user_id == user_id,
            McpOAuthToken.revoked_at.is_(None),
            or_(
                McpOAuthToken.access_expires_at > now,
                McpOAuthToken.refresh_expires_at > now,
            ),
        )
    ).first()
    if consent is None or token is None:
        raise McpToolPermissionTargetNotFoundError(
            "Manageable MCP OAuth client was not found."
        )
    return client


def update_oauth_client_tool_permissions(
    db: Session,
    *,
    user_id: int,
    client_database_id: int,
    denied_tools: Any,
    actor_user_id: int,
    commit: bool = True,
) -> McpClientToolPermissionsResponse:
    client = _manageable_oauth_client(
        db,
        user_id=user_id,
        client_database_id=client_database_id,
    )
    before = normalize_denied_tools(client.denied_tools_json)
    after = normalize_denied_tools(denied_tools)
    if before == after:
        return client_tool_permissions_response(db, before)

    try:
        client.denied_tools_json = after
        db.add(
            AuditLog(
                event_type="settings.mcp_oauth_client_permissions_updated",
                entity_type="mcp_oauth_client",
                entity_id=client.id,
                actor_type="user",
                actor_user_id=actor_user_id,
                summary=f"Updated MCP OAuth client permissions for {client.client_name}.",
                before_json={"denied_tools": before},
                after_json={"denied_tools": after},
                metadata_json={
                    "changed_tools": _changed_tool_names(set(before), set(after))
                },
            )
        )
        db.flush()
        if commit:
            db.commit()
            db.refresh(client)
    except Exception:
        if commit:
            db.rollback()
        raise
    return client_tool_permissions_response(db, client.denied_tools_json)


def update_direct_client_tool_permissions(
    db: Session,
    *,
    client_id: int,
    denied_tools: Any,
    actor_user_id: int,
    commit: bool = True,
) -> McpClientToolPermissionsResponse:
    client = db.get(McpDirectAuth, client_id)
    if client is None or client.revoked_at is not None:
        raise McpToolPermissionTargetNotFoundError(
            "MCP direct client was not found."
        )
    before = normalize_denied_tools(client.denied_tools_json)
    after = normalize_denied_tools(denied_tools)
    if before == after:
        return client_tool_permissions_response(db, before)

    try:
        client.denied_tools_json = after
        db.add(
            AuditLog(
                event_type="settings.mcp_direct_client_permissions_updated",
                entity_type="mcp_direct_auth",
                entity_id=client.id,
                actor_type="user",
                actor_user_id=actor_user_id,
                summary=f"Updated MCP direct client permissions for {client.name}.",
                before_json={"denied_tools": before},
                after_json={"denied_tools": after},
                metadata_json={
                    "changed_tools": _changed_tool_names(set(before), set(after)),
                    "secret_material": "redacted",
                },
            )
        )
        db.flush()
        if commit:
            db.commit()
            db.refresh(client)
    except Exception:
        if commit:
            db.rollback()
        raise
    return client_tool_permissions_response(db, client.denied_tools_json)


def _client_denied_tools(db: Session, principal: dict[str, Any]) -> list[str]:
    auth_method = principal.get("auth_method")
    if auth_method == "oauth":
        oauth = principal.get("oauth")
        client_id = oauth.get("client_database_id") if isinstance(oauth, dict) else None
        if type(client_id) is not int:
            raise McpToolPermissionConfigurationError(
                "Authenticated MCP OAuth principal has no client identity."
            )
        client = db.get(McpOAuthClient, client_id)
        if client is None or client.revoked_at is not None:
            raise McpToolPermissionDeniedError("MCP OAuth client is no longer active.")
        return normalize_denied_tools(client.denied_tools_json)

    if auth_method in {
        "direct_bearer",
        "direct_custom_header",
        "direct_trusted_network",
    }:
        client_id = principal.get("direct_auth_id")
        if type(client_id) is not int:
            raise McpToolPermissionConfigurationError(
                "Authenticated MCP direct principal has no client identity."
            )
        client = db.get(McpDirectAuth, client_id)
        if client is None or client.revoked_at is not None or not client.enabled:
            raise McpToolPermissionDeniedError("MCP direct client is no longer active.")
        return normalize_denied_tools(client.denied_tools_json)

    if auth_method == "direct_no_auth":
        if principal.get("direct_auth_id") is not None:
            raise McpToolPermissionConfigurationError(
                "No-auth MCP principal unexpectedly has a named client identity."
            )
        return []

    raise McpToolPermissionConfigurationError("Unsupported MCP principal type.")


def _write_authorization_user_id(
    db: Session,
    principal: dict[str, Any],
) -> int:
    auth_method = principal.get("auth_method")
    if auth_method == "direct_no_auth":
        raise McpToolPermissionDeniedError(
            "No-auth MCP access is read-only and cannot receive write access."
        )

    user_id: int | None = None
    if auth_method == "oauth":
        candidate = principal.get("actor_user_id")
        if type(candidate) is int:
            user_id = candidate
    elif auth_method in {
        "direct_bearer",
        "direct_custom_header",
        "direct_trusted_network",
    }:
        client_id = principal.get("direct_auth_id")
        if type(client_id) is not int:
            raise McpToolPermissionConfigurationError(
                "Authenticated MCP direct principal has no client identity."
            )
        client = db.get(McpDirectAuth, client_id)
        if client is None or client.revoked_at is not None or not client.enabled:
            raise McpToolPermissionDeniedError("MCP direct client is no longer active.")
        user_id = client.created_by_user_id
    else:
        raise McpToolPermissionConfigurationError("Unsupported MCP principal type.")

    if type(user_id) is not int:
        raise McpToolPermissionDeniedError(
            "This MCP client has no active user authority for write operations."
        )
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise McpToolPermissionDeniedError(
            "The user authority behind this MCP client is inactive."
        )
    from app.services.authorization import ROLE_OPERATOR, role_at_least
    if not role_at_least(user.role, ROLE_OPERATOR):
        raise McpToolPermissionDeniedError(
            "MCP write tools require an Operator, Administrator, or Owner authority."
        )
    return user.id


def authorize_mcp_tool(
    db: Session,
    principal: dict[str, Any],
    tool_name: str,
) -> int | None:
    canonical = _canonical_tool_name(tool_name)
    definition = MCP_TOOL_DEFINITIONS[canonical]
    principal_scopes = principal.get("scopes")

    if not get_bool_setting(db, MCP_ENABLED_KEY, False):
        raise McpToolPermissionDeniedError("MCP is disabled in Part Pilot settings.")

    authorization_user_id: int | None = None
    if definition.capability == MCP_TOOL_CAPABILITY_READ:
        if not get_bool_setting(db, MCP_READ_ENABLED_KEY, True):
            raise McpToolPermissionDeniedError(
                "MCP read tools are disabled in Part Pilot settings."
            )
        required_scope = MCP_SCOPE_READ
    elif definition.capability == MCP_TOOL_CAPABILITY_WRITE:
        if not get_bool_setting(db, MCP_WRITE_ENABLED_KEY, False):
            raise McpToolPermissionDeniedError(
                "MCP write tools are disabled in Part Pilot settings."
            )
        required_scope = MCP_SCOPE_WRITE
        authorization_user_id = _write_authorization_user_id(db, principal)
    else:
        raise McpToolPermissionConfigurationError(
            "MCP tool capability has no implemented authorization policy."
        )

    if not isinstance(principal_scopes, list) or required_scope not in principal_scopes:
        raise McpToolPermissionDeniedError(
            f"Authenticated MCP client does not have {required_scope} scope."
        )

    global_policy = get_global_tool_permissions(db)
    if not global_policy[canonical]:
        raise McpToolPermissionDeniedError(
            f"MCP tool {canonical} is disabled by the global permission policy."
        )
    if canonical in _client_denied_tools(db, principal):
        raise McpToolPermissionDeniedError(
            f"MCP tool {canonical} is blocked for this client."
        )
    return authorization_user_id


# PARTPILOT:MCP_VISIBLE_TOOL_CATALOGUE:V657
def visible_mcp_tool_names(
    db: Session,
    principal: dict[str, Any],
) -> tuple[str, ...]:
    visible: list[str] = []
    for name in MCP_TOOL_NAMES:
        try:
            authorize_mcp_tool(db, principal, name)
        except McpToolPermissionDeniedError:
            continue
        visible.append(name)
    return tuple(visible)
