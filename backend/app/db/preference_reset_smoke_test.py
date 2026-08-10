from __future__ import annotations

import argparse
import copy
import sqlite3
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AppSetting, AuditLog, User, UserSession
from app.services.app_settings import (
    APPEARANCE_THEME_KEY,
    PREFERENCE_TARGET_SETTING_KEYS,
    RESERVATION_EXPIRY_DEFAULT_DAYS_KEY,
    RESERVATION_EXPIRY_MODE_KEY,
    SEARCH_SHOW_OUT_OF_STOCK_SECTION_KEY,
    reset_reversible_preference,
)
from app.services.auth import create_session

# PARTPILOT:TARGETED_PREFERENCE_RESET_SMOKE:V673
NON_DEFAULTS = {
    APPEARANCE_THEME_KEY: ("system", "system"),
    SEARCH_SHOW_OUT_OF_STOCK_SECTION_KEY: (False, None),
    RESERVATION_EXPIRY_MODE_KEY: ("default", "default"),
    RESERVATION_EXPIRY_DEFAULT_DAYS_KEY: (37, None),
}
DEFAULTS = {
    APPEARANCE_THEME_KEY: ("dark", "dark"),
    SEARCH_SHOW_OUT_OF_STOCK_SECTION_KEY: (True, None),
    RESERVATION_EXPIRY_MODE_KEY: ("none", "none"),
    RESERVATION_EXPIRY_DEFAULT_DAYS_KEY: (None, None),
}
TARGETS = ("appearance", "inventory", "reservations")
ALL_KEYS = tuple(NON_DEFAULTS)

class SmokeFailure(RuntimeError): pass

def fail(message: str) -> None: raise SmokeFailure(message)

def sqlite_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix): fail(f"Preference reset smoke requires SQLite, got {url!r}")
    return Path(url[len(prefix):]).resolve()

