from __future__ import annotations

import base64
import binascii
import hmac
import html
import json
import re
import secrets
from datetime import timezone
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import McpOAuthClient
from app.schemas.mcp_oauth import (
    DynamicClientRegistrationRequest,
    DynamicClientRegistrationResponse,
    OAuthTokenResponse,
)
from app.services.auth import authenticate_user
from app.services.mcp_oauth import (
    MCP_SCOPE_READ,
    MCP_SCOPE_WRITE,
    PKCE_VALUE_PATTERN,
    SUPPORTED_CLIENT_AUTH_METHODS,
    SUPPORTED_GRANT_TYPES,
    SUPPORTED_RESPONSE_TYPES,
    McpOAuthDisabledError,
    McpOAuthError,
    McpOAuthInsufficientScopeError,
    McpOAuthInvalidClientError,
    McpOAuthInvalidGrantError,
    McpOAuthRefreshReplayError,
    McpOAuthValidationError,
    authenticate_client,
    available_scopes,
    exchange_authorization_code,
    get_active_client,
    grant_consent,
    issue_authorization_code,
    normalise_scopes,
    register_client,
    revoke_token,
    rotate_refresh_token,
    validate_redirect_uri,
    validate_resource_uri,
)


# PARTPILOT:MCP_OAUTH_HTTP_ROUTES:V467
router = APIRouter(tags=["mcp-oauth"])

CSRF_COOKIE = "partpilot_mcp_oauth_csrf"
CSRF_MAX_AGE = 600
STATE_MAX_LENGTH = 2048
SCOPE_DESCRIPTIONS = {
    MCP_SCOPE_READ: "Search and read Part Pilot inventory, Projects, and Reservations.",
    MCP_SCOPE_WRITE: "Use explicitly enabled Part Pilot write tools.",
}


def _no_store_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "X-Content-Type-Options": "nosniff",
    }


