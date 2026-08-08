from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AuditLog, McpDirectAuth, User, UserSession
from app.services.auth import create_session
from app.services.mcp_direct_auth import (
    McpDirectAuthNetworkError,
    configure_trusted_networks,
    normalize_trusted_networks,
    trusted_networks_for_record,
)


# PARTPILOT:MCP_TRUSTED_NETWORK_MANAGEMENT_SMOKE:V503
SECRET_FILE = Path("/data/.partpilot-instance-secret")


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def sqlite_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"SQLite required, got {url!r}")
    return Path(url[len(prefix):]).resolve()


def snapshot() -> dict[str, object]:
    connection = sqlite3.connect(sqlite_path())
    connection.row_factory = sqlite3.Row
    try:
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        rows = {table: [dict(row) for row in connection.execute(
            f'SELECT * FROM "{table}" ORDER BY rowid'
        )] for table in tables}
        has_sequence = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='sqlite_sequence'"
        ).fetchone() is not None
        sequences = ([tuple(row) for row in connection.execute(
            "SELECT name,seq FROM sqlite_sequence ORDER BY name"
        )] if has_sequence else [])
        return {"rows": rows, "has_sequence": has_sequence, "sequences": sequences}
    finally:
        connection.close()


def restore_sequences(before: dict[str, object]) -> None:
    connection = sqlite3.connect(sqlite_path())
    try:
        has_sequence = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='sqlite_sequence'"
        ).fetchone() is not None
        if before["has_sequence"]:
            if not has_sequence:
                fail("sqlite_sequence disappeared")
            connection.execute("DELETE FROM sqlite_sequence")
            connection.executemany(
                "INSERT INTO sqlite_sequence(name,seq) VALUES (?,?)",
                before["sequences"],
            )
            connection.commit()
        elif has_sequence:
            current = list(connection.execute(
                "SELECT name,seq FROM sqlite_sequence ORDER BY name"
            ))
            if current:
                fail(f"Unexpected sequence rows: {current}")
    finally:
        connection.close()


def restore_direct_baseline(before: dict[str, object]) -> None:
    connection = sqlite3.connect(sqlite_path())
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("DELETE FROM mcp_direct_auth")
        for row in before["rows"]["mcp_direct_auth"]:
            columns = list(row)
            connection.execute(
                f'INSERT INTO mcp_direct_auth ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})',
                tuple(row[column] for column in columns),
            )
        keys = ("mcp.direct_clients_enabled", "mcp.direct_no_auth_enabled")
        connection.executemany("DELETE FROM app_settings WHERE key=?", [(key,) for key in keys])
        for row in before["rows"]["app_settings"]:
            if row["key"] not in keys:
                continue
            columns = list(row)
            connection.execute(
                f'INSERT INTO app_settings ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})',
                tuple(row[column] for column in columns),
            )
        connection.commit()
    finally:
        connection.close()


def assert_no_store(response) -> None:
    if response.headers.get("cache-control") != "no-store" or response.headers.get("pragma") != "no-cache":
        fail("Trusted-network response is cacheable")


