from __future__ import annotations

from contextlib import contextmanager

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import exc, text

from app.core.security import hash_password, verify_password
from app.db.constants import FIELD_TYPES, MOVEMENT_TYPES, PROJECT_STATUSES, RESERVATION_STATUSES
from app.db.session import SessionLocal, engine
from app.db.settings import get_bool_setting, get_str_setting, set_app_setting
from app.db.utils import available_quantity, display_part_title, normalize_location_name, slugify
from app.models import Part
from app.services.auth import (
    authenticate_user,
    create_first_user,
    create_session,
    create_user,
    get_user_by_session_token,
    hash_session_token,
    is_setup_complete,
    logout_session,
)


EXPECTED_PART_TYPES = 34
EXPECTED_AUTH_SCHEMA_HEAD = "0003_user_display_name"
MIN_TEMPLATE_FIELDS = 140
EXPECTED_SETTINGS = {
    "setup.completed",
    "app.display_name",
    "appearance.theme",
    "search.show_out_of_stock_section",
    "price.warn_when_missing",
    "backups.path",
    "mcp.enabled",
    "mcp.write_tools_enabled",
}


class SmokeFailure(RuntimeError):
    pass


def ok(message: str) -> None:
    print(f"[PASS] {message}")


def fail(message: str) -> None:
    raise SmokeFailure(message)


@contextmanager
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connects() -> None:
    with db_session() as db:
        value = db.execute(text("select 1")).scalar()
        if value != 1:
            fail("Database returned unexpected result for select 1")
    ok("Database connection works")


def check_sqlite_foreign_keys() -> None:
    if not str(engine.url).startswith("sqlite"):
        ok("Foreign key PRAGMA check skipped for non-SQLite database")
        return

    with db_session() as db:
        value = db.execute(text("PRAGMA foreign_keys")).scalar()
        if value != 1:
            fail(f"SQLite foreign keys are not enabled. Got: {value!r}")
    ok("SQLite foreign keys are enabled")


def check_alembic_at_head() -> None:
    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    heads = set(script.get_heads())

    with db_session() as db:
        current_rows = db.execute(text("select version_num from alembic_version")).fetchall()

    current = {row[0] for row in current_rows}
    if current != heads:
        fail(f"Alembic is not at head. current={sorted(current)} heads={sorted(heads)}")

    ok(f"Alembic is at head: {', '.join(sorted(current))}")


def check_seed_data() -> None:
    with db_session() as db:
        part_type_count = db.execute(text("select count(*) from part_types")).scalar()
        field_count = db.execute(text("select count(*) from part_type_fields")).scalar()
        settings_count = db.execute(text("select count(*) from app_settings")).scalar()

        missing_settings = []
        for key in EXPECTED_SETTINGS:
            exists = db.execute(
                text("select 1 from app_settings where key = :key"),
                {"key": key},
            ).scalar()
            if exists != 1:
                missing_settings.append(key)

    if part_type_count != EXPECTED_PART_TYPES:
        fail(f"Expected {EXPECTED_PART_TYPES} built-in part types, got {part_type_count}")

    if field_count < MIN_TEMPLATE_FIELDS:
        fail(f"Expected at least {MIN_TEMPLATE_FIELDS} template fields, got {field_count}")

    if missing_settings:
        fail(f"Missing default app settings: {', '.join(sorted(missing_settings))}")

    ok(f"Built-in part types exist: {part_type_count}")
    ok(f"Template fields exist: {field_count}")
    ok(f"Default app settings exist: {settings_count}")


def check_invalid_part_rejected() -> None:
    with db_session() as db:
        try:
            first_type_id = db.execute(text("select id from part_types order by id limit 1")).scalar()
            if first_type_id is None:
                fail("Cannot test invalid part without at least one part type")

            db.add(
                Part(
                    part_type_id=first_type_id,
                    name="",
                    part_number="",
                    total_quantity=0,
                    reserved_quantity=0,
                )
            )
            db.flush()
        except exc.IntegrityError:
            db.rollback()
            ok("Invalid part without name/part number is rejected")
            return
        except Exception:
            db.rollback()
            raise
        else:
            db.rollback()
            fail("Invalid part without name/part number was accepted")


