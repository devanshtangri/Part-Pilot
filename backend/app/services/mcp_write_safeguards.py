from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import secrets
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import McpWriteIntent

# PARTPILOT:MCP_WRITE_SAFEGUARDS:V734
CONFIRMATION_TTL = timedelta(minutes=5)
IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,119}$")
CONFIRMATION_PREFIX = "pp_mcp_confirm_"

class McpWriteSafeguardError(RuntimeError):
    pass
class McpWriteIdempotencyError(McpWriteSafeguardError):
    pass
class McpWriteConfirmationError(McpWriteSafeguardError):
    pass
class McpWriteStateDriftError(McpWriteSafeguardError):
    pass

@dataclass(frozen=True)
class PreparedWriteIntent:
    intent: McpWriteIntent
    confirmation_token: str | None
    replay_result: dict[str, Any] | None


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def confirmation_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_idempotency_key(value: str) -> str:
    key = value.strip()
    if not IDEMPOTENCY_RE.fullmatch(key):
        raise McpWriteIdempotencyError(
            "idempotency_key must be 8-120 characters using letters, digits, dot, underscore, colon, or hyphen."
        )
    return key


def principal_key(principal: dict[str, Any]) -> str:
    auth_method = principal.get("auth_method")
    if auth_method == "oauth":
        oauth = principal.get("oauth")
        user_id = principal.get("actor_user_id")
        if not isinstance(oauth, dict) or type(oauth.get("client_database_id")) is not int or type(user_id) is not int:
            raise McpWriteSafeguardError("Authenticated OAuth principal identity is invalid.")
        return f"oauth:{oauth['client_database_id']}:{user_id}"
    if auth_method in {"direct_bearer", "direct_custom_header", "direct_trusted_network"}:
        direct_id = principal.get("direct_auth_id")
        if type(direct_id) is not int:
            raise McpWriteSafeguardError("Authenticated direct principal identity is invalid.")
        return f"direct:{direct_id}"
    raise McpWriteSafeguardError("This MCP principal cannot create write intents.")


def _find_intent(db: Session, pkey: str, tool_name: str, idempotency_key: str, *, lock: bool = False) -> McpWriteIntent | None:
    query = select(McpWriteIntent).where(
        McpWriteIntent.principal_key == pkey,
        McpWriteIntent.tool_name == tool_name,
        McpWriteIntent.idempotency_key == idempotency_key,
    )
    if lock:
        query = query.with_for_update()
    return db.execute(query).scalar_one_or_none()


def _new_confirmation_token() -> str:
    return CONFIRMATION_PREFIX + secrets.token_urlsafe(32)


def completed_write_replay(
    db: Session,
    *,
    principal: dict[str, Any],
    tool_name: str,
    idempotency_key: str,
    arguments: dict[str, Any],
) -> dict[str, Any] | None:
    key = normalize_idempotency_key(idempotency_key)
    pkey = principal_key(principal)
    intent = _find_intent(db, pkey, tool_name, key, lock=False)
    if intent is None:
        return None
    if intent.argument_hash != canonical_hash(arguments):
        raise McpWriteIdempotencyError(
            "This idempotency_key was already used with different arguments."
        )
    if intent.status != "completed":
        return None
    if not isinstance(intent.result_json, dict):
        raise McpWriteSafeguardError("Completed MCP write intent has no replay result.")
    return dict(intent.result_json)


