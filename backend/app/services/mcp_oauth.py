from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from urllib.parse import urlsplit

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.db.settings import get_bool_setting
from app.models import (
    AuditLog,
    McpOAuthAuthorizationCode,
    McpOAuthClient,
    McpOAuthConsent,
    McpOAuthToken,
    User,
)

from app.schemas.app_settings import (
    McpOAuthClientSummaryResponse,
    McpOAuthClientsResponse,
)


# PARTPILOT:MCP_OAUTH_SERVICE:V466
MCP_ENABLED_KEY = "mcp.enabled"
MCP_READ_ENABLED_KEY = "mcp.read_tools_enabled"
MCP_WRITE_ENABLED_KEY = "mcp.write_tools_enabled"

MCP_SCOPE_READ = "mcp:read"
MCP_SCOPE_WRITE = "mcp:write"
SUPPORTED_SCOPES = frozenset({MCP_SCOPE_READ, MCP_SCOPE_WRITE})

SUPPORTED_CLIENT_AUTH_METHODS = frozenset(
    {"none", "client_secret_post", "client_secret_basic"}
)
SUPPORTED_GRANT_TYPES = frozenset({"authorization_code", "refresh_token"})
SUPPORTED_RESPONSE_TYPES = frozenset({"code"})

AUTHORIZATION_CODE_TTL = timedelta(minutes=5)
ACCESS_TOKEN_TTL = timedelta(hours=1)
REFRESH_TOKEN_TTL = timedelta(days=30)

PKCE_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9\-._~]{43,128}$")
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class McpOAuthError(RuntimeError):
    """Base class for OAuth service failures."""


class McpOAuthDisabledError(McpOAuthError):
    pass


class McpOAuthValidationError(McpOAuthError):
    pass


class McpOAuthInvalidClientError(McpOAuthError):
    pass


class McpOAuthInvalidGrantError(McpOAuthError):
    pass


class McpOAuthInvalidTokenError(McpOAuthError):
    pass


class McpOAuthInsufficientScopeError(McpOAuthError):
    pass


class McpOAuthRefreshReplayError(McpOAuthInvalidGrantError):
    pass


# PARTPILOT:MCP_OAUTH_CLIENT_REVOCATION_SERVICE:V541
class McpOAuthConnectedClientNotFoundError(McpOAuthError):
    pass


@dataclass(frozen=True)
class RegisteredOAuthClient:
    client: McpOAuthClient
    client_id: str
    client_secret: str | None


@dataclass(frozen=True)
class IssuedAuthorizationCode:
    grant: McpOAuthAuthorizationCode
    code: str


@dataclass(frozen=True)
class IssuedOAuthTokens:
    token: McpOAuthToken
    access_token: str
    refresh_token: str | None
    token_type: str
    expires_in: int
    scope: str


@dataclass(frozen=True)
class AccessTokenPrincipal:
    token_id: int
    user_id: int
    client_database_id: int
    client_id: str
    scopes: frozenset[str]
    resource_uri: str


def _naive_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _commit_or_flush(db: Session, *, commit: bool) -> None:
    if commit:
        db.commit()
    else:
        db.flush()


def hash_oauth_secret(secret: str) -> str:
    if not secret:
        raise McpOAuthValidationError("OAuth secret cannot be empty.")
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _generate_opaque(prefix: str, *, bytes_count: int = 32) -> str:
    return prefix + secrets.token_urlsafe(bytes_count)


def generate_client_id() -> str:
    return _generate_opaque("pp_mcp_client_", bytes_count=24)


def generate_client_secret() -> str:
    return _generate_opaque("pp_mcp_secret_")


def generate_authorization_code() -> str:
    return _generate_opaque("pp_mcp_code_")


def generate_access_token() -> str:
    return _generate_opaque("pp_mcp_access_")


def generate_refresh_token() -> str:
    return _generate_opaque("pp_mcp_refresh_")


def generate_token_family_id() -> str:
    return _generate_opaque("pp_mcp_family_", bytes_count=24)


def _normalise_text(value: str, *, label: str, maximum: int) -> str:
    normalised = value.strip()
    if not normalised:
        raise McpOAuthValidationError(f"{label} cannot be empty.")
    if len(normalised) > maximum:
        raise McpOAuthValidationError(
            f"{label} must be {maximum} characters or fewer."
        )
    return normalised


