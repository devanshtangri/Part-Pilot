from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from app.core.client_ip import (
    ClientAddressError,
    TrustedProxyConfigurationError,
    TrustedProxyResolver,
    resolve_public_origin,
)
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.db.settings import get_bool_setting, set_app_setting
from app.mcp.part_tools import register_part_tools
from app.mcp.workspace_tools import register_workspace_tools
from app.services.mcp_direct_auth import (
    DIRECT_KEY_PREFIX,
    McpDirectAuthConfigurationError,
    configured_custom_header_names,
    validate_named_bearer_client,
    validate_named_custom_header_client,
    validate_named_trusted_network_client,
)
from app.services.app_settings import (
    MCP_DIRECT_CLIENTS_ENABLED_KEY,
    MCP_DIRECT_NO_AUTH_ENABLED_KEY,
    MCP_DIRECT_NO_AUTH_LAST_CLIENT_IP_KEY,
)
from app.services.mcp_oauth import (
    MCP_SCOPE_READ,
    McpOAuthDisabledError,
    McpOAuthInsufficientScopeError,
    McpOAuthInvalidTokenError,
    McpOAuthValidationError,
    available_scopes,
    validate_access_token,
    validate_resource_uri,
)


# PARTPILOT:MCP_STREAMABLE_HTTP_RUNTIME:V509
_PARTPILOT_MCP = FastMCP(
    name="Part Pilot",
    instructions=(
        "Access the authenticated Part Pilot workspace. "
        "Use the read-only tools to inspect inventory, Projects, and Reservations."
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(
        # Part Pilot validates Origin and Host against its externally visible
        # origin in the gateway below, including reverse-proxy headers.
        enable_dns_rebinding_protection=False,
    ),
)
register_part_tools(_PARTPILOT_MCP)
register_workspace_tools(_PARTPILOT_MCP)
_SDK_APP = _PARTPILOT_MCP.streamable_http_app()

def _header_values(scope: dict[str, Any], header_name: str) -> list[str]:
    target = header_name.casefold()
    values: list[str] = []
    for raw_name, raw_value in scope.get("headers", []):
        try:
            name = raw_name.decode("latin-1").casefold()
            value = raw_value.decode("latin-1")
        except (AttributeError, UnicodeDecodeError):
            continue
        if name == target:
            values.append(value)
    return values


def _header_map(scope: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_name, raw_value in scope.get("headers", []):
        try:
            name = raw_name.decode("latin-1").casefold()
            value = raw_value.decode("latin-1")
        except (AttributeError, UnicodeDecodeError):
            continue
        if name not in result:
            result[name] = value
    return result


def _public_origin(scope: dict[str, Any]) -> str:
    settings = get_settings()
    try:
        return resolve_public_origin(
            scope,
            configured_public_base_url=settings.public_base_url,
            trusted_proxy_cidrs=settings.trusted_proxy_cidrs,
        )
    except ClientAddressError as exc:
        raise McpOAuthValidationError(str(exc)) from exc
    except TrustedProxyConfigurationError as exc:
        raise RuntimeError(str(exc)) from exc


# PARTPILOT:MCP_FORWARDED_ORIGIN_RUNTIME:V508

def _normalise_origin(value: str) -> str | None:
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _bearer_credential(scope: dict[str, Any]) -> tuple[bool, str | None]:
    values = _header_values(scope, "authorization")
    if len(values) > 1:
        raise McpOAuthValidationError(
            "Duplicate Authorization headers are not allowed for MCP requests."
        )
    if not values:
        return False, None
    scheme, separator, token = values[0].partition(" ")
    if not separator or scheme.casefold() != "bearer":
        return False, None
    value = token.strip()
    return True, value or None


def _configured_custom_header_names() -> list[str]:
    db = SessionLocal()
    try:
        if not get_bool_setting(db, MCP_DIRECT_CLIENTS_ENABLED_KEY, False):
            return []
        return configured_custom_header_names(db)
    finally:
        db.close()


def _custom_header_credentials(
    scope: dict[str, Any],
    header_names: list[str],
) -> list[tuple[str, str]]:
    credentials: list[tuple[str, str]] = []
    for header_name in header_names:
        values = _header_values(scope, header_name)
        if len(values) > 1:
            raise McpOAuthValidationError(
                "Duplicate MCP custom credential headers are not allowed."
            )
        if not values:
            continue
        value = values[0].strip()
        if value:
            credentials.append((header_name, value))
    if len(credentials) > 1:
        raise McpOAuthValidationError(
            "MCP requests must use exactly one direct custom credential header."
        )
    return credentials


async def _send_json(
    send,
    *,
    status: int,
    content: dict[str, Any],
    headers: list[tuple[bytes, bytes]] | None = None,
) -> None:
    body = json.dumps(content, separators=(",", ":")).encode("utf-8")
    response_headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode("ascii")),
        (b"cache-control", b"no-store"),
        (b"pragma", b"no-cache"),
        (b"x-content-type-options", b"nosniff"),
    ]
    if headers:
        response_headers.extend(headers)
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": response_headers,
        }
    )
    await send({"type": "http.response.body", "body": body})


