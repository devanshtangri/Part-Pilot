from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import secrets
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ApiKey, AuditLog, User


# PARTPILOT:REST_API_KEY_SERVICE:V615
API_KEY_PREFIX = "pp_api_key_"
API_KEY_VISIBLE_PREFIX_LENGTH = 24
AVAILABLE_API_KEY_SCOPES = (
    "inventory:read",
    "inventory:write",
    "catalogues:read",
    "catalogues:write",
    "projects:read",
    "projects:write",
    "reservations:read",
    "reservations:write",
    "history:read",
)
_SCOPE_ORDER = {scope: index for index, scope in enumerate(AVAILABLE_API_KEY_SCOPES)}


class ApiKeyError(RuntimeError):
    pass


class ApiKeyValidationError(ApiKeyError):
    pass


class ApiKeyNotFoundError(ApiKeyError):
    pass


class ApiKeyStateError(ApiKeyError):
    pass


class ApiKeyAuthenticationError(ApiKeyError):
    pass


class ApiKeyScopeError(ApiKeyError):
    pass


@dataclass(frozen=True)
class IssuedApiKey:
    record: ApiKey
    plaintext_key: str


@dataclass(frozen=True)
class ValidatedApiKey:
    record: ApiKey
    user: User


def _naive_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_expiry(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ApiKeyValidationError("API key expiry must include a timezone.")
    normalized = value.astimezone(timezone.utc).replace(tzinfo=None)
    if normalized <= _naive_utc_now():
        raise ApiKeyValidationError("API key expiry must be in the future.")
    return normalized


def normalize_api_key_name(value: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ApiKeyValidationError("API key name cannot be empty.")
    if len(normalized) > 120:
        raise ApiKeyValidationError("API key name cannot exceed 120 characters.")
    return normalized


def normalize_api_key_scopes(
    values: Iterable[str],
    *,
    require_one: bool = True,
) -> list[str]:
    normalized: set[str] = set()
    for raw in values:
        if not isinstance(raw, str):
            raise ApiKeyValidationError("API key scopes must be strings.")
        scope = raw.strip()
        if scope not in _SCOPE_ORDER:
            raise ApiKeyValidationError(f"Unsupported API key scope: {scope or raw!r}.")
        normalized.add(scope)
    if require_one and not normalized:
        raise ApiKeyValidationError("At least one API key scope is required.")
    return sorted(normalized, key=_SCOPE_ORDER.__getitem__)


def generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(plaintext_key: str) -> str:
    if (
        not isinstance(plaintext_key, str)
        or not plaintext_key.startswith(API_KEY_PREFIX)
        or len(plaintext_key) <= len(API_KEY_PREFIX)
    ):
        raise ApiKeyAuthenticationError("Invalid API key.")
    return hashlib.sha256(plaintext_key.encode("utf-8")).hexdigest()


def _key_prefix(plaintext_key: str) -> str:
    return plaintext_key[:API_KEY_VISIBLE_PREFIX_LENGTH]


def _active_user(db: Session, user_id: int) -> User:
    user = db.execute(
        select(User).where(User.id == user_id, User.is_active.is_(True))
    ).scalar_one_or_none()
    if user is None:
        raise ApiKeyValidationError("An active user is required to manage API keys.")
    return user


def _owned_key(db: Session, *, user_id: int, key_id: int) -> ApiKey:
    record = db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id)
    ).scalar_one_or_none()
    if record is None:
        raise ApiKeyNotFoundError("API key was not found.")
    return record


def scopes_for_api_key(record: ApiKey) -> list[str]:
    raw = record.scopes_json
    if not isinstance(raw, list):
        raise ApiKeyValidationError("Stored API key scopes are invalid.")
    return normalize_api_key_scopes(raw)


def api_key_status(record: ApiKey, *, now: datetime | None = None) -> str:
    current = now or _naive_utc_now()
    if record.revoked_at is not None:
        return "revoked"
    if record.expires_at is not None and record.expires_at <= current:
        return "expired"
    return "active"


def masked_api_key(record: ApiKey) -> str:
    return f"{record.key_prefix}••••••••"


def _snapshot(record: ApiKey) -> dict[str, object]:
    return {
        "name": record.name,
        "key_prefix": record.key_prefix,
        "scopes": scopes_for_api_key(record),
        "status": api_key_status(record),
        "expires_at": None if record.expires_at is None else record.expires_at.isoformat(),
        "rotated_at": None if record.rotated_at is None else record.rotated_at.isoformat(),
        "last_used_at": None if record.last_used_at is None else record.last_used_at.isoformat(),
        "revoked_at": None if record.revoked_at is None else record.revoked_at.isoformat(),
    }


def _audit(
    db: Session,
    *,
    record: ApiKey,
    actor_user_id: int,
    event_type: str,
    summary: str,
    before: dict[str, object] | None,
    after: dict[str, object] | None,
) -> None:
    db.add(
        AuditLog(
            event_type=event_type,
            entity_type="api_key",
            entity_id=record.id,
            actor_type="user",
            actor_user_id=actor_user_id,
            summary=summary,
            before_json=before,
            after_json=after,
            metadata_json={"secret_material": "redacted"},
        )
    )


def _commit_record(db: Session, record: ApiKey, *, commit: bool) -> ApiKey:
    if commit:
        db.commit()
        db.refresh(record)
    else:
        db.flush()
    return record