def _validate_absolute_uri(
    value: str,
    *,
    label: str,
    allow_loopback_http: bool,
    allow_query: bool,
) -> str:
    normalised = _normalise_text(value, label=label, maximum=2048)
    parsed = urlsplit(normalised)
    if not parsed.scheme or not parsed.netloc:
        raise McpOAuthValidationError(f"{label} must be an absolute URI.")
    if parsed.username is not None or parsed.password is not None:
        raise McpOAuthValidationError(f"{label} cannot include user information.")
    if parsed.fragment:
        raise McpOAuthValidationError(f"{label} cannot include a fragment.")
    if not allow_query and parsed.query:
        raise McpOAuthValidationError(f"{label} cannot include a query string.")
    scheme = parsed.scheme.casefold()
    host = (parsed.hostname or "").casefold()
    if scheme == "https":
        return normalised
    if allow_loopback_http and scheme == "http" and host in LOOPBACK_HOSTS:
        return normalised
    raise McpOAuthValidationError(
        f"{label} must use HTTPS"
        + (" or loopback HTTP." if allow_loopback_http else ".")
    )


def validate_redirect_uri(value: str) -> str:
    return _validate_absolute_uri(
        value,
        label="Redirect URI",
        allow_loopback_http=True,
        allow_query=True,
    )


def validate_resource_uri(value: str) -> str:
    return _validate_absolute_uri(
        value,
        label="Resource URI",
        allow_loopback_http=False,
        allow_query=False,
    )


