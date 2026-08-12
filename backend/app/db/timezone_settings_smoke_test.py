from __future__ import annotations

import argparse
import copy
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AppSetting, AuditLog, User, UserSession
from app.services.app_setup import DEFAULT_TIMEZONE_KEY
from app.services.app_settings import get_timezone_settings
from app.services.auth import create_session

# PARTPILOT:TIMEZONE_PREFERENCE_SMOKE:V676

class SmokeFailure(RuntimeError):
    pass

def fail(message: str) -> None:
    raise SmokeFailure(message)

def sqlite_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"Timezone settings smoke requires SQLite, got {url!r}")
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

def check_only() -> None:
    from app.main import app
    with TestClient(app) as client:
        if client.get("/api/settings/timezone").status_code != 401:
            fail("GET timezone settings must require authentication")
        if client.patch("/api/settings/timezone", json={"timezone": "UTC"}).status_code != 401:
            fail("PATCH timezone settings must require authentication")
        methods = client.get("/openapi.json").json().get("paths", {}).get("/api/settings/timezone", {})
        if set(methods) != {"get", "patch"}:
            fail(f"Unexpected timezone settings OpenAPI methods: {methods}")
    print("[PASS] Timezone preference GET/PATCH routes are protected and present in OpenAPI")

def full_flow() -> None:
    before = database_snapshot(); db = SessionLocal(); session_id = None; audit_ids = []; original = None
    try:
        user = db.execute(select(User).order_by(User.id.asc())).scalars().first()
        if user is None: fail("Timezone settings smoke requires one existing user")
        row = db.execute(select(AppSetting).where(AppSetting.key == DEFAULT_TIMEZONE_KEY)).scalar_one()
        original = (copy.deepcopy(row.value_json), row.value_text, row.updated_at)
        initial = get_timezone_settings(db)
        existing_audits = set(db.execute(select(AuditLog.id).where(AuditLog.event_type == "settings.timezone_updated")).scalars())
        issued = create_session(db, user=user, user_agent="Patch 676 timezone preference smoke", ip_address="127.0.0.1", commit=False)
        session_id = issued.session.id; headers = {"Authorization": f"Bearer {issued.token}"}; db.commit()
        alternate = "UTC" if initial.timezone != "UTC" else "Asia/Kolkata"
        from app.main import app
        with TestClient(app) as client:
            loaded = client.get("/api/settings/timezone", headers=headers)
            if loaded.status_code != 200 or loaded.json() != {"timezone": initial.timezone}:
                fail(f"Timezone GET mismatch: {loaded.status_code} {loaded.text[:300]}")
            for payload in ({"timezone": ""}, {"timezone": "Not/AZone"}, {"timezone": alternate, "extra": True}):
                invalid = client.patch("/api/settings/timezone", headers=headers, json=payload)
                if invalid.status_code != 422: fail(f"Invalid timezone payload {payload} returned {invalid.status_code}")
            changed = client.patch("/api/settings/timezone", headers=headers, json={"timezone": f"  {alternate}  "})
            if changed.status_code != 200 or changed.json() != {"timezone": alternate}:
                fail(f"Timezone PATCH failed: {changed.status_code} {changed.text[:300]}")
            status = client.get("/api/auth/setup-status")
            if status.status_code != 200 or status.json().get("timezone") != alternate:
                fail("Setup status did not reflect updated workspace timezone")
            again = client.patch("/api/settings/timezone", headers=headers, json={"timezone": alternate})
            if again.status_code != 200 or again.json() != {"timezone": alternate}:
                fail("No-op timezone PATCH mismatch")
        verify = SessionLocal()
        try:
            current = verify.execute(select(AppSetting).where(AppSetting.key == DEFAULT_TIMEZONE_KEY)).scalar_one()
            if current.value_json != alternate or current.value_text != alternate:
                fail("Timezone setting was not persisted consistently")
            audits = [a for a in verify.execute(select(AuditLog).where(AuditLog.event_type == "settings.timezone_updated").order_by(AuditLog.id)).scalars() if a.id not in existing_audits]
            if len(audits) != 1: fail(f"Expected one timezone audit, got {len(audits)}")
            audit = audits[0]; audit_ids = [audit.id]
            if audit.before_json != {"timezone": initial.timezone} or audit.after_json != {"timezone": alternate}:
                fail("Timezone audit before/after mismatch")
            if audit.metadata_json.get("display_only") is not True or audit.metadata_json.get("stored_timestamps_preserved") is not True:
                fail("Timezone audit semantics missing")
        finally: verify.close()
        cleanup = SessionLocal()
        try:
            row = cleanup.execute(select(AppSetting).where(AppSetting.key == DEFAULT_TIMEZONE_KEY)).scalar_one()
            row.value_json, row.value_text, row.updated_at = original
            if audit_ids: cleanup.query(AuditLog).filter(AuditLog.id.in_(audit_ids)).delete(synchronize_session=False)
            if session_id is not None:
                session = cleanup.get(UserSession, session_id)
                if session is not None: cleanup.delete(session)
            cleanup.commit()
        finally: cleanup.close()
        restore_sequences(before)
        if database_snapshot() != before: fail("Timezone settings smoke did not restore exact database")
    except Exception:
        db.rollback(); raise
    finally: db.close()
    print("[PASS] Timezone preference is authenticated, IANA-validated, audited once, reflected by setup status, display-only, and restores the exact copied database")

def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--check-only", action="store_true"); args=parser.parse_args()
    check_only() if args.check_only else full_flow()

if __name__ == "__main__":
    main()