def prepare_write_intent(
    db: Session,
    *,
    principal: dict[str, Any],
    authorization_user_id: int,
    tool_name: str,
    idempotency_key: str,
    arguments: dict[str, Any],
    preview: dict[str, Any],
) -> PreparedWriteIntent:
    key = normalize_idempotency_key(idempotency_key)
    pkey = principal_key(principal)
    arg_hash = canonical_hash(arguments)
    preview_hash = canonical_hash(preview)
    now = utc_now_naive()
    intent = _find_intent(db, pkey, tool_name, key, lock=True)
    if intent is not None:
        if intent.argument_hash != arg_hash:
            raise McpWriteIdempotencyError(
                "This idempotency_key was already used with different arguments."
            )
        if intent.status == "completed":
            if not isinstance(intent.result_json, dict):
                raise McpWriteSafeguardError("Completed MCP write intent has no replay result.")
            return PreparedWriteIntent(intent, None, dict(intent.result_json))
        if intent.status in {"failed", "expired"}:
            raise McpWriteIdempotencyError(
                "This idempotency_key belongs to a failed or expired write intent; use a new key."
            )
        if intent.expires_at <= now:
            intent.status = "expired"
            intent.error_type = "expired"
            intent.confirmation_digest = None
            intent.updated_at = now
            db.flush()
            raise McpWriteConfirmationError(
                "The MCP write preview expired; request a new preview with a new idempotency_key."
            )
        if intent.preview_hash != preview_hash:
            intent.status = "failed"
            intent.error_type = "state_drift"
            intent.confirmation_digest = None
            intent.updated_at = now
            db.flush()
            raise McpWriteStateDriftError(
                "Workspace state changed since this idempotency_key was previewed; use a new key."
            )
        token = _new_confirmation_token()
        intent.confirmation_digest = confirmation_digest(token)
        intent.expires_at = now + CONFIRMATION_TTL
        intent.preview_json = preview
        intent.updated_at = now
        db.flush()
        return PreparedWriteIntent(intent, token, None)

    token = _new_confirmation_token()
    intent = McpWriteIntent(
        principal_key=pkey,
        authorization_user_id=authorization_user_id,
        tool_name=tool_name,
        argument_hash=arg_hash,
        preview_hash=preview_hash,
        idempotency_key=key,
        confirmation_digest=confirmation_digest(token),
        status="pending",
        expires_at=now + CONFIRMATION_TTL,
        preview_json=preview,
    )
    db.add(intent)
    db.flush()
    return PreparedWriteIntent(intent, token, None)


def validate_confirmation(
    db: Session,
    *,
    principal: dict[str, Any],
    tool_name: str,
    idempotency_key: str,
    confirmation_token: str,
    arguments: dict[str, Any],
    current_preview: dict[str, Any],
) -> PreparedWriteIntent:
    key = normalize_idempotency_key(idempotency_key)
    pkey = principal_key(principal)
    intent = _find_intent(db, pkey, tool_name, key, lock=True)
    if intent is None:
        raise McpWriteConfirmationError("No pending MCP write preview matches this confirmation.")
    if intent.argument_hash != canonical_hash(arguments):
        raise McpWriteIdempotencyError(
            "This idempotency_key was already used with different arguments."
        )
    if intent.status == "completed":
        if not isinstance(intent.result_json, dict):
            raise McpWriteSafeguardError("Completed MCP write intent has no replay result.")
        return PreparedWriteIntent(intent, None, dict(intent.result_json))
    if intent.status != "pending":
        raise McpWriteConfirmationError(
            "This MCP write intent is no longer pending; request a new preview with a new idempotency_key."
        )
    now = utc_now_naive()
    if intent.expires_at <= now:
        intent.status = "expired"
        intent.error_type = "expired"
        intent.confirmation_digest = None
        intent.updated_at = now
        db.flush()
        raise McpWriteConfirmationError(
            "The MCP write confirmation expired; request a new preview with a new idempotency_key."
        )
    if (
        not confirmation_token.startswith(CONFIRMATION_PREFIX)
        or intent.confirmation_digest is None
        or not secrets.compare_digest(intent.confirmation_digest, confirmation_digest(confirmation_token))
    ):
        raise McpWriteConfirmationError("The MCP write confirmation token is invalid.")
    if intent.preview_hash != canonical_hash(current_preview):
        intent.status = "failed"
        intent.error_type = "state_drift"
        intent.confirmation_digest = None
        intent.updated_at = now
        db.flush()
        raise McpWriteStateDriftError(
            "Workspace state changed after preview; no mutation was applied. Request a new preview with a new idempotency_key."
        )
    return PreparedWriteIntent(intent, None, None)


def complete_write_intent(db: Session, intent: McpWriteIntent, result: dict[str, Any]) -> None:
    now = utc_now_naive()
    intent.status = "completed"
    intent.result_json = result
    intent.consumed_at = now
    intent.confirmation_digest = None
    intent.error_type = None
    intent.updated_at = now
    db.flush()


def fail_write_intent(
    db: Session,
    *,
    principal: dict[str, Any],
    tool_name: str,
    idempotency_key: str,
    error_type: str,
) -> None:
    try:
        key = normalize_idempotency_key(idempotency_key)
        pkey = principal_key(principal)
    except McpWriteSafeguardError:
        return
    intent = _find_intent(db, pkey, tool_name, key, lock=True)
    if intent is None or intent.status != "pending":
        return
    intent.status = "failed"
    intent.error_type = error_type[:80]
    intent.confirmation_digest = None
    intent.updated_at = utc_now_naive()
    db.flush()