def _json_response(
    content: dict[str, Any],
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    merged = _no_store_headers()
    if headers:
        merged.update(headers)
    return JSONResponse(content=content, status_code=status_code, headers=merged)


def _oauth_error(
    error: str,
    description: str,
    *,
    status_code: int = 400,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return _json_response(
        {"error": error, "error_description": description},
        status_code=status_code,
        headers=headers,
    )


def _first_forwarded(value: str | None) -> str | None:
    if value is None:
        return None
    item = value.split(",", 1)[0].strip()
    return item or None


def _valid_host(value: str) -> bool:
    return bool(value) and not re.search(r"[\\/\\s#?]", value)


def _public_origin(request: Request) -> str:
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
        raise RuntimeError("PARTPILOT_PUBLIC_BASE_URL must be an origin without a path.")

    scheme = _first_forwarded(request.headers.get("x-forwarded-proto"))
    host = _first_forwarded(request.headers.get("x-forwarded-host"))
    if scheme not in {"http", "https"}:
        scheme = request.url.scheme
    if not host:
        host = request.headers.get("host") or request.url.netloc
    if not _valid_host(host):
        raise HTTPException(status_code=400, detail="Invalid request host")
    return f"{scheme}://{host}".rstrip("/")


def _resource_uri(request: Request) -> str:
    origin = _public_origin(request)
    resource = f"{origin}/mcp"
    try:
        return validate_resource_uri(resource)
    except McpOAuthValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _scope_values(db: Session) -> list[str]:
    return sorted(available_scopes(db, require_enabled=False))


def _append_query(uri: str, values: dict[str, str]) -> str:
    parsed = urlsplit(uri)
    query = list(parse_qsl(parsed.query, keep_blank_values=True))
    query.extend(values.items())
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


def _redirect_oauth_error(
    redirect_uri: str,
    *,
    error: str,
    description: str,
    state_value: str | None,
) -> RedirectResponse:
    values = {"error": error, "error_description": description}
    if state_value:
        values["state"] = state_value
    return RedirectResponse(_append_query(redirect_uri, values), status_code=302)


def _client_authentication(
    authorization: str | None,
    form: dict[str, str],
) -> tuple[str, str | None]:
    form_client_id = form.get("client_id", "").strip()
    form_secret = form.get("client_secret")
    basic_id: str | None = None
    basic_secret: str | None = None
    if authorization:
        scheme, _, encoded = authorization.partition(" ")
        if scheme.casefold() != "basic" or not encoded:
            raise McpOAuthInvalidClientError("Invalid OAuth client.")
        try:
            decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError) as exc:
            raise McpOAuthInvalidClientError("Invalid OAuth client.") from exc
        basic_id, separator, basic_secret = decoded.partition(":")
        if not separator or not basic_id:
            raise McpOAuthInvalidClientError("Invalid OAuth client.")
    if basic_id is not None:
        if form_client_id and not hmac.compare_digest(form_client_id, basic_id):
            raise McpOAuthInvalidClientError("Invalid OAuth client.")
        return basic_id, basic_secret
    if not form_client_id:
        raise McpOAuthInvalidClientError("Invalid OAuth client.")
    return form_client_id, form_secret


def _validated_authorization_request(
    db: Session,
    request: Request,
    values: dict[str, str],
) -> dict[str, Any]:
    client_id = values.get("client_id", "").strip()
    redirect_uri = values.get("redirect_uri", "").strip()
    response_type = values.get("response_type", "").strip()
    scope_text = values.get("scope", MCP_SCOPE_READ).strip()
    state_value = values.get("state", "").strip() or None
    code_challenge = values.get("code_challenge", "").strip()
    code_challenge_method = values.get("code_challenge_method", "").strip()
    requested_resource = values.get("resource", "").strip() or _resource_uri(request)

    client = get_active_client(db, client_id)
    redirect = validate_redirect_uri(redirect_uri)
    if redirect not in set(client.redirect_uris_json or []):
        raise McpOAuthInvalidGrantError("Redirect URI is not registered.")
    if response_type != "code" or response_type not in set(client.response_types_json or []):
        raise McpOAuthValidationError("Only response_type=code is supported.")
    if state_value is not None and len(state_value) > STATE_MAX_LENGTH:
        raise McpOAuthValidationError("OAuth state is too long.")
    if code_challenge_method != "S256" or not PKCE_VALUE_PATTERN.fullmatch(code_challenge):
        raise McpOAuthValidationError("A valid S256 PKCE challenge is required.")
    resource = validate_resource_uri(requested_resource)
    expected_resource = _resource_uri(request)
    if resource != expected_resource:
        raise McpOAuthInvalidGrantError("OAuth resource does not match this MCP server.")
    scopes = normalise_scopes(db, scope_text.split())
    return {
        "client": client,
        "client_id": client.client_id,
        "redirect_uri": redirect,
        "response_type": "code",
        "scopes": scopes,
        "scope": " ".join(scopes),
        "state": state_value,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "resource": resource,
    }


def _hidden(name: str, value: str | None) -> str:
    if value is None:
        return ""
    return (
        f'<input type="hidden" name="{html.escape(name, quote=True)}" '
        f'value="{html.escape(value, quote=True)}">'
    )


def _authorization_html(
    auth: dict[str, Any],
    *,
    csrf_token: str,
    error_message: str | None = None,
    username: str = "",
) -> str:
    client = auth["client"]
    scope_items = "".join(
        "<li><strong>"
        + html.escape(scope)
        + "</strong><span>"
        + html.escape(SCOPE_DESCRIPTIONS.get(scope, "Access Part Pilot through MCP."))
        + "</span></li>"
        for scope in auth["scopes"]
    )
    error = (
        '<p class="oauth-error" role="alert">' + html.escape(error_message) + "</p>"
        if error_message
        else ""
    )
    client_uri = (
        '<a class="client-link" href="'
        + html.escape(client.client_uri, quote=True)
        + '" rel="noreferrer">View client website</a>'
        if client.client_uri
        else ""
    )
    hidden = "".join(
        [
            _hidden("csrf_token", csrf_token),
            _hidden("client_id", auth["client_id"]),
            _hidden("redirect_uri", auth["redirect_uri"]),
            _hidden("response_type", auth["response_type"]),
            _hidden("scope", auth["scope"]),
            _hidden("state", auth["state"]),
            _hidden("code_challenge", auth["code_challenge"]),
            _hidden("code_challenge_method", auth["code_challenge_method"]),
            _hidden("resource", auth["resource"]),
        ]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Authorize {html.escape(client.client_name)} · Part Pilot</title>
<style>
:root {{ color-scheme: dark; font-family: "Avenir Next", "Segoe UI", sans-serif; background:#111315; color:#f3f5f6; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; min-height:100vh; display:grid; place-items:center; padding:28px 18px; background:#111315; }}
.oauth-shell {{ width:min(920px,100%); display:grid; grid-template-columns:minmax(0,0.9fr) minmax(360px,1.1fr); border:1px solid #30353a; background:#171a1d; box-shadow:0 24px 70px rgba(0,0,0,.28); }}
.oauth-summary,.oauth-form {{ padding:42px; }}
.oauth-summary {{ display:flex; flex-direction:column; justify-content:space-between; gap:48px; background:#141719; border-right:1px solid #30353a; }}
.brand {{ display:flex; align-items:center; gap:13px; }}
.mark {{ width:38px; height:38px; display:grid; place-items:center; border:1px solid #3daba3; color:#73d6cf; font-weight:800; }}
.brand strong {{ display:block; font-size:16px; }} .brand span {{ display:block; margin-top:2px; color:#929ba3; font-size:13px; }}
.eyebrow {{ margin:0 0 12px; color:#73d6cf; font-size:12px; font-weight:800; letter-spacing:.12em; text-transform:uppercase; }}
h1 {{ margin:0; font-size:clamp(30px,4vw,48px); line-height:1.05; letter-spacing:-.035em; }}
.summary-copy {{ margin:16px 0 0; color:#aeb5bb; line-height:1.65; }}
.installation {{ margin:0; padding-top:20px; border-top:1px solid #30353a; color:#818b93; font-size:13px; }}
.oauth-form h2 {{ margin:0; font-size:26px; letter-spacing:-.02em; }}
.client-name {{ margin:10px 0 4px; color:#f4f7f7; font-size:18px; font-weight:700; }}
.client-link {{ color:#73d6cf; font-size:13px; }}
.scope-list {{ list-style:none; margin:26px 0; padding:0; border:1px solid #30353a; }}
.scope-list li {{ padding:15px 16px; display:grid; gap:5px; border-bottom:1px solid #30353a; }}
.scope-list li:last-child {{ border-bottom:0; }}
.scope-list strong {{ font-size:13px; }} .scope-list span {{ color:#9da6ad; font-size:13px; line-height:1.45; }}
label {{ display:grid; gap:7px; margin-top:15px; color:#cdd2d6; font-size:13px; font-weight:700; }}
input[type=text],input[type=password] {{ width:100%; border:1px solid #3a4045; border-radius:3px; background:#111315; color:#fff; padding:12px 13px; font:inherit; outline:none; }}
input:focus {{ border-color:#62c7c0; box-shadow:0 0 0 2px rgba(98,199,192,.14); }}
.oauth-error {{ margin:16px 0 0; padding:11px 12px; border:1px solid #8f4545; background:#2a1818; color:#ffb7b7; font-size:13px; }}
.actions {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:22px; }}
button {{ min-height:44px; border-radius:3px; border:1px solid #3b4247; background:#202428; color:#f4f6f7; font:inherit; font-weight:800; cursor:pointer; }}
button[value=approve] {{ border-color:#399d96; background:#237a74; }}
button:hover {{ filter:brightness(1.08); }}
.privacy {{ margin:18px 0 0; color:#7f8991; font-size:12px; line-height:1.5; }}
@media(max-width:760px) {{ .oauth-shell {{ grid-template-columns:1fr; }} .oauth-summary {{ border-right:0; border-bottom:1px solid #30353a; gap:28px; }} .oauth-summary,.oauth-form {{ padding:28px; }} }}
</style>
</head>
<body>
<main class="oauth-shell">
<section class="oauth-summary">
<div><div class="brand"><div class="mark">P</div><div><strong>Part Pilot</strong><span>Private inventory access</span></div></div>
<div style="margin-top:54px"><p class="eyebrow">MCP authorization</p><h1>Connect your assistant.</h1><p class="summary-copy">Sign in to this Part Pilot installation and explicitly approve the requested access.</p></div></div>
<p class="installation">Tokens are stored as one-way hashes. You can revoke this connector later.</p>
</section>
<section class="oauth-form">
<p class="eyebrow">Access request</p><h2>Authorize connector</h2><p class="client-name">{html.escape(client.client_name)}</p>{client_uri}
<ul class="scope-list">{scope_items}</ul>
{error}
<form method="post" action="/oauth/authorize" autocomplete="on">{hidden}
<label>Username<input type="text" name="username" value="{html.escape(username, quote=True)}" autocomplete="username" required></label>
<label>Password<input type="password" name="password" autocomplete="current-password" required></label>
<div class="actions"><button type="submit" name="decision" value="deny" formnovalidate>Deny</button><button type="submit" name="decision" value="approve">Authorize</button></div>
</form>
<p class="privacy">Only the permissions shown above will be granted. Closing this page does not authorize access.</p>
</section>
</main>
</body>
</html>"""


def _html_response(
    content: str,
    *,
    status_code: int = 200,
    csrf_token: str | None = None,
    secure_cookie: bool = True,
) -> HTMLResponse:
    response = HTMLResponse(
        content,
        status_code=status_code,
        headers={
            **_no_store_headers(),
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
                "base-uri 'none'; frame-ancestors 'none'"
            ),
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
        },
    )
    if csrf_token is not None:
        response.set_cookie(
            CSRF_COOKIE,
            csrf_token,
            max_age=CSRF_MAX_AGE,
            httponly=True,
            secure=secure_cookie,
            samesite="lax",
            path="/oauth/authorize",
        )
    return response


@router.get("/.well-known/oauth-protected-resource")
@router.get("/.well-known/oauth-protected-resource/mcp")
def protected_resource_metadata(
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    origin = _public_origin(request)
    return _json_response(
        {
            "resource": _resource_uri(request),
            "authorization_servers": [origin],
            "scopes_supported": _scope_values(db),
            "bearer_methods_supported": ["header"],
            "resource_name": "Part Pilot MCP",
        }
    )


@router.get("/.well-known/oauth-authorization-server")
def authorization_server_metadata(
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    origin = _public_origin(request)
    return _json_response(
        {
            "issuer": origin,
            "authorization_endpoint": f"{origin}/oauth/authorize",
            "token_endpoint": f"{origin}/oauth/token",
            "registration_endpoint": f"{origin}/oauth/register",
            "revocation_endpoint": f"{origin}/oauth/revoke",
            "response_types_supported": sorted(SUPPORTED_RESPONSE_TYPES),
            "grant_types_supported": sorted(SUPPORTED_GRANT_TYPES),
            "token_endpoint_auth_methods_supported": sorted(
                SUPPORTED_CLIENT_AUTH_METHODS
            ),
            "code_challenge_methods_supported": ["S256"],
            "scopes_supported": _scope_values(db),
            "client_id_metadata_document_supported": False,
        }
    )


@router.post(
    "/oauth/register",
    response_model=DynamicClientRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def dynamic_client_registration(
    payload: DynamicClientRegistrationRequest,
    db: Session = Depends(get_db),
) -> JSONResponse:
    try:
        available_scopes(db)
        application_type = (payload.application_type or "").strip() or None
        if application_type not in {None, "native", "web"}:
            raise McpOAuthValidationError("Unsupported application_type.")
        if application_type == "web":
            for redirect in payload.redirect_uris:
                if urlsplit(redirect).scheme.casefold() != "https":
                    raise McpOAuthValidationError(
                        "Web OAuth clients must use HTTPS redirect URIs."
                    )
        metadata = {
            key: value
            for key, value in {
                "application_type": application_type,
                "software_id": payload.software_id,
                "software_version": payload.software_version,
            }.items()
            if value is not None
        }
        registered = register_client(
            db,
            client_name=payload.client_name,
            redirect_uris=payload.redirect_uris,
            grant_types=payload.grant_types,
            response_types=payload.response_types,
            token_endpoint_auth_method=payload.token_endpoint_auth_method,
            client_uri=payload.client_uri,
            metadata=metadata or None,
            commit=True,
        )
        client = registered.client
        issued_at = int(client.created_at.replace(tzinfo=timezone.utc).timestamp())
        content = DynamicClientRegistrationResponse(
            client_id=registered.client_id,
            client_secret=registered.client_secret,
            client_id_issued_at=issued_at,
            client_secret_expires_at=(
                None if registered.client_secret is None else 0
            ),
            redirect_uris=list(client.redirect_uris_json or []),
            client_name=client.client_name,
            client_uri=client.client_uri,
            grant_types=list(client.grant_types_json or []),
            response_types=list(client.response_types_json or []),
            token_endpoint_auth_method=client.token_endpoint_auth_method,
            application_type=metadata.get("application_type") if metadata else None,
            software_id=metadata.get("software_id") if metadata else None,
            software_version=metadata.get("software_version") if metadata else None,
        ).model_dump(exclude_none=True)
        return _json_response(content, status_code=201)
    except McpOAuthDisabledError as exc:
        db.rollback()
        return _oauth_error("temporarily_unavailable", str(exc), status_code=503)
    except (McpOAuthValidationError, McpOAuthInsufficientScopeError) as exc:
        db.rollback()
        return _oauth_error("invalid_client_metadata", str(exc), status_code=400)
    except Exception:
        db.rollback()
        raise


@router.get("/oauth/authorize", response_class=HTMLResponse)
def authorize_page(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    values = {key: value for key, value in request.query_params.items()}
    redirect_value = values.get("redirect_uri", "")
    state_value = values.get("state")
    try:
        auth = _validated_authorization_request(db, request, values)
    except (McpOAuthInvalidClientError, McpOAuthInvalidGrantError):
        return _html_response(
            "<!doctype html><title>Invalid authorization request</title>"
            "<h1>Invalid authorization request</h1>",
            status_code=400,
            secure_cookie=request.url.scheme == "https",
        )
    except (McpOAuthDisabledError, McpOAuthInsufficientScopeError) as exc:
        try:
            redirect = validate_redirect_uri(redirect_value)
        except McpOAuthError:
            redirect = ""
        if redirect:
            return _redirect_oauth_error(
                redirect,
                error="temporarily_unavailable",
                description=str(exc),
                state_value=state_value,
            )
        return _html_response(
            "<!doctype html><title>MCP unavailable</title><h1>MCP is unavailable</h1>",
            status_code=503,
            secure_cookie=request.url.scheme == "https",
        )
    except McpOAuthValidationError as exc:
        try:
            client = get_active_client(db, values.get("client_id", ""))
            redirect = validate_redirect_uri(redirect_value)
            valid_redirect = redirect in set(client.redirect_uris_json or [])
        except McpOAuthError:
            valid_redirect = False
            redirect = ""
        if valid_redirect:
            return _redirect_oauth_error(
                redirect,
                error="invalid_request",
                description=str(exc),
                state_value=state_value,
            )
        return _html_response(
            "<!doctype html><title>Invalid authorization request</title>"
            "<h1>Invalid authorization request</h1>",
            status_code=400,
            secure_cookie=request.url.scheme == "https",
        )

    csrf_token = secrets.token_urlsafe(32)
    return _html_response(
        _authorization_html(auth, csrf_token=csrf_token),
        csrf_token=csrf_token,
        secure_cookie=_public_origin(request).startswith("https://"),
    )


@router.post("/oauth/authorize", response_class=HTMLResponse)
async def authorize_decision(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    form_data = await request.form()
    values = {key: str(value) for key, value in form_data.items()}
    redirect_value = values.get("redirect_uri", "")
    state_value = values.get("state") or None
    try:
        auth = _validated_authorization_request(db, request, values)
    except McpOAuthError:
        return _html_response(
            "<!doctype html><title>Invalid authorization request</title>"
            "<h1>Invalid authorization request</h1>",
            status_code=400,
            secure_cookie=_public_origin(request).startswith("https://"),
        )

    if values.get("decision") == "deny":
        response = _redirect_oauth_error(
            auth["redirect_uri"],
            error="access_denied",
            description="The Part Pilot owner denied this request.",
            state_value=auth["state"],
        )
        response.delete_cookie(CSRF_COOKIE, path="/oauth/authorize")
        return response

    cookie_token = request.cookies.get(CSRF_COOKIE, "")
    submitted_token = values.get("csrf_token", "")
    if not cookie_token or not hmac.compare_digest(cookie_token, submitted_token):
        return _html_response(
            "<!doctype html><title>Authorization expired</title>"
            "<h1>Authorization request expired</h1>",
            status_code=400,
            secure_cookie=_public_origin(request).startswith("https://"),
        )

    username = values.get("username", "").strip()
    password = values.get("password", "")
    user = authenticate_user(db, username=username, password=password)
    if user is None:
        db.rollback()
        csrf_token = secrets.token_urlsafe(32)
        return _html_response(
            _authorization_html(
                auth,
                csrf_token=csrf_token,
                error_message="Invalid username or password.",
                username=username,
            ),
            status_code=401,
            csrf_token=csrf_token,
            secure_cookie=_public_origin(request).startswith("https://"),
        )

    try:
        grant_consent(
            db,
            user_id=user.id,
            client_id=auth["client_id"],
            scopes=auth["scopes"],
            commit=False,
        )
        issued = issue_authorization_code(
            db,
            client_id=auth["client_id"],
            user_id=user.id,
            redirect_uri=auth["redirect_uri"],
            scopes=auth["scopes"],
            code_challenge=auth["code_challenge"],
            code_challenge_method="S256",
            resource_uri=auth["resource"],
            commit=False,
        )
        db.commit()
    except McpOAuthError as exc:
        db.rollback()
        return _redirect_oauth_error(
            auth["redirect_uri"],
            error="server_error",
            description=str(exc),
            state_value=auth["state"],
        )
    except Exception:
        db.rollback()
        raise

    response_values = {"code": issued.code}
    if auth["state"]:
        response_values["state"] = auth["state"]
    response = RedirectResponse(
        _append_query(auth["redirect_uri"], response_values), status_code=302
    )
    response.delete_cookie(CSRF_COOKIE, path="/oauth/authorize")
    return response


@router.post("/oauth/token", response_model=OAuthTokenResponse)
async def token_endpoint(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> JSONResponse:
    form_data = await request.form()
    form = {key: str(value) for key, value in form_data.items()}
    try:
        client_id, client_secret = _client_authentication(authorization, form)
        grant_type = form.get("grant_type", "")
        resource = form.get("resource", "").strip() or _resource_uri(request)
        if resource != _resource_uri(request):
            raise McpOAuthInvalidGrantError("OAuth resource does not match this MCP server.")
        if grant_type == "authorization_code":
            issued = exchange_authorization_code(
                db,
                code=form.get("code", ""),
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=form.get("redirect_uri", ""),
                code_verifier=form.get("code_verifier", ""),
                resource_uri=resource,
                commit=True,
            )
        elif grant_type == "refresh_token":
            scope_value = form.get("scope")
            issued = rotate_refresh_token(
                db,
                refresh_token=form.get("refresh_token", ""),
                client_id=client_id,
                client_secret=client_secret,
                scopes=(None if scope_value is None else scope_value.split()),
                resource_uri=resource,
                commit=True,
            )
        else:
            raise McpOAuthValidationError("Unsupported grant_type.")
        content = OAuthTokenResponse(
            access_token=issued.access_token,
            refresh_token=issued.refresh_token,
            token_type=issued.token_type,
            expires_in=issued.expires_in,
            scope=issued.scope,
        ).model_dump(exclude_none=True)
        return _json_response(content)
    except McpOAuthInvalidClientError as exc:
        db.rollback()
        return _oauth_error(
            "invalid_client",
            str(exc),
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Part Pilot OAuth"'},
        )
    except McpOAuthRefreshReplayError as exc:
        return _oauth_error("invalid_grant", str(exc), status_code=400)
    except McpOAuthInvalidGrantError as exc:
        db.rollback()
        return _oauth_error("invalid_grant", str(exc), status_code=400)
    except McpOAuthInsufficientScopeError as exc:
        db.rollback()
        return _oauth_error("invalid_scope", str(exc), status_code=400)
    except McpOAuthDisabledError as exc:
        db.rollback()
        return _oauth_error("temporarily_unavailable", str(exc), status_code=503)
    except McpOAuthValidationError as exc:
        db.rollback()
        return _oauth_error("invalid_request", str(exc), status_code=400)
    except Exception:
        db.rollback()
        raise


@router.post("/oauth/revoke")
async def revocation_endpoint(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Response:
    form_data = await request.form()
    form = {key: str(value) for key, value in form_data.items()}
    try:
        client_id, client_secret = _client_authentication(authorization, form)
        authenticate_client(
            db, client_id=client_id, client_secret=client_secret
        )
        token_value = form.get("token", "")
        if token_value:
            revoke_token(
                db,
                token_value=token_value,
                client_id=client_id,
                client_secret=client_secret,
                commit=True,
            )
        return Response(status_code=200, headers=_no_store_headers())
    except McpOAuthInvalidClientError as exc:
        db.rollback()
        return _oauth_error(
            "invalid_client",
            str(exc),
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Part Pilot OAuth"'},
        )
    except McpOAuthError:
        db.rollback()
        return Response(status_code=200, headers=_no_store_headers())
    except Exception:
        db.rollback()
        raise
