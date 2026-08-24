from __future__ import annotations

import json
from typing import Callable, TypeVar

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import (
    AppSetting,
    AuditLog,
    McpOAuthAuthorizationCode,
    McpOAuthClient,
    McpOAuthConsent,
    McpOAuthToken,
    User,
)
from app.services.mcp_oauth import (
    MCP_ENABLED_KEY,
    MCP_READ_ENABLED_KEY,
    MCP_SCOPE_READ,
    MCP_SCOPE_WRITE,
    MCP_WRITE_ENABLED_KEY,
    McpOAuthDisabledError,
    McpOAuthInsufficientScopeError,
    McpOAuthInvalidClientError,
    McpOAuthInvalidGrantError,
    McpOAuthInvalidTokenError,
    McpOAuthRefreshReplayError,
    McpOAuthValidationError,
    authenticate_client,
    exchange_authorization_code,
    grant_consent,
    hash_oauth_secret,
    issue_authorization_code,
    pkce_s256_challenge,
    register_client,
    revoke_client,
    revoke_consent,
    revoke_token,
    rotate_refresh_token,
    validate_access_token,
)


# PARTPILOT:MCP_OAUTH_SERVICE_SMOKE:V466
RESOURCE_URI = "https://partpilot.example/mcp"
CLAUDE_REDIRECT_URI = "https://claude.ai/api/mcp/auth_callback"
LOOPBACK_REDIRECT_URI = "http://127.0.0.1:47123/callback"
VERIFIER = "partpilot-claude-pkce-verifier-0123456789-ABCDE"

T = TypeVar("T")


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def expect_error(
    error_type: type[BaseException],
    callback: Callable[[], T],
    label: str,
) -> BaseException:
    try:
        callback()
    except error_type as exc:
        return exc
    except Exception as exc:
        fail(
            f"{label} raised {type(exc).__name__}, expected "
            f"{error_type.__name__}: {exc}"
        )
    fail(f"{label} did not raise {error_type.__name__}")


def table_counts(db) -> dict[str, int]:
    models = {
        "clients": McpOAuthClient,
        "codes": McpOAuthAuthorizationCode,
        "tokens": McpOAuthToken,
        "consents": McpOAuthConsent,
        "audits": AuditLog,
    }
    return {name: int(db.query(model).count()) for name, model in models.items()}


def setting_snapshot(db) -> dict[str, tuple[object, str | None, object]]:
    result: dict[str, tuple[object, str | None, object]] = {}
    for key in (
        MCP_ENABLED_KEY,
        MCP_READ_ENABLED_KEY,
        MCP_WRITE_ENABLED_KEY,
    ):
        row = db.query(AppSetting).filter(AppSetting.key == key).one()
        result[key] = (row.value_json, row.value_text, row.updated_at)
    return result


def set_bool_setting(db, key: str, value: bool) -> None:
    row = db.query(AppSetting).filter(AppSetting.key == key).one()
    row.value_json = value
    row.value_text = None
    db.flush()


def assert_secret_absent(db, secret: str, label: str) -> None:
    needle = secret.encode("utf-8")
    for model, columns in (
        (
            McpOAuthClient,
            ("client_id", "client_secret_hash", "client_name", "client_uri"),
        ),
        (
            McpOAuthAuthorizationCode,
            ("code_hash", "redirect_uri", "code_challenge", "resource_uri"),
        ),
        (
            McpOAuthToken,
            (
                "access_token_hash",
                "refresh_token_hash",
                "token_family_id",
                "resource_uri",
            ),
        ),
        (
            AuditLog,
            ("event_type", "summary", "metadata_json"),
        ),
    ):
        for row in db.execute(select(model)).scalars():
            for column in columns:
                value = getattr(row, column)
                if value is None:
                    continue
                payload = (
                    json.dumps(value, sort_keys=True, default=str)
                    if isinstance(value, (dict, list))
                    else str(value)
                ).encode("utf-8")
                if needle in payload:
                    fail(f"{label} plaintext leaked into {model.__name__}.{column}")