def validate_client_uri(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return _validate_absolute_uri(
        value,
        label="Client URI",
        allow_loopback_http=False,
        allow_query=True,
    )


def _normalise_unique_strings(
    values: Iterable[str],
    *,
    label: str,
    allowed: frozenset[str] | None = None,
    minimum: int = 1,
    maximum: int = 20,
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip()
        if not value:
            raise McpOAuthValidationError(f"{label} cannot contain empty values.")
        if value in seen:
            continue
        if allowed is not None and value not in allowed:
            raise McpOAuthValidationError(
                f"Unsupported {label.rstrip('s')}: {value}."
            )
        seen.add(value)
        result.append(value)
    if len(result) < minimum or len(result) > maximum:
        raise McpOAuthValidationError(
            f"{label} must contain between {minimum} and {maximum} values."
        )
    return result


def available_scopes(db: Session, *, require_enabled: bool = True) -> frozenset[str]:
    enabled = get_bool_setting(db, MCP_ENABLED_KEY, False)
    if require_enabled and not enabled:
        raise McpOAuthDisabledError("MCP is disabled.")
    scopes: set[str] = set()
    if get_bool_setting(db, MCP_READ_ENABLED_KEY, True):
        scopes.add(MCP_SCOPE_READ)
    if get_bool_setting(db, MCP_WRITE_ENABLED_KEY, False):
        scopes.add(MCP_SCOPE_WRITE)
    return frozenset(scopes)


def normalise_scopes(
    db: Session,
    scopes: Iterable[str],
    *,
    require_enabled: bool = True,
) -> list[str]:
    requested = _normalise_unique_strings(
        scopes,
        label="Scopes",
        allowed=SUPPORTED_SCOPES,
        maximum=len(SUPPORTED_SCOPES),
    )
    configured = available_scopes(db, require_enabled=require_enabled)
    unavailable = set(requested) - configured
    if unavailable:
        raise McpOAuthInsufficientScopeError(
            "Requested scopes are not currently enabled: "
            + ", ".join(sorted(unavailable))
            + "."
        )
    return sorted(requested)


def _active_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise McpOAuthInvalidGrantError("OAuth user is unavailable.")
    return user


def _active_client_by_identifier(db: Session, client_id: str) -> McpOAuthClient:
    normalised = _normalise_text(client_id, label="Client ID", maximum=160)
    client = db.execute(
        select(McpOAuthClient).where(McpOAuthClient.client_id == normalised)
    ).scalar_one_or_none()
    if client is None or client.revoked_at is not None:
        raise McpOAuthInvalidClientError("Invalid OAuth client.")
    return client


def authenticate_client(
    db: Session,
    *,
    client_id: str,
    client_secret: str | None,
) -> McpOAuthClient:
    client = _active_client_by_identifier(db, client_id)
    method = client.token_endpoint_auth_method
    if method == "none":
        if client.client_secret_hash is not None:
            raise McpOAuthInvalidClientError("Invalid OAuth client.")
        return client
    if method not in SUPPORTED_CLIENT_AUTH_METHODS:
        raise McpOAuthInvalidClientError("Invalid OAuth client.")
    if not client_secret or not client.client_secret_hash:
        raise McpOAuthInvalidClientError("Invalid OAuth client.")
    supplied = hash_oauth_secret(client_secret)
    if not hmac.compare_digest(supplied, client.client_secret_hash):
        raise McpOAuthInvalidClientError("Invalid OAuth client.")
    return client


def _append_audit(
    db: Session,
    *,
    event_type: str,
    entity_type: str,
    entity_id: int | None,
    actor_type: str,
    actor_user_id: int | None,
    summary: str,
    metadata: dict[str, Any],
) -> None:
    db.add(
        AuditLog(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            summary=summary,
            metadata_json=metadata,
        )
    )


def register_client(
    db: Session,
    *,
    client_name: str,
    redirect_uris: Iterable[str],
    grant_types: Iterable[str] = ("authorization_code", "refresh_token"),
    response_types: Iterable[str] = ("code",),
    token_endpoint_auth_method: str = "none",
    client_uri: str | None = None,
    metadata: dict[str, Any] | None = None,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> RegisteredOAuthClient:
    name = _normalise_text(client_name, label="Client name", maximum=200)
    redirect_values = _normalise_unique_strings(
        (validate_redirect_uri(value) for value in redirect_uris),
        label="Redirect URIs",
    )
    grant_values = _normalise_unique_strings(
        grant_types,
        label="Grant types",
        allowed=SUPPORTED_GRANT_TYPES,
    )
    if "authorization_code" not in grant_values:
        raise McpOAuthValidationError(
            "OAuth clients must support authorization_code."
        )
    response_values = _normalise_unique_strings(
        response_types,
        label="Response types",
        allowed=SUPPORTED_RESPONSE_TYPES,
    )
    method = token_endpoint_auth_method.strip()
    if method not in SUPPORTED_CLIENT_AUTH_METHODS:
        raise McpOAuthValidationError(
            f"Unsupported client authentication method: {method}."
        )
    if metadata is not None and not isinstance(metadata, dict):
        raise McpOAuthValidationError("Client metadata must be an object.")

    public_identifier = generate_client_id()
    plaintext_secret = None if method == "none" else generate_client_secret()
    client = McpOAuthClient(
        client_id=public_identifier,
        client_secret_hash=(
            None
            if plaintext_secret is None
            else hash_oauth_secret(plaintext_secret)
        ),
        client_name=name,
        client_uri=validate_client_uri(client_uri),
        redirect_uris_json=redirect_values,
        grant_types_json=grant_values,
        response_types_json=response_values,
        token_endpoint_auth_method=method,
        metadata_json=metadata,
        revoked_at=None,
    )
    db.add(client)
    db.flush()
    _append_audit(
        db,
        event_type="mcp.oauth_client_registered",
        entity_type="mcp_oauth_client",
        entity_id=client.id,
        actor_type="user" if actor_user_id is not None else "system",
        actor_user_id=actor_user_id,
        summary=f"Registered MCP OAuth client {name}.",
        metadata={
            "client_id": public_identifier,
            "authentication_method": method,
            "redirect_uri_count": len(redirect_values),
            "grant_types": grant_values,
        },
    )
    _commit_or_flush(db, commit=commit)
    if commit:
        db.refresh(client)
    return RegisteredOAuthClient(
        client=client,
        client_id=public_identifier,
        client_secret=plaintext_secret,
    )


def get_active_client(db: Session, client_id: str) -> McpOAuthClient:
    return _active_client_by_identifier(db, client_id)


def grant_consent(
    db: Session,
    *,
    user_id: int,
    client_id: str,
    scopes: Iterable[str],
    commit: bool = True,
) -> McpOAuthConsent:
    _active_user(db, user_id)
    client = _active_client_by_identifier(db, client_id)
    approved = normalise_scopes(db, scopes)
    consent = db.execute(
        select(McpOAuthConsent).where(
            McpOAuthConsent.user_id == user_id,
            McpOAuthConsent.client_id == client.id,
        )
    ).scalar_one_or_none()
    if consent is None:
        consent = McpOAuthConsent(
            user_id=user_id,
            client_id=client.id,
            approved_scopes_json=approved,
            revoked_at=None,
        )
        db.add(consent)
    else:
        consent.approved_scopes_json = approved
        consent.revoked_at = None
    db.flush()
    _append_audit(
        db,
        event_type="mcp.oauth_consent_granted",
        entity_type="mcp_oauth_consent",
        entity_id=consent.id,
        actor_type="user",
        actor_user_id=user_id,
        summary=f"Granted MCP OAuth access to {client.client_name}.",
        metadata={"client_id": client.client_id, "scopes": approved},
    )
    _commit_or_flush(db, commit=commit)
    if commit:
        db.refresh(consent)
    return consent


def _active_consent(
    db: Session,
    *,
    user_id: int,
    client: McpOAuthClient,
    scopes: Iterable[str],
) -> McpOAuthConsent:
    consent = db.execute(
        select(McpOAuthConsent).where(
            McpOAuthConsent.user_id == user_id,
            McpOAuthConsent.client_id == client.id,
        )
    ).scalar_one_or_none()
    requested = set(scopes)
    if (
        consent is None
        or consent.revoked_at is not None
        or not requested.issubset(set(consent.approved_scopes_json or []))
    ):
        raise McpOAuthInvalidGrantError(
            "OAuth consent is missing or insufficient."
        )
    return consent


def _validate_pkce_challenge(value: str) -> str:
    challenge = value.strip()
    if not PKCE_VALUE_PATTERN.fullmatch(challenge):
        raise McpOAuthValidationError(
            "PKCE challenge must contain 43 to 128 unreserved characters."
        )
    return challenge


def _validate_pkce_verifier(value: str) -> str:
    verifier = value.strip()
    if not PKCE_VALUE_PATTERN.fullmatch(verifier):
        raise McpOAuthInvalidGrantError("Invalid authorization grant.")
    return verifier


def pkce_s256_challenge(verifier: str) -> str:
    normalised = _validate_pkce_verifier(verifier)
    digest = hashlib.sha256(normalised.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def verify_pkce_s256(verifier: str, expected_challenge: str) -> bool:
    try:
        actual = pkce_s256_challenge(verifier)
    except McpOAuthInvalidGrantError:
        return False
    return hmac.compare_digest(actual, expected_challenge)


def issue_authorization_code(
    db: Session,
    *,
    client_id: str,
    user_id: int,
    redirect_uri: str,
    scopes: Iterable[str],
    code_challenge: str,
    code_challenge_method: str,
    resource_uri: str,
    commit: bool = True,
) -> IssuedAuthorizationCode:
    client = _active_client_by_identifier(db, client_id)
    _active_user(db, user_id)
    if "authorization_code" not in set(client.grant_types_json or []):
        raise McpOAuthInvalidGrantError(
            "Client cannot use authorization_code."
        )
    redirect = validate_redirect_uri(redirect_uri)
    if redirect not in set(client.redirect_uris_json or []):
        raise McpOAuthInvalidGrantError("Redirect URI is not registered.")
    approved_scopes = normalise_scopes(db, scopes)
    _active_consent(
        db,
        user_id=user_id,
        client=client,
        scopes=approved_scopes,
    )
    if code_challenge_method != "S256":
        raise McpOAuthValidationError("Only S256 PKCE is supported.")
    challenge = _validate_pkce_challenge(code_challenge)
    resource = validate_resource_uri(resource_uri)

    plaintext = generate_authorization_code()
    grant = McpOAuthAuthorizationCode(
        code_hash=hash_oauth_secret(plaintext),
        client_id=client.id,
        user_id=user_id,
        redirect_uri=redirect,
        scopes_json=approved_scopes,
        code_challenge=challenge,
        code_challenge_method="S256",
        resource_uri=resource,
        expires_at=_naive_utc_now() + AUTHORIZATION_CODE_TTL,
        consumed_at=None,
    )
    db.add(grant)
    db.flush()
    _append_audit(
        db,
        event_type="mcp.oauth_code_issued",
        entity_type="mcp_oauth_authorization_code",
        entity_id=grant.id,
        actor_type="user",
        actor_user_id=user_id,
        summary=(
            "Issued an MCP OAuth authorization code for "
            f"{client.client_name}."
        ),
        metadata={
            "client_id": client.client_id,
            "scopes": approved_scopes,
            "resource_uri": resource,
        },
    )
    _commit_or_flush(db, commit=commit)
    if commit:
        db.refresh(grant)
    return IssuedAuthorizationCode(grant=grant, code=plaintext)


def _create_token_pair(
    db: Session,
    *,
    client: McpOAuthClient,
    user_id: int,
    scopes: list[str],
    resource_uri: str,
    token_family_id: str | None = None,
) -> IssuedOAuthTokens:
    access_plaintext = generate_access_token()
    refresh_plaintext = (
        generate_refresh_token()
        if "refresh_token" in set(client.grant_types_json or [])
        else None
    )
    now = _naive_utc_now()
    token = McpOAuthToken(
        access_token_hash=hash_oauth_secret(access_plaintext),
        refresh_token_hash=(
            None
            if refresh_plaintext is None
            else hash_oauth_secret(refresh_plaintext)
        ),
        token_family_id=token_family_id or generate_token_family_id(),
        client_id=client.id,
        user_id=user_id,
        scopes_json=list(scopes),
        resource_uri=resource_uri,
        access_expires_at=now + ACCESS_TOKEN_TTL,
        refresh_expires_at=(
            None
            if refresh_plaintext is None
            else now + REFRESH_TOKEN_TTL
        ),
        last_used_at=None,
        revoked_at=None,
        replaced_by_token_id=None,
        replay_detected_at=None,
    )
    db.add(token)
    db.flush()
    return IssuedOAuthTokens(
        token=token,
        access_token=access_plaintext,
        refresh_token=refresh_plaintext,
        token_type="Bearer",
        expires_in=int(ACCESS_TOKEN_TTL.total_seconds()),
        scope=" ".join(scopes),
    )


def exchange_authorization_code(
    db: Session,
    *,
    code: str,
    client_id: str,
    client_secret: str | None,
    redirect_uri: str,
    code_verifier: str,
    resource_uri: str,
    commit: bool = True,
) -> IssuedOAuthTokens:
    client = authenticate_client(
        db,
        client_id=client_id,
        client_secret=client_secret,
    )
    grant = db.execute(
        select(McpOAuthAuthorizationCode).where(
            McpOAuthAuthorizationCode.code_hash == hash_oauth_secret(code)
        )
    ).scalar_one_or_none()
    now = _naive_utc_now()
    if (
        grant is None
        or grant.client_id != client.id
        or grant.consumed_at is not None
        or _to_naive_utc(grant.expires_at) is None
        or _to_naive_utc(grant.expires_at) <= now
    ):
        raise McpOAuthInvalidGrantError("Invalid authorization grant.")
    redirect = validate_redirect_uri(redirect_uri)
    resource = validate_resource_uri(resource_uri)
    if (
        redirect != grant.redirect_uri
        or resource != grant.resource_uri
        or grant.code_challenge_method != "S256"
        or not verify_pkce_s256(code_verifier, grant.code_challenge)
    ):
        raise McpOAuthInvalidGrantError("Invalid authorization grant.")

    _active_user(db, grant.user_id)
    scopes = normalise_scopes(db, grant.scopes_json or [])
    _active_consent(
        db,
        user_id=grant.user_id,
        client=client,
        scopes=scopes,
    )
    grant.consumed_at = now
    issued = _create_token_pair(
        db,
        client=client,
        user_id=grant.user_id,
        scopes=scopes,
        resource_uri=resource,
    )
    _append_audit(
        db,
        event_type="mcp.oauth_tokens_issued",
        entity_type="mcp_oauth_token",
        entity_id=issued.token.id,
        actor_type="user",
        actor_user_id=grant.user_id,
        summary=f"Issued MCP OAuth tokens for {client.client_name}.",
        metadata={
            "client_id": client.client_id,
            "scopes": scopes,
            "resource_uri": resource,
            "refresh_token_issued": issued.refresh_token is not None,
        },
    )
    _commit_or_flush(db, commit=commit)
    if commit:
        db.refresh(issued.token)
    return issued


def _revoke_family(
    db: Session,
    *,
    token_family_id: str,
    now: datetime,
    replay_token_id: int | None = None,
) -> int:
    tokens = list(
        db.execute(
            select(McpOAuthToken).where(
                McpOAuthToken.token_family_id == token_family_id
            )
        ).scalars()
    )
    for token in tokens:
        if token.revoked_at is None:
            token.revoked_at = now
        if replay_token_id is not None and token.id == replay_token_id:
            token.replay_detected_at = now
    db.flush()
    return len(tokens)


def rotate_refresh_token(
    db: Session,
    *,
    refresh_token: str,
    client_id: str,
    client_secret: str | None,
    scopes: Iterable[str] | None = None,
    resource_uri: str | None = None,
    commit: bool = True,
) -> IssuedOAuthTokens:
    client = authenticate_client(
        db,
        client_id=client_id,
        client_secret=client_secret,
    )
    token = db.execute(
        select(McpOAuthToken).where(
            McpOAuthToken.refresh_token_hash
            == hash_oauth_secret(refresh_token)
        )
    ).scalar_one_or_none()
    now = _naive_utc_now()
    if token is None or token.client_id != client.id:
        raise McpOAuthInvalidGrantError("Invalid refresh token.")
    if token.replaced_by_token_id is not None:
        family_size = _revoke_family(
            db,
            token_family_id=token.token_family_id,
            now=now,
            replay_token_id=token.id,
        )
        _append_audit(
            db,
            event_type="mcp.oauth_refresh_replay_detected",
            entity_type="mcp_oauth_token",
            entity_id=token.id,
            actor_type="system",
            actor_user_id=token.user_id,
            summary=(
                "Revoked an MCP OAuth token family for "
                f"{client.client_name}."
            ),
            metadata={
                "client_id": client.client_id,
                "revoked_token_count": family_size,
            },
        )
        _commit_or_flush(db, commit=commit)
        raise McpOAuthRefreshReplayError(
            "Refresh token replay was detected."
        )
    refresh_expires = _to_naive_utc(token.refresh_expires_at)
    if (
        token.revoked_at is not None
        or refresh_expires is None
        or refresh_expires <= now
    ):
        raise McpOAuthInvalidGrantError("Invalid refresh token.")

    _active_user(db, token.user_id)
    requested_scopes = (
        list(token.scopes_json or [])
        if scopes is None
        else normalise_scopes(db, scopes)
    )
    if not set(requested_scopes).issubset(set(token.scopes_json or [])):
        raise McpOAuthInsufficientScopeError(
            "Refresh scopes cannot exceed the original grant."
        )
    requested_scopes = normalise_scopes(db, requested_scopes)
    resource = (
        token.resource_uri
        if resource_uri is None
        else validate_resource_uri(resource_uri)
    )
    if resource != token.resource_uri:
        raise McpOAuthInvalidGrantError(
            "Refresh token resource does not match."
        )
    _active_consent(
        db,
        user_id=token.user_id,
        client=client,
        scopes=requested_scopes,
    )

    issued = _create_token_pair(
        db,
        client=client,
        user_id=token.user_id,
        scopes=requested_scopes,
        resource_uri=resource,
        token_family_id=token.token_family_id,
    )
    token.revoked_at = now
    token.replaced_by_token_id = issued.token.id
    _append_audit(
        db,
        event_type="mcp.oauth_tokens_refreshed",
        entity_type="mcp_oauth_token",
        entity_id=issued.token.id,
        actor_type="system",
        actor_user_id=token.user_id,
        summary=f"Rotated MCP OAuth tokens for {client.client_name}.",
        metadata={
            "client_id": client.client_id,
            "scopes": requested_scopes,
            "resource_uri": resource,
            "replaced_token_id": token.id,
        },
    )
    _commit_or_flush(db, commit=commit)
    if commit:
        db.refresh(issued.token)
    return issued


def validate_access_token(
    db: Session,
    *,
    access_token: str,
    resource_uri: str,
    required_scopes: Iterable[str] = (),
    touch: bool = True,
    commit: bool = True,
) -> AccessTokenPrincipal:
    resource = validate_resource_uri(resource_uri)
    token = db.execute(
        select(McpOAuthToken).where(
            McpOAuthToken.access_token_hash
            == hash_oauth_secret(access_token)
        )
    ).scalar_one_or_none()
    now = _naive_utc_now()
    access_expires = (
        None if token is None else _to_naive_utc(token.access_expires_at)
    )
    if (
        token is None
        or token.revoked_at is not None
        or access_expires is None
        or access_expires <= now
        or token.resource_uri != resource
    ):
        raise McpOAuthInvalidTokenError("Invalid access token.")

    client = db.get(McpOAuthClient, token.client_id)
    user = db.get(User, token.user_id)
    if (
        client is None
        or client.revoked_at is not None
        or user is None
        or not user.is_active
    ):
        raise McpOAuthInvalidTokenError("Invalid access token.")

    token_scopes = frozenset(token.scopes_json or [])
    configured = available_scopes(db)
    if not token_scopes.issubset(configured):
        raise McpOAuthInvalidTokenError(
            "Access token contains disabled scopes."
        )
    required = frozenset(
        _normalise_unique_strings(
            required_scopes,
            label="Required scopes",
            allowed=SUPPORTED_SCOPES,
            minimum=0,
            maximum=len(SUPPORTED_SCOPES),
        )
    )
    if not required.issubset(token_scopes):
        raise McpOAuthInsufficientScopeError(
            "Access token does not provide the required scopes."
        )
    _active_consent(
        db,
        user_id=token.user_id,
        client=client,
        scopes=token_scopes,
    )
    if touch:
        token.last_used_at = now
        _commit_or_flush(db, commit=commit)
    return AccessTokenPrincipal(
        token_id=token.id,
        user_id=token.user_id,
        client_database_id=client.id,
        client_id=client.client_id,
        scopes=token_scopes,
        resource_uri=resource,
    )


def revoke_token(
    db: Session,
    *,
    token_value: str,
    client_id: str,
    client_secret: str | None,
    commit: bool = True,
) -> bool:
    client = authenticate_client(
        db,
        client_id=client_id,
        client_secret=client_secret,
    )
    token_hash = hash_oauth_secret(token_value)
    token = db.execute(
        select(McpOAuthToken).where(
            McpOAuthToken.client_id == client.id,
            or_(
                McpOAuthToken.access_token_hash == token_hash,
                McpOAuthToken.refresh_token_hash == token_hash,
            ),
        )
    ).scalar_one_or_none()
    if token is None:
        return False
    if token.revoked_at is None:
        token.revoked_at = _naive_utc_now()
        _append_audit(
            db,
            event_type="mcp.oauth_token_revoked",
            entity_type="mcp_oauth_token",
            entity_id=token.id,
            actor_type="system",
            actor_user_id=token.user_id,
            summary=f"Revoked an MCP OAuth token for {client.client_name}.",
            metadata={"client_id": client.client_id},
        )
        _commit_or_flush(db, commit=commit)
    return True


def revoke_consent(
    db: Session,
    *,
    user_id: int,
    client_id: str,
    commit: bool = True,
) -> bool:
    client = _active_client_by_identifier(db, client_id)
    consent = db.execute(
        select(McpOAuthConsent).where(
            McpOAuthConsent.user_id == user_id,
            McpOAuthConsent.client_id == client.id,
        )
    ).scalar_one_or_none()
    if consent is None:
        return False
    now = _naive_utc_now()
    changed = consent.revoked_at is None
    consent.revoked_at = consent.revoked_at or now
    db.execute(
        update(McpOAuthAuthorizationCode)
        .where(
            McpOAuthAuthorizationCode.user_id == user_id,
            McpOAuthAuthorizationCode.client_id == client.id,
            McpOAuthAuthorizationCode.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    db.execute(
        update(McpOAuthToken)
        .where(
            McpOAuthToken.user_id == user_id,
            McpOAuthToken.client_id == client.id,
            McpOAuthToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    if changed:
        _append_audit(
            db,
            event_type="mcp.oauth_consent_revoked",
            entity_type="mcp_oauth_consent",
            entity_id=consent.id,
            actor_type="user",
            actor_user_id=user_id,
            summary=f"Revoked MCP OAuth access for {client.client_name}.",
            metadata={"client_id": client.client_id},
        )
    _commit_or_flush(db, commit=commit)
    return True


def revoke_client(
    db: Session,
    *,
    client_id: str,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> bool:
    client = db.execute(
        select(McpOAuthClient).where(
            McpOAuthClient.client_id == client_id.strip()
        )
    ).scalar_one_or_none()
    if client is None:
        return False
    now = _naive_utc_now()
    changed = client.revoked_at is None
    client.revoked_at = client.revoked_at or now
    db.execute(
        update(McpOAuthAuthorizationCode)
        .where(
            McpOAuthAuthorizationCode.client_id == client.id,
            McpOAuthAuthorizationCode.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    db.execute(
        update(McpOAuthToken)
        .where(
            McpOAuthToken.client_id == client.id,
            McpOAuthToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    db.execute(
        update(McpOAuthConsent)
        .where(
            McpOAuthConsent.client_id == client.id,
            McpOAuthConsent.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    if changed:
        _append_audit(
            db,
            event_type="mcp.oauth_client_revoked",
            entity_type="mcp_oauth_client",
            entity_id=client.id,
            actor_type="user" if actor_user_id is not None else "system",
            actor_user_id=actor_user_id,
            summary=f"Revoked MCP OAuth client {client.client_name}.",
            metadata={"client_id": client.client_id},
        )
    _commit_or_flush(db, commit=commit)
    return True

# PARTPILOT:MCP_OAUTH_CLIENT_ADMIN_SERVICE:V540
def _oauth_redirect_origins(redirect_uris: Iterable[str]) -> list[str]:
    origins: list[str] = []
    for redirect_uri in redirect_uris:
        parsed = urlsplit(str(redirect_uri))
        if not parsed.scheme or not parsed.netloc:
            continue
        origin = f"{parsed.scheme.casefold()}://{parsed.netloc.casefold()}"
        if origin not in origins:
            origins.append(origin)
    return origins


def _oauth_token_session_is_active(
    token: McpOAuthToken,
    *,
    now: datetime,
) -> bool:
    if token.revoked_at is not None:
        return False
    access_expires_at = _to_naive_utc(token.access_expires_at)
    refresh_expires_at = _to_naive_utc(token.refresh_expires_at)
    return bool(
        (access_expires_at is not None and access_expires_at > now)
        or (refresh_expires_at is not None and refresh_expires_at > now)
    )


def list_connected_oauth_clients(
    db: Session,
    *,
    user_id: int,
) -> McpOAuthClientsResponse:
    now = _naive_utc_now()
    clients = list(
        db.execute(
            select(McpOAuthClient)
            .where(McpOAuthClient.revoked_at.is_(None))
            .order_by(McpOAuthClient.created_at.asc(), McpOAuthClient.id.asc())
        ).scalars()
    )
    summaries: list[McpOAuthClientSummaryResponse] = []

    for client in clients:
        active_consents = list(
            db.execute(
                select(McpOAuthConsent).where(
                    McpOAuthConsent.client_id == client.id,
                    McpOAuthConsent.user_id == user_id,
                    McpOAuthConsent.revoked_at.is_(None),
                )
            ).scalars()
        )
        if not active_consents:
            continue

        tokens = list(
            db.execute(
                select(McpOAuthToken)
                .where(
                    McpOAuthToken.client_id == client.id,
                    McpOAuthToken.user_id == user_id,
                )
                .order_by(McpOAuthToken.created_at.asc(), McpOAuthToken.id.asc())
            ).scalars()
        )
        active_tokens = [
            token
            for token in tokens
            if _oauth_token_session_is_active(token, now=now)
        ]
        if not active_tokens:
            continue

        authorization_code_count = len(
            list(
                db.execute(
                    select(McpOAuthAuthorizationCode.id).where(
                        McpOAuthAuthorizationCode.client_id == client.id,
                        McpOAuthAuthorizationCode.user_id == user_id,
                    )
                ).scalars()
            )
        )
        scopes = sorted(
            {
                str(scope)
                for token in active_tokens
                for scope in (token.scopes_json or [])
            }
        )
        connected_at = min(
            _to_naive_utc(token.created_at) or token.created_at
            for token in tokens
        )
        last_used_values = [
            value
            for value in (
                _to_naive_utc(token.last_used_at)
                for token in tokens
            )
            if value is not None
        ]
        token_families = {
            str(token.token_family_id)
            for token in active_tokens
        }
        auth_method = str(client.token_endpoint_auth_method)

        summaries.append(
            McpOAuthClientSummaryResponse(
                database_id=client.id,
                client_id=client.client_id,
                client_name=client.client_name,
                status="connected",
                client_type=(
                    "public" if auth_method == "none" else "confidential"
                ),
                token_endpoint_auth_method=auth_method,
                redirect_origins=_oauth_redirect_origins(
                    client.redirect_uris_json or []
                ),
                scopes=scopes,
                created_at=client.created_at,
                connected_at=connected_at,
                last_used_at=(max(last_used_values) if last_used_values else None),
                active_token_count=len(active_tokens),
                token_family_count=len(token_families),
                total_token_count=len(tokens),
                authorization_code_count=authorization_code_count,
                active_consent_count=len(active_consents),
            )
        )

    return McpOAuthClientsResponse(
        clients=summaries,
        total=len(summaries),
    )


# PARTPILOT:MCP_OAUTH_CLIENT_REVOCATION_SERVICE:V541
def revoke_connected_oauth_client(
    db: Session,
    *,
    user_id: int,
    client_database_id: int,
    commit: bool = True,
) -> McpOAuthClientsResponse:
    now = _naive_utc_now()
    client = db.get(McpOAuthClient, client_database_id)
    if client is None or client.revoked_at is not None:
        raise McpOAuthConnectedClientNotFoundError(
            "Connected OAuth client was not found."
        )

    consent = db.execute(
        select(McpOAuthConsent).where(
            McpOAuthConsent.client_id == client.id,
            McpOAuthConsent.user_id == user_id,
            McpOAuthConsent.revoked_at.is_(None),
        )
    ).scalar_one_or_none()
    tokens = list(
        db.execute(
            select(McpOAuthToken).where(
                McpOAuthToken.client_id == client.id,
                McpOAuthToken.user_id == user_id,
            )
        ).scalars()
    )
    if consent is None or not any(
        _oauth_token_session_is_active(token, now=now)
        for token in tokens
    ):
        raise McpOAuthConnectedClientNotFoundError(
            "Connected OAuth client was not found."
        )

    if not revoke_client(
        db,
        client_id=client.client_id,
        actor_user_id=user_id,
        commit=False,
    ):
        raise McpOAuthConnectedClientNotFoundError(
            "Connected OAuth client was not found."
        )
    _commit_or_flush(db, commit=commit)
    return list_connected_oauth_clients(db, user_id=user_id)
