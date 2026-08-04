from __future__ import annotations

import asyncio
import json
import re
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.mcp.part_tools import register_part_tools
from app.mcp.workspace_tools import register_workspace_tools
from app.services.mcp_direct_auth import (
    DIRECT_AUTH_CUSTOM_HEADER,
    DIRECT_AUTH_SINGLETON_ID,
    DIRECT_KEY_PREFIX,
    McpDirectAuthConfigurationError,
    get_direct_auth,
    validate_bearer_key,
    validate_custom_header_key,
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


# PARTPILOT:MCP_STREAMABLE_HTTP_RUNTIME:V499
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
_INVALID_HOST = re.compile(r"[\\/\s#?]")


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


def _first_forwarded(value: str | None) -> str | None:
    if value is None:
        return None
    item = value.split(",", 1)[0].strip()
    return item or None


def _public_origin(scope: dict[str, Any], headers: dict[str, str]) -> str:
    configured = get_settings().public_base_url
    if configured:
        parsed = urlsplit(configured.strip())
        if (
            parsed.scheme in {"http", "https"}
            and parsed.netloc
            and not parsed.path.rstrip("/")
            and not parsed.query
            and not parsed.fragment
        ):
            return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        raise RuntimeError(
            "PARTPILOT_PUBLIC_BASE_URL must be an origin without a path."
        )

    scheme = _first_forwarded(headers.get("x-forwarded-proto"))
    host = _first_forwarded(headers.get("x-forwarded-host"))
    if scheme not in {"http", "https"}:
        scheme = str(scope.get("scheme") or "http").casefold()
    if not host:
        host = headers.get("host", "").strip()
    if not host or _INVALID_HOST.search(host):
        raise McpOAuthValidationError("Invalid MCP request host.")
    return f"{scheme}://{host}".rstrip("/")


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


def _configured_custom_header_name() -> str | None:
    db = SessionLocal()
    try:
        record = get_direct_auth(db)
        if (
            record is not None
            and record.mode == DIRECT_AUTH_CUSTOM_HEADER
            and record.custom_header_name
        ):
            return record.custom_header_name
        return None
    finally:
        db.close()


def _custom_header_credential(
    scope: dict[str, Any],
    header_name: str | None,
) -> tuple[bool, str | None]:
    if header_name is None:
        return False, None
    values = _header_values(scope, header_name)
    if len(values) > 1:
        raise McpOAuthValidationError(
            "Duplicate MCP custom credential headers are not allowed."
        )
    if not values:
        return False, None
    value = values[0].strip()
    return True, value or None


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


def _direct_bearer_principal(token: str, resource_uri: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        try:
            accepted = validate_bearer_key(
                db,
                token,
                touch=True,
                commit=False,
            )
        except McpDirectAuthConfigurationError as exc:
            raise McpOAuthInvalidTokenError("Invalid MCP direct Bearer key.") from exc
        if not accepted:
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
            "direct_auth_id": DIRECT_AUTH_SINGLETON_ID,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _direct_custom_header_principal(
    supplied_key: str,
    resource_uri: str,
) -> dict[str, Any]:
    db = SessionLocal()
    try:
        try:
            accepted = validate_custom_header_key(
                db,
                supplied_key,
                touch=True,
                commit=False,
            )
        except McpDirectAuthConfigurationError as exc:
            raise McpOAuthInvalidTokenError(
                "Invalid MCP custom-header key."
            ) from exc
        if not accepted:
            raise McpOAuthInvalidTokenError(
                "Invalid MCP custom-header key."
            )
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
            "direct_auth_id": DIRECT_AUTH_SINGLETON_ID,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _validate_bearer(token: str, resource_uri: str) -> dict[str, Any]:
    if token.startswith(DIRECT_KEY_PREFIX):
        return _direct_bearer_principal(token, resource_uri)
    return _oauth_principal(token, resource_uri)


class PartPilotMcpGateway:
    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await _SDK_APP(scope, receive, send)
            return

        headers = _header_map(scope)
        try:
            public_origin = _public_origin(scope, headers)
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
            custom_header_name = await asyncio.to_thread(
                _configured_custom_header_name
            )
            custom_present, custom_key = _custom_header_credential(
                scope,
                custom_header_name,
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
            auth_method = "missing"
            credential = None

        if credential is None:
            await _send_json(
                send,
                status=401,
                content={
                    "error": "invalid_token",
                    "error_description": (
                        "A valid OAuth bearer token or configured MCP direct key "
                        "is required."
                    ),
                },
                headers=[(b"www-authenticate", challenge.encode("latin-1"))],
            )
            return

        try:
            if auth_method == "direct_custom_header":
                principal = await asyncio.to_thread(
                    _direct_custom_header_principal,
                    credential,
                    resource_uri,
                )
            else:
                principal = await asyncio.to_thread(
                    _validate_bearer,
                    credential,
                    resource_uri,
                )
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
                            else "The OAuth bearer token is invalid or expired."
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
