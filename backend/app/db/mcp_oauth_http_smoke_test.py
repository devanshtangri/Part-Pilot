from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.db.settings import set_app_setting
from app.main import app
from app.models import AppSetting, AuditLog, McpOAuthClient, McpOAuthToken, User
from app.services.auth import create_user
from app.services.mcp_oauth import pkce_s256_challenge


# PARTPILOT:MCP_OAUTH_HTTP_SMOKE:V467
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
            f"{response.text[:500]}"
        )


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
    page = client.get(
        "/oauth/authorize",
        params=params,
        headers=HEADERS,
        follow_redirects=False,
    )
    assert_response(page, 200, "authorization page")
    if "Authorize connector" not in page.text or "Part Pilot" not in page.text:
        fail("Authorization page is missing its expected content")
    if page.headers.get("cache-control") != "no-store":
        fail("Authorization page is not marked no-store")
    csrf = csrf_from_html(page.text)
    form = {
        **params,
        "csrf_token": csrf,
        "username": username,
        "password": password,
        "decision": "approve",
    }
    response = client.post(
        "/oauth/authorize",
        data=form,
        headers=HEADERS,
        follow_redirects=False,
    )
    assert_response(response, 302, "authorization approval")
    location = response.headers.get("location", "")
    parsed = urlsplit(location)
    if f"{parsed.scheme}://{parsed.netloc}{parsed.path}" != REDIRECT:
        fail(f"Authorization redirected to an unexpected URI: {location}")
    query = parse_qs(parsed.query)
    if query.get("state") != [state] or len(query.get("code", [])) != 1:
        fail(f"Authorization redirect is missing code/state: {location}")
    return query["code"][0]


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
    body = response.json()
    if (
        not str(body.get("access_token", "")).startswith("pp_mcp_access_")
        or not str(body.get("refresh_token", "")).startswith("pp_mcp_refresh_")
        or body.get("token_type") != "Bearer"
        or body.get("scope") != "mcp:read"
    ):
        fail(f"Token response is invalid: {body}")
    return body


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
    fixture_password = "PartPilot-OAuth-Smoke-467!"
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
            display_name="Patch 467 OAuth Smoke",
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
                "client_name": "Claude Website Patch 467 Smoke",
                "client_uri": "https://claude.ai",
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
                "application_type": "web",
                "software_id": "partpilot-patch-467-smoke",
                "software_version": "467",
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

            invalid_redirect = client.get(
                "/oauth/authorize",
                params={
                    **authorization_params(client_id, "v" * 64, "bad-redirect"),
                    "redirect_uri": "https://evil.example/callback",
                },
                headers=HEADERS,
                follow_redirects=False,
            )
            assert_response(invalid_redirect, 400, "unregistered redirect rejection")

            wrong_params = authorization_params(client_id, "w" * 64, "wrong-login")
            wrong_page = client.get(
                "/oauth/authorize",
                params=wrong_params,
                headers=HEADERS,
            )
            assert_response(wrong_page, 200, "wrong-login authorization page")
            wrong_login = client.post(
                "/oauth/authorize",
                data={
                    **wrong_params,
                    "csrf_token": csrf_from_html(wrong_page.text),
                    "username": fixture_username,
                    "password": "not-the-password",
                    "decision": "approve",
                },
                headers=HEADERS,
                follow_redirects=False,
            )
            assert_response(wrong_login, 401, "wrong OAuth owner credentials")
            if "Invalid username or password" not in wrong_login.text:
                fail("Wrong-credential page did not show a safe error")

            first_verifier = "a" * 64
            first_code = authorize(
                client,
                client_id=client_id,
                username=fixture_username,
                password=fixture_password,
                verifier=first_verifier,
                state="state-one",
            )
            first_tokens = exchange(
                client,
                client_id=client_id,
                code=first_code,
                verifier=first_verifier,
            )
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
            deny_page = client.get(
                "/oauth/authorize", params=deny_params, headers=HEADERS
            )
            assert_response(deny_page, 200, "denial authorization page")
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
            if denied_query.get("error") != ["access_denied"]:
                fail(f"Authorization denial is invalid: {denied.headers['location']}")

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
        "[PASS] MCP OAuth HTTP covers protected-resource and authorization-server "
        "metadata, disabled gating, dynamic registration, safe redirects, owner "
        "sign-in and consent, S256 code exchange, refresh rotation/replay revocation, "
        "token revocation, hashed credentials, no-store responses and exact cleanup"
    )


if __name__ == "__main__":
    main()
