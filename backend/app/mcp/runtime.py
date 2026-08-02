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
from app.services.mcp_oauth import (
    MCP_SCOPE_READ,
    McpOAuthDisabledError,
    McpOAuthInsufficientScopeError,
    McpOAuthInvalidTokenError,
    McpOAuthValidationError,
    validate_access_token,
    validate_resource_uri,
)


# PARTPILOT:MCP_STREAMABLE_HTTP_RUNTIME:V469
_PARTPILOT_MCP = FastMCP(
    name="Part Pilot",
    instructions=(
        "Access the authenticated Part Pilot inventory workspace. "
        "This foundation endpoint intentionally exposes no tools yet."
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
_SDK_APP = _PARTPILOT_MCP.streamable_http_app()
_INVALID_HOST = re.compile(r"[\\/\s#?]")


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


def _bearer_token(headers: dict[str, str]) -> str | None:
    authorization = headers.get("authorization", "")
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.casefold() != "bearer":
        return None
    value = token.strip()
    return value or None


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


def _validate_bearer(token: str, resource_uri: str) -> dict[str, Any]:
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
            "token_id": principal.token_id,
            "user_id": principal.user_id,
            "client_database_id": principal.client_database_id,
            "client_id": principal.client_id,
            "scopes": sorted(principal.scopes),
            "resource_uri": principal.resource_uri,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


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
        token = _bearer_token(headers)
        if token is None:
            await _send_json(
                send,
                status=401,
                content={
                    "error": "invalid_token",
                    "error_description": "A valid OAuth bearer token is required.",
                },
                headers=[(b"www-authenticate", challenge.encode("latin-1"))],
            )
            return

        try:
            principal = await asyncio.to_thread(
                _validate_bearer,
                token,
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
                    "error_description": "The OAuth token lacks MCP read access.",
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
                    "error_description": "The OAuth bearer token is invalid or expired.",
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


@asynccontextmanager
async def mcp_runtime_lifespan():
    async with _PARTPILOT_MCP.session_manager.run():
        yield
