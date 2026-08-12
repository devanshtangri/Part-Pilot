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
from app.services.app_setup import DEFAULT_CURRENCY_KEY
from app.services.app_settings import get_currency_settings
from app.services.auth import create_session

# PARTPILOT:CURRENCY_PREFERENCE_SMOKE:V675

class SmokeFailure(RuntimeError):
    pass

def fail(message: str) -> None:
    raise SmokeFailure(message)

def sqlite_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"Currency settings smoke requires SQLite, got {url!r}")
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
        if client.get("/api/settings/currency").status_code != 401:
            fail("GET currency settings must require authentication")
        if client.patch("/api/settings/currency", json={"currency": "USD"}).status_code != 401:
            fail("PATCH currency settings must require authentication")
        methods = client.get("/openapi.json").json().get("paths", {}).get("/api/settings/currency", {})
        if set(methods) != {"get", "patch"}:
            fail(f"Unexpected currency settings OpenAPI methods: {methods}")
    print("[PASS] Currency preference GET/PATCH routes are protected and present in OpenAPI")

def full_flow() -> None:
    before = database_snapshot(); db = SessionLocal(); session_id = None; audit_ids = []
    original = None
    try:
        user = db.execute(select(User).order_by(User.id.asc())).scalars().first()
        if user is None: fail("Currency settings smoke requires one existing user")
        row = db.execute(select(AppSetting).where(AppSetting.key == DEFAULT_CURRENCY_KEY)).scalar_one()
        original = (copy.deepcopy(row.value_json), row.value_text, row.updated_at)
        initial = get_currency_settings(db)
        existing_audits = set(db.execute(select(AuditLog.id).where(AuditLog.event_type == "settings.currency_updated")).scalars())
        issued = create_session(db, user=user, user_agent="Patch 675 currency preference smoke", ip_address="127.0.0.1", commit=False)
        session_id = issued.session.id; headers = {"Authorization": f"Bearer {issued.token}"}; db.commit()
        alternate = "USD" if initial.currency != "USD" else "EUR"
        from app.main import app
        with TestClient(app) as client:
            loaded = client.get("/api/settings/currency", headers=headers)
            if loaded.status_code != 200 or loaded.json() != {"currency": initial.currency}:
                fail(f"Currency GET mismatch: {loaded.status_code} {loaded.text[:300]}")
            for payload in ({"currency": "US"}, {"currency": "US1"}, {"currency": "USDX"}, {"currency": alternate, "extra": True}):
                invalid = client.patch("/api/settings/currency", headers=headers, json=payload)
                if invalid.status_code != 422: fail(f"Invalid currency payload {payload} returned {invalid.status_code}")
            changed = client.patch("/api/settings/currency", headers=headers, json={"currency": alternate.lower()})
            if changed.status_code != 200 or changed.json() != {"currency": alternate}:
                fail(f"Currency PATCH failed: {changed.status_code} {changed.text[:300]}")
            status = client.get("/api/auth/setup-status")
            if status.status_code != 200 or status.json().get("default_currency") != alternate:
                fail("Setup status did not reflect updated app-wide currency")
            again = client.patch("/api/settings/currency", headers=headers, json={"currency": alternate})
            if again.status_code != 200 or again.json() != {"currency": alternate}:
                fail("No-op currency PATCH mismatch")
        verify = SessionLocal()
        try:
            current = verify.execute(select(AppSetting).where(AppSetting.key == DEFAULT_CURRENCY_KEY)).scalar_one()
            if current.value_json != alternate or current.value_text != alternate:
                fail("Currency setting was not persisted consistently")
            audits = [a for a in verify.execute(select(AuditLog).where(AuditLog.event_type == "settings.currency_updated").order_by(AuditLog.id)).scalars() if a.id not in existing_audits]
            if len(audits) != 1: fail(f"Expected one currency audit, got {len(audits)}")
            audit = audits[0]; audit_ids = [audit.id]
            if audit.before_json != {"currency": initial.currency} or audit.after_json != {"currency": alternate}:
                fail("Currency audit before/after mismatch")
            if audit.metadata_json.get("formatting_only") is not True or audit.metadata_json.get("historical_snapshots_preserved") is not True:
                fail("Currency audit semantics missing")
        finally: verify.close()
        cleanup = SessionLocal()
        try:
            row = cleanup.execute(select(AppSetting).where(AppSetting.key == DEFAULT_CURRENCY_KEY)).scalar_one()
            row.value_json, row.value_text, row.updated_at = original
            if audit_ids: cleanup.query(AuditLog).filter(AuditLog.id.in_(audit_ids)).delete(synchronize_session=False)
            if session_id is not None:
                session = cleanup.get(UserSession, session_id)
                if session is not None: cleanup.delete(session)
            cleanup.commit()
        finally: cleanup.close()
        restore_sequences(before)
        if database_snapshot() != before: fail("Currency settings smoke did not restore exact database")
    except Exception:
        db.rollback(); raise
    finally: db.close()
    print("[PASS] Currency preference is authenticated, normalized, audited once, reflected by setup status, formatting-only, and restores the exact copied database")

def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--check-only", action="store_true"); args=parser.parse_args()
    check_only() if args.check_only else full_flow()
if __name__ == "__main__": main()
