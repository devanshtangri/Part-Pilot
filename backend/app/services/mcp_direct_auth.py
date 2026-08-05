from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
from collections.abc import Sequence
import secrets

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AuditLog, McpDirectAuth, User


# PARTPILOT:MCP_DIRECT_AUTH_SERVICE:V509
DIRECT_AUTH_SINGLETON_ID = 1
DIRECT_AUTH_DISABLED = "disabled"
DIRECT_AUTH_BEARER_KEY = "bearer_key"
DIRECT_AUTH_CUSTOM_HEADER = "custom_header"
DIRECT_AUTH_TRUSTED_NETWORK = "trusted_network"
DIRECT_KEY_PREFIX = "pp_mcp_key_"
CUSTOM_HEADER_KEY_PREFIX = "pp_mcp_header_"
DEFAULT_CUSTOM_HEADER_NAME = "x-partpilot-mcp-key"
LAST_USED_TOUCH_INTERVAL = timedelta(minutes=5)
INSTANCE_SECRET_MIN_LENGTH = 32
CUSTOM_HEADER_NAME_MAX_LENGTH = 120
TRUSTED_NETWORK_MAX_ITEMS = 64
_CUSTOM_HEADER_NAME_PATTERN = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
_RESERVED_CUSTOM_HEADER_NAMES = frozenset(
    {
        "authorization",
        "connection",
        "content-length",
        "cookie",
        "forwarded",
        "host",
        "origin",
        "proxy-authorization",
        "set-cookie",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "x-real-ip",
    }
)


class McpDirectAuthError(RuntimeError):
    pass


class McpDirectAuthConfigurationError(McpDirectAuthError):
    pass


class McpDirectAuthHeaderNameError(McpDirectAuthConfigurationError):
    pass


class McpDirectAuthNetworkError(McpDirectAuthConfigurationError):
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


def validate_custom_header_name(value: str) -> str:
    if not isinstance(value, str):
        raise McpDirectAuthHeaderNameError(
            "The MCP custom header name must be text."
        )
    canonical = value.strip().casefold()
    if not canonical:
        raise McpDirectAuthHeaderNameError(
            "The MCP custom header name is required."
        )
    if len(canonical) > CUSTOM_HEADER_NAME_MAX_LENGTH:
        raise McpDirectAuthHeaderNameError(
            "The MCP custom header name is too long."
        )
    if _CUSTOM_HEADER_NAME_PATTERN.fullmatch(canonical) is None:
        raise McpDirectAuthHeaderNameError(
            "The MCP custom header name contains invalid characters."
        )
    if (
        canonical in _RESERVED_CUSTOM_HEADER_NAMES
        or canonical.startswith("x-forwarded-")
    ):
        raise McpDirectAuthHeaderNameError(
            "That HTTP header name is reserved and cannot carry an MCP credential."
        )
    return canonical


def normalize_trusted_networks(values: Sequence[str]) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise McpDirectAuthNetworkError(
            "Trusted networks must be supplied as a list of CIDRs."
        )
    raw_values = list(values)
    if not raw_values:
        raise McpDirectAuthNetworkError(
            "At least one trusted-network CIDR is required."
        )
    if len(raw_values) > TRUSTED_NETWORK_MAX_ITEMS:
        raise McpDirectAuthNetworkError(
            f"No more than {TRUSTED_NETWORK_MAX_ITEMS} trusted networks are allowed."
        )
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for raw in raw_values:
        if not isinstance(raw, str) or not raw.strip():
            raise McpDirectAuthNetworkError(
                "Each trusted network must be a non-empty IPv4 or IPv6 CIDR."
            )
        try:
            network = ipaddress.ip_network(raw.strip(), strict=False)
        except ValueError as exc:
            raise McpDirectAuthNetworkError(
                f"Invalid trusted-network CIDR: {raw!r}."
            ) from exc
        if (
            network.prefixlen == 0
            or network.is_multicast
            or network.network_address.is_unspecified
        ):
            raise McpDirectAuthNetworkError(
                f"Unsafe trusted-network CIDR: {raw!r}."
            )
        for existing in networks:
            if network.version == existing.version and network.overlaps(existing):
                raise McpDirectAuthNetworkError(
                    f"Trusted-network CIDRs overlap: {existing} and {network}."
                )
        networks.append(network)
    networks.sort(
        key=lambda value: (value.version, int(value.network_address), value.prefixlen)
    )
    return [str(value) for value in networks]