def check_valid_part_insert_rolls_back() -> None:
    with db_session() as db:
        try:
            mosfet_type_id = db.execute(
                text("select id from part_types where name = 'MOSFET'")
            ).scalar()
            if mosfet_type_id is None:
                fail("Cannot test valid sample part because MOSFET type is missing")

            sample = Part(
                part_type_id=mosfet_type_id,
                part_number="SMOKE-TEST-IRFZ44N",
                name="Smoke Test IRFZ44N",
                package="TO-220",
                total_quantity=10,
                reserved_quantity=2,
            )
            db.add(sample)
            db.flush()

            inserted = db.execute(
                text("select total_quantity - reserved_quantity from parts where id = :id"),
                {"id": sample.id},
            ).scalar()

            if inserted != 8:
                fail(f"Valid sample part inserted but available quantity calculation was unexpected: {inserted!r}")

            db.rollback()

            remaining = db.execute(
                text("select count(*) from parts where part_number = 'SMOKE-TEST-IRFZ44N'")
            ).scalar()
            if remaining != 0:
                fail("Smoke test sample part was not rolled back")
        except Exception:
            db.rollback()
            raise

    ok("Valid sample part can be inserted and rolled back")


def check_backend_db_helpers() -> None:
    if display_part_title(" IRFZ44N ", "MOSFET") != "IRFZ44N":
        fail("display_part_title did not prefer part_number")

    if display_part_title(None, " MOSFET ") != "MOSFET":
        fail("display_part_title did not fall back to name")

    if available_quantity(10, 2) != 8:
        fail("available_quantity returned unexpected result")

    if normalize_location_name("  Drawer   A1  ") != "drawer a1":
        fail("normalize_location_name returned unexpected result")

    if slugify("RGB LED") != "rgb-led":
        fail("slugify returned unexpected result")

    required_field_types = {"text", "number", "boolean", "dropdown", "url", "unit_value"}
    if not required_field_types.issubset(FIELD_TYPES):
        fail("FIELD_TYPES is missing expected values")

    if "consume" not in MOVEMENT_TYPES:
        fail("MOVEMENT_TYPES is missing consume")

    if "active" not in PROJECT_STATUSES or "active" not in RESERVATION_STATUSES:
        fail("Status constants are missing active")

    with db_session() as db:
        app_name = get_str_setting(db, "app.display_name")
        if app_name != "Part Pilot":
            fail(f"get_str_setting returned unexpected app.display_name: {app_name!r}")

        setup_done = get_bool_setting(db, "setup.completed", True)
        if setup_done is not False:
            fail(f"get_bool_setting returned unexpected setup.completed: {setup_done!r}")

        try:
            set_app_setting(db, "smoke.test.setting", {"ok": True}, text_value="temporary", commit=False)
            db.flush()

            db.execute(text("delete from app_settings where key = 'smoke.test.setting'"))
            db.flush()
            db.rollback()
        except Exception:
            db.rollback()
            raise

    ok("Backend DB utilities work")



def check_phase3_auth_foundation() -> None:
    password_hash = hash_password("partpilot-smoke-password")

    if password_hash == "partpilot-smoke-password":
        fail("Password hashing returned the plain password")

    if not verify_password("partpilot-smoke-password", password_hash):
        fail("Password verification rejected the correct password")

    if verify_password("wrong-password", password_hash):
        fail("Password verification accepted the wrong password")

    with db_session() as db:
        user_columns = {
            row[1]
            for row in db.execute(text("PRAGMA table_info(users)")).fetchall()
        }
        session_columns = {
            row[1]
            for row in db.execute(text("PRAGMA table_info(sessions)")).fetchall()
        }

        required_user_columns = {
            "id",
            "username",
            "display_name",
            "password_hash",
            "is_active",
            "last_login_at",
            "created_at",
            "updated_at",
        }
        required_session_columns = {
            "id",
            "user_id",
            "token_hash",
            "expires_at",
            "revoked_at",
            "created_at",
            "updated_at",
        }

        missing_user_columns = required_user_columns - user_columns
        missing_session_columns = required_session_columns - session_columns

        if missing_user_columns:
            fail(f"users table is missing auth columns: {sorted(missing_user_columns)}")

        if missing_session_columns:
            fail(f"sessions table is missing auth columns: {sorted(missing_session_columns)}")

    ok("Phase 3 auth foundation works")



