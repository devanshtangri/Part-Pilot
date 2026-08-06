from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.db.settings import set_app_setting
from app.main import app
from app.models import AppSetting, AuditLog, McpOAuthClient, McpOAuthToken, User
from app.services.auth import create_user
from app.services.mcp_oauth import McpOAuthDisabledError, pkce_s256_challenge


# PARTPILOT:MCP_OAUTH_HTTP_SMOKE:V519
ORIGIN = "https://partpilot.example"
RESOURCE = f"{ORIGIN}/mcp"
REDIRECT = "https://claude.ai/api/mcp/auth_callback"
HEADERS = {
    "host": "partpilot.example",
    "x-forwarded-proto": "https",
    "x-forwarded-host": "partpilot.example",
}


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def sqlite_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"OAuth HTTP smoke requires SQLite, got {url!r}")
    return Path(url[len(prefix):]).resolve()


def serialize(value):
    if isinstance(value, bytes):
        return {"bytes": value.hex()}
    return value


def database_snapshot() -> dict[str, list[dict[str, object]]]:
    db = sqlite3.connect(sqlite_path())
    db.row_factory = sqlite3.Row
    try:
        tables = [
            str(row[0])
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        result: dict[str, list[dict[str, object]]] = {}
        for table in tables:
            info = list(db.execute(f'PRAGMA table_info("{table}")'))
            columns = [str(row[1]) for row in info]
            primary = [str(row[1]) for row in info if row[5]]
            order = primary or columns
            order_sql = ", ".join(f'"{name}"' for name in order)
            rows = db.execute(
                f'SELECT * FROM "{table}" ORDER BY {order_sql}'
            ).fetchall()
            result[table] = [
                {name: serialize(row[name]) for name in columns}
                for row in rows
            ]
        return result
    finally:
        db.close()


def assert_response(response, status_code: int, label: str) -> None:
    if response.status_code != status_code:
        fail(
            f"{label} returned HTTP {response.status_code}: "
            f"{response.text[:700]}"
        )


def assert_security_headers(
    response,
    *,
    scripted: bool,
    form_action_origin: str | None = None,
) -> None:
    expected = {
        "cache-control": "no-store",
        "pragma": "no-cache",
        "x-content-type-options": "nosniff",
        "referrer-policy": "no-referrer",
        "x-frame-options": "DENY",
    }
    for name, value in expected.items():
        if response.headers.get(name) != value:
            fail(f"OAuth HTML has wrong {name}: {response.headers.get(name)!r}")
    csp = response.headers.get("content-security-policy", "")
    directives: dict[str, str] = {}
    for raw_directive in csp.split(";"):
        words = raw_directive.strip().split()
        if words:
            directives[words[0]] = " ".join(words[1:])
    expected_values = {
        "default-src": "'none'",
        "style-src": "'unsafe-inline'",
        "base-uri": "'none'",
        "frame-ancestors": "'none'",
    }
    for name, value in expected_values.items():
        if directives.get(name) != value:
            fail(f"OAuth HTML CSP has wrong {name!r}: {csp}")
    expected_form_action = "'self'"
    if form_action_origin is not None:
        expected_form_action += " " + form_action_origin
    if directives.get("form-action") != expected_form_action:
        fail(
            "OAuth HTML CSP has wrong form-action: "
            f"{directives.get('form-action')!r}; expected {expected_form_action!r}"
        )
    if scripted:
        match = re.search(r"script-src 'nonce-([^']+)'", csp)
        if match is None:
            fail(f"Scripted OAuth HTML has no nonce CSP: {csp}")
        nonce = match.group(1)
        if f'nonce="{nonce}"' not in response.text:
            fail("OAuth HTML script nonce does not match its CSP")
        if "script-src 'unsafe-inline'" in csp:
            fail("OAuth HTML weakened script CSP with unsafe-inline")
    elif "script-src 'none'" not in csp:
        fail(f"Result OAuth HTML should disable scripts: {csp}")


def assert_shell(
    response,
    *,
    status_code: int,
    heading: str,
    scripted: bool = False,
    form_action_origin: str | None = None,
) -> None:
    assert_response(response, status_code, heading)
    assert_security_headers(
        response,
        scripted=scripted,
        form_action_origin=form_action_origin,
    )
    for marker in (
        'class="oauth-shell"',
        "Part Pilot",
        f'id="oauth-heading">{heading}</h1>',
        "Private inventory access",
    ):
        if marker not in response.text:
            fail(f"OAuth shell is missing marker {marker!r}")


def authorization_params(client_id: str, verifier: str, state: str) -> dict[str, str]:
    return {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "scope": "mcp:read",
        "state": state,
        "code_challenge": pkce_s256_challenge(verifier),
        "code_challenge_method": "S256",
        "resource": RESOURCE,
    }


def csrf_from_html(text: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', text)
    if match is None:
        fail("Authorization page did not contain a CSRF token")
    return match.group(1)


def authorization_page(
    client: TestClient,
    params: dict[str, str],
    label: str,
):
    page = client.get(
        "/oauth/authorize",
        params=params,
        headers=HEADERS,
        follow_redirects=False,
    )
    callback_parts = urlsplit(REDIRECT)
    callback_origin = f"{callback_parts.scheme}://{callback_parts.netloc}"
    assert_shell(
        page,
        status_code=200,
        heading="Authorize connector",
        scripted=True,
        form_action_origin=callback_origin,
    )
    for marker in (
        "data-oauth-form",
        'autocomplete="username"',
        'autocomplete="current-password"',
        "input:-webkit-autofill",
        "::selection",
        "Authorizing...",
        "Denying...",
        "event.submitter",
        'window.addEventListener("pageshow"',
        'event.key === "Enter"',
    ):
        if marker not in page.text:
            fail(f"{label} page is missing browser-lock/style marker {marker!r}")
    cookie = page.headers.get("set-cookie", "")
    for marker in (
        "partpilot_mcp_oauth_csrf=",
        "HttpOnly",
        "Secure",
        "SameSite=lax",
        "Path=/oauth/authorize",
    ):
        if marker not in cookie:
            fail(f"{label} page CSRF cookie is missing {marker!r}: {cookie}")
    return page


def callback_code(response, *, state: str, label: str) -> str:
    assert_response(response, 302, label)
    location = response.headers.get("location", "")
    parsed = urlsplit(location)
    if f"{parsed.scheme}://{parsed.netloc}{parsed.path}" != REDIRECT:
        fail(f"{label} redirected to an unexpected URI: {location}")
    query = parse_qs(parsed.query)
    if query.get("state") != [state] or len(query.get("code", [])) != 1:
        fail(f"{label} redirect is missing exact code/state: {location}")
    return query["code"][0]


def authorize(
    client: TestClient,
    *,
    client_id: str,
    username: str,
    password: str,
    verifier: str,
    state: str,
) -> str:
    params = authorization_params(client_id, verifier, state)
    page = authorization_page(client, params, f"{state} authorization")
    response = client.post(
        "/oauth/authorize",
        data={
            **params,
            "csrf_token": csrf_from_html(page.text),
            "username": username,
            "password": password,
            "decision": "approve",
        },
        headers=HEADERS,
        follow_redirects=False,
    )
    return callback_code(response, state=state, label=f"{state} approval")


def exchange(
    client: TestClient,
    *,
    client_id: str,
    code: str,
    verifier: str,
) -> dict[str, object]:
    response = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "redirect_uri": REDIRECT,
            "code_verifier": verifier,
            "resource": RESOURCE,
        },
        headers=HEADERS,
    )
    assert_response(response, 200, "authorization-code exchange")
    if response.headers.get("cache-control") != "no-store":
        fail("Token response is not no-store")
    body = response.json()
    if (
        not str(body.get("access_token", "")).startswith("pp_mcp_access_")
        or not str(body.get("refresh_token", "")).startswith("pp_mcp_refresh_")
        or body.get("token_type") != "Bearer"
        or body.get("scope") != "mcp:read"
    ):
        fail(f"Token response is invalid: {body}")
    return body