def main() -> None:
    before = snapshot()
    secret_before = SECRET_FILE.read_bytes() if SECRET_FILE.exists() else None
    db = SessionLocal()
    session_id = None
    baseline_audit_id = 0
    try:
        if db.query(McpDirectAuth).count() != 1:
            fail("Trusted-network smoke requires the migrated disabled legacy row")
        legacy = db.get(McpDirectAuth, 1)
        if legacy is None or legacy.mode != "disabled" or legacy.enabled:
            fail("Trusted-network migrated legacy row has unexpected state")
        user = db.execute(select(User).where(User.is_active.is_(True)).order_by(User.id)).scalars().first()
        if user is None:
            fail("One active user is required")
        baseline_audit_id = int(db.execute(select(func.max(AuditLog.id))).scalar() or 0)

        canonical = normalize_trusted_networks(["2001:db8::7/64", "192.168.1.7/24"])
        if canonical != ["192.168.1.0/24", "2001:db8::/64"]:
            fail(f"Unexpected canonical CIDRs: {canonical}")
        for invalid in ([], ["0.0.0.0/0"], ["::/0"], ["224.0.0.0/4"], ["ff00::/8"], ["bad"], ["192.168.1.0/24", "192.168.1.2/32"]):
            try:
                normalize_trusted_networks(invalid)
            except McpDirectAuthNetworkError:
                pass
            else:
                fail(f"Unsafe trusted-network list was accepted: {invalid}")

        record = configure_trusted_networks(
            db, actor_user_id=user.id, networks=["10.7.8.9/24"], commit=False
        )
        if record.mode != "trusted_network" or trusted_networks_for_record(record) != ["10.7.8.0/24"]:
            fail("Service stored the wrong trusted-network configuration")
        if any((record.key_ciphertext, record.key_digest, record.key_prefix, record.custom_header_name)):
            fail("Trusted-network service retained direct-key material")
        db.rollback()

        issued = create_session(
            db, user=user, user_agent="Patch 503 trusted-network smoke",
            ip_address="127.0.0.1", commit=False
        )
        session_id = issued.session.id
        db.commit()
        headers = {"Authorization": f"Bearer {issued.token}"}
        from app.main import app
        with TestClient(app) as client:
            unauth = client.post(
                "/api/settings/mcp/direct-auth/trusted-network",
                json={"networks": ["192.168.50.0/24"]},
            )
            if unauth.status_code != 401:
                fail(f"Unauthenticated trusted-network API returned {unauth.status_code}")
            for invalid in (["0.0.0.0/0"], ["192.168.1.0/24", "192.168.1.5/32"], ["bad"]):
                response = client.post(
                    "/api/settings/mcp/direct-auth/trusted-network",
                    headers=headers, json={"networks": invalid},
                )
                assert_no_store(response)
                if response.status_code != 422:
                    fail(f"Invalid trusted networks returned {response.status_code}: {response.text}")
            configured = client.post(
                "/api/settings/mcp/direct-auth/trusted-network",
                headers=headers,
                json={"networks": ["2001:db8::5/64", "192.168.50.27/24"]},
            )
            assert_no_store(configured)
            if configured.status_code != 200:
                fail(f"Trusted-network configuration failed: {configured.status_code} {configured.text}")
            expected = {
                "mode": "trusted_network", "configured": True,
                "masked_key": None, "custom_header_name": None,
                "trusted_networks": ["192.168.50.0/24", "2001:db8::/64"],
                "rotated_at": None, "last_used_at": None,
            }
            if configured.json() != expected:
                fail(f"Unexpected trusted-network status: {configured.text}")
            reveal = client.post(
                "/api/settings/mcp/direct-auth/reveal", headers=headers
            )
            assert_no_store(reveal)
            if reveal.status_code != 409:
                fail(f"Trusted-network mode unexpectedly revealed a key: {reveal.status_code}")
            status = client.get("/api/settings/mcp/direct-auth", headers=headers)
            if status.json() != expected:
                fail(f"Trusted-network status was not persisted: {status.text}")
            disabled = client.delete("/api/settings/mcp/direct-auth", headers=headers)
            if disabled.status_code != 200 or disabled.json().get("trusted_networks") != []:
                fail(f"Disable did not clear trusted networks: {disabled.text}")

        audits = db.execute(select(AuditLog).where(AuditLog.id > baseline_audit_id).order_by(AuditLog.id)).scalars().all()
        events = [row.event_type for row in audits]
        if events != ["settings.mcp_trusted_networks_configured", "settings.mcp_direct_auth_disabled"]:
            fail(f"Unexpected trusted-network audits: {events}")
        payload = json.dumps([{"before": row.before_json, "after": row.after_json, "metadata": row.metadata_json} for row in audits], sort_keys=True, default=str)
        if "key_ciphertext" in payload or "key_digest" in payload:
            fail("Trusted-network audit contains key material")

        cleanup = SessionLocal()
        try:
            cleanup.query(AuditLog).filter(AuditLog.id > baseline_audit_id).delete(synchronize_session=False)
            if session_id is not None:
                row = cleanup.get(UserSession, session_id)
                if row is not None:
                    cleanup.delete(row)
            cleanup.commit()
        finally:
            cleanup.close()
        restore_direct_baseline(before)
        restore_sequences(before)
        if snapshot() != before:
            fail("Trusted-network smoke cleanup mismatch")
    finally:
        db.rollback()
        db.close()
        if secret_before is None:
            SECRET_FILE.unlink(missing_ok=True)
        else:
            SECRET_FILE.write_bytes(secret_before)
            os.chmod(SECRET_FILE, 0o600)
    print("MCP trusted-network management smoke PASS")


if __name__ == "__main__":
    main()