def check_phase3_auth_service() -> None:
    username = "smoke_auth_service_user"
    password = "correct horse battery staple"
    display_name = "Smoke Auth Service User"

    with db_session() as db:
        try:
            db.execute(
                text("delete from sessions where user_id in (select id from users where username = :username)"),
                {"username": username},
            )
            db.execute(text("delete from users where username = :username"), {"username": username})
            db.flush()

            if is_setup_complete(db):
                user = create_user(
                    db,
                    username=f"  {username.upper()}  ",
                    display_name=display_name,
                    password=password,
                    commit=False,
                )
            else:
                user = create_first_user(
                    db,
                    username=f"  {username.upper()}  ",
                    display_name=display_name,
                    password=password,
                    commit=False,
                )
            db.flush()

            if user.username != username:
                fail(f"auth service did not normalize username: {user.username!r}")
            if user.display_name != display_name:
                fail(f"auth service did not store display name: {user.display_name!r}")

            if authenticate_user(db, username=username, password="wrong password") is not None:
                fail("authenticate_user accepted the wrong password")

            authenticated = authenticate_user(db, username=username.upper(), password=password)
            if authenticated is None or authenticated.id != user.id:
                fail("authenticate_user rejected the correct password")

            session_token = create_session(db, user=user, user_agent="smoke-test", ip_address="127.0.0.1", commit=False)
            db.flush()

            if not session_token.token:
                fail("create_session returned an empty token")
            if session_token.session.token_hash == session_token.token:
                fail("create_session stored the plain token instead of a hash")
            if session_token.session.token_hash != hash_session_token(session_token.token):
                fail("create_session stored an unexpected token hash")

            session_user = get_user_by_session_token(db, session_token.token)
            if session_user is None or session_user.id != user.id:
                fail("get_user_by_session_token did not resolve the active session")

            if not logout_session(db, session_token.token, commit=False):
                fail("logout_session did not revoke the active session")
            db.flush()

            if get_user_by_session_token(db, session_token.token) is not None:
                fail("get_user_by_session_token accepted a revoked session")

            db.rollback()
        except Exception:
            db.rollback()
            raise

    ok("Phase 3 auth service works")


def check_phase3_auth_api_routes() -> None:
    from app.main import app as fastapi_app

    # Newer FastAPI versions can keep internal _IncludedRouter objects in
    # app.routes, and those objects do not expose .path. The OpenAPI schema is
    # the stable public view of registered HTTP paths, so use that for the
    # smoke test.
    paths = set(fastapi_app.openapi().get("paths", {}).keys())
    expected = {
        "/api/auth/setup-status",
        "/api/auth/setup",
        "/api/auth/login",
        "/api/auth/me",
        "/api/auth/logout",
    }
    missing = sorted(expected - paths)
    if missing:
        fail(f"Missing auth API routes: {missing}")

    ok("Phase 3 auth API routes are registered")


