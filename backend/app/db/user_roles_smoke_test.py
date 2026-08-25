from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import tempfile

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.db.session import SessionLocal, dispose_database_engine
from app.main import app
from app.models import User
from app.services.auth import create_session, create_user
from app.services.authorization import (
    ROLE_ADMINISTRATOR,
    ROLE_OPERATOR,
    ROLE_OWNER,
    ROLE_VIEWER,
)

# PARTPILOT:USER_ROLE_AUTHORIZATION_SMOKE:V732
EXPECTED_HEAD = "0022_mcp_inventory_part_lifecycle"


class RoleSmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise RoleSmokeFailure(message)


def db_path() -> Path:
    from app.core.config import get_settings

    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"SQLite required, got {url!r}")
    return Path(url[len(prefix):]).resolve()


def snapshot() -> tuple[dict[str, list[tuple]], list[tuple]]:
    connection = sqlite3.connect(db_path())
    try:
        tables = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        rows = {
            table: list(connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid'))
            for table in tables
        }
        sequence: list[tuple] = []
        if connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='sqlite_sequence'"
        ).fetchone():
            sequence = list(
                connection.execute("SELECT name,seq FROM sqlite_sequence ORDER BY name")
            )
        return rows, sequence
    finally:
        connection.close()


def backup_database() -> Path:
    fd, raw = tempfile.mkstemp(prefix="pp732_roles_", suffix=".db")
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