def run_service_lifecycle() -> None:
    db = SessionLocal()
    baseline_counts: dict[str, int] = {}
    baseline_settings: dict[str, tuple[object, str | None, object]] = {}
    plaintext_secrets: list[tuple[str, str]] = []
    try:
        baseline_counts = table_counts(db)
        baseline_settings = setting_snapshot(db)
        user = db.execute(
            select(User).where(User.is_active.is_(True)).order_by(User.id)
        ).scalars().first()
        if user is None:
            fail("MCP OAuth service smoke requires one active user")

        set_bool_setting(db, MCP_ENABLED_KEY, True)
        set_bool_setting(db, MCP_READ_ENABLED_KEY, True)
        set_bool_setting(db, MCP_WRITE_ENABLED_KEY, False)

        expect_error(
            McpOAuthValidationError,
            lambda: register_client(
                db,
                client_name="Invalid HTTP client",
                redirect_uris=["http://example.com/callback"],
                commit=False,
            ),
            "non-loopback HTTP redirect validation",
        )

        public = register_client(
            db,
            client_name="Claude Web",
            redirect_uris=[CLAUDE_REDIRECT_URI, LOOPBACK_REDIRECT_URI],
            token_endpoint_auth_method="none",
            client_uri="https://claude.ai",
            metadata={"software": "claude-web", "dynamic": True},
            actor_user_id=user.id,
            commit=False,
        )
        if public.client_secret is not None:
            fail("Public OAuth client unexpectedly received a client secret")
        if authenticate_client(
            db,
            client_id=public.client_id,
            client_secret=None,
        ).id != public.client.id:
            fail("Public OAuth client authentication failed")

        confidential = register_client(
            db,
            client_name="Hermes Agent",
            redirect_uris=[LOOPBACK_REDIRECT_URI],
            token_endpoint_auth_method="client_secret_post",
            actor_user_id=user.id,
            commit=False,
        )
        if confidential.client_secret is None:
            fail("Confidential OAuth client did not receive a client secret")
        plaintext_secrets.append((confidential.client_secret, "client secret"))
        if (
            confidential.client.client_secret_hash
            != hash_oauth_secret(confidential.client_secret)
        ):
            fail("Client secret was not stored as its SHA-256 hash")
        expect_error(
            McpOAuthInvalidClientError,
            lambda: authenticate_client(
                db,
                client_id=confidential.client_id,
                client_secret="wrong-client-secret",
            ),
            "wrong client secret",
        )
        authenticate_client(
            db,
            client_id=confidential.client_id,
            client_secret=confidential.client_secret,
        )

        grant_consent(
            db,
            user_id=user.id,
            client_id=public.client_id,
            scopes=[MCP_SCOPE_READ],
            commit=False,
        )
        expect_error(
            McpOAuthInsufficientScopeError,
            lambda: grant_consent(
                db,
                user_id=user.id,
                client_id=public.client_id,
                scopes=[MCP_SCOPE_WRITE],
                commit=False,
            ),
            "disabled write-scope consent",
        )

        challenge = pkce_s256_challenge(VERIFIER)
        issued_code = issue_authorization_code(
            db,
            client_id=public.client_id,
            user_id=user.id,
            redirect_uri=CLAUDE_REDIRECT_URI,
            scopes=[MCP_SCOPE_READ],
            code_challenge=challenge,
            code_challenge_method="S256",
            resource_uri=RESOURCE_URI,
            commit=False,
        )
        plaintext_secrets.append((issued_code.code, "authorization code"))
        if issued_code.grant.code_hash != hash_oauth_secret(issued_code.code):
            fail("Authorization code was not stored as its SHA-256 hash")

        expect_error(
            McpOAuthInvalidGrantError,
            lambda: exchange_authorization_code(
                db,
                code=issued_code.code,
                client_id=public.client_id,
                client_secret=None,
                redirect_uri=LOOPBACK_REDIRECT_URI,
                code_verifier=VERIFIER,
                resource_uri=RESOURCE_URI,
                commit=False,
            ),
            "authorization-code redirect binding",
        )
        expect_error(
            McpOAuthInvalidGrantError,
            lambda: exchange_authorization_code(
                db,
                code=issued_code.code,
                client_id=public.client_id,
                client_secret=None,
                redirect_uri=CLAUDE_REDIRECT_URI,
                code_verifier="wrong-verifier-value-0123456789-ABCDEFGHIJKLMN",
                resource_uri=RESOURCE_URI,
                commit=False,
            ),
            "authorization-code PKCE binding",
        )
        if issued_code.grant.consumed_at is not None:
            fail("Failed exchanges consumed the authorization code")

        first_tokens = exchange_authorization_code(
            db,
            code=issued_code.code,
            client_id=public.client_id,
            client_secret=None,
            redirect_uri=CLAUDE_REDIRECT_URI,
            code_verifier=VERIFIER,
            resource_uri=RESOURCE_URI,
            commit=False,
        )
        plaintext_secrets.append((first_tokens.access_token, "access token"))
        if first_tokens.refresh_token is None:
            fail("Refresh token was not issued")
        plaintext_secrets.append((first_tokens.refresh_token, "refresh token"))
        if first_tokens.token_type != "Bearer" or first_tokens.expires_in != 3600:
            fail("Token response metadata is incorrect")
        if first_tokens.token.access_token_hash != hash_oauth_secret(
            first_tokens.access_token
        ):
            fail("Access token was not stored as its SHA-256 hash")
        if first_tokens.token.refresh_token_hash != hash_oauth_secret(
            first_tokens.refresh_token
        ):
            fail("Refresh token was not stored as its SHA-256 hash")

        expect_error(
            McpOAuthInvalidGrantError,
            lambda: exchange_authorization_code(
                db,
                code=issued_code.code,
                client_id=public.client_id,
                client_secret=None,
                redirect_uri=CLAUDE_REDIRECT_URI,
                code_verifier=VERIFIER,
                resource_uri=RESOURCE_URI,
                commit=False,
            ),
            "authorization-code one-time use",
        )

        principal = validate_access_token(
            db,
            access_token=first_tokens.access_token,
            resource_uri=RESOURCE_URI,
            required_scopes=[MCP_SCOPE_READ],
            commit=False,
        )
        if (
            principal.user_id != user.id
            or principal.client_id != public.client_id
            or principal.client_name != public.client.client_name
            or principal.scopes != frozenset({MCP_SCOPE_READ})
        ):
            fail("Access-token principal is incorrect")
        expect_error(
            McpOAuthInsufficientScopeError,
            lambda: validate_access_token(
                db,
                access_token=first_tokens.access_token,
                resource_uri=RESOURCE_URI,
                required_scopes=[MCP_SCOPE_WRITE],
                touch=False,
                commit=False,
            ),
            "access-token scope enforcement",
        )
        expect_error(
            McpOAuthInvalidTokenError,
            lambda: validate_access_token(
                db,
                access_token=first_tokens.access_token,
                resource_uri="https://other.example/mcp",
                touch=False,
                commit=False,
            ),
            "access-token resource binding",
        )

        set_bool_setting(db, MCP_READ_ENABLED_KEY, False)
        expect_error(
            McpOAuthInvalidTokenError,
            lambda: validate_access_token(
                db,
                access_token=first_tokens.access_token,
                resource_uri=RESOURCE_URI,
                touch=False,
                commit=False,
            ),
            "immediate read-scope disable",
        )
        set_bool_setting(db, MCP_READ_ENABLED_KEY, True)
        set_bool_setting(db, MCP_ENABLED_KEY, False)
        expect_error(
            McpOAuthDisabledError,
            lambda: validate_access_token(
                db,
                access_token=first_tokens.access_token,
                resource_uri=RESOURCE_URI,
                touch=False,
                commit=False,
            ),
            "immediate MCP disable",
        )
        set_bool_setting(db, MCP_ENABLED_KEY, True)

        rotated = rotate_refresh_token(
            db,
            refresh_token=first_tokens.refresh_token,
            client_id=public.client_id,
            client_secret=None,
            resource_uri=RESOURCE_URI,
            commit=False,
        )
        plaintext_secrets.append((rotated.access_token, "rotated access token"))
        if rotated.refresh_token is None:
            fail("Rotated refresh token was not issued")
        plaintext_secrets.append((rotated.refresh_token, "rotated refresh token"))
        if (
            rotated.token.token_family_id
            != first_tokens.token.token_family_id
            or first_tokens.token.replaced_by_token_id != rotated.token.id
            or first_tokens.token.revoked_at is None
        ):
            fail("Refresh-token rotation did not preserve and advance its family")
        expect_error(
            McpOAuthInvalidTokenError,
            lambda: validate_access_token(
                db,
                access_token=first_tokens.access_token,
                resource_uri=RESOURCE_URI,
                touch=False,
                commit=False,
            ),
            "replaced access-token revocation",
        )

        expect_error(
            McpOAuthRefreshReplayError,
            lambda: rotate_refresh_token(
                db,
                refresh_token=first_tokens.refresh_token,
                client_id=public.client_id,
                client_secret=None,
                resource_uri=RESOURCE_URI,
                commit=False,
            ),
            "refresh-token replay detection",
        )
        db.refresh(rotated.token)
        if rotated.token.revoked_at is None:
            fail("Refresh replay did not revoke the replacement token")
        expect_error(
            McpOAuthInvalidTokenError,
            lambda: validate_access_token(
                db,
                access_token=rotated.access_token,
                resource_uri=RESOURCE_URI,
                touch=False,
                commit=False,
            ),
            "refresh-replay family revocation",
        )

        grant_consent(
            db,
            user_id=user.id,
            client_id=confidential.client_id,
            scopes=[MCP_SCOPE_READ],
            commit=False,
        )
        confidential_code = issue_authorization_code(
            db,
            client_id=confidential.client_id,
            user_id=user.id,
            redirect_uri=LOOPBACK_REDIRECT_URI,
            scopes=[MCP_SCOPE_READ],
            code_challenge=challenge,
            code_challenge_method="S256",
            resource_uri=RESOURCE_URI,
            commit=False,
        )
        plaintext_secrets.append(
            (confidential_code.code, "confidential authorization code")
        )
        confidential_tokens = exchange_authorization_code(
            db,
            code=confidential_code.code,
            client_id=confidential.client_id,
            client_secret=confidential.client_secret,
            redirect_uri=LOOPBACK_REDIRECT_URI,
            code_verifier=VERIFIER,
            resource_uri=RESOURCE_URI,
            commit=False,
        )
        plaintext_secrets.append(
            (confidential_tokens.access_token, "confidential access token")
        )
        if not revoke_token(
            db,
            token_value=confidential_tokens.access_token,
            client_id=confidential.client_id,
            client_secret=confidential.client_secret,
            commit=False,
        ):
            fail("Token revocation did not find the confidential access token")
        expect_error(
            McpOAuthInvalidTokenError,
            lambda: validate_access_token(
                db,
                access_token=confidential_tokens.access_token,
                resource_uri=RESOURCE_URI,
                touch=False,
                commit=False,
            ),
            "explicit token revocation",
        )

        if not revoke_consent(
            db,
            user_id=user.id,
            client_id=confidential.client_id,
            commit=False,
        ):
            fail("Consent revocation did not find the confidential consent")
        confidential_consent = db.execute(
            select(McpOAuthConsent).where(
                McpOAuthConsent.client_id == confidential.client.id,
                McpOAuthConsent.user_id == user.id,
            )
        ).scalar_one()
        if confidential_consent.revoked_at is None:
            fail("Consent revocation did not persist its marker")

        grant_consent(
            db,
            user_id=user.id,
            client_id=confidential.client_id,
            scopes=[MCP_SCOPE_READ],
            commit=False,
        )
        pending_code = issue_authorization_code(
            db,
            client_id=confidential.client_id,
            user_id=user.id,
            redirect_uri=LOOPBACK_REDIRECT_URI,
            scopes=[MCP_SCOPE_READ],
            code_challenge=challenge,
            code_challenge_method="S256",
            resource_uri=RESOURCE_URI,
            commit=False,
        )
        if not revoke_client(
            db,
            client_id=confidential.client_id,
            actor_user_id=user.id,
            commit=False,
        ):
            fail("Client revocation did not find the confidential client")
        db.refresh(pending_code.grant)
        if pending_code.grant.consumed_at is None:
            fail("Client revocation did not invalidate pending codes")
        expect_error(
            McpOAuthInvalidClientError,
            lambda: authenticate_client(
                db,
                client_id=confidential.client_id,
                client_secret=confidential.client_secret,
            ),
            "revoked client authentication",
        )

        expected_events = {
            "mcp.oauth_client_registered",
            "mcp.oauth_consent_granted",
            "mcp.oauth_code_issued",
            "mcp.oauth_tokens_issued",
            "mcp.oauth_tokens_refreshed",
            "mcp.oauth_refresh_replay_detected",
            "mcp.oauth_token_revoked",
            "mcp.oauth_consent_revoked",
            "mcp.oauth_client_revoked",
        }
        actual_events = {
            event
            for event in db.execute(
                select(AuditLog.event_type).where(
                    AuditLog.event_type.like("mcp.oauth_%")
                )
            ).scalars()
        }
        missing = expected_events - actual_events
        if missing:
            fail(f"OAuth service audit coverage is incomplete: {sorted(missing)}")

        for secret, label in plaintext_secrets:
            assert_secret_absent(db, secret, label)

    finally:
        db.rollback()
        db.close()

    verification = SessionLocal()
    try:
        if table_counts(verification) != baseline_counts:
            fail(
                "OAuth service smoke did not restore table counts: "
                f"{baseline_counts} -> {table_counts(verification)}"
            )
        if setting_snapshot(verification) != baseline_settings:
            fail("OAuth service smoke did not restore MCP settings exactly")
    finally:
        verification.close()


def main() -> None:
    run_service_lifecycle()
    print(
        "[PASS] MCP OAuth service covers public and confidential clients, "
        "S256 PKCE, exact redirect/resource binding, hashed credentials, "
        "settings-driven scopes, consent, code exchange, access validation, "
        "refresh rotation/replay revocation, token/client revocation, "
        "secret-free audits and exact rollback"
    )


if __name__ == "__main__":
    main()
