from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import sqlite3
import tempfile

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal, dispose_database_engine
from app.models import UserSession
from app.services.auth import create_user

# PARTPILOT:SESSION_REQUEST_METADATA_SMOKE:V605


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def db_path() -> Path:
    from app.core.config import get_settings
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"SQLite required, got {url!r}")
    return Path(url[len(prefix):]).resolve()


def snapshot():
    connection = sqlite3.connect(db_path())
    connection.row_factory = sqlite3.Row
    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        rows = {
            table: [
                dict(row)
                for row in connection.execute(
                    f'SELECT * FROM "{table}" ORDER BY rowid'
                )
            ]
            for table in tables
        }
        sequence = []
        if connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='sqlite_sequence'"
        ).fetchone():
            sequence = [
                tuple(row)
                for row in connection.execute(
                    "SELECT name,seq FROM sqlite_sequence ORDER BY name"
                )
            ]
        return rows, sequence
    finally:
        connection.close()


def backup() -> Path:
    fd, raw = tempfile.mkstemp(prefix="pp605_", suffix=".db")
    os.close(fd)
    target = Path(raw)
    source = sqlite3.connect(db_path())
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return target


def restore(source_path: Path) -> None:
    dispose_database_engine()
    for suffix in ("-wal", "-shm", "-journal"):
        Path(str(db_path()) + suffix).unlink(missing_ok=True)
    source = sqlite3.connect(source_path)
    destination = sqlite3.connect(db_path())
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    dispose_database_engine()


def check_only() -> None:
    from app.api.routes import auth as auth_route
    if auth_route.MAX_SESSION_USER_AGENT_CHARS != 1024:
        fail("session User-Agent limit changed")
    source = Path(auth_route.__file__).read_text(encoding="utf-8")
    if source.count("_session_request_metadata(request)") != 2:
        fail("setup/login do not both use session request metadata")
    if source.count("user_agent=user_agent") != 2:
        fail("setup/login do not both pass User-Agent metadata")
    if source.count("ip_address=ip_address") != 2:
        fail("setup/login do not both pass IP metadata")
    print("[PASS] setup/login session-request metadata source contract")


def full() -> None:
    before = snapshot()
    backup_path = backup()
    suffix = secrets.token_hex(5)
    username = f"patch605_session_meta_{suffix}"
    password = "Patch605-session-metadata-password"
    try:
        db = SessionLocal()
        try:
            user = create_user(
                db,
                username=username,
                display_name="Patch 605 Session Metadata",
                password=password,
                commit=True,
            )
            user_id = int(user.id)
        finally:
            db.close()

        from app.main import app
        with TestClient(
            app,
            client=("198.51.100.44", 43111),
        ) as client:
            first = client.post(
                "/api/auth/login",
                headers={
                    "User-Agent": "Patch 605 Browser/1.0",
                    "X-Forwarded-For": "203.0.113.99",
                },
                json={"username": username, "password": password},
            )
            if first.status_code != 200:
                fail(
                    f"metadata login failed: "
                    f"{first.status_code} {first.text[:300]}"
                )

            long_agent = "Patch605/" + ("x" * 1400)
            second = client.post(
                "/api/auth/login",
                headers={"User-Agent": long_agent},
                json={"username": username, "password": password},
            )
            if second.status_code != 200:
                fail(
                    f"long User-Agent login failed: "
                    f"{second.status_code} {second.text[:300]}"
                )

        db = SessionLocal()
        try:
            sessions = list(
                db.execute(
                    select(UserSession)
                    .where(UserSession.user_id == user_id)
                    .order_by(UserSession.id)
                ).scalars()
            )
            if len(sessions) != 2:
                fail(f"expected two login sessions, found {len(sessions)}")
            if sessions[0].user_agent != "Patch 605 Browser/1.0":
                fail(
                    f"first User-Agent mismatch: "
                    f"{sessions[0].user_agent!r}"
                )
            if sessions[0].ip_address != "198.51.100.44":
                fail(
                    "untrusted forwarded address was accepted or peer IP lost: "
                    f"{sessions[0].ip_address!r}"
                )
            if sessions[1].user_agent != long_agent[:1024]:
                fail(
                    "long User-Agent was not clipped safely: "
                    f"{len(sessions[1].user_agent or '')}"
                )
            if sessions[1].ip_address != "198.51.100.44":
                fail(
                    f"second peer IP mismatch: "
                    f"{sessions[1].ip_address!r}"
                )
        finally:
            db.close()
    finally:
        restore(backup_path)
        backup_path.unlink(missing_ok=True)

    if snapshot() != before:
        fail("exact logical restore failed after session metadata smoke")

    print(
        "[PASS] login captures bounded User-Agent and trusted-resolver client IP, "
        "ignores spoofed untrusted X-Forwarded-For and restores copied DB exactly"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    check_only() if args.check_only else full()


if __name__ == "__main__":
    main()
