from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.db.settings import get_bool_setting
from app.models import AuditLog, McpDirectAuth, User
from app.schemas.app_settings import McpSettingsUpdateRequest
from app.services.app_settings import (
    MCP_DIRECT_CLIENTS_ENABLED_KEY,
    MCP_DIRECT_NO_AUTH_ENABLED_KEY,
    McpSettingsValidationError,
    get_mcp_settings,
    update_mcp_settings,
)
from app.services.mcp_direct_auth import (
    DIRECT_AUTH_BEARER_KEY,
    DIRECT_AUTH_CUSTOM_HEADER,
    DIRECT_AUTH_TRUSTED_NETWORK,
    McpDirectAuthNetworkError,
    create_named_direct_client,
    list_direct_clients,
    reveal_named_direct_client_key,
    revoke_named_direct_client,
    rotate_named_direct_client_key,
    update_named_direct_client,
    validate_named_bearer_client,
    validate_named_custom_header_client,
    validate_named_trusted_network_client,
)

# PARTPILOT:MCP_NAMED_DIRECT_CLIENTS_SMOKE:V627
SECRET = "patch627-named-direct-smoke-secret-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ"

class SmokeFailure(RuntimeError):
    pass

def fail(message: str) -> None:
    raise SmokeFailure(message)

def _database_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"Named-direct smoke requires SQLite, got {url!r}")
    return Path(url[len(prefix):]).resolve()