def check_phase3_auth_api_flow() -> None:
    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app
    from app.services.auth import create_user, get_user_count

    username = "smoke_auth_api_user"
    display_name = "Smoke Auth API User"
    password = "correct horse battery staple"

    def cleanup_user() -> None:
        with db_session() as db:
            db.execute(
                text(
                    "delete from sessions "
                    "where user_id in "
                    "(select id from users where username = :username)"
                ),
                {"username": username},
            )
            db.execute(
                text("delete from users where username = :username"),
                {"username": username},
            )
            db.commit()

    cleanup_user()
    client = TestClient(fastapi_app)

    try:
        setup_status = client.get("/api/auth/setup-status")
        if setup_status.status_code != 200:
            fail(
                "GET /api/auth/setup-status returned "
                f"{setup_status.status_code}"
            )

        setup_status_json = setup_status.json()
        if "setup_complete" not in setup_status_json:
            fail(
                "GET /api/auth/setup-status response is missing "
                "setup_complete"
            )

        with db_session() as db:
            users_before = get_user_count(db)

        if users_before == 0:
            setup_response = client.post(
                "/api/auth/setup",
                json={
                    "username": username,
                    "display_name": display_name,
                    "password": password,
                },
            )
            if setup_response.status_code != 201:
                fail(
                    "POST /api/auth/setup returned "
                    f"{setup_response.status_code}: "
                    f"{setup_response.text}"
                )

            setup_json = setup_response.json()

            if setup_json.get("username") != username:
                fail(
                    "POST /api/auth/setup returned the wrong username: "
                    f"{setup_json}"
                )

            if setup_json.get("display_name") != display_name:
                fail(
                    "POST /api/auth/setup returned the wrong display name: "
                    f"{setup_json}"
                )

            if not setup_json.get("token"):
                fail(
                    "POST /api/auth/setup did not return a session token"
                )
        else:
            setup_response = client.post(
                "/api/auth/setup",
                json={
                    "username": "another_setup_user",
                    "display_name": "Another Setup User",
                    "password": password,
                },
            )

            if setup_response.status_code != 409:
                fail(
                    "POST /api/auth/setup should reject setup after "
                    f"users exist, got {setup_response.status_code}"
                )

            with db_session() as db:
                create_user(
                    db,
                    username=username,
                    display_name=display_name,
                    password=password,
                    commit=True,
                )

        bad_username_response = client.post(
            "/api/auth/setup",
            json={
                "username": "bad username",
                "display_name": display_name,
                "password": password,
            },
        )

        if bad_username_response.status_code not in (409, 422):
            fail(
                "POST /api/auth/setup should reject invalid usernames, "
                f"got {bad_username_response.status_code}"
            )

        bad_login = client.post(
            "/api/auth/login",
            json={
                "username": username,
                "password": "wrong password",
            },
        )

        if bad_login.status_code != 401:
            fail(
                "POST /api/auth/login accepted the wrong password: "
                f"{bad_login.status_code}"
            )

        login_response = client.post(
            "/api/auth/login",
            json={
                "username": username,
                "password": password,
            },
        )

        if login_response.status_code != 200:
            fail(
                "POST /api/auth/login returned "
                f"{login_response.status_code}: {login_response.text}"
            )

        login_json = login_response.json()
        token = login_json.get("token")

        if not token:
            fail("POST /api/auth/login did not return a token")

        if login_json.get("display_name") != display_name:
            fail(
                "POST /api/auth/login returned the wrong display name: "
                f"{login_json}"
            )

        me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        if me_response.status_code != 200:
            fail(
                "GET /api/auth/me returned "
                f"{me_response.status_code}: {me_response.text}"
            )

        me_json = me_response.json()

        if me_json.get("username") != username:
            fail(
                "GET /api/auth/me returned the wrong username: "
                f"{me_json}"
            )

        if me_json.get("display_name") != display_name:
            fail(
                "GET /api/auth/me returned the wrong display name: "
                f"{me_json}"
            )

        logout_response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )

        if logout_response.status_code != 200:
            fail(
                "POST /api/auth/logout returned "
                f"{logout_response.status_code}: {logout_response.text}"
            )

        if logout_response.json().get("ok") is not True:
            fail(
                "POST /api/auth/logout did not confirm revocation: "
                f"{logout_response.json()}"
            )

        revoked_me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        if revoked_me_response.status_code != 401:
            fail(
                "GET /api/auth/me accepted a revoked session: "
                f"{revoked_me_response.status_code}"
            )
    finally:
        cleanup_user()

    ok("Phase 3 auth API flow works")


def main() -> None:
    checks = [
        check_db_connects,
        check_sqlite_foreign_keys,
        check_alembic_at_head,
        check_seed_data,
        check_invalid_part_rejected,
        check_valid_part_insert_rolls_back,
        check_backend_db_helpers,
        check_phase3_auth_foundation,
        check_phase3_auth_service,
        check_phase3_auth_api_routes,
        check_phase3_auth_api_flow,
    ]

    for check in checks:
        check()

    print("[PASS] Phase 3 auth service smoke test completed")


if __name__ == "__main__":
    main()
