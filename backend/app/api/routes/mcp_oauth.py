from __future__ import annotations

import base64
import binascii
import hmac
import html
import json
import secrets
from datetime import timezone
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.client_ip import (
    ClientAddressError,
    TrustedProxyConfigurationError,
    resolve_public_origin,
)
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


def _public_origin(request: Request) -> str:
    settings = get_settings()
    try:
        return resolve_public_origin(
            request.scope,
            configured_public_base_url=settings.public_base_url,
            trusted_proxy_cidrs=settings.trusted_proxy_cidrs,
        )
    except ClientAddressError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TrustedProxyConfigurationError as exc:
        raise RuntimeError(str(exc)) from exc


# PARTPILOT:MCP_FORWARDED_ORIGIN_OAUTH:V508

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


# PARTPILOT:MCP_OAUTH_STANDALONE_SHELL:V519
OAUTH_STYLES = r"""
:root {
  color-scheme: dark;
  --bg: #0b1018;
  --sidebar: #0f1724;
  --panel: #121a27;
  --panel-soft: #182235;
  --panel-raised: #1c2636;
  --border: #273247;
  --border-strong: #35435c;
  --text: #f1f5f9;
  --muted: #9aa8bd;
  --accent: #2dd4a3;
  --accent-strong: #42d6ab;
  --accent-soft: rgba(45, 212, 163, 0.12);
  --danger: #ff7b7b;
  --danger-soft: rgba(255, 123, 123, 0.08);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--text);
}
* { box-sizing: border-box; }
::selection { background: var(--accent); color: #07130f; }
html { min-width: 320px; min-height: 100%; background: var(--bg); }
body {
  min-height: 100vh;
  margin: 0;
  display: grid;
  place-items: center;
  padding: 24px 16px;
  background: var(--bg);
  color: var(--text);
}
button, input { font: inherit; }
a { color: var(--accent-strong); text-underline-offset: 3px; }
a:hover { color: #70e6c2; }
.oauth-shell {
  width: min(760px, 100%);
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: var(--panel);
}
.oauth-header {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--border);
  background: var(--sidebar);
}
.oauth-mark {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  border: 1px solid rgba(45, 212, 163, 0.32);
  border-radius: 7px;
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 850;
}
.oauth-brand strong, .oauth-brand span { display: block; }
.oauth-brand strong { font-size: 0.94rem; }
.oauth-brand span { margin-top: 2px; color: var(--muted); font-size: 0.72rem; }
.oauth-content { padding: 22px; }
.oauth-eyebrow {
  margin: 0 0 7px;
  color: var(--accent);
  font-size: 0.69rem;
  font-weight: 800;
  letter-spacing: 0.09em;
  text-transform: uppercase;
}
h1 { margin: 0; font-size: clamp(1.55rem, 5vw, 2rem); line-height: 1.15; letter-spacing: -0.025em; }
.oauth-description { max-width: 62ch; margin: 10px 0 0; color: var(--muted); font-size: 0.88rem; line-height: 1.55; }
.oauth-client {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 7px 12px;
  margin: 18px 0 0;
  padding: 12px 13px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: var(--panel-soft);
}
.oauth-client strong { font-size: 0.83rem; }
.oauth-client a { font-size: 0.73rem; }
.scope-list { list-style: none; margin: 12px 0 0; padding: 0; border: 1px solid var(--border); border-radius: 7px; overflow: hidden; }
.scope-list li { display: grid; gap: 4px; padding: 11px 12px; border-bottom: 1px solid var(--border); background: var(--panel-soft); }
.scope-list li:last-child { border-bottom: 0; }
.scope-list strong { font-size: 0.76rem; }
.scope-list span { color: var(--muted); font-size: 0.72rem; line-height: 1.45; }
.oauth-error, .oauth-result {
  margin: 15px 0 0;
  padding: 11px 12px;
  border: 1px solid rgba(255, 123, 123, 0.3);
  border-radius: 7px;
  background: var(--danger-soft);
  color: var(--danger);
  font-size: 0.78rem;
  line-height: 1.5;
}
.oauth-result.is-neutral { border-color: var(--border); background: var(--panel-soft); color: var(--muted); }
.oauth-form { margin-top: 16px; }
.oauth-field { display: grid; gap: 6px; margin-top: 12px; }
.oauth-field > span { color: #dbe4ef; font-size: 0.76rem; font-weight: 720; }
.oauth-field input {
  width: 100%;
  min-height: 44px;
  padding: 10px 11px;
  border: 1px solid var(--border);
  border-radius: 7px;
  outline: none;
  background: var(--panel-raised);
  color: var(--text);
  caret-color: var(--accent);
}
.oauth-field input:hover { border-color: var(--border-strong); }
.oauth-field input:focus-visible { border-color: rgba(45, 212, 163, 0.82); box-shadow: 0 0 0 3px var(--accent-soft); }
.oauth-field input[aria-invalid="true"] { border-color: var(--danger); }
.oauth-field input:-webkit-autofill,
.oauth-field input:-webkit-autofill:hover,
.oauth-field input:-webkit-autofill:focus,
.oauth-field input:-webkit-autofill:active {
  -webkit-text-fill-color: var(--text);
  caret-color: var(--accent);
  box-shadow: 0 0 0 1000px var(--panel-raised) inset;
  transition: background-color 9999s ease-out 0s;
}
.oauth-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; margin-top: 17px; }
.oauth-button {
  min-height: 43px;
  padding: 9px 12px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: var(--panel-soft);
  color: var(--text);
  cursor: pointer;
  font-weight: 780;
}
.oauth-button:hover:not(:disabled) { border-color: var(--border-strong); background: #202a39; }
.oauth-button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.oauth-button.is-primary { border-color: rgba(45, 212, 163, 0.54); background: var(--accent-strong); color: #07130f; }
.oauth-button.is-primary:hover:not(:disabled) { background: #55dfb8; }
.oauth-button:disabled { cursor: wait; opacity: 0.58; }
.oauth-form[aria-busy="true"] .oauth-field input { opacity: 0.75; }
.oauth-privacy { margin: 14px 0 0; color: var(--muted); font-size: 0.69rem; line-height: 1.5; }
.oauth-footer { padding: 12px 18px; border-top: 1px solid var(--border); background: var(--sidebar); color: var(--muted); font-size: 0.67rem; line-height: 1.45; }
@media (max-width: 560px) {
  body { place-items: start center; padding: 12px; }
  .oauth-content { padding: 18px 16px; }
  .oauth-header, .oauth-footer { padding-left: 16px; padding-right: 16px; }
  .oauth-actions { grid-template-columns: 1fr; }
  .oauth-button.is-primary { order: -1; }
}
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; } }
"""