def create_api_key(
    db: Session,
    *,
    actor_user_id: int,
    name: str,
    scopes: Iterable[str],
    expires_at: datetime | None = None,
    commit: bool = True,
) -> IssuedApiKey:
    user = _active_user(db, actor_user_id)
    normalized_name = normalize_api_key_name(name)
    normalized_scopes = normalize_api_key_scopes(scopes)
    normalized_expiry = _normalize_expiry(expires_at)
    plaintext = generate_api_key()
    record = ApiKey(
        user_id=user.id,
        name=normalized_name,
        key_digest=hash_api_key(plaintext),
        key_prefix=_key_prefix(plaintext),
        scopes_json=normalized_scopes,
        expires_at=normalized_expiry,
    )
    try:
        db.add(record)
        db.flush()
        _audit(
            db,
            record=record,
            actor_user_id=user.id,
            event_type="settings.api_key_created",
            summary=f"Created REST API key {normalized_name}.",
            before=None,
            after=_snapshot(record),
        )
        _commit_record(db, record, commit=commit)
    except Exception:
        if commit:
            db.rollback()
        raise
    return IssuedApiKey(record=record, plaintext_key=plaintext)


def list_api_keys(db: Session, *, user_id: int) -> list[ApiKey]:
    _active_user(db, user_id)
    return list(
        db.execute(
            select(ApiKey)
            .where(ApiKey.user_id == user_id)
            .order_by(ApiKey.created_at.desc(), ApiKey.id.desc())
        ).scalars()
    )


def update_api_key(
    db: Session,
    *,
    actor_user_id: int,
    key_id: int,
    name: str,
    scopes: Iterable[str],
    expires_at: datetime | None,
    commit: bool = True,
) -> ApiKey:
    _active_user(db, actor_user_id)
    record = _owned_key(db, user_id=actor_user_id, key_id=key_id)
    if record.revoked_at is not None:
        raise ApiKeyStateError("Revoked API keys cannot be edited.")
    normalized_name = normalize_api_key_name(name)
    normalized_scopes = normalize_api_key_scopes(scopes)
    normalized_expiry = _normalize_expiry(expires_at)
    before = _snapshot(record)
    changed = (
        record.name != normalized_name
        or scopes_for_api_key(record) != normalized_scopes
        or record.expires_at != normalized_expiry
    )
    if not changed:
        return record
    record.name = normalized_name
    record.scopes_json = normalized_scopes
    record.expires_at = normalized_expiry
    try:
        db.flush()
        _audit(
            db,
            record=record,
            actor_user_id=actor_user_id,
            event_type="settings.api_key_updated",
            summary=f"Updated REST API key {normalized_name}.",
            before=before,
            after=_snapshot(record),
        )
        return _commit_record(db, record, commit=commit)
    except Exception:
        if commit:
            db.rollback()
        raise


def rotate_api_key(
    db: Session,
    *,
    actor_user_id: int,
    key_id: int,
    commit: bool = True,
) -> IssuedApiKey:
    _active_user(db, actor_user_id)
    record = _owned_key(db, user_id=actor_user_id, key_id=key_id)
    if api_key_status(record) != "active":
        raise ApiKeyStateError("Only active API keys can be rotated.")
    before = _snapshot(record)
    plaintext = generate_api_key()
    now = _naive_utc_now()
    record.key_digest = hash_api_key(plaintext)
    record.key_prefix = _key_prefix(plaintext)
    record.rotated_at = now
    record.last_used_at = None
    try:
        db.flush()
        _audit(
            db,
            record=record,
            actor_user_id=actor_user_id,
            event_type="settings.api_key_rotated",
            summary=f"Rotated REST API key {record.name}.",
            before=before,
            after=_snapshot(record),
        )
        _commit_record(db, record, commit=commit)
    except Exception:
        if commit:
            db.rollback()
        raise
    return IssuedApiKey(record=record, plaintext_key=plaintext)


def revoke_api_key(
    db: Session,
    *,
    actor_user_id: int,
    key_id: int,
    commit: bool = True,
) -> ApiKey:
    _active_user(db, actor_user_id)
    record = _owned_key(db, user_id=actor_user_id, key_id=key_id)
    if record.revoked_at is not None:
        return record
    before = _snapshot(record)
    record.revoked_at = _naive_utc_now()
    try:
        db.flush()
        _audit(
            db,
            record=record,
            actor_user_id=actor_user_id,
            event_type="settings.api_key_revoked",
            summary=f"Revoked REST API key {record.name}.",
            before=before,
            after=_snapshot(record),
        )
        return _commit_record(db, record, commit=commit)
    except Exception:
        if commit:
            db.rollback()
        raise


def validate_api_key(
    db: Session,
    plaintext_key: str,
    *,
    required_scopes: Iterable[str] = (),
    touch_last_used: bool = True,
    commit: bool = True,
) -> ValidatedApiKey:
    digest = hash_api_key(plaintext_key)
    row = db.execute(
        select(ApiKey, User)
        .join(User, User.id == ApiKey.user_id)
        .where(ApiKey.key_digest == digest)
    ).one_or_none()
    if row is None:
        raise ApiKeyAuthenticationError("Invalid API key.")
    record, user = row
    if not user.is_active or api_key_status(record) != "active":
        raise ApiKeyAuthenticationError("Invalid API key.")
    try:
        granted = set(scopes_for_api_key(record))
        required = set(normalize_api_key_scopes(required_scopes, require_one=False))
    except ApiKeyValidationError as exc:
        raise ApiKeyAuthenticationError("Invalid API key.") from exc
    if required - granted:
        raise ApiKeyScopeError("API key does not grant the required scope.")
    if touch_last_used:
        record.last_used_at = _naive_utc_now()
        if commit:
            db.commit()
            db.refresh(record)
        else:
            db.flush()
    return ValidatedApiKey(record=record, user=user)
