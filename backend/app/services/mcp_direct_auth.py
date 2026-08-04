from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
from pathlib import Path
import secrets

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AuditLog, McpDirectAuth, User


# PARTPILOT:MCP_DIRECT_AUTH_SERVICE:V482
DIRECT_AUTH_SINGLETON_ID = 1
DIRECT_AUTH_DISABLED = "disabled"
DIRECT_AUTH_BEARER_KEY = "bearer_key"
DIRECT_KEY_PREFIX = "pp_mcp_key_"
LAST_USED_TOUCH_INTERVAL = timedelta(minutes=5)
INSTANCE_SECRET_MIN_LENGTH = 32


class McpDirectAuthError(RuntimeError):
    pass


class McpDirectAuthConfigurationError(McpDirectAuthError):
    pass


class McpDirectAuthNotConfiguredError(McpDirectAuthError):
    pass


class McpDirectAuthDecryptionError(McpDirectAuthError):
    pass


@dataclass(frozen=True)
class IssuedMcpDirectKey:
    record: McpDirectAuth
    plaintext_key: str


def _naive_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _validate_instance_secret(value: str) -> str:
    if len(value) < INSTANCE_SECRET_MIN_LENGTH:
        raise McpDirectAuthConfigurationError(
            "The Part Pilot instance secret must contain at least 32 characters."
        )
    return value


def _instance_secret(
    explicit: str | None = None,
    *,
    create: bool = False,
) -> str:
    if explicit is not None:
        return _validate_instance_secret(explicit)
    settings = get_settings()
    if settings.instance_secret is not None:
        return _validate_instance_secret(settings.instance_secret)
    path = Path(settings.instance_secret_file)
    if path.is_symlink():
        raise McpDirectAuthConfigurationError(
            "The Part Pilot instance-secret path is unsafe."
        )
    try:
        value = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        if not create:
            raise McpDirectAuthConfigurationError(
                "The Part Pilot instance secret is not configured."
            )
        if not path.parent.is_dir() or path.parent.is_symlink():
            raise McpDirectAuthConfigurationError(
                "The Part Pilot instance-secret directory is unavailable."
            )
        value = secrets.token_urlsafe(48)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            value = path.read_text(encoding="utf-8").strip()
        else:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(value + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(path, 0o600)
    except OSError as exc:
        raise McpDirectAuthConfigurationError(
            "The Part Pilot instance secret could not be read."
        ) from exc
    if path.is_symlink() or not path.is_file():
        raise McpDirectAuthConfigurationError(
            "The Part Pilot instance-secret path is unsafe."
        )
    return _validate_instance_secret(value)


def _derive(secret: str, purpose: bytes) -> bytes:
    return hmac.new(
        secret.encode("utf-8"),
        b"partpilot:mcp-direct-auth:v1:" + purpose,
        hashlib.sha256,
    ).digest()


def _fernet(secret: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_derive(secret, b"encryption")))


def generate_bearer_key() -> str:
    return DIRECT_KEY_PREFIX + secrets.token_urlsafe(32)