OAUTH_SUBMIT_SCRIPT = r"""
(() => {
  const form = document.querySelector("[data-oauth-form]");
  if (!form) return;
  const buttons = Array.from(form.querySelectorAll("button[type='submit']"));
  const approve = form.querySelector("button[value='approve']");
  let clicked = null;
  let decisionInput = null;
  const originals = buttons.map((button) => ({
    button,
    name: button.name,
    label: button.textContent,
  }));

  buttons.forEach((button) => {
    button.addEventListener("click", () => { clicked = button; });
  });

  form.addEventListener("keydown", (event) => {
    if (
      event.key === "Enter" &&
      event.target instanceof HTMLInputElement &&
      form.dataset.submitting !== "true" &&
      approve
    ) {
      event.preventDefault();
      approve.click();
    }
  });

  form.addEventListener("submit", (event) => {
    if (form.dataset.submitting === "true") {
      event.preventDefault();
      return;
    }
    const submitter = event.submitter || clicked || approve;
    const decision = submitter && submitter.value === "deny" ? "deny" : "approve";
    decisionInput = document.createElement("input");
    decisionInput.type = "hidden";
    decisionInput.name = "decision";
    decisionInput.value = decision;
    decisionInput.dataset.submitLockDecision = "true";
    form.appendChild(decisionInput);
    form.dataset.submitting = "true";
    form.setAttribute("aria-busy", "true");
    originals.forEach(({ button }) => {
      button.removeAttribute("name");
      button.disabled = true;
    });
    if (submitter) {
      submitter.textContent = decision === "deny" ? "Denying..." : "Authorizing...";
    }
  });

  window.addEventListener("pageshow", (event) => {
    if (!event.persisted) return;
    form.dataset.submitting = "false";
    form.removeAttribute("aria-busy");
    if (decisionInput && decisionInput.isConnected) decisionInput.remove();
    decisionInput = null;
    originals.forEach(({ button, name, label }) => {
      button.disabled = false;
      button.textContent = label;
      if (name) button.name = name;
    });
    clicked = null;
  });
})();
"""