def database_snapshot() -> dict[str, object]:
    db = sqlite3.connect(sqlite_path()); db.row_factory = sqlite3.Row
    try:
        tables = [str(row[0]) for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        rows = {table: [{key: row[key] for key in row.keys()} for row in db.execute(f'SELECT * FROM "{table}" ORDER BY rowid')] for table in tables}
        has_sequences = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'").fetchone()
        sequences = [tuple(row) for row in db.execute("SELECT name,seq FROM sqlite_sequence ORDER BY name")] if has_sequences else []
        return {"rows": rows, "sequences": sequences}
    finally: db.close()

def restore_sequences(snapshot: dict[str, object]) -> None:
    db = sqlite3.connect(sqlite_path())
    try:
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'").fetchone():
            db.execute("DELETE FROM sqlite_sequence")
            for name, sequence in snapshot["sequences"]:
                db.execute("INSERT INTO sqlite_sequence(name,seq) VALUES (?,?)", (name, sequence))
            db.commit()
    finally: db.close()

def raw_setting(db, key: str) -> tuple[object, object, object]:
    row = db.execute(select(AppSetting).where(AppSetting.key == key)).scalar_one()
    return copy.deepcopy(row.value_json), row.value_text, row.updated_at

def seed_non_defaults(db) -> None:
    for key, (value_json, value_text) in NON_DEFAULTS.items():
        row = db.execute(select(AppSetting).where(AppSetting.key == key)).scalar_one()
        row.value_json = copy.deepcopy(value_json); row.value_text = value_text
    db.commit()

def check_only() -> None:
    from app.main import app
    with TestClient(app) as client:
        response = client.post("/api/settings/preferences/reset", json={"target": "appearance"})
        if response.status_code != 401: fail(f"Preference reset should require authentication, got {response.status_code}")
        methods = client.get("/openapi.json").json().get("paths", {}).get("/api/settings/preferences/reset", {})
        if set(methods) != {"post"}: fail(f"Unexpected preference reset OpenAPI methods: {methods}")
    print("[PASS] Targeted preference reset route is protected and present in OpenAPI")

def full_flow() -> None:
    before = database_snapshot(); db = SessionLocal(); originals = {}; session_id = None; audit_ids = []
    try:
        user = db.execute(select(User).order_by(User.id.asc())).scalars().first()
        if user is None: fail("Preference reset smoke requires one existing user")
        for key in ALL_KEYS: originals[key] = raw_setting(db, key)
        non_target_settings = {row.key: (copy.deepcopy(row.value_json), row.value_text, row.updated_at) for row in db.execute(select(AppSetting)).scalars() if row.key not in ALL_KEYS}
        existing_audits = set(db.execute(select(AuditLog.id).where(AuditLog.event_type == "settings.preference_reset")).scalars())
        issued = create_session(db, user=user, user_agent="Patch 673 targeted preference reset smoke", ip_address="127.0.0.1", commit=False)
        session_id = issued.session.id; headers = {"Authorization": f"Bearer {issued.token}"}; db.commit()
        from app.main import app
        with TestClient(app) as client:
            invalid = client.post("/api/settings/preferences/reset", headers=headers, json={"target": "all"})
            if invalid.status_code != 422: fail(f"Invalid reset target returned {invalid.status_code}, expected 422")
            extra = client.post("/api/settings/preferences/reset", headers=headers, json={"target": "appearance", "extra": True})
            if extra.status_code != 422: fail(f"Extra reset field returned {extra.status_code}, expected 422")
            for target in TARGETS:
                seed = SessionLocal()
                try:
                    seed_non_defaults(seed)
                    before_target = {key: raw_setting(seed, key)[:2] for key in ALL_KEYS}
                finally: seed.close()
                response = client.post("/api/settings/preferences/reset", headers=headers, json={"target": target})
                if response.status_code != 200: fail(f"{target} reset returned {response.status_code}: {response.text[:500]}")
                body = response.json()
                if body.get("target") != target: fail(f"{target} reset returned wrong target: {body}")
                populated = [name for name in TARGETS if body.get(name) is not None]
                if populated != [target]: fail(f"{target} reset populated wrong groups: {body}")
                verify = SessionLocal()
                try:
                    target_keys = set(PREFERENCE_TARGET_SETTING_KEYS[target])
                    for key in ALL_KEYS:
                        current = raw_setting(verify, key)[:2]
                        expected = DEFAULTS[key] if key in target_keys else before_target[key]
                        if current != expected: fail(f"{target} reset changed wrong key {key}: {current} != {expected}")
                finally: verify.close()
                again = client.post("/api/settings/preferences/reset", headers=headers, json={"target": target})
                if again.status_code != 200 or again.json() != body: fail(f"{target} no-op reset mismatch")
        verify = SessionLocal()
        try:
            for key, expected in non_target_settings.items():
                if raw_setting(verify, key) != expected: fail(f"Non-preference setting changed: {key}")
            new_audits = [row for row in verify.execute(select(AuditLog).where(AuditLog.event_type == "settings.preference_reset").order_by(AuditLog.id.asc())).scalars() if row.id not in existing_audits]
            if len(new_audits) != 3: fail(f"Expected three targeted audits, got {len(new_audits)}")
            audit_ids = [row.id for row in new_audits]
            if [row.metadata_json.get("target") for row in new_audits] != list(TARGETS): fail("Audit targets are incorrect")
            for row in new_audits:
                metadata = row.metadata_json; target = metadata.get("target")
                if metadata.get("setting_keys") != list(PREFERENCE_TARGET_SETTING_KEYS[target]): fail(f"Audit keys incorrect for {target}")
                if metadata.get("preserves_other_preferences") is not True or metadata.get("preserves_security_and_business_data") is not True: fail(f"Audit preservation marker missing for {target}")
        finally: verify.close()
        failure_db = SessionLocal()
        try:
            seed_non_defaults(failure_db)
            before_failure = {key: raw_setting(failure_db, key)[:2] for key in ALL_KEYS}
            audit_count = failure_db.query(AuditLog).filter(AuditLog.event_type == "settings.preference_reset").count()
            from app.services import app_settings as service_module
            real_set = service_module.set_app_setting; calls = 0
            def injected(*args, **kwargs):
                nonlocal calls; calls += 1
                if calls == 2: raise RuntimeError("injected targeted preference reset failure")
                return real_set(*args, **kwargs)
            try:
                with patch("app.services.app_settings.set_app_setting", side_effect=injected):
                    reset_reversible_preference(failure_db, target="reservations", actor_user_id=user.id, commit=True)
            except RuntimeError as exc:
                if str(exc) != "injected targeted preference reset failure": raise
            else: fail("Injected targeted reset failure did not raise")
            after_failure = {key: raw_setting(failure_db, key)[:2] for key in ALL_KEYS}
            audit_after = failure_db.query(AuditLog).filter(AuditLog.event_type == "settings.preference_reset").count()
            if after_failure != before_failure or audit_after != audit_count: fail("Reservation reset failure was not atomic")
        finally: failure_db.close()
        cleanup = SessionLocal()
        try:
            for key, (value_json, value_text, updated_at) in originals.items():
                row = cleanup.execute(select(AppSetting).where(AppSetting.key == key)).scalar_one()
                row.value_json = copy.deepcopy(value_json); row.value_text = value_text; row.updated_at = updated_at
            if audit_ids: cleanup.query(AuditLog).filter(AuditLog.id.in_(audit_ids)).delete(synchronize_session=False)
            if session_id is not None:
                session = cleanup.get(UserSession, session_id)
                if session is not None: cleanup.delete(session)
            cleanup.commit()
        finally: cleanup.close()
        restore_sequences(before)
        if database_snapshot() != before: fail("Targeted preference reset smoke did not restore exact database")
    except Exception:
        db.rollback(); raise
    finally: db.close()
    print("[PASS] Targeted preference resets are authenticated and isolated by target, suppress no-op audits, preserve non-target settings/security/business data, roll back reservation failures, and restore the exact copied database")

def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--check-only", action="store_true"); args = parser.parse_args()
    check_only() if args.check_only else full_flow()
if __name__ == "__main__": main()