def _trusted_networks_from_json(value: str | None) -> list[str]:
    if value is None:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise McpDirectAuthConfigurationError(
            "The stored MCP trusted-network configuration is invalid."
        ) from exc
    if not isinstance(parsed, list):
        raise McpDirectAuthConfigurationError(
            "The stored MCP trusted-network configuration is invalid."
        )
    return normalize_trusted_networks(parsed)


def trusted_networks_for_record(record: McpDirectAuth | None) -> list[str]:
    if record is None or record.mode != DIRECT_AUTH_TRUSTED_NETWORK:
        return []
    return _trusted_networks_from_json(record.trusted_networks_json)


def _generate_direct_key(prefix: str) -> str:
    return prefix + secrets.token_urlsafe(32)


def generate_bearer_key() -> str:
    return _generate_direct_key(DIRECT_KEY_PREFIX)


def generate_custom_header_key() -> str:
    return _generate_direct_key(CUSTOM_HEADER_KEY_PREFIX)


def _require_key_prefix(plaintext_key: str, expected_prefix: str) -> None:
    if not plaintext_key.startswith(expected_prefix):
        raise McpDirectAuthConfigurationError(
            "The MCP direct key has an invalid Part Pilot prefix."
        )


def _digest_direct_key(
    plaintext_key: str,
    *,
    expected_prefix: str,
    instance_secret: str | None = None,
) -> str:
    _require_key_prefix(plaintext_key, expected_prefix)
    secret = _instance_secret(instance_secret)
    return hmac.new(
        _derive(secret, b"validation"),
        plaintext_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _encrypt_direct_key(
    plaintext_key: str,
    *,
    expected_prefix: str,
    instance_secret: str | None = None,
) -> str:
    _require_key_prefix(plaintext_key, expected_prefix)
    return _fernet(_instance_secret(instance_secret)).encrypt(
        plaintext_key.encode("utf-8")
    ).decode("ascii")


def _decrypt_direct_key(
    ciphertext: str,
    *,
    expected_prefix: str,
    instance_secret: str | None = None,
) -> str:
    try:
        plaintext = _fernet(_instance_secret(instance_secret)).decrypt(
            ciphertext.encode("ascii")
        ).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise McpDirectAuthDecryptionError(
            "Unable to decrypt the configured MCP direct key."
        ) from exc
    if not plaintext.startswith(expected_prefix):
        raise McpDirectAuthDecryptionError(
            "The configured MCP direct key has an invalid prefix."
        )
    return plaintext


def digest_bearer_key(
    plaintext_key: str,
    *,
    instance_secret: str | None = None,
) -> str:
    return _digest_direct_key(
        plaintext_key,
        expected_prefix=DIRECT_KEY_PREFIX,
        instance_secret=instance_secret,
    )


def encrypt_bearer_key(
    plaintext_key: str,
    *,
    instance_secret: str | None = None,
) -> str:
    return _encrypt_direct_key(
        plaintext_key,
        expected_prefix=DIRECT_KEY_PREFIX,
        instance_secret=instance_secret,
    )


def decrypt_bearer_key(
    ciphertext: str,
    *,
    instance_secret: str | None = None,
) -> str:
    return _decrypt_direct_key(
        ciphertext,
        expected_prefix=DIRECT_KEY_PREFIX,
        instance_secret=instance_secret,
    )


def digest_custom_header_key(
    plaintext_key: str,
    *,
    instance_secret: str | None = None,
) -> str:
    return _digest_direct_key(
        plaintext_key,
        expected_prefix=CUSTOM_HEADER_KEY_PREFIX,
        instance_secret=instance_secret,
    )


def encrypt_custom_header_key(
    plaintext_key: str,
    *,
    instance_secret: str | None = None,
) -> str:
    return _encrypt_direct_key(
        plaintext_key,
        expected_prefix=CUSTOM_HEADER_KEY_PREFIX,
        instance_secret=instance_secret,
    )


def decrypt_custom_header_key(
    ciphertext: str,
    *,
    instance_secret: str | None = None,
) -> str:
    return _decrypt_direct_key(
        ciphertext,
        expected_prefix=CUSTOM_HEADER_KEY_PREFIX,
        instance_secret=instance_secret,
    )

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


def _record_snapshot(record: McpDirectAuth) -> dict[str, object]:
    return {
        "mode": record.mode,
        "key_prefix": record.key_prefix,
        "custom_header_name": record.custom_header_name,
        "trusted_networks": (
            _trusted_networks_from_json(record.trusted_networks_json)
            if record.mode == DIRECT_AUTH_TRUSTED_NETWORK
            else []
        ),
        "rotated_at": (
            None if record.rotated_at is None else record.rotated_at.isoformat()
        ),
    }


def _rotate_direct_key(
    db: Session,
    *,
    actor_user_id: int,
    mode: str,
    credential_prefix: str,
    custom_header_name: str | None,
    event_type: str,
    summary: str,
    instance_secret: str | None,
    commit: bool,
) -> IssuedMcpDirectKey:
    _active_actor(db, actor_user_id)
    secret = _instance_secret(instance_secret, create=True)
    plaintext = _generate_direct_key(credential_prefix)
    ciphertext = _encrypt_direct_key(
        plaintext,
        expected_prefix=credential_prefix,
        instance_secret=secret,
    )
    digest = _digest_direct_key(
        plaintext,
        expected_prefix=credential_prefix,
        instance_secret=secret,
    )
    prefix = plaintext[:20]
    now = _naive_utc_now()
    record = get_direct_auth(db)
    before = None if record is None else _record_snapshot(record)
    if record is None:
        record = McpDirectAuth(id=DIRECT_AUTH_SINGLETON_ID, mode=mode)
        db.add(record)
    record.mode = mode
    record.key_ciphertext = ciphertext
    record.key_digest = digest
    record.key_prefix = prefix
    record.custom_header_name = custom_header_name
    record.trusted_networks_json = None
    record.rotated_at = now
    record.last_used_at = None
    db.flush()
    _audit(
        db,
        event_type=event_type,
        actor_user_id=actor_user_id,
        summary=summary,
        before=before,
        after=_record_snapshot(record),
    )
    if commit:
        db.commit()
        db.refresh(record)
    else:
        db.flush()
    return IssuedMcpDirectKey(record=record, plaintext_key=plaintext)


def rotate_bearer_key(
    db: Session,
    *,
    actor_user_id: int,
    instance_secret: str | None = None,
    commit: bool = True,
) -> IssuedMcpDirectKey:
    return _rotate_direct_key(
        db,
        actor_user_id=actor_user_id,
        mode=DIRECT_AUTH_BEARER_KEY,
        credential_prefix=DIRECT_KEY_PREFIX,
        custom_header_name=None,
        event_type="settings.mcp_direct_key_rotated",
        summary="Rotated the MCP direct Bearer key.",
        instance_secret=instance_secret,
        commit=commit,
    )


def rotate_custom_header_key(
    db: Session,
    *,
    actor_user_id: int,
    header_name: str = DEFAULT_CUSTOM_HEADER_NAME,
    instance_secret: str | None = None,
    commit: bool = True,
) -> IssuedMcpDirectKey:
    canonical_header_name = validate_custom_header_name(header_name)
    return _rotate_direct_key(
        db,
        actor_user_id=actor_user_id,
        mode=DIRECT_AUTH_CUSTOM_HEADER,
        credential_prefix=CUSTOM_HEADER_KEY_PREFIX,
        custom_header_name=canonical_header_name,
        event_type="settings.mcp_custom_header_key_rotated",
        summary="Rotated the MCP custom-header key.",
        instance_secret=instance_secret,
        commit=commit,
    )


def configure_trusted_networks(
    db: Session,
    *,
    actor_user_id: int,
    networks: Sequence[str],
    commit: bool = True,
) -> McpDirectAuth:
    _active_actor(db, actor_user_id)
    canonical = normalize_trusted_networks(networks)
    record = get_direct_auth(db)
    before = None if record is None else _record_snapshot(record)
    if record is None:
        record = McpDirectAuth(
            id=DIRECT_AUTH_SINGLETON_ID,
            mode=DIRECT_AUTH_TRUSTED_NETWORK,
        )
        db.add(record)
    record.mode = DIRECT_AUTH_TRUSTED_NETWORK
    record.key_ciphertext = None
    record.key_digest = None
    record.key_prefix = None
    record.custom_header_name = None
    record.trusted_networks_json = json.dumps(canonical, separators=(",", ":"))
    record.rotated_at = None
    record.last_used_at = None
    db.flush()
    _audit(
        db,
        event_type="settings.mcp_trusted_networks_configured",
        actor_user_id=actor_user_id,
        summary="Configured MCP trusted-network authentication.",
        before=before,
        after=_record_snapshot(record),
    )
    if commit:
        db.commit()
        db.refresh(record)
    else:
        db.flush()
    return record


def _mode_prefix(mode: str) -> str | None:
    if mode == DIRECT_AUTH_BEARER_KEY:
        return DIRECT_KEY_PREFIX
    if mode == DIRECT_AUTH_CUSTOM_HEADER:
        return CUSTOM_HEADER_KEY_PREFIX
    return None


def _not_configured_message(expected_mode: str | None) -> str:
    if expected_mode == DIRECT_AUTH_BEARER_KEY:
        return "An MCP direct Bearer key is not configured."
    if expected_mode == DIRECT_AUTH_CUSTOM_HEADER:
        return "An MCP custom-header key is not configured."
    return "An MCP direct key is not configured."


def _reveal_direct_key(
    db: Session,
    *,
    expected_mode: str | None,
    instance_secret: str | None,
    actor_user_id: int | None,
    commit: bool,
) -> str:
    if actor_user_id is not None:
        _active_actor(db, actor_user_id)
    record = get_direct_auth(db)
    credential_prefix = None if record is None else _mode_prefix(record.mode)
    configured = bool(
        record is not None
        and credential_prefix is not None
        and (expected_mode is None or record.mode == expected_mode)
        and record.key_ciphertext
        and record.key_digest
        and record.key_prefix
        and (
            record.mode != DIRECT_AUTH_CUSTOM_HEADER
            or record.custom_header_name is not None
        )
    )
    if not configured or record is None or credential_prefix is None:
        raise McpDirectAuthNotConfiguredError(
            _not_configured_message(expected_mode)
        )
    plaintext = _decrypt_direct_key(
        record.key_ciphertext,
        expected_prefix=credential_prefix,
        instance_secret=instance_secret,
    )
    expected = _digest_direct_key(
        plaintext,
        expected_prefix=credential_prefix,
        instance_secret=instance_secret,
    )
    if not hmac.compare_digest(expected, record.key_digest):
        raise McpDirectAuthDecryptionError(
            "The configured MCP direct key failed integrity validation."
        )
    if actor_user_id is not None:
        custom_mode = record.mode == DIRECT_AUTH_CUSTOM_HEADER
        _audit(
            db,
            event_type=(
                "settings.mcp_custom_header_key_revealed"
                if custom_mode
                else "settings.mcp_direct_key_revealed"
            ),
            actor_user_id=actor_user_id,
            summary=(
                "Revealed the MCP custom-header key."
                if custom_mode
                else "Revealed the MCP direct Bearer key."
            ),
            before=None,
            after={
                "mode": record.mode,
                "custom_header_name": record.custom_header_name,
            },
        )
        if commit:
            db.commit()
        else:
            db.flush()
    return plaintext


def reveal_direct_key(
    db: Session,
    *,
    instance_secret: str | None = None,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> str:
    return _reveal_direct_key(
        db,
        expected_mode=None,
        instance_secret=instance_secret,
        actor_user_id=actor_user_id,
        commit=commit,
    )


def reveal_bearer_key(
    db: Session,
    *,
    instance_secret: str | None = None,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> str:
    return _reveal_direct_key(
        db,
        expected_mode=DIRECT_AUTH_BEARER_KEY,
        instance_secret=instance_secret,
        actor_user_id=actor_user_id,
        commit=commit,
    )


def reveal_custom_header_key(
    db: Session,
    *,
    instance_secret: str | None = None,
    actor_user_id: int | None = None,
    commit: bool = True,
) -> str:
    return _reveal_direct_key(
        db,
        expected_mode=DIRECT_AUTH_CUSTOM_HEADER,
        instance_secret=instance_secret,
        actor_user_id=actor_user_id,
        commit=commit,
    )


def _touch_direct_auth_last_used(
    db: Session,
    record: McpDirectAuth,
    *,
    touch: bool,
    commit: bool,
) -> None:
    now = _naive_utc_now()
    should_touch = touch and (
        record.last_used_at is None
        or record.last_used_at <= now - LAST_USED_TOUCH_INTERVAL
    )
    if not should_touch:
        return
    record.last_used_at = now
    if commit:
        db.commit()
    else:
        db.flush()


def _validate_direct_key(
    db: Session,
    supplied_key: str,
    *,
    expected_mode: str,
    expected_prefix: str,
    instance_secret: str | None,
    touch: bool,
    commit: bool,
) -> bool:
    if not supplied_key.startswith(expected_prefix):
        return False
    record = get_direct_auth(db)
    if (
        record is None
        or record.mode != expected_mode
        or not record.key_digest
        or not record.key_prefix
        or (
            expected_mode == DIRECT_AUTH_CUSTOM_HEADER
            and record.custom_header_name is None
        )
    ):
        return False
    supplied_digest = _digest_direct_key(
        supplied_key,
        expected_prefix=expected_prefix,
        instance_secret=instance_secret,
    )
    if not hmac.compare_digest(supplied_digest, record.key_digest):
        return False
    _touch_direct_auth_last_used(
        db,
        record,
        touch=touch,
        commit=commit,
    )
    return True


def validate_trusted_network_client(
    db: Session,
    client_ip: str | ipaddress.IPv4Address | ipaddress.IPv6Address,
    *,
    touch: bool = True,
    commit: bool = True,
) -> bool:
    record = get_direct_auth(db)
    if record is None or record.mode != DIRECT_AUTH_TRUSTED_NETWORK:
        return False
    try:
        address = (
            client_ip
            if isinstance(client_ip, (ipaddress.IPv4Address, ipaddress.IPv6Address))
            else ipaddress.ip_address(client_ip)
        )
    except ValueError as exc:
        raise McpDirectAuthNetworkError(
            "The resolved MCP client address is invalid."
        ) from exc
    networks = [
        ipaddress.ip_network(value, strict=True)
        for value in trusted_networks_for_record(record)
    ]
    if not any(
        address.version == network.version and address in network
        for network in networks
    ):
        return False
    _touch_direct_auth_last_used(
        db,
        record,
        touch=touch,
        commit=commit,
    )
    return True


def validate_bearer_key(
    db: Session,
    supplied_key: str,
    *,
    instance_secret: str | None = None,
    touch: bool = True,
    commit: bool = True,
) -> bool:
    return _validate_direct_key(
        db,
        supplied_key,
        expected_mode=DIRECT_AUTH_BEARER_KEY,
        expected_prefix=DIRECT_KEY_PREFIX,
        instance_secret=instance_secret,
        touch=touch,
        commit=commit,
    )


def validate_custom_header_key(
    db: Session,
    supplied_key: str,
    *,
    instance_secret: str | None = None,
    touch: bool = True,
    commit: bool = True,
) -> bool:
    return _validate_direct_key(
        db,
        supplied_key,
        expected_mode=DIRECT_AUTH_CUSTOM_HEADER,
        expected_prefix=CUSTOM_HEADER_KEY_PREFIX,
        instance_secret=instance_secret,
        touch=touch,
        commit=commit,
    )

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
        and record.trusted_networks_json is None
    ):
        return False
    before = _record_snapshot(record)
    record.mode = DIRECT_AUTH_DISABLED
    record.key_ciphertext = None
    record.key_digest = None
    record.key_prefix = None
    record.custom_header_name = None
    record.trusted_networks_json = None
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