def _oauth_document(
    *,
    title: str,
    eyebrow: str,
    heading: str,
    description: str,
    body: str,
    script_nonce: str | None = None,
) -> str:
    script = (
        '<script nonce="'
        + html.escape(script_nonce, quote=True)
        + '">'
        + OAUTH_SUBMIT_SCRIPT
        + "</script>"
        if script_nonce
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · Part Pilot</title>
<style>{OAUTH_STYLES}</style>
</head>
<body>
<main class="oauth-shell" aria-labelledby="oauth-heading">
<header class="oauth-header">
<div class="oauth-mark" aria-hidden="true">P</div>
<div class="oauth-brand"><strong>Part Pilot</strong><span>Private inventory access</span></div>
</header>
<section class="oauth-content">
<p class="oauth-eyebrow">{html.escape(eyebrow)}</p>
<h1 id="oauth-heading">{html.escape(heading)}</h1>
<p class="oauth-description">{html.escape(description)}</p>
{body}
</section>
<footer class="oauth-footer">Part Pilot grants only the permissions shown in this request. Connector access can be revoked later.</footer>
</main>
{script}
</body>
</html>"""


def _authorization_html(
    auth: dict[str, Any],
    *,
    csrf_token: str,
    script_nonce: str,
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
        '<a href="'
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
    body = f"""
<div class="oauth-client"><strong>{html.escape(client.client_name)}</strong>{client_uri}</div>
<ul class="scope-list" aria-label="Requested permissions">{scope_items}</ul>
{error}
<form class="oauth-form" method="post" action="/oauth/authorize" autocomplete="on" data-oauth-form>
{hidden}
<label class="oauth-field"><span>Username</span><input type="text" name="username" value="{html.escape(username, quote=True)}" autocomplete="username" required></label>
<label class="oauth-field"><span>Password</span><input type="password" name="password" autocomplete="current-password" required></label>
<div class="oauth-actions"><button class="oauth-button" type="submit" name="decision" value="deny" formnovalidate>Deny</button><button class="oauth-button is-primary" type="submit" name="decision" value="approve">Authorize</button></div>
</form>
<p class="oauth-privacy">Closing this page does not authorize access. Do not approve a connector you did not start.</p>
"""
    return _oauth_document(
        title=f"Authorize {client.client_name}",
        eyebrow="MCP authorization",
        heading="Authorize connector",
        description="Sign in to this Part Pilot installation and explicitly approve the requested access.",
        body=body,
        script_nonce=script_nonce,
    )


def _oauth_result_html(
    *,
    title: str,
    heading: str,
    description: str,
    detail: str,
    status: str = "error",
) -> str:
    result_class = "oauth-result is-neutral" if status == "neutral" else "oauth-result"
    body = f'<p class="{result_class}" role="alert">{html.escape(detail)}</p>'
    return _oauth_document(
        title=title,
        eyebrow="MCP authorization",
        heading=heading,
        description=description,
        body=body,
    )


def _html_response(
    content: str,
    *,
    status_code: int = 200,
    csrf_token: str | None = None,
    secure_cookie: bool = True,
    script_nonce: str | None = None,
    form_action_redirect_uri: str | None = None,
) -> HTMLResponse:
    script_policy = (
        "script-src 'nonce-" + script_nonce + "'; "
        if script_nonce
        else "script-src 'none'; "
    )
    form_action_policy = "form-action 'self'"
    if form_action_redirect_uri is not None:
        validated_redirect = validate_redirect_uri(form_action_redirect_uri)
        redirect_parts = urlsplit(validated_redirect)
        callback_origin = urlunsplit(
            (redirect_parts.scheme, redirect_parts.netloc, "", "", "")
        )
        form_action_policy += " " + callback_origin
    response = HTMLResponse(
        content,
        status_code=status_code,
        headers={
            **_no_store_headers(),
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'unsafe-inline'; "
                + script_policy
                + form_action_policy
                + "; base-uri 'none'; frame-ancestors 'none'"
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
    secure_cookie = _public_origin(request).startswith("https://")
    try:
        auth = _validated_authorization_request(db, request, values)
    except (McpOAuthInvalidClientError, McpOAuthInvalidGrantError):
        return _html_response(
            _oauth_result_html(
                title="Invalid authorization request",
                heading="Invalid authorization request",
                description="Part Pilot could not verify this connector request.",
                detail="Return to the connector and start the connection again. Do not edit the authorization URL.",
            ),
            status_code=400,
            secure_cookie=secure_cookie,
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
            _oauth_result_html(
                title="MCP unavailable",
                heading="MCP is unavailable",
                description="This Part Pilot installation is not accepting the requested MCP access.",
                detail="Return to the connector and reconnect after the Part Pilot owner enables the required access.",
            ),
            status_code=503,
            secure_cookie=secure_cookie,
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
            _oauth_result_html(
                title="Invalid authorization request",
                heading="Invalid authorization request",
                description="Part Pilot rejected an invalid or incomplete connector request.",
                detail="Return to the connector and start the connection again. The request parameters cannot be repaired on this page.",
            ),
            status_code=400,
            secure_cookie=secure_cookie,
        )
    except Exception:
        db.rollback()
        return _html_response(
            _oauth_result_html(
                title="Authorization error",
                heading="Authorization could not continue",
                description="Part Pilot encountered an unexpected error while preparing this request.",
                detail="Return to the connector and reconnect. If the problem continues, ask the Part Pilot owner to review the server logs.",
            ),
            status_code=500,
            secure_cookie=secure_cookie,
        )

    csrf_token = secrets.token_urlsafe(32)
    script_nonce = secrets.token_urlsafe(24)
    return _html_response(
        _authorization_html(
            auth,
            csrf_token=csrf_token,
            script_nonce=script_nonce,
        ),
        csrf_token=csrf_token,
        secure_cookie=secure_cookie,
        script_nonce=script_nonce,
        form_action_redirect_uri=auth["redirect_uri"],
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
    secure_cookie = _public_origin(request).startswith("https://")
    try:
        auth = _validated_authorization_request(db, request, values)
    except McpOAuthError:
        return _html_response(
            _oauth_result_html(
                title="Invalid authorization request",
                heading="Invalid authorization request",
                description="Part Pilot could not verify this submitted connector request.",
                detail="Return to the connector and start the connection again.",
            ),
            status_code=400,
            secure_cookie=secure_cookie,
        )
    except Exception:
        db.rollback()
        return _html_response(
            _oauth_result_html(
                title="Authorization error",
                heading="Authorization could not continue",
                description="Part Pilot encountered an unexpected error while validating this request.",
                detail="Return to the connector and reconnect. If the problem continues, ask the Part Pilot owner to review the server logs.",
            ),
            status_code=500,
            secure_cookie=secure_cookie,
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
            _oauth_result_html(
                title="Authorization expired",
                heading="Authorization request expired",
                description="This one-time authorization request was already used or timed out.",
                detail="Return to the connector and reconnect to create a fresh authorization request.",
            ),
            status_code=400,
            secure_cookie=secure_cookie,
        )

    username = values.get("username", "").strip()
    password = values.get("password", "")
    user = authenticate_user(db, username=username, password=password)
    if user is None:
        db.rollback()
        csrf_token = secrets.token_urlsafe(32)
        script_nonce = secrets.token_urlsafe(24)
        return _html_response(
            _authorization_html(
                auth,
                csrf_token=csrf_token,
                script_nonce=script_nonce,
                error_message="Invalid username or password.",
                username=username,
            ),
            status_code=401,
            csrf_token=csrf_token,
            secure_cookie=secure_cookie,
            script_nonce=script_nonce,
            form_action_redirect_uri=auth["redirect_uri"],
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
        return _html_response(
            _oauth_result_html(
                title="Authorization error",
                heading="Authorization could not be completed",
                description="Part Pilot encountered an unexpected error while granting this request.",
                detail="Return to the connector and reconnect. No connector access was granted by this failed attempt.",
            ),
            status_code=500,
            secure_cookie=secure_cookie,
        )

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