def oauth_code_count() -> int:
    db = sqlite3.connect(sqlite_path())
    try:
        return int(db.execute("SELECT COUNT(*) FROM mcp_oauth_authorization_codes").fetchone()[0])
    finally:
        db.close()


def cleanup_fixture(
    *,
    fixture_username: str,
    client_ids: list[str],
    original_settings: dict[str, tuple[object, ...]],
) -> None:
    db = SessionLocal()
    try:
        for client_id in client_ids:
            oauth_client = db.execute(
                select(McpOAuthClient).where(McpOAuthClient.client_id == client_id)
            ).scalar_one_or_none()
            if oauth_client is not None:
                db.delete(oauth_client)
        for audit in list(
            db.execute(
                select(AuditLog).where(AuditLog.event_type.like("mcp.oauth_%"))
            ).scalars()
        ):
            db.delete(audit)
        user = db.execute(
            select(User).where(User.username == fixture_username)
        ).scalar_one_or_none()
        if user is not None:
            db.delete(user)
        for key, values in original_settings.items():
            setting = db.execute(
                select(AppSetting).where(AppSetting.key == key)
            ).scalar_one()
            (
                setting.value_json,
                setting.value_text,
                setting.created_at,
                setting.updated_at,
            ) = values
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    before = database_snapshot()
    if any(before.get(table) for table in (
        "mcp_oauth_clients",
        "mcp_oauth_authorization_codes",
        "mcp_oauth_tokens",
        "mcp_oauth_consents",
    )):
        fail("OAuth HTTP smoke requires empty OAuth persistence tables")
    if any(
        row.get("event_type", "").startswith("mcp.oauth_")
        for row in before.get("audit_log", [])
    ):
        fail("OAuth HTTP smoke requires no pre-existing OAuth audit rows")

    fixture_username = "ppoauth" + uuid4().hex[:12]
    fixture_password = "PartPilot-OAuth-Smoke-518!"
    client_ids: list[str] = []
    setting_keys = (
        "mcp.enabled",
        "mcp.read_tools_enabled",
        "mcp.write_tools_enabled",
    )
    db = SessionLocal()
    try:
        original_settings = {}
        for key in setting_keys:
            setting = db.execute(
                select(AppSetting).where(AppSetting.key == key)
            ).scalar_one()
            original_settings[key] = (
                setting.value_json,
                setting.value_text,
                setting.created_at,
                setting.updated_at,
            )
        create_user(
            db,
            username=fixture_username,
            display_name="Patch 518 OAuth Smoke",
            password=fixture_password,
            commit=False,
        )
        set_app_setting(db, "mcp.enabled", False, commit=False)
        set_app_setting(db, "mcp.read_tools_enabled", True, commit=False)
        set_app_setting(db, "mcp.write_tools_enabled", False, commit=False)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    try:
        with TestClient(app, base_url=ORIGIN) as client:
            metadata = client.get(
                "/.well-known/oauth-protected-resource/mcp", headers=HEADERS
            )
            assert_response(metadata, 200, "protected-resource metadata")
            if metadata.json().get("resource") != RESOURCE:
                fail(f"Protected-resource metadata is wrong: {metadata.json()}")

            server_metadata = client.get(
                "/.well-known/oauth-authorization-server", headers=HEADERS
            )
            assert_response(server_metadata, 200, "authorization-server metadata")
            expected_metadata = {
                "issuer": ORIGIN,
                "authorization_endpoint": f"{ORIGIN}/oauth/authorize",
                "token_endpoint": f"{ORIGIN}/oauth/token",
                "registration_endpoint": f"{ORIGIN}/oauth/register",
                "revocation_endpoint": f"{ORIGIN}/oauth/revoke",
            }
            if any(server_metadata.json().get(k) != v for k, v in expected_metadata.items()):
                fail(f"Authorization-server metadata is wrong: {server_metadata.json()}")

            registration_payload = {
                "redirect_uris": [REDIRECT],
                "client_name": "Claude Website Patch 518 Smoke",
                "client_uri": "https://claude.ai",
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
                "application_type": "web",
                "software_id": "partpilot-patch-518-smoke",
                "software_version": "518",
            }
            disabled = client.post(
                "/oauth/register", json=registration_payload, headers=HEADERS
            )
            assert_response(disabled, 503, "disabled dynamic registration")

            db = SessionLocal()
            try:
                set_app_setting(db, "mcp.enabled", True, commit=True)
            finally:
                db.close()

            registration = client.post(
                "/oauth/register", json=registration_payload, headers=HEADERS
            )
            assert_response(registration, 201, "dynamic registration")
            registration_body = registration.json()
            client_id = str(registration_body.get("client_id", ""))
            client_ids.append(client_id)
            if (
                not client_id.startswith("pp_mcp_client_")
                or "client_secret" in registration_body
                or registration_body.get("token_endpoint_auth_method") != "none"
            ):
                fail(f"Dynamic registration response is invalid: {registration_body}")

            initial_params = authorization_params(client_id, "i" * 64, "initial-state")
            authorization_page(client, initial_params, "initial authorization")

            invalid_redirect = client.get(
                "/oauth/authorize",
                params={
                    **authorization_params(client_id, "v" * 64, "bad-redirect"),
                    "redirect_uri": "https://evil.example/callback",
                },
                headers=HEADERS,
                follow_redirects=False,
            )
            assert_shell(
                invalid_redirect,
                status_code=400,
                heading="Invalid authorization request",
            )

            invalid_pkce = client.get(
                "/oauth/authorize",
                params={
                    **authorization_params(client_id, "p" * 64, "pkce-state"),
                    "code_challenge": "invalid",
                },
                headers=HEADERS,
                follow_redirects=False,
            )
            assert_response(invalid_pkce, 302, "invalid PKCE callback")
            pkce_query = parse_qs(urlsplit(invalid_pkce.headers["location"]).query)
            if pkce_query.get("error") != ["invalid_request"] or pkce_query.get("state") != ["pkce-state"]:
                fail(f"Invalid PKCE callback is wrong: {invalid_pkce.headers['location']}")

            with patch(
                "app.api.routes.mcp_oauth._validated_authorization_request",
                side_effect=McpOAuthDisabledError("MCP is unavailable."),
            ):
                unavailable = client.get(
                    "/oauth/authorize", headers=HEADERS, follow_redirects=False
                )
            assert_shell(
                unavailable,
                status_code=503,
                heading="MCP is unavailable",
            )
            if "Return to the connector and reconnect" not in unavailable.text:
                fail("Unavailable page is missing reconnect guidance")

            with patch(
                "app.api.routes.mcp_oauth._validated_authorization_request",
                side_effect=RuntimeError("synthetic preparation failure"),
            ):
                server_error = client.get(
                    "/oauth/authorize", headers=HEADERS, follow_redirects=False
                )
            assert_shell(
                server_error,
                status_code=500,
                heading="Authorization could not continue",
            )

            wrong_params = authorization_params(client_id, "w" * 64, "wrong-login")
            wrong_page = authorization_page(client, wrong_params, "wrong-login authorization")
            wrong_csrf = csrf_from_html(wrong_page.text)
            wrong_login = client.post(
                "/oauth/authorize",
                data={
                    **wrong_params,
                    "csrf_token": wrong_csrf,
                    "username": fixture_username,
                    "password": "not-the-password",
                    "decision": "approve",
                },
                headers=HEADERS,
                follow_redirects=False,
            )
            callback_parts = urlsplit(REDIRECT)
            callback_origin = f"{callback_parts.scheme}://{callback_parts.netloc}"
            assert_shell(
                wrong_login,
                status_code=401,
                heading="Authorize connector",
                scripted=True,
                form_action_origin=callback_origin,
            )
            if (
                "Invalid username or password" not in wrong_login.text
                or f'value="{fixture_username}"' not in wrong_login.text
                or 'type="password" name="password" value=' in wrong_login.text
                or csrf_from_html(wrong_login.text) == wrong_csrf
            ):
                fail("Wrong-credential page did not safely refresh its form")

            duplicate_verifier = "a" * 64
            duplicate_state = "duplicate-state"
            duplicate_params = authorization_params(
                client_id, duplicate_verifier, duplicate_state
            )
            duplicate_page = authorization_page(
                client, duplicate_params, "duplicate authorization"
            )
            duplicate_form = {
                **duplicate_params,
                "csrf_token": csrf_from_html(duplicate_page.text),
                "username": fixture_username,
                "password": fixture_password,
                "decision": "approve",
            }
            before_codes = oauth_code_count()
            first_approve = client.post(
                "/oauth/authorize",
                data=duplicate_form,
                headers=HEADERS,
                follow_redirects=False,
            )
            first_code = callback_code(
                first_approve,
                state=duplicate_state,
                label="first authorization approval",
            )
            if oauth_code_count() != before_codes + 1:
                fail("First approval did not create exactly one authorization code")
            deleted_cookie = first_approve.headers.get("set-cookie", "")
            if "partpilot_mcp_oauth_csrf=" not in deleted_cookie or "Max-Age=0" not in deleted_cookie:
                fail(f"Successful approval did not delete the CSRF cookie: {deleted_cookie}")

            duplicate = client.post(
                "/oauth/authorize",
                data=duplicate_form,
                headers=HEADERS,
                follow_redirects=False,
            )
            assert_shell(
                duplicate,
                status_code=400,
                heading="Authorization request expired",
            )
            for marker in (
                "already used or timed out",
                "Return to the connector and reconnect",
            ):
                if marker not in duplicate.text:
                    fail(f"Expired page is missing guidance {marker!r}")
            if oauth_code_count() != before_codes + 1:
                fail("Duplicate authorization POST created another code")

            wrong_resource = client.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "code": first_code,
                    "redirect_uri": REDIRECT,
                    "code_verifier": duplicate_verifier,
                    "resource": "https://evil.example/mcp",
                },
                headers=HEADERS,
            )
            assert_response(wrong_resource, 400, "wrong token resource")
            if wrong_resource.json().get("error") != "invalid_grant":
                fail(f"Wrong resource returned the wrong token error: {wrong_resource.json()}")

            first_tokens = exchange(
                client,
                client_id=client_id,
                code=first_code,
                verifier=duplicate_verifier,
            )
            repeated_exchange = client.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "code": first_code,
                    "redirect_uri": REDIRECT,
                    "code_verifier": duplicate_verifier,
                    "resource": RESOURCE,
                },
                headers=HEADERS,
            )
            assert_response(repeated_exchange, 400, "authorization-code replay")
            if repeated_exchange.json().get("error") != "invalid_grant":
                fail(f"Code replay returned the wrong error: {repeated_exchange.json()}")

            revoke = client.post(
                "/oauth/revoke",
                data={
                    "client_id": client_id,
                    "token": first_tokens["access_token"],
                },
                headers=HEADERS,
            )
            assert_response(revoke, 200, "token revocation")

            second_verifier = "b" * 64
            second_code = authorize(
                client,
                client_id=client_id,
                username=fixture_username,
                password=fixture_password,
                verifier=second_verifier,
                state="state-two",
            )
            second_tokens = exchange(
                client,
                client_id=client_id,
                code=second_code,
                verifier=second_verifier,
            )
            refreshed = client.post(
                "/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "refresh_token": second_tokens["refresh_token"],
                    "scope": "mcp:read",
                    "resource": RESOURCE,
                },
                headers=HEADERS,
            )
            assert_response(refreshed, 200, "refresh-token rotation")
            refreshed_body = refreshed.json()
            if refreshed_body.get("refresh_token") == second_tokens["refresh_token"]:
                fail("Refresh-token rotation reused the old token")

            replay = client.post(
                "/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "refresh_token": second_tokens["refresh_token"],
                    "resource": RESOURCE,
                },
                headers=HEADERS,
            )
            assert_response(replay, 400, "refresh replay rejection")
            if replay.json().get("error") != "invalid_grant":
                fail(f"Refresh replay returned the wrong error: {replay.json()}")

            deny_verifier = "c" * 64
            deny_params = authorization_params(client_id, deny_verifier, "deny-state")
            deny_page = authorization_page(client, deny_params, "denial authorization")
            denied = client.post(
                "/oauth/authorize",
                data={
                    **deny_params,
                    "csrf_token": csrf_from_html(deny_page.text),
                    "decision": "deny",
                },
                headers=HEADERS,
                follow_redirects=False,
            )
            assert_response(denied, 302, "authorization denial")
            denied_query = parse_qs(urlsplit(denied.headers["location"]).query)
            if (
                denied_query.get("error") != ["access_denied"]
                or denied_query.get("state") != ["deny-state"]
            ):
                fail(f"Authorization denial is invalid: {denied.headers['location']}")

            invalid_post = client.post(
                "/oauth/authorize",
                data={"decision": "approve"},
                headers=HEADERS,
                follow_redirects=False,
            )
            assert_shell(
                invalid_post,
                status_code=400,
                heading="Invalid authorization request",
            )

            error_params = authorization_params(client_id, "e" * 64, "error-state")
            error_page = authorization_page(client, error_params, "server-error authorization")
            with patch(
                "app.api.routes.mcp_oauth.grant_consent",
                side_effect=RuntimeError("synthetic grant failure"),
            ):
                failed_grant = client.post(
                    "/oauth/authorize",
                    data={
                        **error_params,
                        "csrf_token": csrf_from_html(error_page.text),
                        "username": fixture_username,
                        "password": fixture_password,
                        "decision": "approve",
                    },
                    headers=HEADERS,
                    follow_redirects=False,
                )
            assert_shell(
                failed_grant,
                status_code=500,
                heading="Authorization could not be completed",
            )
            if "No connector access was granted" not in failed_grant.text:
                fail("Server-error result does not explain that access was not granted")

            db = SessionLocal()
            try:
                token_rows = list(db.execute(select(McpOAuthToken)).scalars())
                client_row = db.execute(
                    select(McpOAuthClient).where(McpOAuthClient.client_id == client_id)
                ).scalar_one()
                persisted = json.dumps(
                    {
                        "client": {
                            "client_id": client_row.client_id,
                            "client_secret_hash": client_row.client_secret_hash,
                            "metadata": client_row.metadata_json,
                        },
                        "tokens": [
                            {
                                "access": token.access_token_hash,
                                "refresh": token.refresh_token_hash,
                            }
                            for token in token_rows
                        ],
                        "audits": [
                            audit.metadata_json
                            for audit in db.execute(
                                select(AuditLog).where(
                                    AuditLog.event_type.like("mcp.oauth_%")
                                )
                            ).scalars()
                        ],
                    },
                    sort_keys=True,
                )
                secrets_to_reject = [
                    first_code,
                    str(first_tokens["access_token"]),
                    str(first_tokens["refresh_token"]),
                    second_code,
                    str(second_tokens["access_token"]),
                    str(second_tokens["refresh_token"]),
                    str(refreshed_body.get("access_token", "")),
                    str(refreshed_body.get("refresh_token", "")),
                ]
                if any(secret and secret in persisted for secret in secrets_to_reject):
                    fail("Plaintext OAuth credentials were persisted")
                if not token_rows or not all(
                    len(token.access_token_hash) == 64 for token in token_rows
                ):
                    fail("OAuth access tokens are not stored as SHA-256 hashes")
            finally:
                db.close()
    finally:
        cleanup_fixture(
            fixture_username=fixture_username,
            client_ids=client_ids,
            original_settings=original_settings,
        )

    after = database_snapshot()
    if after != before:
        changed = sorted(key for key in before if before.get(key) != after.get(key))
        fail(f"OAuth HTTP smoke did not restore the database exactly: {changed}")
    print(
        "[PASS] MCP OAuth HTTP covers shared standalone shell styling, autofill, "
        "selection, nonce-CSP submit locking, validated callback-origin form-action, "
        "bfcache recovery, initial GET, invalid "
        "login, first approval, duplicate POST expiry, denial, invalid/unavailable/"
        "server-error pages, exact callback state, PKCE/resource validation, token "
        "exchange/replay, refresh rotation/replay, revocation, hashed credentials, "
        "no-store security headers and exact copied-database cleanup"
    )


if __name__ == "__main__":
    main()