def main() -> None:
    database_path = _database_path()
    before_bytes = database_path.read_bytes()
    db = SessionLocal()
    try:
        actor = db.execute(select(User).where(User.is_active.is_(True)).order_by(User.id)).scalars().first()
        if actor is None:
            fail("Named-direct smoke requires one active user")
        legacy = db.get(McpDirectAuth, 1)
        if legacy is None or legacy.mode != "disabled" or legacy.enabled:
            fail("0015 did not preserve the disabled legacy row")
        settings = get_mcp_settings(db)
        if settings.direct_clients_enabled or settings.direct_no_auth_enabled:
            fail("Direct clients/no-auth were not safely disabled by default")

        try:
            update_mcp_settings(
                db,
                McpSettingsUpdateRequest(
                    enabled=True,
                    read_tools_enabled=True,
                    write_tools_enabled=False,
                    direct_clients_enabled=True,
                    direct_no_auth_enabled=True,
                ),
                actor_user_id=actor.id,
                commit=False,
            )
        except McpSettingsValidationError:
            db.rollback()
        else:
            fail("No-auth enabled without typed confirmation")

        settings = update_mcp_settings(
            db,
            McpSettingsUpdateRequest(
                enabled=True,
                read_tools_enabled=True,
                write_tools_enabled=False,
                direct_clients_enabled=True,
                direct_no_auth_enabled=True,
                direct_no_auth_confirmation="ALLOW NO AUTH",
            ),
            actor_user_id=actor.id,
            commit=True,
        )
        if not settings.direct_no_auth_enabled or settings.write_tools_enabled:
            fail("Confirmed no-auth settings were not read-only")

        first = create_named_direct_client(
            db,
            actor_user_id=actor.id,
            name="Hermes agent",
            mode=DIRECT_AUTH_BEARER_KEY,
            instance_secret=SECRET,
            commit=True,
        )
        second = create_named_direct_client(
            db,
            actor_user_id=actor.id,
            name="Claude local",
            mode=DIRECT_AUTH_BEARER_KEY,
            instance_secret=SECRET,
            commit=True,
        )
        if first.plaintext_key == second.plaintext_key:
            fail("Named Bearer clients reused credential material")
        if validate_named_bearer_client(db, first.plaintext_key, instance_secret=SECRET, touch=False) is None:
            fail("First named Bearer key was rejected")
        if validate_named_bearer_client(db, second.plaintext_key, instance_secret=SECRET, touch=False) is None:
            fail("Second named Bearer key was rejected")

        old_first = first.plaintext_key
        rotated = rotate_named_direct_client_key(
            db,
            client_id=first.record.id,
            actor_user_id=actor.id,
            instance_secret=SECRET,
            commit=True,
        )
        if rotated.plaintext_key == old_first:
            fail("Named Bearer rotation reused key material")
        if validate_named_bearer_client(db, old_first, instance_secret=SECRET, touch=False) is not None:
            fail("Rotated named Bearer key remained valid")
        if validate_named_bearer_client(db, second.plaintext_key, instance_secret=SECRET, touch=False) is None:
            fail("Rotating one client invalidated another client")

        custom = create_named_direct_client(
            db,
            actor_user_id=actor.id,
            name="n8n custom header",
            mode=DIRECT_AUTH_CUSTOM_HEADER,
            header_name="X-PartPilot-N8N-Key",
            instance_secret=SECRET,
            commit=True,
        )
        if validate_named_custom_header_client(
            db,
            "x-partpilot-n8n-key",
            custom.plaintext_key,
            instance_secret=SECRET,
            touch=False,
        ) is None:
            fail("Named custom-header client was rejected")

        trusted = create_named_direct_client(
            db,
            actor_user_id=actor.id,
            name="Workshop LAN",
            mode=DIRECT_AUTH_TRUSTED_NETWORK,
            networks=["192.0.2.0/24"],
            commit=True,
        )
        if validate_named_trusted_network_client(db, "192.0.2.25", touch=False) is None:
            fail("Named trusted-network client was rejected")
        try:
            create_named_direct_client(
                db,
                actor_user_id=actor.id,
                name="Overlapping LAN",
                mode=DIRECT_AUTH_TRUSTED_NETWORK,
                networks=["192.0.2.128/25"],
                commit=False,
            )
        except McpDirectAuthNetworkError:
            db.rollback()
        else:
            fail("Overlapping named trusted networks were accepted")

        # Reacquire after rollback from the deliberate overlap failure.
        second_record = db.get(McpDirectAuth, second.record.id)
        if second_record is None:
            fail("Second named client disappeared")
        update_named_direct_client(
            db,
            client_id=second_record.id,
            actor_user_id=actor.id,
            enabled=False,
            commit=True,
        )
        if validate_named_bearer_client(db, second.plaintext_key, instance_secret=SECRET, touch=False) is not None:
            fail("Disabled named client still authenticated")
        update_named_direct_client(
            db,
            client_id=second_record.id,
            actor_user_id=actor.id,
            enabled=True,
            commit=True,
        )
        if validate_named_bearer_client(db, second.plaintext_key, instance_secret=SECRET, touch=False) is None:
            fail("Re-enabled named client did not authenticate")

        revoked_id = custom.record.id
        revoke_named_direct_client(db, client_id=revoked_id, actor_user_id=actor.id, commit=True)
        if any(row.id == revoked_id for row in list_direct_clients(db)):
            fail("Revoked named client remains in active list")
        retained = db.get(McpDirectAuth, revoked_id)
        if retained is None or retained.revoked_at is None or retained.key_digest is not None:
            fail("Revoked client audit record was not retained safely")

        if not get_bool_setting(db, MCP_DIRECT_CLIENTS_ENABLED_KEY, False):
            fail("Direct-client master setting was not persisted")
        if not get_bool_setting(db, MCP_DIRECT_NO_AUTH_ENABLED_KEY, False):
            fail("No-auth setting was not persisted")

        serialized = json.dumps(
            [
                {
                    "event": row.event_type,
                    "summary": row.summary,
                    "before": row.before_json,
                    "after": row.after_json,
                    "metadata": row.metadata_json,
                }
                for row in db.execute(
                    select(AuditLog).where(AuditLog.event_type.like("settings.mcp%"))
                ).scalars()
            ],
            default=str,
            sort_keys=True,
        )
        for secret in (old_first, rotated.plaintext_key, second.plaintext_key, custom.plaintext_key):
            if secret in serialized:
                fail("Plaintext named direct credential leaked into audit data")
        for row in db.execute(select(McpDirectAuth)).scalars():
            for secret in (old_first, rotated.plaintext_key, second.plaintext_key, custom.plaintext_key):
                if secret and secret in (row.key_ciphertext or ""):
                    fail("Plaintext named direct credential leaked into database ciphertext")

        print("[PASS] Named MCP direct clients have independent Bearer/custom/trusted identities, safe rotation/disable/revoke, overlap protection, typed no-auth confirmation, read-only no-auth policy, secret-free persistence and audit attribution")
    finally:
        db.rollback()
        db.close()
        engine.dispose()
        database_path.write_bytes(before_bytes)
        if database_path.read_bytes() != before_bytes:
            fail("Named-direct smoke did not restore the copied database exactly")

if __name__ == "__main__":
    main()
