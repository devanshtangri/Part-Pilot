from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import secrets

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text

from app.db.base import Base
from app.db.session import SessionLocal
from app.main import app
from app.models import ApiKey, AuditLog, User, UserSession
from app.services.api_keys import (
    API_KEY_PREFIX,
    AVAILABLE_API_KEY_SCOPES,
    ApiKeyAuthenticationError,
    ApiKeyScopeError,
    validate_api_key,
)
from app.services.auth import create_session, create_user


# PARTPILOT:REST_API_KEY_SMOKE:V615
class ApiKeySmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise ApiKeySmokeFailure(message)


def _api_key_rows(db) -> list[tuple]:
    return list(
        db.execute(
            text(
                "select id,user_id,name,key_digest,key_prefix,scopes_json,"
                "expires_at,rotated_at,last_used_at,revoked_at,"
                "created_at,updated_at from api_keys order by id"
            )
        ).fetchall()
    )


def main() -> None:
    suffix = secrets.token_hex(5)
    username = f"smoke_api_key_{suffix}"
    password = "api-key-smoke-password"
    key_id: int | None = None
    user_id: int | None = None

    with SessionLocal() as db:
        baseline_keys = _api_key_rows(db)
        audit_floor = int(
            db.execute(select(func.coalesce(func.max(AuditLog.id), 0))).scalar_one()
        )
        historical_audits = list(
            db.execute(
                text(
                    "select * from audit_log where id <= :audit_floor order by id"
                ),
                {"audit_floor": audit_floor},
            ).fetchall()
        )

    def cleanup() -> None:
        with SessionLocal() as db:
            if key_id is not None:
                db.execute(
                    delete(AuditLog).where(
                        AuditLog.id > audit_floor,
                        AuditLog.entity_type == "api_key",
                        AuditLog.entity_id == key_id,
                    )
                )
            if user_id is not None:
                db.execute(
                    delete(AuditLog).where(
                        AuditLog.id > audit_floor,
                        AuditLog.actor_user_id == user_id,
                        AuditLog.event_type.like("settings.api_key_%"),
                    )
                )
                db.execute(delete(UserSession).where(UserSession.user_id == user_id))
                db.execute(delete(User).where(User.id == user_id))
            else:
                existing = db.execute(
                    select(User.id).where(User.username == username)
                ).scalar_one_or_none()
                if existing is not None:
                    db.execute(
                        delete(UserSession).where(UserSession.user_id == existing)
                    )
                    db.execute(delete(User).where(User.id == existing))
            db.commit()

    cleanup()
    client = TestClient(app)

    try:
        with SessionLocal() as db:
            table_sql = db.execute(
                text(
                    "select sql from sqlite_master "
                    "where type='table' and name='api_keys'"
                )
            ).scalar_one_or_none()
            if table_sql is None:
                fail("api_keys table is missing")
            columns = {
                str(row[1])
                for row in db.execute(text('PRAGMA table_info("api_keys")')).fetchall()
            }
            expected_columns = {
                "id", "user_id", "name", "key_digest", "key_prefix",
                "scopes_json", "expires_at", "rotated_at", "last_used_at",
                "revoked_at", "created_at", "updated_at",
            }
            if columns != expected_columns:
                fail(f"api_keys columns changed: {sorted(columns)}")
            for marker in (
                "ck_api_keys_name_length",
                "ck_api_keys_digest_length",
                "ck_api_keys_prefix_length",
                "uq_api_keys_key_digest",
            ):
                if marker not in table_sql:
                    fail(f"api_keys table is missing {marker}")
            indexes = {
                str(row[1])
                for row in db.execute(text('PRAGMA index_list("api_keys")')).fetchall()
            }
            for marker in (
                "ix_api_keys_user_id",
                "ix_api_keys_revoked_at",
                "ix_api_keys_expires_at",
                "ix_api_keys_last_used_at",
            ):
                if marker not in indexes:
                    fail(f"api_keys is missing index {marker}")
            foreign_keys = db.execute(
                text('PRAGMA foreign_key_list("api_keys")')
            ).fetchall()
            if not any(
                str(row[2]) == "users"
                and str(row[3]) == "user_id"
                and str(row[6]).upper() == "CASCADE"
                for row in foreign_keys
            ):
                fail("api_keys user foreign key is not CASCADE")
            if "api_keys" not in Base.metadata.tables:
                fail("ORM metadata is missing api_keys")
            if set(Base.metadata.tables["api_keys"].columns.keys()) != expected_columns:
                fail("ORM api_keys columns do not match the migration")

            user = create_user(
                db,
                username=username,
                display_name="API Key Smoke User",
                password=password,
                commit=True,
            )
            user_id = user.id
            session = create_session(db, user=user, commit=True)
            session_token = session.token

        unauthenticated = client.get("/api/settings/api-keys")
        if unauthenticated.status_code != 401:
            fail("API-key administration must require a user session")

        expiry = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        created_response = client.post(
            "/api/settings/api-keys",
            headers={"Authorization": f"Bearer {session_token}"},
            json={
                "name": "  Automation   Reader  ",
                "scopes": ["history:read", "inventory:read", "inventory:read"],
                "expires_at": expiry,
            },
        )
        if created_response.status_code != 201:
            fail(
                "API key creation failed: "
                f"{created_response.status_code} {created_response.text}"
            )
        if (
            created_response.headers.get("cache-control") != "no-store"
            or created_response.headers.get("pragma") != "no-cache"
        ):
            fail("API key secret response is cacheable")

        created = created_response.json()
        key_id = created.get("id")
        plaintext = created.get("key")
        if not isinstance(key_id, int) or key_id < 1:
            fail("API key create response lacks an ID")
        if (
            not isinstance(plaintext, str)
            or not plaintext.startswith(API_KEY_PREFIX)
            or len(plaintext) < 40
        ):
            fail("API key create response lacks a valid one-time key")
        if created.get("name") != "Automation Reader":
            fail("API key name normalization failed")
        if created.get("scopes") != ["inventory:read", "history:read"]:
            fail(f"API key scopes were not canonical: {created}")
        if created.get("status") != "active":
            fail("Fresh API key should be active")
        if not str(created.get("masked_key", "")).endswith("••••••••"):
            fail("API key response is missing masked key metadata")

        expected_digest = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
        with SessionLocal() as db:
            record = db.get(ApiKey, key_id)
            if record is None:
                fail("Created API key was not persisted")
            if record.key_digest != expected_digest:
                fail("API key digest-only storage is incorrect")
            if plaintext in record.key_digest:
                fail("API key plaintext leaked into digest storage")
            if record.key_prefix != plaintext[:24]:
                fail("API key visible prefix is incorrect")
            raw_record = repr(
                db.execute(
                    text("select * from api_keys where id=:key_id"),
                    {"key_id": key_id},
                ).fetchone()
            )
            if plaintext in raw_record:
                fail("API key plaintext is stored in api_keys")
            principal = validate_api_key(
                db,
                plaintext,
                required_scopes=("inventory:read",),
                touch_last_used=False,
            )
            if principal.user.id != user_id:
                fail("API key validation returned the wrong owner")
            try:
                validate_api_key(
                    db,
                    plaintext,
                    required_scopes=("projects:write",),
                    touch_last_used=False,
                )
            except ApiKeyScopeError:
                pass
            else:
                fail("Missing API key scope was accepted")

        listed_response = client.get(
            "/api/settings/api-keys",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        if listed_response.status_code != 200:
            fail("API key list endpoint failed")
        listed = listed_response.json()
        if listed.get("available_scopes") != list(AVAILABLE_API_KEY_SCOPES):
            fail("API key scope catalogue changed")
        if listed.get("total") != 1 or len(listed.get("keys", [])) != 1:
            fail(f"API key list shape is wrong: {listed}")
        list_item = listed["keys"][0]
        if "key" in list_item or "key_digest" in list_item:
            fail("API key list exposed secret material")

        key_as_admin = client.get(
            "/api/settings/api-keys",
            headers={"Authorization": f"Bearer {plaintext}"},
        )
        if key_as_admin.status_code != 401:
            fail("REST API key unexpectedly gained Settings administration")

        invalid_scope = client.post(
            "/api/settings/api-keys",
            headers={"Authorization": f"Bearer {session_token}"},
            json={"name": "Bad scope", "scopes": ["settings:write"], "expires_at": None},
        )
        if invalid_scope.status_code != 422:
            fail("Unsupported API key scope was accepted")

        naive_expiry = client.post(
            "/api/settings/api-keys",
            headers={"Authorization": f"Bearer {session_token}"},
            json={
                "name": "Naive expiry",
                "scopes": ["inventory:read"],
                "expires_at": "2030-01-01T00:00:00",
            },
        )
        if naive_expiry.status_code != 422:
            fail("Timezone-free API key expiry was accepted")

        past_expiry = client.post(
            "/api/settings/api-keys",
            headers={"Authorization": f"Bearer {session_token}"},
            json={
                "name": "Past expiry",
                "scopes": ["inventory:read"],
                "expires_at": "2020-01-01T00:00:00Z",
            },
        )
        if past_expiry.status_code != 422:
            fail("Past API key expiry was accepted")

        updated_response = client.put(
            f"/api/settings/api-keys/{key_id}",
            headers={"Authorization": f"Bearer {session_token}"},
            json={
                "name": "Automation Observer",
                "scopes": ["inventory:read", "projects:read", "history:read"],
                "expires_at": (
                    datetime.now(timezone.utc) + timedelta(days=3)
                ).isoformat(),
            },
        )
        if updated_response.status_code != 200:
            fail(
                "API key update failed: "
                f"{updated_response.status_code} {updated_response.text}"
            )
        updated = updated_response.json()
        if (
            updated.get("name") != "Automation Observer"
            or updated.get("scopes")
            != ["inventory:read", "projects:read", "history:read"]
        ):
            fail(f"API key update result is wrong: {updated}")

        rotated_response = client.post(
            f"/api/settings/api-keys/{key_id}/rotate",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        if rotated_response.status_code != 200:
            fail(
                "API key rotation failed: "
                f"{rotated_response.status_code} {rotated_response.text}"
            )
        rotated = rotated_response.json()
        rotated_key = rotated.get("key")
        if (
            not isinstance(rotated_key, str)
            or rotated_key == plaintext
            or not rotated_key.startswith(API_KEY_PREFIX)
        ):
            fail("API key rotation did not issue a new secret")
        if rotated.get("rotated_at") is None:
            fail("API key rotation timestamp is missing")

        with SessionLocal() as db:
            try:
                validate_api_key(db, plaintext, touch_last_used=False)
            except ApiKeyAuthenticationError:
                pass
            else:
                fail("Rotated-out API key remained valid")

            validate_api_key(
                db,
                rotated_key,
                required_scopes=("projects:read",),
                touch_last_used=True,
                commit=True,
            )
            refreshed = db.get(ApiKey, key_id)
            if refreshed is None or refreshed.last_used_at is None:
                fail("API key last-used timestamp was not recorded")

        revoke_response = client.delete(
            f"/api/settings/api-keys/{key_id}",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        if (
            revoke_response.status_code != 200
            or revoke_response.json().get("status") != "revoked"
        ):
            fail(
                "API key revocation failed: "
                f"{revoke_response.status_code} {revoke_response.text}"
            )

        second_revoke = client.delete(
            f"/api/settings/api-keys/{key_id}",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        if (
            second_revoke.status_code != 200
            or second_revoke.json().get("status") != "revoked"
        ):
            fail("API key revocation is not idempotent")

        rotate_revoked = client.post(
            f"/api/settings/api-keys/{key_id}/rotate",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        if rotate_revoked.status_code != 409:
            fail("Revoked API key could be rotated")

        with SessionLocal() as db:
            try:
                validate_api_key(db, rotated_key, touch_last_used=False)
            except ApiKeyAuthenticationError:
                pass
            else:
                fail("Revoked API key remained valid")

            audits = list(
                db.execute(
                    select(AuditLog)
                    .where(
                        AuditLog.id > audit_floor,
                        AuditLog.entity_type == "api_key",
                        AuditLog.entity_id == key_id,
                    )
                    .order_by(AuditLog.id)
                ).scalars()
            )
            events = [audit.event_type for audit in audits]
            if events != [
                "settings.api_key_created",
                "settings.api_key_updated",
                "settings.api_key_rotated",
                "settings.api_key_revoked",
            ]:
                fail(f"API key audit events changed: {events}")
            serialized_audits = json.dumps(
                [
                    {
                        "summary": audit.summary,
                        "before": audit.before_json,
                        "after": audit.after_json,
                        "metadata": audit.metadata_json,
                    }
                    for audit in audits
                ],
                sort_keys=True,
                default=str,
            )
            for secret_value in (
                plaintext,
                rotated_key,
                expected_digest,
                hashlib.sha256(rotated_key.encode("utf-8")).hexdigest(),
            ):
                if secret_value in serialized_audits:
                    fail("API key audit exposed secret material")

    finally:
        cleanup()

    with SessionLocal() as db:
        if _api_key_rows(db) != baseline_keys:
            fail("API key smoke did not preserve pre-existing keys")
        current_historical = list(
            db.execute(
                text("select * from audit_log where id <= :audit_floor order by id"),
                {"audit_floor": audit_floor},
            ).fetchall()
        )
        if current_historical != historical_audits:
            fail("API key smoke changed historical audit rows")

    print(
        "[PASS] Scoped REST API-key lifecycle, digest-only storage, "
        "session-only administration, scope validation, expiry, rotation, "
        "revocation, last-used metadata, audit redaction and cleanup"
    )


if __name__ == "__main__":
    main()