def _resolved_client_ip(scope: dict[str, Any]) -> str:
    settings = get_settings()
    try:
        return str(
            TrustedProxyResolver.from_raw(
                settings.trusted_proxy_cidrs
            ).resolve_client_ip(scope)
        )
    except ClientAddressError as exc:
        raise McpOAuthValidationError(str(exc)) from exc
    except TrustedProxyConfigurationError as exc:
        raise McpDirectAuthConfigurationError(
            "MCP trusted-proxy configuration is invalid."
        ) from exc


def _direct_policy(db) -> tuple[bool, bool]:
    return (
        get_bool_setting(db, MCP_DIRECT_CLIENTS_ENABLED_KEY, False),
        get_bool_setting(db, MCP_DIRECT_NO_AUTH_ENABLED_KEY, False),
    )


def _optional_resolved_client_ip(scope: dict[str, Any]) -> str | None:
    try:
        return _resolved_client_ip(scope)
    except McpOAuthValidationError:
        return None


def _oauth_principal(token: str, resource_uri: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        principal = validate_access_token(
            db,
            access_token=token,
            resource_uri=resource_uri,
            required_scopes=(MCP_SCOPE_READ,),
            touch=True,
            commit=True,
        )
        return {
            "auth_method": "oauth",
            "actor_type": "mcp",
            "actor_user_id": principal.user_id,
            "scopes": sorted(principal.scopes),
            "resource_uri": principal.resource_uri,
            "oauth": {
                "token_id": principal.token_id,
                "client_database_id": principal.client_database_id,
                "client_id": principal.client_id,
            },
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _direct_bearer_principal(
    token: str,
    resource_uri: str,
    scope: dict[str, Any],
) -> dict[str, Any]:
    db = SessionLocal()
    try:
        master_enabled, _ = _direct_policy(db)
        if not master_enabled:
            raise McpOAuthInvalidTokenError("MCP direct clients are disabled.")
        client_ip = _optional_resolved_client_ip(scope)
        record = validate_named_bearer_client(
            db,
            token,
            client_ip=client_ip,
            touch=True,
            commit=False,
        )
        if record is None:
            raise McpOAuthInvalidTokenError("Invalid MCP direct Bearer key.")
        scopes = available_scopes(db, require_enabled=True)
        if MCP_SCOPE_READ not in scopes:
            raise McpOAuthInsufficientScopeError(
                "MCP read tools are disabled in Part Pilot settings."
            )
        db.commit()
        return {
            "auth_method": "direct_bearer",
            "actor_type": "mcp",
            "actor_user_id": None,
            "scopes": [MCP_SCOPE_READ],
            "resource_uri": resource_uri,
            "direct_auth_id": record.id,
            "direct_client_name": record.name,
            "client_ip": client_ip,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _direct_custom_header_principal(
    header_name: str,
    supplied_key: str,
    resource_uri: str,
    scope: dict[str, Any],
) -> dict[str, Any]:
    db = SessionLocal()
    try:
        master_enabled, _ = _direct_policy(db)
        if not master_enabled:
            raise McpOAuthInvalidTokenError("MCP direct clients are disabled.")
        client_ip = _optional_resolved_client_ip(scope)
        record = validate_named_custom_header_client(
            db,
            header_name,
            supplied_key,
            client_ip=client_ip,
            touch=True,
            commit=False,
        )
        if record is None:
            raise McpOAuthInvalidTokenError("Invalid MCP custom-header key.")
        scopes = available_scopes(db, require_enabled=True)
        if MCP_SCOPE_READ not in scopes:
            raise McpOAuthInsufficientScopeError(
                "MCP read tools are disabled in Part Pilot settings."
            )
        db.commit()
        return {
            "auth_method": "direct_custom_header",
            "actor_type": "mcp",
            "actor_user_id": None,
            "scopes": [MCP_SCOPE_READ],
            "resource_uri": resource_uri,
            "direct_auth_id": record.id,
            "direct_client_name": record.name,
            "client_ip": client_ip,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _direct_trusted_network_principal(
    scope: dict[str, Any],
    resource_uri: str,
) -> dict[str, Any] | None:
    client_ip = _resolved_client_ip(scope)
    db = SessionLocal()
    try:
        master_enabled, _ = _direct_policy(db)
        if not master_enabled:
            return None
        record = validate_named_trusted_network_client(
            db,
            client_ip,
            touch=True,
            commit=False,
        )
        if record is None:
            db.rollback()
            return None
        scopes = available_scopes(db, require_enabled=True)
        if MCP_SCOPE_READ not in scopes:
            raise McpOAuthInsufficientScopeError(
                "MCP read tools are disabled in Part Pilot settings."
            )
        db.commit()
        return {
            "auth_method": "direct_trusted_network",
            "actor_type": "mcp",
            "actor_user_id": None,
            "scopes": [MCP_SCOPE_READ],
            "resource_uri": resource_uri,
            "direct_auth_id": record.id,
            "direct_client_name": record.name,
            "client_ip": client_ip,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _direct_no_auth_principal(
    scope: dict[str, Any],
    resource_uri: str,
) -> dict[str, Any] | None:
    client_ip = _resolved_client_ip(scope)
    db = SessionLocal()
    try:
        master_enabled, no_auth_enabled = _direct_policy(db)
        if not master_enabled or not no_auth_enabled:
            return None
        scopes = available_scopes(db, require_enabled=True)
        if MCP_SCOPE_READ not in scopes:
            raise McpOAuthInsufficientScopeError(
                "MCP read tools are disabled in Part Pilot settings."
            )
        set_app_setting(
            db,
            MCP_DIRECT_NO_AUTH_LAST_CLIENT_IP_KEY,
            client_ip,
            commit=False,
        )
        db.commit()
        return {
            "auth_method": "direct_no_auth",
            "actor_type": "mcp",
            "actor_user_id": None,
            "scopes": [MCP_SCOPE_READ],
            "resource_uri": resource_uri,
            "direct_auth_id": None,
            "direct_client_name": "No authentication",
            "client_ip": client_ip,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _validate_bearer(
    token: str,
    resource_uri: str,
    scope: dict[str, Any],
) -> dict[str, Any]:
    if token.startswith(DIRECT_KEY_PREFIX):
        return _direct_bearer_principal(token, resource_uri, scope)
    return _oauth_principal(token, resource_uri)


# PARTPILOT:MCP_NAMED_DIRECT_RUNTIME:V627
class PartPilotMcpGateway:
    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await _SDK_APP(scope, receive, send)
            return

        headers = _header_map(scope)
        try:
            public_origin = _public_origin(scope)
            resource_uri = validate_resource_uri(f"{public_origin}/mcp")
        except (McpOAuthValidationError, RuntimeError) as exc:
            await _send_json(
                send,
                status=400,
                content={"error": "invalid_request", "error_description": str(exc)},
            )
            return

        origin = headers.get("origin")
        if origin is not None and _normalise_origin(origin) != public_origin:
            await _send_json(
                send,
                status=403,
                content={
                    "error": "invalid_origin",
                    "error_description": "The MCP request Origin is not allowed.",
                },
            )
            return

        metadata_url = (
            f"{public_origin}/.well-known/oauth-protected-resource/mcp"
        )
        challenge = (
            'Bearer resource_metadata="'
            + metadata_url
            + '", scope="'
            + MCP_SCOPE_READ
            + '"'
        )
        try:
            bearer_present, token = _bearer_credential(scope)
            custom_header_names = await asyncio.to_thread(
                _configured_custom_header_names
            )
            custom_credentials = _custom_header_credentials(
                scope,
                custom_header_names,
            )
            custom_present = bool(custom_credentials)
            custom_header_name, custom_key = (
                custom_credentials[0]
                if custom_credentials
                else (None, None)
            )
        except McpOAuthValidationError as exc:
            await _send_json(
                send,
                status=400,
                content={
                    "error": "invalid_request",
                    "error_description": str(exc),
                },
            )
            return

        if bearer_present and custom_present:
            await _send_json(
                send,
                status=400,
                content={
                    "error": "invalid_request",
                    "error_description": (
                        "MCP requests must use exactly one authentication credential."
                    ),
                },
            )
            return

        auth_method: str
        credential: str | None
        if custom_present:
            auth_method = "direct_custom_header"
            credential = custom_key
        elif bearer_present:
            auth_method = (
                "direct_bearer"
                if token is not None and token.startswith(DIRECT_KEY_PREFIX)
                else "oauth"
            )
            credential = token
        else:
            auth_method = "direct_implicit"
            credential = None

        try:
            if auth_method == "direct_implicit":
                principal = await asyncio.to_thread(
                    _direct_trusted_network_principal,
                    scope,
                    resource_uri,
                )
                if principal is None:
                    principal = await asyncio.to_thread(
                        _direct_no_auth_principal,
                        scope,
                        resource_uri,
                    )
                if principal is None:
                    await _send_json(
                        send,
                        status=401,
                        content={
                            "error": "invalid_token",
                            "error_description": (
                                "A valid OAuth token, named direct credential, trusted "
                                "request source, or explicitly enabled no-auth policy is required."
                            ),
                        },
                        headers=[
                            (b"www-authenticate", challenge.encode("latin-1"))
                        ],
                    )
                    return
                auth_method = principal["auth_method"]
            elif auth_method == "direct_custom_header":
                principal = await asyncio.to_thread(
                    _direct_custom_header_principal,
                    custom_header_name,
                    credential,
                    resource_uri,
                    scope,
                )
            elif auth_method == "direct_bearer":
                principal = await asyncio.to_thread(
                    _direct_bearer_principal,
                    credential,
                    resource_uri,
                    scope,
                )
            else:
                principal = await asyncio.to_thread(
                    _validate_bearer,
                    credential,
                    resource_uri,
                    scope,
                )
        except McpDirectAuthConfigurationError:
            await _send_json(
                send,
                status=503,
                content={
                    "error": "temporarily_unavailable",
                    "error_description": (
                        "MCP direct-client authentication is misconfigured."
                    ),
                },
                headers=[(b"retry-after", b"60")],
            )
            return
        except McpOAuthDisabledError:
            await _send_json(
                send,
                status=503,
                content={
                    "error": "temporarily_unavailable",
                    "error_description": "MCP is disabled in Part Pilot settings.",
                },
                headers=[(b"retry-after", b"60")],
            )
            return
        except McpOAuthInsufficientScopeError:
            await _send_json(
                send,
                status=403,
                content={
                    "error": "insufficient_scope",
                    "error_description": (
                        "MCP read tools are disabled in Part Pilot settings."
                        if auth_method in {
                            "direct_bearer",
                            "direct_custom_header",
                            "direct_trusted_network",
                            "direct_no_auth",
                        }
                        else "The OAuth token lacks MCP read access."
                    ),
                },
                headers=[
                    (
                        b"www-authenticate",
                        (
                            challenge
                            + ', error="insufficient_scope"'
                        ).encode("latin-1"),
                    )
                ],
            )
            return
        except (McpOAuthInvalidTokenError, McpOAuthValidationError):
            await _send_json(
                send,
                status=401,
                content={
                    "error": "invalid_token",
                    "error_description": (
                        "The Part Pilot direct Bearer key is invalid."
                        if auth_method == "direct_bearer"
                        else (
                            "The Part Pilot custom-header key is invalid."
                            if auth_method == "direct_custom_header"
                            else (
                                "The MCP request source is not trusted."
                                if auth_method == "direct_trusted_network"
                                else "The OAuth bearer token is invalid or expired."
                            )
                        )
                    ),
                },
                headers=[(b"www-authenticate", challenge.encode("latin-1"))],
            )
            return

        forwarded_scope = dict(scope)
        forwarded_scope["path"] = "/"
        forwarded_scope["raw_path"] = b"/"
        state = dict(forwarded_scope.get("state") or {})
        state["partpilot_mcp_principal"] = principal
        forwarded_scope["state"] = state
        await _SDK_APP(forwarded_scope, receive, send)


mcp_http_endpoint = PartPilotMcpGateway()


async def mcp_registered_tool_names() -> tuple[str, ...]:
    tools = await _PARTPILOT_MCP.list_tools()
    return tuple(sorted(tool.name for tool in tools))


@asynccontextmanager
async def mcp_runtime_lifespan():
    async with _PARTPILOT_MCP.session_manager.run():
        yield