def restore_database(source_path: Path) -> None:
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


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def main() -> None:
    before = snapshot()
    backup = backup_database()
    client = TestClient(app)
    try:
        with SessionLocal() as db:
            head = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            if head != EXPECTED_HEAD:
                fail(f"Expected Alembic {EXPECTED_HEAD}, got {head!r}")
            columns = {
                str(row[1])
                for row in db.execute(text('PRAGMA table_info("users")')).fetchall()
            }
            if "role" not in columns:
                fail("users.role is missing")
            table_sql = str(
                db.execute(
                    text(
                        "SELECT sql FROM sqlite_master "
                        "WHERE type='table' AND name='users'"
                    )
                ).scalar_one()
            )
            if "ck_users_role" not in table_sql:
                fail("users role check constraint is missing")
            indexes = {
                str(row[1])
                for row in db.execute(text('PRAGMA index_list("users")')).fetchall()
            }
            if "ix_users_role" not in indexes:
                fail("users role index is missing")
            invalid = db.execute(
                select(User.id).where(
                    User.role.not_in(
                        (ROLE_OWNER, ROLE_ADMINISTRATOR, ROLE_OPERATOR, ROLE_VIEWER)
                    )
                )
            ).first()
            if invalid is not None:
                fail(f"invalid stored user role: {invalid}")
            preexisting = list(db.execute(select(User).order_by(User.id)).scalars())
            if not preexisting or any(user.role != ROLE_OWNER for user in preexisting):
                fail("pre-role accounts were not preserved as Owners")

            owner = create_user(
                db,
                username="role_smoke_owner",
                display_name="Role Smoke Owner",
                password="RoleSmokeOwnerPassword!",
                role=ROLE_OWNER,
                commit=False,
            )
            db.flush()
            owner_token = create_session(db, user=owner, commit=False).token
            db.commit()
            owner_id = owner.id

        response = client.get("/api/auth/me", headers=bearer(owner_token))
        if response.status_code != 200 or response.json().get("role") != ROLE_OWNER:
            fail(f"Owner /auth/me role response failed: {response.status_code} {response.text}")

        def create_managed(username: str, role: str, actor_token: str = owner_token):
            response = client.post(
                "/api/auth/users",
                headers=bearer(actor_token),
                json={
                    "username": username,
                    "display_name": username.replace("_", " ").title(),
                    "password": "RoleSmokeManagedPassword!",
                    "role": role,
                },
            )
            if response.status_code != 201:
                fail(f"create {role} failed: {response.status_code} {response.text}")
            if response.json().get("role") != role:
                fail(f"create {role} returned wrong role: {response.json()}")
            return int(response.json()["id"])

        admin_id = create_managed("role_smoke_admin", ROLE_ADMINISTRATOR)
        operator_id = create_managed("role_smoke_operator", ROLE_OPERATOR)
        viewer_id = create_managed("role_smoke_viewer", ROLE_VIEWER)

        with SessionLocal() as db:
            admin = db.get(User, admin_id)
            operator = db.get(User, operator_id)
            viewer = db.get(User, viewer_id)
            if not admin or not operator or not viewer:
                fail("managed role fixtures disappeared")
            admin_token = create_session(db, user=admin, commit=False).token
            operator_token = create_session(db, user=operator, commit=False).token
            viewer_token = create_session(db, user=viewer, commit=False).token
            db.commit()

        response = client.post(
            "/api/auth/users",
            headers=bearer(admin_token),
            json={
                "username": "role_smoke_forbidden_admin",
                "display_name": "Forbidden Admin",
                "password": "RoleSmokeManagedPassword!",
                "role": ROLE_ADMINISTRATOR,
            },
        )
        if response.status_code != 403:
            fail(f"Administrator elevated another Administrator: {response.status_code}")

        response = client.post(
            "/api/auth/users",
            headers=bearer(admin_token),
            json={
                "username": "role_smoke_admin_viewer",
                "display_name": "Admin Viewer",
                "password": "RoleSmokeManagedPassword!",
                "role": ROLE_VIEWER,
            },
        )
        if response.status_code != 201:
            fail(f"Administrator could not create Viewer: {response.status_code} {response.text}")

        response = client.get("/api/parts?limit=1", headers=bearer(viewer_token))
        if response.status_code != 200:
            fail(f"Viewer read access failed: {response.status_code} {response.text}")
        response = client.post(
            "/api/parts/2147483647/quantity-adjustments",
            headers=bearer(viewer_token),
            json={"operation": "add", "quantity": 1, "reason": "role smoke"},
        )
        if response.status_code != 403:
            fail(f"Viewer write was not denied: {response.status_code} {response.text}")

        response = client.patch(
            "/api/settings/search",
            headers={**bearer(viewer_token), "Content-Type": "application/json"},
            json={"show_out_of_stock_section": True},
        )
        if response.status_code != 403:
            fail(f"Viewer workspace-setting write was not denied: {response.status_code}")

        response = client.get("/api/settings/search", headers=bearer(viewer_token))
        if response.status_code != 200:
            fail(f"Viewer workspace-setting read failed: {response.status_code} {response.text}")

        response = client.post(
            "/api/settings/api-keys",
            headers=bearer(viewer_token),
            json={"name": "viewer write key", "scopes": ["inventory:write"]},
        )
        if response.status_code != 403:
            fail(f"Viewer created write API key: {response.status_code} {response.text}")

        response = client.post(
            "/api/settings/api-keys",
            headers=bearer(operator_token),
            json={"name": "operator write key", "scopes": ["inventory:write"]},
        )
        if response.status_code != 201:
            fail(f"Operator could not create write key: {response.status_code} {response.text}")
        operator_key = response.json().get("key")
        if not isinstance(operator_key, str) or not operator_key.startswith("pp_api_"):
            fail("Operator API key response did not contain the one-time key")

        response = client.patch(
            f"/api/auth/users/{operator_id}",
            headers=bearer(owner_token),
            json={"role": ROLE_VIEWER},
        )
        if response.status_code != 200 or response.json().get("role") != ROLE_VIEWER:
            fail(f"Owner could not demote Operator: {response.status_code} {response.text}")
        response = client.post(
            "/api/parts/2147483647/quantity-adjustments",
            headers={"Authorization": f"Bearer {operator_key}"},
            json={"operation": "add", "quantity": 1, "reason": "role ceiling"},
        )
        if response.status_code != 403:
            fail(f"Demoted user's old write API key bypassed role ceiling: {response.status_code}")

        response = client.patch(
            f"/api/auth/users/{owner_id}",
            headers=bearer(admin_token),
            json={"role": ROLE_VIEWER},
        )
        if response.status_code != 403:
            fail(f"Administrator modified Owner access: {response.status_code}")

        response = client.post(
            f"/api/auth/users/{viewer_id}/force-password",
            headers=bearer(owner_token),
            json={"new_password": "RoleSmokeForcedPassword!"},
        )
        if response.status_code != 200 or int(response.json().get("revoked_sessions", 0)) < 1:
            fail(f"Owner force-reset did not revoke Viewer sessions: {response.status_code} {response.text}")
        response = client.get("/api/parts?limit=1", headers=bearer(viewer_token))
        if response.status_code != 401:
            fail(f"Force-reset Viewer session remained usable: {response.status_code}")

        with SessionLocal() as db:
            viewer = db.get(User, viewer_id)
            if viewer is None:
                fail("Viewer disappeared before session-revocation test")
            viewer_token = create_session(db, user=viewer, commit=True).token
        response = client.post(
            f"/api/auth/users/{viewer_id}/revoke-sessions",
            headers=bearer(owner_token),
        )
        if response.status_code != 200 or int(response.json().get("revoked_sessions", 0)) < 1:
            fail(f"Owner could not revoke Viewer sessions: {response.status_code} {response.text}")
        response = client.get("/api/parts?limit=1", headers=bearer(viewer_token))
        if response.status_code != 401:
            fail(f"Explicitly revoked Viewer session remained usable: {response.status_code}")

        response = client.patch(
            f"/api/auth/users/{viewer_id}",
            headers=bearer(owner_token),
            json={"is_active": False},
        )
        if response.status_code != 200 or response.json().get("is_active") is not False:
            fail(f"Owner could not disable Viewer: {response.status_code} {response.text}")
        response = client.patch(
            f"/api/auth/users/{viewer_id}",
            headers=bearer(owner_token),
            json={"is_active": True},
        )
        if response.status_code != 200 or response.json().get("is_active") is not True:
            fail(f"Owner could not reactivate Viewer: {response.status_code} {response.text}")

        delete_id = create_managed("role_smoke_delete_me", ROLE_VIEWER)
        response = client.request(
            "DELETE",
            f"/api/auth/users/{delete_id}",
            headers=bearer(owner_token),
            json={"confirmation_username": "wrong-user"},
        )
        if response.status_code != 409:
            fail(f"User deletion accepted wrong confirmation: {response.status_code}")
        response = client.request(
            "DELETE",
            f"/api/auth/users/{delete_id}",
            headers=bearer(owner_token),
            json={"confirmation_username": "role_smoke_delete_me"},
        )
        if response.status_code != 200:
            fail(f"Owner could not delete Viewer: {response.status_code} {response.text}")
        with SessionLocal() as db:
            if db.get(User, delete_id) is not None:
                fail("Deleted Viewer still exists")

        with SessionLocal() as db:
            db.execute(
                text(
                    "UPDATE users SET is_active=0 "
                    "WHERE role='owner' AND id != :fixture_owner"
                ),
                {"fixture_owner": owner_id},
            )
            db.commit()
        response = client.patch(
            f"/api/auth/users/{owner_id}",
            headers=bearer(owner_token),
            json={"role": ROLE_VIEWER},
        )
        if response.status_code != 409 or "last active Owner" not in response.text:
            fail(f"Last Owner demotion was not blocked: {response.status_code} {response.text}")

        document = client.get("/openapi.json").json()
        for path, method in (
            ("/api/auth/users", "get"),
            ("/api/auth/users", "post"),
            ("/api/auth/users/{user_id}", "patch"),
            ("/api/auth/users/{user_id}/force-password", "post"),
            ("/api/auth/users/{user_id}/revoke-sessions", "post"),
            ("/api/auth/users/{user_id}", "delete"),
        ):
            if method not in document.get("paths", {}).get(path, {}):
                fail(f"OpenAPI missing {method.upper()} {path}")

        print("[PASS] Owner/Administrator/Operator/Viewer schema, administration, last-Owner protection, REST role ceilings and API-key anti-escalation are valid")
    finally:
        client.close()
        restore_database(backup)
        backup.unlink(missing_ok=True)
        after = snapshot()
        if after != before:
            fail("Role smoke did not restore the copied database exactly")


if __name__ == "__main__":
    main()