def digest_bearer_key(plaintext_key: str, *, instance_secret: str | None = None) -> str:
    secret = _instance_secret(instance_secret)
    return hmac.new(
        _derive(secret, b"validation"),
        plaintext_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def encrypt_bearer_key(plaintext_key: str, *, instance_secret: str | None = None) -> str:
    if not plaintext_key.startswith(DIRECT_KEY_PREFIX):
        raise McpDirectAuthConfigurationError("MCP direct keys must use the Part Pilot key prefix.")
    return _fernet(_instance_secret(instance_secret)).encrypt(
        plaintext_key.encode("utf-8")
    ).decode("ascii")


def decrypt_bearer_key(ciphertext: str, *, instance_secret: str | None = None) -> str:
    try:
        plaintext = _fernet(_instance_secret(instance_secret)).decrypt(
            ciphertext.encode("ascii")
        ).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise McpDirectAuthDecryptionError(
            "Unable to decrypt the configured MCP direct key."
        ) from exc
    if not plaintext.startswith(DIRECT_KEY_PREFIX):
        raise McpDirectAuthDecryptionError("The configured MCP direct key has an invalid prefix.")
    return plaintext


def get_direct_auth(db: Session) -> McpDirectAuth | None:
    return db.get(McpDirectAuth, DIRECT_AUTH_SINGLETON_ID)


def _active_actor(db: Session, actor_user_id: int) -> User:
    actor = db.execute(
        select(User).where(User.id == actor_user_id, User.is_active.is_(True))
    ).scalar_one_or_none()
    if actor is None:
        raise McpDirectAuthConfigurationError(
            "An active user is required to change MCP direct authentication."
        )
    return actor


def _audit(
    db: Session,
    *,
    event_type: str,
    actor_user_id: int,
    summary: str,
    before: dict[str, object] | None,
    after: dict[str, object] | None,
) -> None:
    db.add(
        AuditLog(
            event_type=event_type,
            entity_type="mcp_direct_auth",
            entity_id=DIRECT_AUTH_SINGLETON_ID,
            actor_type="user",
            actor_user_id=actor_user_id,
            summary=summary,
            before_json=before,
            after_json=after,
            metadata_json={"secret_material": "redacted"},
        )
    )


def rotate_bearer_key(
    db: Session,
    *,
    actor_user_id: int,
    instance_secret: str | None = None,
    commit: bool = True,
) -> IssuedMcpDirectKey:
    _active_actor(db, actor_user_id)
    secret = _instance_secret(instance_secret, create=True)
    plaintext = generate_bearer_key()
    ciphertext = encrypt_bearer_key(plaintext, instance_secret=secret)
    digest = digest_bearer_key(plaintext, instance_secret=secret)
    prefix = plaintext[:20]
    now = _naive_utc_now()
    record = get_direct_auth(db)
    before = None
    if record is None:
        record = McpDirectAuth(
            id=DIRECT_AUTH_SINGLETON_ID,
            mode=DIRECT_AUTH_BEARER_KEY,
            key_ciphertext=ciphertext,
            key_digest=digest,
            key_prefix=prefix,
            custom_header_name=None,
            rotated_at=now,
            last_used_at=None,
        )
        db.add(record)
    else:
        before = {
            "mode": record.mode,
            "key_prefix": record.key_prefix,
            "rotated_at": None if record.rotated_at is None else record.rotated_at.isoformat(),
        }
        record.mode = DIRECT_AUTH_BEARER_KEY
        record.key_ciphertext = ciphertext
        record.key_digest = digest
        record.key_prefix = prefix
        record.custom_header_name = None
        record.rotated_at = now
        record.last_used_at = None
    db.flush()
    _audit(
        db,
        event_type="settings.mcp_direct_key_rotated",
        actor_user_id=actor_user_id,
        summary="Rotated the MCP direct Bearer key.",
        before=before,
        after={"mode": DIRECT_AUTH_BEARER_KEY, "key_prefix": prefix, "rotated_at": now.isoformat()},
    )
    if commit:
        db.commit()
        db.refresh(record)
    else:
        db.flush()
    return IssuedMcpDirectKey(record=record, plaintext_key=plaintext)


def reveal_bearer_key(
    db: Session,
    *,
    instance_secret: str | None = None,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> str:
    if actor_user_id is not None:
        _active_actor(db, actor_user_id)
    record = get_direct_auth(db)
    if (
        record is None
        or record.mode != DIRECT_AUTH_BEARER_KEY
        or not record.key_ciphertext
        or not record.key_digest
    ):
        raise McpDirectAuthNotConfiguredError(
            "An MCP direct Bearer key is not configured."
        )
    plaintext = decrypt_bearer_key(record.key_ciphertext, instance_secret=instance_secret)
    expected = digest_bearer_key(plaintext, instance_secret=instance_secret)
    if not hmac.compare_digest(expected, record.key_digest):
        raise McpDirectAuthDecryptionError(
            "The configured MCP direct key failed integrity validation."
        )
    if actor_user_id is not None:
        _audit(
            db,
            event_type="settings.mcp_direct_key_revealed",
            actor_user_id=actor_user_id,
            summary="Revealed the MCP direct Bearer key.",
            before=None,
            after={"mode": DIRECT_AUTH_BEARER_KEY},
        )
        if commit:
            db.commit()
        else:
            db.flush()
    return plaintext


def validate_bearer_key(
    db: Session,
    supplied_key: str,
    *,
    instance_secret: str | None = None,
    touch: bool = True,
    commit: bool = True,
) -> bool:
    if not supplied_key.startswith(DIRECT_KEY_PREFIX):
        return False
    record = get_direct_auth(db)
    if record is None or record.mode != DIRECT_AUTH_BEARER_KEY or not record.key_digest:
        return False
    supplied_digest = digest_bearer_key(supplied_key, instance_secret=instance_secret)
    if not hmac.compare_digest(supplied_digest, record.key_digest):
        return False
    now = _naive_utc_now()
    should_touch = touch and (
        record.last_used_at is None
        or record.last_used_at <= now - LAST_USED_TOUCH_INTERVAL
    )
    if should_touch:
        record.last_used_at = now
        if commit:
            db.commit()
        else:
            db.flush()
    return True


def disable_direct_auth(db: Session, *, actor_user_id: int, commit: bool = True) -> bool:
    _active_actor(db, actor_user_id)
    record = get_direct_auth(db)
    if record is None:
        return False
    if (
        record.mode == DIRECT_AUTH_DISABLED
        and record.key_ciphertext is None
        and record.key_digest is None
        and record.key_prefix is None
        and record.custom_header_name is None
    ):
        return False
    before = {
        "mode": record.mode,
        "key_prefix": record.key_prefix,
        "rotated_at": None if record.rotated_at is None else record.rotated_at.isoformat(),
    }
    record.mode = DIRECT_AUTH_DISABLED
    record.key_ciphertext = None
    record.key_digest = None
    record.key_prefix = None
    record.custom_header_name = None
    record.rotated_at = None
    record.last_used_at = None
    _audit(
        db,
        event_type="settings.mcp_direct_auth_disabled",
        actor_user_id=actor_user_id,
        summary="Disabled MCP direct authentication.",
        before=before,
        after={"mode": DIRECT_AUTH_DISABLED},
    )
    if commit:
        db.commit()
    else:
        db.flush()
    return True
