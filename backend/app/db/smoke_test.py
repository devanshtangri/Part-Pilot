from __future__ import annotations

from uuid import uuid4

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



from app.schemas.part_types import (
    PartTypeCreateRequest,
    PartTypeFieldCreateRequest,
)
from app.services.part_types import create_custom_part_type

EXPECTED_PART_TYPES = 34
EXPECTED_AUTH_SCHEMA_HEAD = "0005_packages"
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
        part_type_count = db.execute(text("select count(*) from part_types where is_builtin = 1")).scalar()
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

        setup_done = get_bool_setting(db, "setup.completed", False)
        if not isinstance(setup_done, bool):
            fail(
                "get_bool_setting did not return a boolean for "
                f"setup.completed: {setup_done!r}"
            )

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
        "/api/auth/complete-setup",
        "/api/auth/debug/reset-database",
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
    from app.models import AppSetting
    from app.services.auth import create_user, get_user_count

    username = "smoke_auth_api_user"
    display_name = "Smoke Auth API User"
    password = "correct horse battery staple"
    default_currency = "INR"
    timezone_name = "Asia/Kolkata"
    setting_keys = (
        "setup.completed",
        "currency.default",
        "timezone.default",
    )

    def snapshot_settings() -> dict[str, tuple[object, str | None] | None]:
        with db_session() as db:
            snapshot: dict[str, tuple[object, str | None] | None] = {}
            for key in setting_keys:
                row = (
                    db.query(AppSetting)
                    .filter(AppSetting.key == key)
                    .one_or_none()
                )
                snapshot[key] = (
                    None
                    if row is None
                    else (row.value_json, row.value_text)
                )
            return snapshot

    original_settings = snapshot_settings()

    def cleanup() -> None:
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

            for key, original in original_settings.items():
                row = (
                    db.query(AppSetting)
                    .filter(AppSetting.key == key)
                    .one_or_none()
                )

                if original is None:
                    if row is not None:
                        db.delete(row)
                    continue

                if row is None:
                    row = AppSetting(
                        key=key,
                        value_json=original[0],
                        value_text=original[1],
                    )
                    db.add(row)
                else:
                    row.value_json = original[0]
                    row.value_text = original[1]

            db.commit()

    cleanup()
    original_settings = snapshot_settings()
    client = TestClient(fastapi_app)

    try:
        setup_status = client.get("/api/auth/setup-status")
        if setup_status.status_code != 200:
            fail(
                "GET /api/auth/setup-status returned "
                f"{setup_status.status_code}"
            )

        setup_status_json = setup_status.json()
        for key in (
            "setup_complete",
            "account_exists",
            "default_currency",
            "timezone",
        ):
            if key not in setup_status_json:
                fail(
                    "GET /api/auth/setup-status response is missing "
                    f"{key}"
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
                    "default_currency": default_currency,
                    "timezone": timezone_name,
                },
            )

            if setup_response.status_code != 201:
                fail(
                    "POST /api/auth/setup returned "
                    f"{setup_response.status_code}: "
                    f"{setup_response.text}"
                )

            setup_json = setup_response.json()
            token = setup_json.get("token")

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

            if not token:
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
                    "default_currency": default_currency,
                    "timezone": timezone_name,
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

            token = None

        bad_username_response = client.post(
            "/api/auth/setup",
            json={
                "username": "bad username",
                "display_name": display_name,
                "password": password,
                "default_currency": default_currency,
                "timezone": timezone_name,
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

        complete_response = client.post(
            "/api/auth/complete-setup",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "default_currency": default_currency,
                "timezone": timezone_name,
            },
        )

        if complete_response.status_code != 200:
            fail(
                "POST /api/auth/complete-setup returned "
                f"{complete_response.status_code}: "
                f"{complete_response.text}"
            )

        complete_json = complete_response.json()
        if complete_json.get("setup_complete") is not True:
            fail(
                "POST /api/auth/complete-setup did not mark setup complete: "
                f"{complete_json}"
            )

        if complete_json.get("default_currency") != default_currency:
            fail(
                "POST /api/auth/complete-setup returned the wrong currency: "
                f"{complete_json}"
            )

        if complete_json.get("timezone") != timezone_name:
            fail(
                "POST /api/auth/complete-setup returned the wrong timezone: "
                f"{complete_json}"
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
        cleanup()

    ok("Phase 3 auth and application setup API flow works")





def check_phase4_part_types_service() -> None:
    from app.services.part_types import list_part_types

    with db_session() as db:
        collection = list_part_types(db)

    # PATCH 070: custom part types are valid service results
    if collection.total != (
        collection.builtin_count + collection.custom_count
    ):
        fail(
            "Part type service returned inconsistent collection counts: "
            f"total={collection.total}, "
            f"built_in={collection.builtin_count}, "
            f"custom={collection.custom_count}"
        )
    if len(collection.part_types) != collection.total:
        fail(
            "Part type service returned a list length that does not match "
            f"its total: list={len(collection.part_types)}, "
            f"total={collection.total}"
        )

    if collection.builtin_count != EXPECTED_PART_TYPES:
        fail(
            "Expected every seeded type to be built-in at this stage, got "
            f"{collection.builtin_count}"
        )

    if collection.total_fields < MIN_TEMPLATE_FIELDS:
        fail(
            "Part type service returned too few template fields: "
            f"{collection.total_fields}"
        )

    mosfet = next(
        (item for item in collection.part_types if item.name == "MOSFET"),
        None,
    )
    if mosfet is None:
        fail("Part type service did not return MOSFET")

    mosfet_keys = {field.field_key for field in mosfet.fields}
    required = {
        "channel_type",
        "max_voltage",
        "max_current",
        "rds_on",
        "logic_level",
        "package",
    }
    missing = required - mosfet_keys
    if missing:
        fail(f"MOSFET template is missing fields: {sorted(missing)}")

    ok("Phase 4 part type service returns seeded templates")


def check_phase4_part_types_api() -> None:
    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app

    username = "smoke_part_types_api_user"
    password = "part-types-smoke-password"

    def cleanup() -> None:
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

    cleanup()
    client = TestClient(fastapi_app)

    try:
        unauthenticated = client.get("/api/part-types")
        if unauthenticated.status_code != 401:
            fail(
                "GET /api/part-types should require authentication, got "
                f"{unauthenticated.status_code}"
            )

        with db_session() as db:
            user = create_user(
                db,
                username=username,
                display_name="Part Types Smoke User",
                password=password,
                commit=True,
            )
            session_token = create_session(db, user=user, commit=True)

        headers = {
            "Authorization": f"Bearer {session_token.token}",
        }
        response = client.get("/api/part-types", headers=headers)

        if response.status_code != 200:
            fail(
                "GET /api/part-types returned "
                f"{response.status_code}: {response.text}"
            )

        payload = response.json()
        # PATCH 070: custom part types are valid API results
        total = payload.get("total")
        builtin_count = payload.get("builtin_count")
        custom_count = payload.get("custom_count")

        if builtin_count != EXPECTED_PART_TYPES:
            fail(
                "GET /api/part-types returned the wrong built-in count: "
                f"{payload}"
            )
        if not isinstance(total, int):
            fail(
                "GET /api/part-types returned a non-integer total: "
                f"{payload}"
            )
        if not isinstance(custom_count, int):
            fail(
                "GET /api/part-types returned a non-integer custom count: "
                f"{payload}"
            )
        if total != builtin_count + custom_count:
            fail(
                "GET /api/part-types returned inconsistent collection counts: "
                f"{payload}"
            )

        part_types = payload.get("part_types")
        if not isinstance(part_types, list) or not part_types:
            fail("GET /api/part-types returned no part types")
        # PATCH 070: API list length matches total
        if len(part_types) != total:
            fail(
                "GET /api/part-types returned a list length that does not "
                f"match its total: list={len(part_types)}, total={total}"
            )

        mosfet = next(
            (
                item
                for item in part_types
                if item.get("name") == "MOSFET"
            ),
            None,
        )
        if mosfet is None:
            fail("GET /api/part-types did not return MOSFET")

        detail = client.get(
            f"/api/part-types/{mosfet['id']}",
            headers=headers,
        )
        if detail.status_code != 200:
            fail(
                "GET /api/part-types/{id} returned "
                f"{detail.status_code}: {detail.text}"
            )

        missing = client.get(
            "/api/part-types/999999999",
            headers=headers,
        )
        if missing.status_code != 404:
            fail(
                "GET /api/part-types/{id} should return 404 for a missing "
                f"type, got {missing.status_code}"
            )
    finally:
        cleanup()

    ok("Phase 4 part type API is protected and returns templates")



def check_custom_part_type_creation() -> None:
    suffix = uuid4().hex[:10]
    name = f"Smoke Custom Type {suffix}"

    with db_session() as db:
        payload = PartTypeCreateRequest(
            name=name,
            description="Temporary smoke-test template",
            fields=[
                PartTypeFieldCreateRequest(
                    field_key="manufacturer",
                    label="Manufacturer",
                    field_type="text",
                    is_required=True,
                ),
                PartTypeFieldCreateRequest(
                    field_key="mounting_style",
                    label="Mounting style",
                    field_type="dropdown",
                    options=["Through-hole", "Surface mount"],
                ),
            ],
        )

        created = create_custom_part_type(
            db,
            payload,
            actor_user_id=None,
            commit=False,
        )

        if created.is_builtin:
            fail("Created custom part type was marked built-in")
        if created.field_count != 2:
            fail(
                "Created custom part type returned an unexpected field count: "
                f"{created.field_count}"
            )
        if [field.sort_order for field in created.fields] != [0, 1]:
            fail("Created custom part type did not preserve field order")
        if created.fields[1].options != ["Through-hole", "Surface mount"]:
            fail("Created dropdown options were not persisted correctly")

        stored_count = db.execute(
            text("select count(*) from part_types where id = :id"),
            {"id": created.id},
        ).scalar()
        stored_field_count = db.execute(
            text(
                "select count(*) from part_type_fields "
                "where part_type_id = :part_type_id"
            ),
            {"part_type_id": created.id},
        ).scalar()

        if stored_count != 1 or stored_field_count != 2:
            fail("Custom part type transaction did not write expected rows")

        created_slug = created.slug
        db.rollback()

        remaining = db.execute(
            text("select count(*) from part_types where slug = :slug"),
            {"slug": created_slug},
        ).scalar()
        if remaining != 0:
            fail("Custom part type smoke-test rows were not rolled back")

    ok("Custom part types can be created with validated ordered fields")

# PATCH 079: custom part type update API smoke test
def check_custom_part_type_update_api() -> None:
    # PATCH 080: schema-compatible options payloads
    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app

    username = "smoke_part_type_update_user"
    password = "part-type-update-smoke-password"
    custom_name = "Smoke Editable Board"
    updated_name = "Smoke Editable Controller Board"
    custom_type_id: int | None = None

    def cleanup() -> None:
        with db_session() as db:
            if custom_type_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'part_type' "
                        "and entity_id = :entity_id"
                    ),
                    {"entity_id": custom_type_id},
                )
                db.execute(
                    text(
                        "delete from part_type_fields "
                        "where part_type_id = :part_type_id"
                    ),
                    {"part_type_id": custom_type_id},
                )
                db.execute(
                    text(
                        "delete from part_types where id = :part_type_id"
                    ),
                    {"part_type_id": custom_type_id},
                )

            db.execute(
                text(
                    "delete from sessions where user_id in "
                    "(select id from users where username = :username)"
                ),
                {"username": username},
            )
            db.execute(
                text("delete from users where username = :username"),
                {"username": username},
            )
            db.commit()

    cleanup()
    client = TestClient(fastapi_app)

    try:
        with db_session() as db:
            user = create_user(
                db,
                username=username,
                display_name="Part Type Update Smoke User",
                password=password,
                commit=True,
            )
            session_token = create_session(
                db,
                user=user,
                commit=True,
            )

        headers = {
            "Authorization": f"Bearer {session_token.token}",
        }

        create_response = client.post(
            "/api/part-types",
            headers=headers,
            json={
                "name": custom_name,
                "description": "Temporary editable smoke template",
                "fields": [
                    {
                        "field_key": "chipset",
                        "label": "Chipset",
                        "field_type": "text",
                        "is_required": True,
                        "options": [],
                        "default_unit": None,
                        "help_text": "Primary controller or chipset",
                    }
                ],
            },
        )
        if create_response.status_code != 201:
            fail(
                "POST /api/part-types for update smoke test returned "
                f"{create_response.status_code}: "
                f"{create_response.text}"
            )

        created = create_response.json()
        custom_type_id = created.get("id")
        if not isinstance(custom_type_id, int):
            fail(
                "POST /api/part-types did not return a custom type ID."
            )

        created_fields = created.get("fields")
        if (
            not isinstance(created_fields, list)
            or len(created_fields) != 1
            or not isinstance(created_fields[0].get("id"), int)
        ):
            fail(
                "POST /api/part-types did not return the created field ID."
            )

        original_field_id = created_fields[0]["id"]
        original_version = created.get("template_version")

        update_response = client.put(
            f"/api/part-types/{custom_type_id}",
            headers=headers,
            json={
                "name": updated_name,
                "description": "Updated temporary smoke template",
                "fields": [
                    {
                        "id": original_field_id,
                        "field_key": "controller_chip",
                        "label": "Controller chip",
                        "field_type": "text",
                        "is_required": True,
                        "options": [],
                        "default_unit": None,
                        "help_text": "Main processor or controller",
                    },
                    {
                        "id": None,
                        "field_key": "logic_voltage",
                        "label": "Logic voltage",
                        "field_type": "unit_value",
                        "is_required": False,
                        "options": [],
                        "default_unit": "V",
                        "help_text": "Nominal I/O voltage",
                    },
                ],
            },
        )
        if update_response.status_code != 200:
            fail(
                "PUT /api/part-types/{id} returned "
                f"{update_response.status_code}: "
                f"{update_response.text}"
            )

        updated = update_response.json()
        if updated.get("name") != updated_name:
            fail(
                "PUT /api/part-types/{id} returned the wrong name: "
                f"{updated}"
            )
        if updated.get("field_count") != 2:
            fail(
                "PUT /api/part-types/{id} returned the wrong field count: "
                f"{updated}"
            )
        if (
            not isinstance(original_version, int)
            or updated.get("template_version") != original_version + 1
        ):
            fail(
                "PUT /api/part-types/{id} did not increment the "
                f"template version: {updated}"
            )

        updated_fields = updated.get("fields")
        if not isinstance(updated_fields, list):
            fail(
                "PUT /api/part-types/{id} returned invalid fields."
            )

        controller_field = next(
            (
                item
                for item in updated_fields
                if item.get("field_key") == "controller_chip"
            ),
            None,
        )
        if (
            controller_field is None
            or controller_field.get("id") != original_field_id
        ):
            fail(
                "PUT /api/part-types/{id} did not preserve the "
                "existing field ID."
            )

        logic_field = next(
            (
                item
                for item in updated_fields
                if item.get("field_key") == "logic_voltage"
            ),
            None,
        )
        if (
            logic_field is None
            or logic_field.get("default_unit") != "V"
        ):
            fail(
                "PUT /api/part-types/{id} did not create the new "
                "unit-aware field correctly."
            )

        with db_session() as db:
            builtin_id = db.execute(
                text(
                    "select id from part_types "
                    "where is_builtin = 1 order by id limit 1"
                )
            ).scalar()

        builtin_response = client.put(
            f"/api/part-types/{builtin_id}",
            headers=headers,
            json={
                "name": "Should Not Update",
                "description": None,
                "fields": [
                    {
                        "id": None,
                        "field_key": "blocked",
                        "label": "Blocked",
                        "field_type": "text",
                        "is_required": False,
                        "options": [],
                        "default_unit": None,
                        "help_text": None,
                    }
                ],
            },
        )
        if builtin_response.status_code != 403:
            fail(
                "PUT /api/part-types/{id} should reject built-in "
                f"types with 403, got {builtin_response.status_code}."
            )

        with db_session() as db:
            audit_count = db.execute(
                text(
                    "select count(*) from audit_log "
                    "where event_type = 'part_type.updated' "
                    "and entity_id = :entity_id"
                ),
                {"entity_id": custom_type_id},
            ).scalar()

        if audit_count != 1:
            fail(
                "Custom part type update did not create exactly one "
                f"audit event: {audit_count!r}"
            )

    finally:
        cleanup()

    ok("Custom part types can be edited with protected ordered fields")

# PATCH 089: custom part type deletion API smoke test
def check_custom_part_type_delete_api() -> None:
    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app

    username = "smoke_part_type_delete_user"
    password = "part-type-delete-smoke-password"
    custom_type_id: int | None = None
    blocking_part_id: int | None = None

    def cleanup() -> None:
        with db_session() as db:
            if blocking_part_id is not None:
                db.execute(
                    text(
                        "delete from part_field_values "
                        "where part_id = :part_id"
                    ),
                    {"part_id": blocking_part_id},
                )
                db.execute(
                    text("delete from parts where id = :part_id"),
                    {"part_id": blocking_part_id},
                )

            if custom_type_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'part_type' "
                        "and entity_id = :entity_id"
                    ),
                    {"entity_id": custom_type_id},
                )
                db.execute(
                    text(
                        "delete from part_type_fields "
                        "where part_type_id = :part_type_id"
                    ),
                    {"part_type_id": custom_type_id},
                )
                db.execute(
                    text(
                        "delete from part_types "
                        "where id = :part_type_id"
                    ),
                    {"part_type_id": custom_type_id},
                )

            db.execute(
                text(
                    "delete from sessions where user_id in "
                    "(select id from users where username = :username)"
                ),
                {"username": username},
            )
            db.execute(
                text("delete from users where username = :username"),
                {"username": username},
            )
            db.commit()

    cleanup()
    client = TestClient(fastapi_app)

    try:
        with db_session() as db:
            user = create_user(
                db,
                username=username,
                display_name="Part Type Delete Smoke User",
                password=password,
                commit=True,
            )
            session_token = create_session(
                db,
                user=user,
                commit=True,
            )

        headers = {
            "Authorization": f"Bearer {session_token.token}",
        }

        create_response = client.post(
            "/api/part-types",
            headers=headers,
            json={
                "name": "Smoke Deletable Part Type",
                "description": "Temporary deletion smoke template",
                "fields": [
                    {
                        "field_key": "temporary_code",
                        "label": "Temporary code",
                        "field_type": "text",
                        "is_required": False,
                        "options": [],
                        "default_unit": None,
                        "help_text": None,
                    }
                ],
            },
        )
        if create_response.status_code != 201:
            fail(
                "POST /api/part-types for delete smoke returned "
                f"{create_response.status_code}: "
                f"{create_response.text}"
            )

        created = create_response.json()
        custom_type_id = created.get("id")
        if not isinstance(custom_type_id, int):
            fail(
                "Delete smoke setup did not return a custom type ID."
            )

        with db_session() as db:
            builtin_id = db.execute(
                text(
                    "select id from part_types "
                    "where is_builtin = 1 order by id limit 1"
                )
            ).scalar()

        builtin_response = client.delete(
            f"/api/part-types/{builtin_id}",
            headers=headers,
        )
        if builtin_response.status_code != 403:
            fail(
                "DELETE /api/part-types/{id} should reject built-in "
                f"types with 403, got {builtin_response.status_code}."
            )

        with db_session() as db:
            blocking_part = Part(
                part_type_id=custom_type_id,
                name="Deletion smoke blocking part",
                total_quantity=0,
                reserved_quantity=0,
            )
            db.add(blocking_part)
            db.commit()
            db.refresh(blocking_part)
            blocking_part_id = blocking_part.id

        conflict_response = client.delete(
            f"/api/part-types/{custom_type_id}",
            headers=headers,
        )
        if conflict_response.status_code != 409:
            fail(
                "DELETE /api/part-types/{id} should reject a used "
                f"type with 409, got {conflict_response.status_code}: "
                f"{conflict_response.text}"
            )

        with db_session() as db:
            db.execute(
                text("delete from parts where id = :part_id"),
                {"part_id": blocking_part_id},
            )
            db.commit()
        blocking_part_id = None

        delete_response = client.delete(
            f"/api/part-types/{custom_type_id}",
            headers=headers,
        )
        if delete_response.status_code != 200:
            fail(
                "DELETE /api/part-types/{id} returned "
                f"{delete_response.status_code}: "
                f"{delete_response.text}"
            )

        deleted = delete_response.json()
        if (
            deleted.get("id") != custom_type_id
            or deleted.get("deleted") is not True
        ):
            fail(
                "DELETE /api/part-types/{id} returned an unexpected "
                f"response: {deleted}"
            )

        with db_session() as db:
            remaining_type = db.execute(
                text(
                    "select count(*) from part_types "
                    "where id = :part_type_id"
                ),
                {"part_type_id": custom_type_id},
            ).scalar()
            remaining_fields = db.execute(
                text(
                    "select count(*) from part_type_fields "
                    "where part_type_id = :part_type_id"
                ),
                {"part_type_id": custom_type_id},
            ).scalar()
            audit_count = db.execute(
                text(
                    "select count(*) from audit_log "
                    "where event_type = 'part_type.deleted' "
                    "and entity_id = :entity_id"
                ),
                {"entity_id": custom_type_id},
            ).scalar()

        if remaining_type != 0:
            fail("Deleted custom part type still exists.")
        if remaining_fields != 0:
            fail("Deleted custom part type fields still exist.")
        if audit_count != 1:
            fail(
                "Custom part type deletion did not create exactly one "
                f"audit event: {audit_count!r}"
            )

    finally:
        cleanup()

    ok(
        "Custom part types delete safely with inventory usage safeguards"
    )

# PATCH 093: inventory part creation API smoke test
def check_inventory_part_creation_api() -> None:
    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app

    username = "smoke_inventory_part_user"
    password = "inventory-part-smoke-password"
    custom_type_id: int | None = None
    created_part_id: int | None = None

    def cleanup() -> None:
        with db_session() as db:
            if created_part_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'part' "
                        "and entity_id = :entity_id"
                    ),
                    {"entity_id": created_part_id},
                )
                db.execute(
                    text(
                        "delete from part_field_values "
                        "where part_id = :part_id"
                    ),
                    {"part_id": created_part_id},
                )
                db.execute(
                    text(
                        "delete from parts where id = :part_id"
                    ),
                    {"part_id": created_part_id},
                )

            if custom_type_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'part_type' "
                        "and entity_id = :entity_id"
                    ),
                    {"entity_id": custom_type_id},
                )
                db.execute(
                    text(
                        "delete from part_type_fields "
                        "where part_type_id = :part_type_id"
                    ),
                    {"part_type_id": custom_type_id},
                )
                db.execute(
                    text(
                        "delete from part_types "
                        "where id = :part_type_id"
                    ),
                    {"part_type_id": custom_type_id},
                )

            db.execute(
                text(
                    "delete from sessions where user_id in "
                    "(select id from users where username = :username)"
                ),
                {"username": username},
            )
            db.execute(
                text(
                    "delete from users where username = :username"
                ),
                {"username": username},
            )
            db.commit()

    cleanup()
    client = TestClient(fastapi_app)

    try:
        with db_session() as db:
            user = create_user(
                db,
                username=username,
                display_name="Inventory Part Smoke User",
                password=password,
                commit=True,
            )
            session_token = create_session(
                db,
                user=user,
                commit=True,
            )

        headers = {
            "Authorization": f"Bearer {session_token.token}",
        }

        protected_response = client.get("/api/parts")
        if protected_response.status_code not in {401, 403}:
            fail(
                "GET /api/parts should require authentication, got "
                f"{protected_response.status_code}."
            )

        type_response = client.post(
            "/api/part-types",
            headers=headers,
            json={
                "name": "Smoke Inventory Device",
                "description": "Temporary dynamic field test",
                "fields": [
                    {
                        "field_key": "manufacturer",
                        "label": "Manufacturer",
                        "field_type": "text",
                        "is_required": True,
                        "options": [],
                        "default_unit": None,
                        "help_text": None,
                    },
                    {
                        "field_key": "logic_voltage",
                        "label": "Logic voltage",
                        "field_type": "unit_value",
                        "is_required": True,
                        "options": [],
                        "default_unit": "V",
                        "help_text": None,
                    },
                    {
                        "field_key": "interface",
                        "label": "Interface",
                        "field_type": "dropdown",
                        "is_required": False,
                        "options": ["I2C", "SPI", "UART"],
                        "default_unit": None,
                        "help_text": None,
                    },
                    {
                        "field_key": "rohs",
                        "label": "RoHS compliant",
                        "field_type": "boolean",
                        "is_required": False,
                        "options": [],
                        "default_unit": None,
                        "help_text": None,
                    },
                ],
            },
        )
        if type_response.status_code != 201:
            fail(
                "Inventory smoke part type creation returned "
                f"{type_response.status_code}: {type_response.text}"
            )

        part_type = type_response.json()
        custom_type_id = part_type.get("id")
        fields = {
            field["field_key"]: field
            for field in part_type.get("fields", [])
        }

        if (
            not isinstance(custom_type_id, int)
            or set(fields) != {
                "manufacturer",
                "logic_voltage",
                "interface",
                "rohs",
            }
        ):
            fail(
                "Inventory smoke part type returned unexpected fields."
            )

        missing_required = client.post(
            "/api/parts",
            headers=headers,
            json={
                "part_type_id": custom_type_id,
                "name": "Incomplete smoke part",
                "total_quantity": 2,
                "field_values": [],
            },
        )
        if missing_required.status_code != 422:
            fail(
                "POST /api/parts should reject missing required "
                f"fields with 422, got {missing_required.status_code}: "
                f"{missing_required.text}"
            )

        invalid_dropdown = client.post(
            "/api/parts",
            headers=headers,
            json={
                "part_type_id": custom_type_id,
                "name": "Invalid dropdown smoke part",
                "total_quantity": 2,
                "field_values": [
                    {
                        "field_id": fields["manufacturer"]["id"],
                        "value_text": "Smoke Labs",
                    },
                    {
                        "field_id": fields["logic_voltage"]["id"],
                        "value_number": "3.3",
                        "unit": "V",
                    },
                    {
                        "field_id": fields["interface"]["id"],
                        "value_text": "CAN",
                    },
                ],
            },
        )
        if invalid_dropdown.status_code != 422:
            fail(
                "POST /api/parts should reject an invalid dropdown "
                f"with 422, got {invalid_dropdown.status_code}: "
                f"{invalid_dropdown.text}"
            )

        create_response = client.post(
            "/api/parts",
            headers=headers,
            json={
                "part_type_id": custom_type_id,
                "part_number": "SMOKE-INV-093",
                "name": "Smoke inventory device",
                "description": "Temporary persisted inventory record",
                "package": "Module",
                "notes": "Created by Patch 093 smoke coverage",
                "total_quantity": 7,
                "unit_price": "42.5000",
                "purchase_link": "https://example.com/smoke-part",
                "low_stock_enabled": True,
                "low_stock_threshold": 2,
                "field_values": [
                    {
                        "field_id": fields["manufacturer"]["id"],
                        "value_text": "Smoke Labs",
                    },
                    {
                        "field_id": fields["logic_voltage"]["id"],
                        "value_number": "3.3",
                        "unit": "V",
                    },
                    {
                        "field_id": fields["interface"]["id"],
                        "value_text": "I2C",
                    },
                    {
                        "field_id": fields["rohs"]["id"],
                        "value_bool": False,
                    },
                ],
            },
        )
        if create_response.status_code != 201:
            fail(
                "POST /api/parts returned "
                f"{create_response.status_code}: "
                f"{create_response.text}"
            )

        created = create_response.json()
        created_part_id = created.get("id")
        if not isinstance(created_part_id, int):
            fail("POST /api/parts did not return a part ID.")

        if (
            created.get("total_quantity") != 7
            or created.get("available_quantity") != 7
            or created.get("part_type_id") != custom_type_id
            or len(created.get("field_values", [])) != 4
        ):
            fail(
                "POST /api/parts returned an unexpected payload: "
                f"{created}"
            )

        detail_response = client.get(
            f"/api/parts/{created_part_id}",
            headers=headers,
        )
        if detail_response.status_code != 200:
            fail(
                "GET /api/parts/{id} returned "
                f"{detail_response.status_code}: "
                f"{detail_response.text}"
            )

        list_response = client.get(
            f"/api/parts?part_type_id={custom_type_id}",
            headers=headers,
        )
        if list_response.status_code != 200:
            fail(
                "GET /api/parts returned "
                f"{list_response.status_code}: "
                f"{list_response.text}"
            )

        collection = list_response.json()
        if (
            collection.get("total") != 1
            or collection.get("parts", [{}])[0].get("id")
            != created_part_id
        ):
            fail(
                "GET /api/parts did not return the created part."
            )

        duplicate_response = client.post(
            "/api/parts",
            headers=headers,
            json={
                "part_type_id": custom_type_id,
                "part_number": "SMOKE-INV-093",
                "name": "Duplicate smoke part",
                "total_quantity": 1,
                "field_values": [
                    {
                        "field_id": fields["manufacturer"]["id"],
                        "value_text": "Smoke Labs",
                    },
                    {
                        "field_id": fields["logic_voltage"]["id"],
                        "value_number": "5",
                    },
                ],
            },
        )
        if duplicate_response.status_code != 409:
            fail(
                "POST /api/parts should reject duplicate part "
                f"numbers with 409, got "
                f"{duplicate_response.status_code}."
            )

        with db_session() as db:
            value_count = db.execute(
                text(
                    "select count(*) from part_field_values "
                    "where part_id = :part_id"
                ),
                {"part_id": created_part_id},
            ).scalar()
            audit_count = db.execute(
                text(
                    "select count(*) from audit_log "
                    "where event_type = 'part.created' "
                    "and entity_id = :entity_id"
                ),
                {"entity_id": created_part_id},
            ).scalar()

        if value_count != 4:
            fail(
                "Created part did not persist all typed field values: "
                f"{value_count!r}"
            )
        if audit_count != 1:
            fail(
                "Created part did not create exactly one audit event: "
                f"{audit_count!r}"
            )

    finally:
        cleanup()

    ok(
        "Inventory parts can be created with validated dynamic fields"
    )

# PATCH 095: manufacturer catalogue API smoke test
def check_manufacturer_catalogue_api() -> None:
    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app

    username = "smoke_manufacturer_catalogue_user"
    password = "manufacturer-catalogue-smoke-password"
    custom_name = "Smoke Components Incorporated"
    custom_id: int | None = None

    def cleanup() -> None:
        with db_session() as db:
            if custom_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'manufacturer' "
                        "and entity_id = :entity_id"
                    ),
                    {"entity_id": custom_id},
                )
                db.execute(
                    text(
                        "delete from manufacturers "
                        "where id = :manufacturer_id"
                    ),
                    {"manufacturer_id": custom_id},
                )

            db.execute(
                text(
                    "delete from sessions where user_id in "
                    "(select id from users where username = :username)"
                ),
                {"username": username},
            )
            db.execute(
                text(
                    "delete from users where username = :username"
                ),
                {"username": username},
            )
            db.commit()

    cleanup()
    client = TestClient(fastapi_app)

    try:
        unauthenticated = client.get("/api/manufacturers")
        if unauthenticated.status_code not in {401, 403}:
            fail(
                "GET /api/manufacturers should require "
                f"authentication, got {unauthenticated.status_code}."
            )

        with db_session() as db:
            user = create_user(
                db,
                username=username,
                display_name="Manufacturer Catalogue Smoke User",
                password=password,
                commit=True,
            )
            session_token = create_session(
                db,
                user=user,
                commit=True,
            )

        headers = {
            "Authorization": f"Bearer {session_token.token}",
        }

        list_response = client.get(
            "/api/manufacturers",
            headers=headers,
        )
        if list_response.status_code != 200:
            fail(
                "GET /api/manufacturers returned "
                f"{list_response.status_code}: "
                f"{list_response.text}"
            )

        payload = list_response.json()
        names = {
            item.get("name")
            for item in payload.get("manufacturers", [])
        }
        expected = {
            "Espressif Systems",
            "Arduino",
            "NXP Semiconductors",
            "STMicroelectronics",
        }
        if not expected.issubset(names):
            fail(
                "Manufacturer catalogue is missing seeded names: "
                f"{sorted(expected - names)}"
            )

        create_response = client.post(
            "/api/manufacturers",
            headers=headers,
            json={"name": custom_name},
        )
        if create_response.status_code != 201:
            fail(
                "POST /api/manufacturers returned "
                f"{create_response.status_code}: "
                f"{create_response.text}"
            )

        created = create_response.json()
        custom_id = created.get("id")
        if (
            not isinstance(custom_id, int)
            or created.get("name") != custom_name
            or created.get("is_builtin") is not False
        ):
            fail(
                "POST /api/manufacturers returned an unexpected "
                f"payload: {created}"
            )

        duplicate_response = client.post(
            "/api/manufacturers",
            headers=headers,
            json={"name": f"  {custom_name.lower()}  "},
        )
        if duplicate_response.status_code != 409:
            fail(
                "POST /api/manufacturers should reject a normalized "
                f"duplicate with 409, got "
                f"{duplicate_response.status_code}."
            )

        with db_session() as db:
            audit_count = db.execute(
                text(
                    "select count(*) from audit_log "
                    "where event_type = 'manufacturer.created' "
                    "and entity_id = :entity_id"
                ),
                {"entity_id": custom_id},
            ).scalar()

        if audit_count != 1:
            fail(
                "Manufacturer creation did not create exactly one "
                f"audit event: {audit_count!r}"
            )

    finally:
        cleanup()

    ok(
        "Reusable manufacturer catalogue is seeded and extensible"
    )

# PATCH 128: package catalogue API smoke test
def check_package_catalogue_api() -> None:
    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app

    username = "smoke_package_catalogue_user"
    password = "package-catalogue-smoke-password"
    custom_name = f"Smoke Package {uuid4().hex[:10]}"
    custom_id: int | None = None

    def cleanup() -> None:
        with db_session() as db:
            if custom_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'package' "
                        "and entity_id = :entity_id"
                    ),
                    {"entity_id": custom_id},
                )
                db.execute(
                    text("delete from packages where id = :package_id"),
                    {"package_id": custom_id},
                )

            db.execute(
                text(
                    "delete from sessions where user_id in "
                    "(select id from users where username = :username)"
                ),
                {"username": username},
            )
            db.execute(
                text("delete from users where username = :username"),
                {"username": username},
            )
            db.commit()

    cleanup()
    client = TestClient(fastapi_app)

    try:
        unauthenticated = client.get("/api/packages")
        if unauthenticated.status_code not in {401, 403}:
            fail(
                "GET /api/packages should require authentication, "
                f"got {unauthenticated.status_code}."
            )

        with db_session() as db:
            user = create_user(
                db,
                username=username,
                display_name="Package Catalogue Smoke User",
                password=password,
                commit=True,
            )
            session_token = create_session(
                db,
                user=user,
                commit=True,
            )

        headers = {
            "Authorization": f"Bearer {session_token.token}",
        }
        list_response = client.get("/api/packages", headers=headers)
        if list_response.status_code != 200:
            fail(
                "GET /api/packages returned "
                f"{list_response.status_code}: {list_response.text}"
            )

        payload = list_response.json()
        names = {
            item.get("name")
            for item in payload.get("packages", [])
        }
        expected = {
            "TO-92",
            "TO-220",
            "SOT-23",
            "SOIC-8",
            "0603",
            "Development Board",
        }
        if not expected.issubset(names):
            fail(
                "Package catalogue is missing seeded names: "
                f"{sorted(expected - names)}"
            )

        with db_session() as db:
            existing_names = {
                " ".join(str(row[0]).split()).casefold()
                for row in db.execute(
                    text(
                        "select distinct package from parts "
                        "where package is not null "
                        "and length(trim(package)) > 0"
                    )
                ).all()
            }
            catalogue_names = {
                str(row[0])
                for row in db.execute(
                    text("select normalized_name from packages")
                ).all()
            }

        missing_backfill = existing_names - catalogue_names
        if missing_backfill:
            fail(
                "Existing Part.package values were not backfilled: "
                f"{sorted(missing_backfill)}"
            )

        create_response = client.post(
            "/api/packages",
            headers=headers,
            json={"name": custom_name},
        )
        if create_response.status_code != 201:
            fail(
                "POST /api/packages returned "
                f"{create_response.status_code}: {create_response.text}"
            )

        created = create_response.json()
        custom_id = created.get("id")
        if not isinstance(custom_id, int):
            fail("Created package did not include an integer id.")
        if created.get("name") != custom_name:
            fail("Created package name did not match the request.")
        if created.get("is_builtin") is not False:
            fail("Created package should be custom.")

        duplicate = client.post(
            "/api/packages",
            headers=headers,
            json={"name": f"  {custom_name.upper()}  "},
        )
        if duplicate.status_code != 409:
            fail(
                "Normalized duplicate package should return 409, got "
                f"{duplicate.status_code}."
            )

        refreshed = client.get("/api/packages", headers=headers)
        refreshed_names = {
            item.get("name")
            for item in refreshed.json().get("packages", [])
        }
        if custom_name not in refreshed_names:
            fail("Created package was not returned by the catalogue.")
    finally:
        cleanup()

    ok("Reusable package catalogue is seeded and extensible")

# PATCH 134: stock quantity adjustment and movement history smoke test
def check_stock_quantity_adjustment_api() -> None:
    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app

    username = "smoke_stock_adjustment_user"
    password = "stock-adjustment-smoke-password"
    part_number = f"SMOKE-STOCK-{uuid4().hex[:10]}"
    created_part_id: int | None = None
    user_id: int | None = None

    def cleanup() -> None:
        with db_session() as db:
            if created_part_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'part' "
                        "and entity_id = :entity_id"
                    ),
                    {"entity_id": created_part_id},
                )
                db.execute(
                    text(
                        "delete from stock_movements "
                        "where part_id = :part_id"
                    ),
                    {"part_id": created_part_id},
                )
                db.execute(
                    text(
                        "delete from part_field_values "
                        "where part_id = :part_id"
                    ),
                    {"part_id": created_part_id},
                )
                db.execute(
                    text("delete from parts where id = :part_id"),
                    {"part_id": created_part_id},
                )
            db.execute(
                text(
                    "delete from sessions where user_id in "
                    "(select id from users where username = :username)"
                ),
                {"username": username},
            )
            db.execute(
                text("delete from users where username = :username"),
                {"username": username},
            )
            db.commit()

    cleanup()
    client = TestClient(fastapi_app)

    try:
        unauthenticated_adjustment = client.post(
            "/api/parts/1/quantity-adjustments",
            json={"operation": "add", "quantity": 1},
        )
        if unauthenticated_adjustment.status_code not in {401, 403}:
            fail(
                "Quantity adjustment endpoint should require authentication, "
                f"got {unauthenticated_adjustment.status_code}."
            )
        unauthenticated_history = client.get("/api/parts/1/movements")
        if unauthenticated_history.status_code not in {401, 403}:
            fail(
                "Movement history endpoint should require authentication, "
                f"got {unauthenticated_history.status_code}."
            )

        with db_session() as db:
            user = create_user(
                db,
                username=username,
                display_name="Stock Adjustment Smoke User",
                password=password,
                commit=True,
            )
            user_id = user.id
            session_token = create_session(
                db,
                user=user,
                commit=True,
            )
            part_type_id = db.execute(
                text("select id from part_types order by id limit 1")
            ).scalar()
            if part_type_id is None:
                fail("Cannot test stock adjustments without a part type.")
            part = Part(
                part_type_id=part_type_id,
                part_number=part_number,
                name="Stock adjustment smoke part",
                total_quantity=10,
                reserved_quantity=2,
                low_stock_enabled=False,
                is_deleted=False,
            )
            db.add(part)
            db.commit()
            db.refresh(part)
            created_part_id = part.id

        headers = {
            "Authorization": f"Bearer {session_token.token}",
        }

        def post_adjustment(
            operation: str,
            quantity: int,
            *,
            reason: str | None = None,
            note: str | None = None,
        ):
            payload: dict[str, object] = {
                "operation": operation,
                "quantity": quantity,
            }
            if reason is not None:
                payload["reason"] = reason
            if note is not None:
                payload["note"] = note
            return client.post(
                f"/api/parts/{created_part_id}/quantity-adjustments",
                headers=headers,
                json=payload,
            )

        add_response = post_adjustment(
            "add",
            5,
            note="Purchase receipt smoke coverage",
        )
        if add_response.status_code != 200:
            fail(
                "Add-stock adjustment returned "
                f"{add_response.status_code}: {add_response.text}"
            )
        added = add_response.json()
        if (
            added.get("operation") != "add"
            or added.get("part", {}).get("total_quantity") != 15
            or added.get("movement", {}).get("movement_type") != "restock"
            or added.get("movement", {}).get("quantity_delta") != 5
            or added.get("movement", {}).get("quantity_before") != 10
            or added.get("movement", {}).get("quantity_after") != 15
            or not added.get("movement", {}).get("reason")
        ):
            fail(f"Unexpected add-stock response: {added}")

        remove_response = post_adjustment(
            "remove",
            3,
            reason="Damaged units removed",
        )
        if remove_response.status_code != 200:
            fail(
                "Remove-stock adjustment returned "
                f"{remove_response.status_code}: {remove_response.text}"
            )
        removed = remove_response.json()
        if (
            removed.get("part", {}).get("total_quantity") != 12
            or removed.get("movement", {}).get("movement_type") != "adjust"
            or removed.get("movement", {}).get("quantity_delta") != -3
            or removed.get("movement", {}).get("quantity_before") != 15
            or removed.get("movement", {}).get("quantity_after") != 12
        ):
            fail(f"Unexpected remove-stock response: {removed}")

        consume_response = post_adjustment(
            "consume",
            4,
            reason="Workbench consumption",
        )
        if consume_response.status_code != 200:
            fail(
                "Consume-stock adjustment returned "
                f"{consume_response.status_code}: {consume_response.text}"
            )
        consumed = consume_response.json()
        if (
            consumed.get("part", {}).get("total_quantity") != 8
            or consumed.get("movement", {}).get("movement_type") != "consume"
            or consumed.get("movement", {}).get("quantity_delta") != -4
            or consumed.get("movement", {}).get("quantity_before") != 12
            or consumed.get("movement", {}).get("quantity_after") != 8
        ):
            fail(f"Unexpected consume-stock response: {consumed}")

        correction_response = post_adjustment(
            "correction",
            -1,
            reason="Cycle count correction",
            note="Physical count found one fewer unit",
        )
        if correction_response.status_code != 200:
            fail(
                "Correction adjustment returned "
                f"{correction_response.status_code}: "
                f"{correction_response.text}"
            )
        corrected = correction_response.json()
        if (
            corrected.get("part", {}).get("total_quantity") != 7
            or corrected.get("movement", {}).get("movement_type") != "adjust"
            or corrected.get("movement", {}).get("quantity_delta") != -1
            or corrected.get("movement", {}).get("quantity_before") != 8
            or corrected.get("movement", {}).get("quantity_after") != 7
        ):
            fail(f"Unexpected correction response: {corrected}")

        below_reserved = post_adjustment(
            "remove",
            6,
            reason="Should fail reserved-stock guard",
        )
        if below_reserved.status_code != 422:
            fail(
                "Removing below reserved quantity should return 422, got "
                f"{below_reserved.status_code}: {below_reserved.text}"
            )

        zero_quantity = post_adjustment("add", 0)
        if zero_quantity.status_code != 422:
            fail(
                "Zero quantity adjustment should return 422, got "
                f"{zero_quantity.status_code}: {zero_quantity.text}"
            )

        correction_without_reason = post_adjustment("correction", 1)
        if correction_without_reason.status_code != 422:
            fail(
                "Correction without a reason should return 422, got "
                f"{correction_without_reason.status_code}: "
                f"{correction_without_reason.text}"
            )

        missing_part = client.post(
            "/api/parts/999999999/quantity-adjustments",
            headers=headers,
            json={"operation": "add", "quantity": 1},
        )
        if missing_part.status_code != 404:
            fail(
                "Quantity adjustment for a missing part should return 404, "
                f"got {missing_part.status_code}."
            )

        history_response = client.get(
            f"/api/parts/{created_part_id}/movements?limit=10",
            headers=headers,
        )
        if history_response.status_code != 200:
            fail(
                "Movement history returned "
                f"{history_response.status_code}: {history_response.text}"
            )
        history_payload = history_response.json()
        movements = history_payload.get("movements", [])
        expected_history = [
            ("adjust", -1, 8, 7),
            ("consume", -4, 12, 8),
            ("adjust", -3, 15, 12),
            ("restock", 5, 10, 15),
        ]
        actual_history = [
            (
                movement.get("movement_type"),
                movement.get("quantity_delta"),
                movement.get("quantity_before"),
                movement.get("quantity_after"),
            )
            for movement in movements
        ]
        if (
            history_payload.get("part_id") != created_part_id
            or actual_history != expected_history
        ):
            fail(
                "Movement history did not return the expected newest-first "
                f"records: {history_payload}"
            )

        detail_response = client.get(
            f"/api/parts/{created_part_id}",
            headers=headers,
        )
        if detail_response.status_code != 200:
            fail(
                "Part detail after adjustments returned "
                f"{detail_response.status_code}: {detail_response.text}"
            )
        detail = detail_response.json()
        if (
            detail.get("total_quantity") != 7
            or detail.get("reserved_quantity") != 2
            or detail.get("available_quantity") != 5
        ):
            fail(f"Part quantities were not updated correctly: {detail}")

        with db_session() as db:
            movement_rows = db.execute(
                text(
                    "select movement_type, quantity_delta, quantity_before, "
                    "quantity_after, reason, source, actor_user_id "
                    "from stock_movements where part_id = :part_id "
                    "order by id"
                ),
                {"part_id": created_part_id},
            ).all()
            audit_count = db.execute(
                text(
                    "select count(*) from audit_log "
                    "where event_type = 'part.quantity_adjusted' "
                    "and entity_type = 'part' "
                    "and entity_id = :entity_id"
                ),
                {"entity_id": created_part_id},
            ).scalar()

        if len(movement_rows) != 4:
            fail(
                "Expected four persisted movement rows after rejected "
                f"operations, got {len(movement_rows)}."
            )
        if audit_count != 4:
            fail(
                "Expected four quantity-adjustment audit rows, got "
                f"{audit_count!r}."
            )
        for row in movement_rows:
            if (
                row[2] is None
                or row[3] is None
                or row[4] is None
                or row[5] != "manual"
                or row[6] != user_id
            ):
                fail(f"Movement row is incomplete: {row!r}")

    finally:
        cleanup()

    ok(
        "Stock quantity adjustments are authenticated, atomic, guarded, "
        "audited, and exposed through recent history"
    )



# PATCH 142: existing-part metadata update smoke test
def check_part_metadata_update_api() -> None:
    import json as json_module

    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app

    username = "smoke_part_metadata_update_user"
    password = "part-metadata-update-smoke-password"
    suffix = uuid4().hex[:10]
    target_part_number = f"SMOKE-META-{suffix}"
    duplicate_part_number = f"SMOKE-META-DUP-{suffix}"
    custom_type_id: int | None = None
    manufacturer_id: int | None = None
    target_part_id: int | None = None
    duplicate_part_id: int | None = None
    user_id: int | None = None

    def cleanup() -> None:
        with db_session() as db:
            for part_id in (target_part_id, duplicate_part_id):
                if part_id is None:
                    continue
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'part' "
                        "and entity_id = :entity_id"
                    ),
                    {"entity_id": part_id},
                )
                db.execute(
                    text(
                        "delete from stock_movements "
                        "where part_id = :part_id"
                    ),
                    {"part_id": part_id},
                )
                db.execute(
                    text(
                        "delete from part_field_values "
                        "where part_id = :part_id"
                    ),
                    {"part_id": part_id},
                )
                db.execute(
                    text("delete from parts where id = :part_id"),
                    {"part_id": part_id},
                )

            if manufacturer_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'manufacturer' "
                        "and entity_id = :entity_id"
                    ),
                    {"entity_id": manufacturer_id},
                )
                db.execute(
                    text(
                        "delete from manufacturers "
                        "where id = :manufacturer_id"
                    ),
                    {"manufacturer_id": manufacturer_id},
                )

            if custom_type_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'part_type' "
                        "and entity_id = :entity_id"
                    ),
                    {"entity_id": custom_type_id},
                )
                db.execute(
                    text(
                        "delete from part_type_fields "
                        "where part_type_id = :part_type_id"
                    ),
                    {"part_type_id": custom_type_id},
                )
                db.execute(
                    text(
                        "delete from part_types "
                        "where id = :part_type_id"
                    ),
                    {"part_type_id": custom_type_id},
                )

            db.execute(
                text(
                    "delete from sessions where user_id in "
                    "(select id from users where username = :username)"
                ),
                {"username": username},
            )
            db.execute(
                text("delete from users where username = :username"),
                {"username": username},
            )
            db.commit()

    cleanup()
    client = TestClient(fastapi_app)

    try:
        unauthenticated = client.put(
            "/api/parts/1",
            json={
                "part_type_id": 1,
                "name": "Unauthenticated metadata update",
                "field_values": [],
            },
        )
        if unauthenticated.status_code not in {401, 403}:
            fail(
                "PUT /api/parts/{id} should require authentication, got "
                f"{unauthenticated.status_code}."
            )

        with db_session() as db:
            user = create_user(
                db,
                username=username,
                display_name="Part Metadata Update Smoke User",
                password=password,
                commit=True,
            )
            user_id = user.id
            session_token = create_session(
                db,
                user=user,
                commit=True,
            )

        headers = {
            "Authorization": f"Bearer {session_token.token}",
        }

        type_response = client.post(
            "/api/part-types",
            headers=headers,
            json={
                "name": f"Smoke Metadata Device {suffix}",
                "description": "Temporary metadata update template",
                "fields": [
                    {
                        "field_key": "model_code",
                        "label": "Model code",
                        "field_type": "text",
                        "is_required": True,
                        "options": [],
                        "default_unit": None,
                        "help_text": None,
                    },
                    {
                        "field_key": "logic_voltage",
                        "label": "Logic voltage",
                        "field_type": "unit_value",
                        "is_required": True,
                        "options": [],
                        "default_unit": "V",
                        "help_text": None,
                    },
                    {
                        "field_key": "interface",
                        "label": "Interface",
                        "field_type": "dropdown",
                        "is_required": False,
                        "options": ["I2C", "SPI", "UART"],
                        "default_unit": None,
                        "help_text": None,
                    },
                    {
                        "field_key": "datasheet",
                        "label": "Datasheet",
                        "field_type": "url",
                        "is_required": False,
                        "options": [],
                        "default_unit": None,
                        "help_text": None,
                    },
                    {
                        "field_key": "rohs",
                        "label": "RoHS compliant",
                        "field_type": "boolean",
                        "is_required": False,
                        "options": [],
                        "default_unit": None,
                        "help_text": None,
                    },
                ],
            },
        )
        if type_response.status_code != 201:
            fail(
                "Metadata smoke part type creation returned "
                f"{type_response.status_code}: {type_response.text}"
            )

        part_type = type_response.json()
        custom_type_id = part_type.get("id")
        fields = {
            field["field_key"]: field
            for field in part_type.get("fields", [])
        }
        expected_field_keys = {
            "model_code",
            "logic_voltage",
            "interface",
            "datasheet",
            "rohs",
        }
        if (
            not isinstance(custom_type_id, int)
            or set(fields) != expected_field_keys
        ):
            fail(
                "Metadata smoke part type returned unexpected fields: "
                f"{part_type}"
            )

        manufacturer_response = client.post(
            "/api/manufacturers",
            headers=headers,
            json={"name": f"Smoke Metadata Manufacturer {suffix}"},
        )
        if manufacturer_response.status_code != 201:
            fail(
                "Metadata smoke manufacturer creation returned "
                f"{manufacturer_response.status_code}: "
                f"{manufacturer_response.text}"
            )
        manufacturer_id = manufacturer_response.json().get("id")
        if not isinstance(manufacturer_id, int):
            fail("Metadata smoke manufacturer did not return an ID.")

        def initial_field_values(model_code: str) -> list[dict[str, object]]:
            return [
                {
                    "field_id": fields["model_code"]["id"],
                    "value_text": model_code,
                },
                {
                    "field_id": fields["logic_voltage"]["id"],
                    "value_number": "3.3",
                    "unit": "V",
                },
                {
                    "field_id": fields["interface"]["id"],
                    "value_text": "I2C",
                },
                {
                    "field_id": fields["datasheet"]["id"],
                    "value_text": "https://example.com/original-datasheet",
                },
                {
                    "field_id": fields["rohs"]["id"],
                    "value_bool": False,
                },
            ]

        target_create = client.post(
            "/api/parts",
            headers=headers,
            json={
                "part_type_id": custom_type_id,
                "part_number": target_part_number,
                "name": "Original metadata smoke part",
                "description": "Original description",
                "package": "Original Module",
                "notes": "Original notes",
                "total_quantity": 9,
                "unit_price": "12.5000",
                "purchase_link": "https://example.com/original-part",
                "low_stock_enabled": False,
                "field_values": initial_field_values("META-OLD"),
            },
        )
        if target_create.status_code != 201:
            fail(
                "Metadata target part creation returned "
                f"{target_create.status_code}: {target_create.text}"
            )
        target_part_id = target_create.json().get("id")
        if not isinstance(target_part_id, int):
            fail("Metadata target part did not return an ID.")

        duplicate_create = client.post(
            "/api/parts",
            headers=headers,
            json={
                "part_type_id": custom_type_id,
                "part_number": duplicate_part_number,
                "name": "Duplicate metadata smoke part",
                "total_quantity": 2,
                "field_values": initial_field_values("META-DUP"),
            },
        )
        if duplicate_create.status_code != 201:
            fail(
                "Metadata duplicate reference part creation returned "
                f"{duplicate_create.status_code}: {duplicate_create.text}"
            )
        duplicate_part_id = duplicate_create.json().get("id")
        if not isinstance(duplicate_part_id, int):
            fail("Metadata duplicate reference part did not return an ID.")

        def valid_update_payload() -> dict[str, object]:
            return {
                "part_type_id": custom_type_id,
                "manufacturer_id": manufacturer_id,
                "part_number": target_part_number,
                "name": "Updated metadata smoke part",
                "description": "Updated description",
                "package": "Updated Module",
                "notes": "Updated notes",
                "unit_price": "19.7500",
                "purchase_link": "https://example.com/updated-part",
                "low_stock_enabled": True,
                "low_stock_threshold": 3,
                "field_values": [
                    {
                        "field_id": fields["model_code"]["id"],
                        "value_text": "META-NEW",
                    },
                    {
                        "field_id": fields["logic_voltage"]["id"],
                        "value_number": "5",
                        "unit": "V",
                    },
                    {
                        "field_id": fields["interface"]["id"],
                        "value_text": "SPI",
                    },
                    {
                        "field_id": fields["datasheet"]["id"],
                        "value_text": "https://example.com/updated-datasheet",
                    },
                    {
                        "field_id": fields["rohs"]["id"],
                        "value_bool": True,
                    },
                ],
            }

        forbidden_quantity_payload = valid_update_payload()
        forbidden_quantity_payload["total_quantity"] = 99
        forbidden_quantity = client.put(
            f"/api/parts/{target_part_id}",
            headers=headers,
            json=forbidden_quantity_payload,
        )
        if forbidden_quantity.status_code != 422:
            fail(
                "Metadata update should reject quantity fields with 422, got "
                f"{forbidden_quantity.status_code}: "
                f"{forbidden_quantity.text}"
            )

        missing_required_payload = valid_update_payload()
        missing_required_payload["field_values"] = [
            item
            for item in missing_required_payload["field_values"]
            if item["field_id"] != fields["model_code"]["id"]
        ]
        missing_required = client.put(
            f"/api/parts/{target_part_id}",
            headers=headers,
            json=missing_required_payload,
        )
        if missing_required.status_code != 422:
            fail(
                "Metadata update should reject a missing required field with "
                f"422, got {missing_required.status_code}: "
                f"{missing_required.text}"
            )

        invalid_dropdown_payload = valid_update_payload()
        for item in invalid_dropdown_payload["field_values"]:
            if item["field_id"] == fields["interface"]["id"]:
                item["value_text"] = "CAN"
        invalid_dropdown = client.put(
            f"/api/parts/{target_part_id}",
            headers=headers,
            json=invalid_dropdown_payload,
        )
        if invalid_dropdown.status_code != 422:
            fail(
                "Metadata update should reject an invalid dropdown with 422, "
                f"got {invalid_dropdown.status_code}: "
                f"{invalid_dropdown.text}"
            )

        invalid_url_payload = valid_update_payload()
        for item in invalid_url_payload["field_values"]:
            if item["field_id"] == fields["datasheet"]["id"]:
                item["value_text"] = "javascript:invalid"
        invalid_url = client.put(
            f"/api/parts/{target_part_id}",
            headers=headers,
            json=invalid_url_payload,
        )
        if invalid_url.status_code != 422:
            fail(
                "Metadata update should reject an invalid URL with 422, got "
                f"{invalid_url.status_code}: {invalid_url.text}"
            )

        invalid_unit_value_payload = valid_update_payload()
        for item in invalid_unit_value_payload["field_values"]:
            if item["field_id"] == fields["logic_voltage"]["id"]:
                item.pop("value_number", None)
                item["value_text"] = "five volts"
        invalid_unit_value = client.put(
            f"/api/parts/{target_part_id}",
            headers=headers,
            json=invalid_unit_value_payload,
        )
        if invalid_unit_value.status_code != 422:
            fail(
                "Metadata update should reject an invalid unit-aware value "
                f"with 422, got {invalid_unit_value.status_code}: "
                f"{invalid_unit_value.text}"
            )

        with db_session() as db:
            other_type_id = db.execute(
                text(
                    "select id from part_types "
                    "where id != :part_type_id order by id limit 1"
                ),
                {"part_type_id": custom_type_id},
            ).scalar()
        if other_type_id is None:
            fail("Cannot test fixed part type without another part type.")

        type_change_payload = valid_update_payload()
        type_change_payload["part_type_id"] = other_type_id
        type_change = client.put(
            f"/api/parts/{target_part_id}",
            headers=headers,
            json=type_change_payload,
        )
        if type_change.status_code != 422:
            fail(
                "Metadata update should reject part-type changes with 422, "
                f"got {type_change.status_code}: {type_change.text}"
            )

        invalid_manufacturer_payload = valid_update_payload()
        invalid_manufacturer_payload["manufacturer_id"] = 2147483647
        invalid_manufacturer = client.put(
            f"/api/parts/{target_part_id}",
            headers=headers,
            json=invalid_manufacturer_payload,
        )
        if invalid_manufacturer.status_code != 422:
            fail(
                "Metadata update should reject an unknown manufacturer with "
                f"422, got {invalid_manufacturer.status_code}: "
                f"{invalid_manufacturer.text}"
            )

        missing_part = client.put(
            "/api/parts/2147483647",
            headers=headers,
            json=valid_update_payload(),
        )
        if missing_part.status_code != 404:
            fail(
                "Metadata update should return 404 for a missing part, got "
                f"{missing_part.status_code}: {missing_part.text}"
            )

        update_response = client.put(
            f"/api/parts/{target_part_id}",
            headers=headers,
            json=valid_update_payload(),
        )
        if update_response.status_code != 200:
            fail(
                "PUT /api/parts/{id} returned "
                f"{update_response.status_code}: {update_response.text}"
            )
        updated = update_response.json()
        if (
            updated.get("id") != target_part_id
            or updated.get("part_type_id") != custom_type_id
            or updated.get("manufacturer_id") != manufacturer_id
            or updated.get("part_number") != target_part_number
            or updated.get("name") != "Updated metadata smoke part"
            or updated.get("description") != "Updated description"
            or updated.get("package") != "Updated Module"
            or updated.get("notes") != "Updated notes"
            or updated.get("total_quantity") != 9
            or updated.get("reserved_quantity") != 0
            or updated.get("available_quantity") != 9
            or updated.get("unit_price") != "19.7500"
            or updated.get("purchase_link")
            != "https://example.com/updated-part"
            or updated.get("low_stock_enabled") is not True
            or updated.get("low_stock_threshold") != 3
            or len(updated.get("field_values", [])) != 5
        ):
            fail(f"Metadata update returned an unexpected payload: {updated}")

        updated_field_values = {
            item.get("field_key"): item
            for item in updated.get("field_values", [])
        }
        if (
            updated_field_values.get("model_code", {}).get("value_text")
            != "META-NEW"
            or updated_field_values.get("logic_voltage", {}).get(
                "value_number"
            )
            != "5.000000"
            or updated_field_values.get("logic_voltage", {}).get("unit")
            != "V"
            or updated_field_values.get("interface", {}).get("value_text")
            != "SPI"
            or updated_field_values.get("datasheet", {}).get("value_text")
            != "https://example.com/updated-datasheet"
            or updated_field_values.get("rohs", {}).get("value_bool")
            is not True
        ):
            fail(
                "Metadata update did not replace all typed template values: "
                f"{updated_field_values}"
            )

        duplicate_payload = valid_update_payload()
        duplicate_payload["part_number"] = duplicate_part_number
        duplicate = client.put(
            f"/api/parts/{target_part_id}",
            headers=headers,
            json=duplicate_payload,
        )
        if duplicate.status_code != 409:
            fail(
                "Metadata update should reject another part's number with "
                f"409, got {duplicate.status_code}: {duplicate.text}"
            )

        detail_response = client.get(
            f"/api/parts/{target_part_id}",
            headers=headers,
        )
        if detail_response.status_code != 200:
            fail(
                "Part detail after metadata update returned "
                f"{detail_response.status_code}: {detail_response.text}"
            )
        detail = detail_response.json()
        if (
            detail.get("name") != "Updated metadata smoke part"
            or detail.get("manufacturer_id") != manufacturer_id
            or detail.get("total_quantity") != 9
            or detail.get("reserved_quantity") != 0
        ):
            fail(
                "Part detail did not preserve the metadata update and "
                f"quantities: {detail}"
            )

        with db_session() as db:
            persisted_part = db.execute(
                text(
                    "select part_type_id, manufacturer_id, part_number, name, "
                    "description, package, notes, total_quantity, "
                    "reserved_quantity, unit_price, purchase_link, "
                    "low_stock_enabled, low_stock_threshold "
                    "from parts where id = :part_id"
                ),
                {"part_id": target_part_id},
            ).one()
            movement_count = db.execute(
                text(
                    "select count(*) from stock_movements "
                    "where part_id = :part_id"
                ),
                {"part_id": target_part_id},
            ).scalar()
            value_count = db.execute(
                text(
                    "select count(*) from part_field_values "
                    "where part_id = :part_id"
                ),
                {"part_id": target_part_id},
            ).scalar()
            audit_rows = db.execute(
                text(
                    "select actor_user_id, before_json, after_json, "
                    "metadata_json from audit_log "
                    "where event_type = 'part.metadata_updated' "
                    "and entity_type = 'part' "
                    "and entity_id = :entity_id order by id"
                ),
                {"entity_id": target_part_id},
            ).all()

        if (
            persisted_part[0] != custom_type_id
            or persisted_part[1] != manufacturer_id
            or persisted_part[2] != target_part_number
            or persisted_part[3] != "Updated metadata smoke part"
            or persisted_part[7] != 9
            or persisted_part[8] != 0
        ):
            fail(
                "Persisted metadata or protected quantity fields are "
                f"unexpected: {persisted_part!r}"
            )
        if movement_count != 0:
            fail(
                "Metadata editing should not create stock movements, got "
                f"{movement_count!r}."
            )
        if value_count != 5:
            fail(
                "Metadata editing did not persist five replacement values, "
                f"got {value_count!r}."
            )
        if len(audit_rows) != 1:
            fail(
                "Metadata editing should create exactly one audit event, got "
                f"{len(audit_rows)}."
            )

        audit_row = audit_rows[0]
        if audit_row[0] != user_id:
            fail(
                "Metadata audit actor does not match the authenticated user: "
                f"{audit_row!r}"
            )

        before_json = (
            json_module.loads(audit_row[1])
            if isinstance(audit_row[1], str)
            else audit_row[1]
        )
        after_json = (
            json_module.loads(audit_row[2])
            if isinstance(audit_row[2], str)
            else audit_row[2]
        )
        metadata_json = (
            json_module.loads(audit_row[3])
            if isinstance(audit_row[3], str)
            else audit_row[3]
        )

        if (
            before_json.get("name") != "Original metadata smoke part"
            or after_json.get("name") != "Updated metadata smoke part"
            or "total_quantity" in before_json
            or "reserved_quantity" in before_json
            or "total_quantity" in after_json
            or "reserved_quantity" in after_json
        ):
            fail(
                "Metadata audit before/after snapshots are incomplete or "
                f"contain quantity fields: {audit_row!r}"
            )

        changed_fields = set(metadata_json.get("changed_fields", []))
        required_changed_fields = {
            "manufacturer_id",
            "manufacturer_name",
            "name",
            "description",
            "package",
            "notes",
            "unit_price",
            "purchase_link",
            "low_stock_enabled",
            "low_stock_threshold",
            "field_values",
        }
        if not required_changed_fields.issubset(changed_fields):
            fail(
                "Metadata audit changed_fields is incomplete: "
                f"{sorted(changed_fields)}"
            )

    finally:
        cleanup()

    ok(
        "Existing part metadata updates are authenticated, typed, atomic, "
        "quantity-safe, duplicate-safe, and audited"
    )


# PATCH 152: part soft-delete and restoration smoke test
def check_part_soft_delete_restore_api() -> None:
    import json as json_module

    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app
    from app.models import PartFieldValue, StockMovement

    username = "smoke_part_lifecycle_user"
    password = "part-lifecycle-smoke-password"
    suffix = uuid4().hex[:10]
    part_number = f"SMOKE-LIFECYCLE-{suffix}"
    part_id: int | None = None
    user_id: int | None = None

    def cleanup() -> None:
        with db_session() as db:
            if part_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'part' "
                        "and entity_id = :entity_id"
                    ),
                    {"entity_id": part_id},
                )
                db.execute(
                    text(
                        "delete from stock_movements "
                        "where part_id = :part_id"
                    ),
                    {"part_id": part_id},
                )
                db.execute(
                    text(
                        "delete from part_field_values "
                        "where part_id = :part_id"
                    ),
                    {"part_id": part_id},
                )
                db.execute(
                    text("delete from parts where id = :part_id"),
                    {"part_id": part_id},
                )
            db.execute(
                text(
                    "delete from sessions where user_id in "
                    "(select id from users where username = :username)"
                ),
                {"username": username},
            )
            db.execute(
                text("delete from users where username = :username"),
                {"username": username},
            )
            db.commit()

    cleanup()
    client = TestClient(fastapi_app)

    try:
        unauthenticated_delete = client.delete("/api/parts/1")
        if unauthenticated_delete.status_code not in {401, 403}:
            fail(
                "DELETE /api/parts/{id} should require authentication, got "
                f"{unauthenticated_delete.status_code}."
            )

        unauthenticated_deleted_list = client.get("/api/parts/deleted")
        if unauthenticated_deleted_list.status_code not in {401, 403}:
            fail(
                "GET /api/parts/deleted should require authentication, got "
                f"{unauthenticated_deleted_list.status_code}."
            )

        unauthenticated_restore = client.post("/api/parts/1/restore")
        if unauthenticated_restore.status_code not in {401, 403}:
            fail(
                "POST /api/parts/{id}/restore should require "
                "authentication, got "
                f"{unauthenticated_restore.status_code}."
            )

        with db_session() as db:
            user = create_user(
                db,
                username=username,
                display_name="Part Lifecycle Smoke User",
                password=password,
                commit=True,
            )
            user_id = user.id
            session_token = create_session(
                db,
                user=user,
                commit=True,
            )

            field_row = db.execute(
                text(
                    "select id, part_type_id from part_type_fields "
                    "where field_type = 'text' order by id limit 1"
                )
            ).one_or_none()
            if field_row is None:
                fail(
                    "Cannot test part lifecycle without a text template field."
                )

            field_id = int(field_row[0])
            part_type_id = int(field_row[1])
            part = Part(
                part_type_id=part_type_id,
                part_number=part_number,
                name="Part lifecycle smoke part",
                description="Must survive soft deletion",
                package="Smoke package",
                notes="Lifecycle retention coverage",
                total_quantity=11,
                reserved_quantity=2,
                unit_price="4.5000",
                purchase_link="https://example.com/lifecycle-smoke",
                low_stock_enabled=True,
                low_stock_threshold=3,
                is_deleted=False,
                deleted_at=None,
            )
            db.add(part)
            db.flush()
            part_id = part.id

            db.add(
                PartFieldValue(
                    part_id=part.id,
                    field_id=field_id,
                    value_text="retained lifecycle value",
                )
            )
            db.add(
                StockMovement(
                    part_id=part.id,
                    movement_type="adjust",
                    quantity_delta=1,
                    quantity_before=10,
                    quantity_after=11,
                    unit_price_snapshot=part.unit_price,
                    currency_snapshot=None,
                    reason="Lifecycle retention seed",
                    note="Must survive soft deletion",
                    source="manual",
                    actor_user_id=user_id,
                )
            )
            db.commit()

        headers = {
            "Authorization": f"Bearer {session_token.token}",
        }

        initial_detail = client.get(
            f"/api/parts/{part_id}",
            headers=headers,
        )
        if initial_detail.status_code != 200:
            fail(
                "Lifecycle part detail before deletion returned "
                f"{initial_detail.status_code}: {initial_detail.text}"
            )
        initial = initial_detail.json()
        if (
            initial.get("total_quantity") != 11
            or initial.get("reserved_quantity") != 2
            or len(initial.get("field_values", [])) != 1
        ):
            fail(f"Unexpected initial lifecycle part: {initial}")

        initial_deleted = client.get(
            "/api/parts/deleted",
            headers=headers,
        )
        if initial_deleted.status_code != 200:
            fail(
                "Initial deleted-parts collection returned "
                f"{initial_deleted.status_code}: {initial_deleted.text}"
            )
        if any(
            item.get("id") == part_id
            for item in initial_deleted.json().get("parts", [])
        ):
            fail("Active part appeared in the deleted-parts collection.")

        delete_response = client.delete(
            f"/api/parts/{part_id}",
            headers=headers,
        )
        if delete_response.status_code != 200:
            fail(
                "Soft deletion returned "
                f"{delete_response.status_code}: {delete_response.text}"
            )
        deleted = delete_response.json()
        if (
            deleted.get("id") != part_id
            or deleted.get("is_deleted") is not True
            or not deleted.get("deleted_at")
            or deleted.get("total_quantity") != 11
            or deleted.get("reserved_quantity") != 2
            or len(deleted.get("field_values", [])) != 1
        ):
            fail(f"Unexpected soft-deletion response: {deleted}")

        repeated_delete = client.delete(
            f"/api/parts/{part_id}",
            headers=headers,
        )
        if repeated_delete.status_code != 409:
            fail(
                "Deleting an already deleted part should return 409, got "
                f"{repeated_delete.status_code}: {repeated_delete.text}"
            )

        hidden_detail = client.get(
            f"/api/parts/{part_id}",
            headers=headers,
        )
        if hidden_detail.status_code != 404:
            fail(
                "Normal part detail should hide deleted parts with 404, got "
                f"{hidden_detail.status_code}: {hidden_detail.text}"
            )

        hidden_movements = client.get(
            f"/api/parts/{part_id}/movements",
            headers=headers,
        )
        if hidden_movements.status_code != 404:
            fail(
                "Normal movement history should hide deleted parts with 404, "
                f"got {hidden_movements.status_code}: "
                f"{hidden_movements.text}"
            )

        active_collection = client.get(
            "/api/parts?limit=250",
            headers=headers,
        )
        if active_collection.status_code != 200:
            fail(
                "Active parts collection after deletion returned "
                f"{active_collection.status_code}: "
                f"{active_collection.text}"
            )
        if any(
            item.get("id") == part_id
            for item in active_collection.json().get("parts", [])
        ):
            fail("Deleted part remained visible in the active collection.")

        deleted_collection = client.get(
            "/api/parts/deleted?limit=250",
            headers=headers,
        )
        if deleted_collection.status_code != 200:
            fail(
                "Deleted-parts collection returned "
                f"{deleted_collection.status_code}: "
                f"{deleted_collection.text}"
            )
        deleted_items = [
            item
            for item in deleted_collection.json().get("parts", [])
            if item.get("id") == part_id
        ]
        if len(deleted_items) != 1:
            fail(
                "Deleted-parts collection should contain the lifecycle part "
                f"exactly once, got {deleted_items!r}."
            )

        duplicate_while_deleted = client.post(
            "/api/parts",
            headers=headers,
            json={
                "part_type_id": initial["part_type_id"],
                "part_number": part_number,
                "name": "Duplicate while original is deleted",
                "total_quantity": 0,
                "field_values": [],
            },
        )
        if duplicate_while_deleted.status_code != 409:
            fail(
                "A deleted part should continue reserving its part number; "
                "duplicate creation should return 409, got "
                f"{duplicate_while_deleted.status_code}: "
                f"{duplicate_while_deleted.text}"
            )

        with db_session() as db:
            deleted_row = db.execute(
                text(
                    "select is_deleted, deleted_at, total_quantity, "
                    "reserved_quantity, part_number, name "
                    "from parts where id = :part_id"
                ),
                {"part_id": part_id},
            ).one()
            value_count = db.execute(
                text(
                    "select count(*) from part_field_values "
                    "where part_id = :part_id"
                ),
                {"part_id": part_id},
            ).scalar()
            movement_rows = db.execute(
                text(
                    "select movement_type, quantity_delta, quantity_before, "
                    "quantity_after, reason, source, actor_user_id "
                    "from stock_movements where part_id = :part_id"
                ),
                {"part_id": part_id},
            ).all()
            deletion_audits = db.execute(
                text(
                    "select actor_user_id, before_json, after_json, "
                    "metadata_json from audit_log "
                    "where event_type = 'part.deleted' "
                    "and entity_type = 'part' "
                    "and entity_id = :entity_id order by id"
                ),
                {"entity_id": part_id},
            ).all()

        if (
            deleted_row[0] != 1
            or deleted_row[1] is None
            or deleted_row[2] != 11
            or deleted_row[3] != 2
            or deleted_row[4] != part_number
            or deleted_row[5] != "Part lifecycle smoke part"
        ):
            fail(
                "Soft deletion changed retained part data unexpectedly: "
                f"{deleted_row!r}"
            )
        if value_count != 1:
            fail(
                "Soft deletion did not preserve the dynamic field value: "
                f"{value_count!r}"
            )
        if len(movement_rows) != 1:
            fail(
                "Soft deletion did not preserve stock movement history: "
                f"{movement_rows!r}"
            )
        if len(deletion_audits) != 1:
            fail(
                "Soft deletion should create exactly one audit event, got "
                f"{len(deletion_audits)}."
            )

        deletion_audit = deletion_audits[0]
        deletion_before = (
            json_module.loads(deletion_audit[1])
            if isinstance(deletion_audit[1], str)
            else deletion_audit[1]
        )
        deletion_after = (
            json_module.loads(deletion_audit[2])
            if isinstance(deletion_audit[2], str)
            else deletion_audit[2]
        )
        deletion_metadata = (
            json_module.loads(deletion_audit[3])
            if isinstance(deletion_audit[3], str)
            else deletion_audit[3]
        )
        if (
            deletion_audit[0] != user_id
            or deletion_before.get("is_deleted") is not False
            or deletion_before.get("deleted_at") is not None
            or deletion_after.get("is_deleted") is not True
            or not deletion_after.get("deleted_at")
            or deletion_before.get("total_quantity") != 11
            or deletion_after.get("total_quantity") != 11
            or deletion_metadata.get("field_value_count") != 1
            or deletion_metadata.get("movement_count") != 1
            or deletion_metadata.get("total_quantity_preserved") != 11
            or deletion_metadata.get("reserved_quantity_preserved") != 2
        ):
            fail(
                "Deletion audit snapshot or retention metadata is incomplete: "
                f"{deletion_audit!r}"
            )

        restore_response = client.post(
            f"/api/parts/{part_id}/restore",
            headers=headers,
        )
        if restore_response.status_code != 200:
            fail(
                "Part restoration returned "
                f"{restore_response.status_code}: {restore_response.text}"
            )
        restored = restore_response.json()
        if (
            restored.get("id") != part_id
            or restored.get("total_quantity") != 11
            or restored.get("reserved_quantity") != 2
            or restored.get("part_number") != part_number
            or len(restored.get("field_values", [])) != 1
        ):
            fail(f"Unexpected restoration response: {restored}")

        repeated_restore = client.post(
            f"/api/parts/{part_id}/restore",
            headers=headers,
        )
        if repeated_restore.status_code != 409:
            fail(
                "Restoring an active part should return 409, got "
                f"{repeated_restore.status_code}: {repeated_restore.text}"
            )

        restored_detail = client.get(
            f"/api/parts/{part_id}",
            headers=headers,
        )
        if restored_detail.status_code != 200:
            fail(
                "Restored part detail returned "
                f"{restored_detail.status_code}: {restored_detail.text}"
            )

        restored_active_collection = client.get(
            "/api/parts?limit=250",
            headers=headers,
        )
        if not any(
            item.get("id") == part_id
            for item in restored_active_collection.json().get("parts", [])
        ):
            fail("Restored part did not return to the active collection.")

        restored_deleted_collection = client.get(
            "/api/parts/deleted?limit=250",
            headers=headers,
        )
        if any(
            item.get("id") == part_id
            for item in restored_deleted_collection.json().get("parts", [])
        ):
            fail("Restored part remained in the deleted-parts collection.")

        restored_movements = client.get(
            f"/api/parts/{part_id}/movements",
            headers=headers,
        )
        if (
            restored_movements.status_code != 200
            or len(restored_movements.json().get("movements", [])) != 1
        ):
            fail(
                "Restoration did not recover movement-history visibility: "
                f"{restored_movements.status_code}: "
                f"{restored_movements.text}"
            )

        with db_session() as db:
            restored_row = db.execute(
                text(
                    "select is_deleted, deleted_at, total_quantity, "
                    "reserved_quantity, part_number, name "
                    "from parts where id = :part_id"
                ),
                {"part_id": part_id},
            ).one()
            restored_value_count = db.execute(
                text(
                    "select count(*) from part_field_values "
                    "where part_id = :part_id"
                ),
                {"part_id": part_id},
            ).scalar()
            restored_movement_count = db.execute(
                text(
                    "select count(*) from stock_movements "
                    "where part_id = :part_id"
                ),
                {"part_id": part_id},
            ).scalar()
            restoration_audits = db.execute(
                text(
                    "select actor_user_id, before_json, after_json, "
                    "metadata_json from audit_log "
                    "where event_type = 'part.restored' "
                    "and entity_type = 'part' "
                    "and entity_id = :entity_id order by id"
                ),
                {"entity_id": part_id},
            ).all()

        if (
            restored_row[0] != 0
            or restored_row[1] is not None
            or restored_row[2] != 11
            or restored_row[3] != 2
            or restored_row[4] != part_number
            or restored_row[5] != "Part lifecycle smoke part"
            or restored_value_count != 1
            or restored_movement_count != 1
        ):
            fail(
                "Restoration did not preserve and reactivate the full part: "
                f"{restored_row!r}, values={restored_value_count!r}, "
                f"movements={restored_movement_count!r}"
            )
        if len(restoration_audits) != 1:
            fail(
                "Restoration should create exactly one audit event, got "
                f"{len(restoration_audits)}."
            )

        restoration_audit = restoration_audits[0]
        restoration_before = (
            json_module.loads(restoration_audit[1])
            if isinstance(restoration_audit[1], str)
            else restoration_audit[1]
        )
        restoration_after = (
            json_module.loads(restoration_audit[2])
            if isinstance(restoration_audit[2], str)
            else restoration_audit[2]
        )
        restoration_metadata = (
            json_module.loads(restoration_audit[3])
            if isinstance(restoration_audit[3], str)
            else restoration_audit[3]
        )
        if (
            restoration_audit[0] != user_id
            or restoration_before.get("is_deleted") is not True
            or not restoration_before.get("deleted_at")
            or restoration_after.get("is_deleted") is not False
            or restoration_after.get("deleted_at") is not None
            or restoration_metadata.get("field_value_count") != 1
            or restoration_metadata.get("movement_count") != 1
            or restoration_metadata.get(
                "part_number_conflict_checked"
            ) is not True
        ):
            fail(
                "Restoration audit snapshot or conflict metadata is "
                f"incomplete: {restoration_audit!r}"
            )

        missing_part_id = 2_147_483_647
        missing_delete = client.delete(
            f"/api/parts/{missing_part_id}",
            headers=headers,
        )
        if missing_delete.status_code != 404:
            fail(
                "Deleting a missing part should return 404, got "
                f"{missing_delete.status_code}: {missing_delete.text}"
            )

        missing_restore = client.post(
            f"/api/parts/{missing_part_id}/restore",
            headers=headers,
        )
        if missing_restore.status_code != 404:
            fail(
                "Restoring a missing part should return 404, got "
                f"{missing_restore.status_code}: {missing_restore.text}"
            )

    finally:
        cleanup()

    ok(
        "Part soft deletion and restoration are authenticated, reversible, "
        "retention-safe, duplicate-safe, hidden from active reads, and audited"
    )


# PATCH 156: reusable location catalogue API smoke test
def check_location_catalogue_api() -> None:
    import json as json_module
    from datetime import datetime as datetime_type
    from datetime import timezone as timezone_type

    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app

    username = "smoke_location_catalogue_user"
    password = "location-catalogue-smoke-password"
    suffix = uuid4().hex[:10]
    first_name = f"Smoke Drawer {suffix}"
    updated_first_name = f"Smoke Drawer Updated {suffix}"
    second_name = f"Smoke Shelf {suffix}"
    part_number = f"SMOKE-LOCATION-{suffix}"

    first_id: int | None = None
    second_id: int | None = None
    part_id: int | None = None
    user_id: int | None = None

    def cleanup() -> None:
        with db_session() as db:
            if part_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'part' "
                        "and entity_id = :entity_id"
                    ),
                    {"entity_id": part_id},
                )
                db.execute(
                    text(
                        "delete from stock_movements "
                        "where part_id = :part_id"
                    ),
                    {"part_id": part_id},
                )
                db.execute(
                    text(
                        "delete from part_field_values "
                        "where part_id = :part_id"
                    ),
                    {"part_id": part_id},
                )
                db.execute(
                    text("delete from parts where id = :part_id"),
                    {"part_id": part_id},
                )

            for location_id in (first_id, second_id):
                if location_id is None:
                    continue
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'location' "
                        "and entity_id = :entity_id"
                    ),
                    {"entity_id": location_id},
                )
                db.execute(
                    text("delete from locations where id = :location_id"),
                    {"location_id": location_id},
                )

            db.execute(
                text(
                    "delete from sessions where user_id in "
                    "(select id from users where username = :username)"
                ),
                {"username": username},
            )
            db.execute(
                text("delete from users where username = :username"),
                {"username": username},
            )
            db.commit()

    cleanup()
    client = TestClient(fastapi_app)

    try:
        unauthenticated_list = client.get("/api/locations")
        if unauthenticated_list.status_code not in {401, 403}:
            fail(
                "GET /api/locations should require authentication, got "
                f"{unauthenticated_list.status_code}."
            )

        unauthenticated_create = client.post(
            "/api/locations",
            json={"name": "Unauthenticated location"},
        )
        if unauthenticated_create.status_code not in {401, 403}:
            fail(
                "POST /api/locations should require authentication, got "
                f"{unauthenticated_create.status_code}."
            )

        unauthenticated_update = client.put(
            "/api/locations/1",
            json={"name": "Unauthenticated update", "note": None},
        )
        if unauthenticated_update.status_code not in {401, 403}:
            fail(
                "PUT /api/locations/{id} should require authentication, got "
                f"{unauthenticated_update.status_code}."
            )

        unauthenticated_delete = client.delete("/api/locations/1")
        if unauthenticated_delete.status_code not in {401, 403}:
            fail(
                "DELETE /api/locations/{id} should require authentication, "
                f"got {unauthenticated_delete.status_code}."
            )

        with db_session() as db:
            user = create_user(
                db,
                username=username,
                display_name="Location Catalogue Smoke User",
                password=password,
                commit=True,
            )
            user_id = user.id
            session_token = create_session(
                db,
                user=user,
                commit=True,
            )

        headers = {
            "Authorization": f"Bearer {session_token.token}",
        }

        blank_name = client.post(
            "/api/locations",
            headers=headers,
            json={"name": "   "},
        )
        if blank_name.status_code != 422:
            fail(
                "Blank location names should return 422, got "
                f"{blank_name.status_code}: {blank_name.text}"
            )

        first_create = client.post(
            "/api/locations",
            headers=headers,
            json={
                "name": f"  {first_name}  ",
                "note": "  Primary component drawer.  ",
            },
        )
        if first_create.status_code != 201:
            fail(
                "First location creation returned "
                f"{first_create.status_code}: {first_create.text}"
            )
        first = first_create.json()
        first_id = first.get("id")
        if (
            not isinstance(first_id, int)
            or first.get("name") != first_name
            or first.get("note") != "Primary component drawer."
            or first.get("part_count") != 0
            or first.get("active_part_count") != 0
            or first.get("deleted_part_count") != 0
        ):
            fail(f"Unexpected first location response: {first}")

        second_create = client.post(
            "/api/locations",
            headers=headers,
            json={
                "name": second_name,
                "note": "Shelf retained for in-use deletion coverage.",
            },
        )
        if second_create.status_code != 201:
            fail(
                "Second location creation returned "
                f"{second_create.status_code}: {second_create.text}"
            )
        second = second_create.json()
        second_id = second.get("id")
        if not isinstance(second_id, int):
            fail(f"Unexpected second location response: {second}")

        normalized_duplicate = client.post(
            "/api/locations",
            headers=headers,
            json={
                "name": f"   {first_name.upper()}   ",
                "note": None,
            },
        )
        if normalized_duplicate.status_code != 409:
            fail(
                "Normalized duplicate location creation should return 409, "
                f"got {normalized_duplicate.status_code}: "
                f"{normalized_duplicate.text}"
            )

        list_response = client.get("/api/locations", headers=headers)
        if list_response.status_code != 200:
            fail(
                "GET /api/locations returned "
                f"{list_response.status_code}: {list_response.text}"
            )
        listed = list_response.json()
        listed_by_id = {
            item.get("id"): item
            for item in listed.get("locations", [])
        }
        if (
            first_id not in listed_by_id
            or second_id not in listed_by_id
            or listed.get("total", 0) < 2
        ):
            fail(
                "Created locations were not returned by the catalogue: "
                f"{listed}"
            )

        first_update = client.put(
            f"/api/locations/{first_id}",
            headers=headers,
            json={
                "name": updated_first_name,
                "note": "Updated drawer note.",
            },
        )
        if first_update.status_code != 200:
            fail(
                "Location update returned "
                f"{first_update.status_code}: {first_update.text}"
            )
        updated = first_update.json()
        if (
            updated.get("id") != first_id
            or updated.get("name") != updated_first_name
            or updated.get("note") != "Updated drawer note."
            or updated.get("part_count") != 0
        ):
            fail(f"Unexpected location update response: {updated}")

        duplicate_update = client.put(
            f"/api/locations/{first_id}",
            headers=headers,
            json={
                "name": f"  {second_name.upper()}  ",
                "note": None,
            },
        )
        if duplicate_update.status_code != 409:
            fail(
                "Updating to another normalized location name should return "
                f"409, got {duplicate_update.status_code}: "
                f"{duplicate_update.text}"
            )

        missing_update = client.put(
            "/api/locations/2147483647",
            headers=headers,
            json={"name": "Missing location", "note": None},
        )
        if missing_update.status_code != 404:
            fail(
                "Updating a missing location should return 404, got "
                f"{missing_update.status_code}: {missing_update.text}"
            )

        with db_session() as db:
            part_type_id = db.execute(
                text("select id from part_types order by id limit 1")
            ).scalar()
            if part_type_id is None:
                fail("Cannot test location usage without a part type.")

            part = Part(
                part_type_id=int(part_type_id),
                location_id=second_id,
                part_number=part_number,
                name="Location catalogue smoke part",
                total_quantity=1,
                reserved_quantity=0,
                is_deleted=False,
                deleted_at=None,
            )
            db.add(part)
            db.commit()
            db.refresh(part)
            part_id = part.id

        active_usage_list = client.get(
            "/api/locations",
            headers=headers,
        )
        active_items = {
            item.get("id"): item
            for item in active_usage_list.json().get("locations", [])
        }
        second_active = active_items.get(second_id, {})
        if (
            second_active.get("part_count") != 1
            or second_active.get("active_part_count") != 1
            or second_active.get("deleted_part_count") != 0
        ):
            fail(
                "Active part usage counts are incorrect: "
                f"{second_active}"
            )

        in_use_delete = client.delete(
            f"/api/locations/{second_id}",
            headers=headers,
        )
        if in_use_delete.status_code != 409:
            fail(
                "Deleting a location assigned to an active part should return "
                f"409, got {in_use_delete.status_code}: "
                f"{in_use_delete.text}"
            )

        with db_session() as db:
            part = db.get(Part, part_id)
            if part is None:
                fail("Location smoke part disappeared before soft deletion.")
            part.is_deleted = True
            part.deleted_at = datetime_type.now(timezone_type.utc)
            db.commit()

        deleted_usage_list = client.get(
            "/api/locations",
            headers=headers,
        )
        deleted_items = {
            item.get("id"): item
            for item in deleted_usage_list.json().get("locations", [])
        }
        second_deleted = deleted_items.get(second_id, {})
        if (
            second_deleted.get("part_count") != 1
            or second_deleted.get("active_part_count") != 0
            or second_deleted.get("deleted_part_count") != 1
        ):
            fail(
                "Deleted part usage counts are incorrect: "
                f"{second_deleted}"
            )

        deleted_part_location_delete = client.delete(
            f"/api/locations/{second_id}",
            headers=headers,
        )
        if deleted_part_location_delete.status_code != 409:
            fail(
                "Deleting a location assigned to a deleted part should return "
                f"409, got {deleted_part_location_delete.status_code}: "
                f"{deleted_part_location_delete.text}"
            )

        unused_delete = client.delete(
            f"/api/locations/{first_id}",
            headers=headers,
        )
        if unused_delete.status_code != 200:
            fail(
                "Deleting an unused location returned "
                f"{unused_delete.status_code}: {unused_delete.text}"
            )
        deleted_location = unused_delete.json()
        if (
            deleted_location.get("id") != first_id
            or deleted_location.get("name") != updated_first_name
            or deleted_location.get("deleted") is not True
        ):
            fail(
                "Unexpected unused-location deletion response: "
                f"{deleted_location}"
            )

        missing_delete = client.delete(
            "/api/locations/2147483647",
            headers=headers,
        )
        if missing_delete.status_code != 404:
            fail(
                "Deleting a missing location should return 404, got "
                f"{missing_delete.status_code}: {missing_delete.text}"
            )

        after_delete_list = client.get(
            "/api/locations",
            headers=headers,
        ).json()
        if any(
            item.get("id") == first_id
            for item in after_delete_list.get("locations", [])
        ):
            fail("Deleted unused location remained in the catalogue.")

        with db_session() as db:
            persisted_second = db.execute(
                text(
                    "select name, normalized_name, note "
                    "from locations where id = :location_id"
                ),
                {"location_id": second_id},
            ).one_or_none()
            part_location = db.execute(
                text(
                    "select location_id, is_deleted "
                    "from parts where id = :part_id"
                ),
                {"part_id": part_id},
            ).one_or_none()
            audit_rows = db.execute(
                text(
                    "select event_type, entity_id, actor_user_id, "
                    "before_json, after_json, metadata_json "
                    "from audit_log "
                    "where entity_type = 'location' "
                    "and entity_id in (:first_id, :second_id) "
                    "order by id"
                ),
                {
                    "first_id": first_id,
                    "second_id": second_id,
                },
            ).all()

        if persisted_second is None:
            fail("In-use location was removed despite deletion conflicts.")
        if persisted_second[1] != " ".join(second_name.split()).casefold():
            fail(
                "Location normalized_name was not persisted correctly: "
                f"{persisted_second!r}"
            )
        if (
            part_location is None
            or part_location[0] != second_id
            or part_location[1] != 1
        ):
            fail(
                "Deleted part did not retain its location reference: "
                f"{part_location!r}"
            )

        event_types = [row[0] for row in audit_rows]
        required_events = {
            "location.created",
            "location.updated",
            "location.deleted",
        }
        if not required_events.issubset(set(event_types)):
            fail(
                "Location audit events are incomplete: "
                f"{event_types}"
            )

        first_audits = [
            row
            for row in audit_rows
            if row[1] == first_id
        ]
        if len(first_audits) != 3:
            fail(
                "The created, updated, and deleted location should have three "
                f"audit rows, got {len(first_audits)}: {first_audits!r}"
            )
        for row in audit_rows:
            if row[2] != user_id:
                fail(
                    "Location audit actor does not match the authenticated "
                    f"user: {row!r}"
                )

        update_audit = next(
            row
            for row in first_audits
            if row[0] == "location.updated"
        )
        delete_audit = next(
            row
            for row in first_audits
            if row[0] == "location.deleted"
        )

        update_before = (
            json_module.loads(update_audit[3])
            if isinstance(update_audit[3], str)
            else update_audit[3]
        )
        update_after = (
            json_module.loads(update_audit[4])
            if isinstance(update_audit[4], str)
            else update_audit[4]
        )
        update_metadata = (
            json_module.loads(update_audit[5])
            if isinstance(update_audit[5], str)
            else update_audit[5]
        )
        delete_before = (
            json_module.loads(delete_audit[3])
            if isinstance(delete_audit[3], str)
            else delete_audit[3]
        )
        delete_after = (
            json_module.loads(delete_audit[4])
            if isinstance(delete_audit[4], str)
            else delete_audit[4]
        )
        delete_metadata = (
            json_module.loads(delete_audit[5])
            if isinstance(delete_audit[5], str)
            else delete_audit[5]
        )

        if (
            update_before.get("name") != first_name
            or update_after.get("name") != updated_first_name
            or set(update_metadata.get("changed_fields", []))
            != {"name", "note"}
        ):
            fail(
                "Location update audit snapshots are incomplete: "
                f"{update_audit!r}"
            )
        if (
            delete_before.get("part_count") != 0
            or delete_after.get("deleted") is not True
            or delete_metadata.get("safe_delete_check") is not True
        ):
            fail(
                "Location deletion audit snapshots are incomplete: "
                f"{delete_audit!r}"
            )

    finally:
        cleanup()

    ok(
        "Reusable location catalogue is authenticated, normalized, editable, "
        "usage-aware, safe for active and deleted part references, and audited"
    )



# PATCH 160: reusable part location assignment API smoke test
def check_part_location_assignment_api() -> None:
    import json as json_module

    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app

    username = "smoke_part_location_user"
    password = "part-location-smoke-password"
    suffix = uuid4().hex[:10]
    first_name = f"Smoke Parts Drawer {suffix}"
    second_name = f"Smoke Parts Shelf {suffix}"
    part_number = f"SMOKE-PART-LOCATION-{suffix}"

    first_location_id: int | None = None
    second_location_id: int | None = None
    part_id: int | None = None
    user_id: int | None = None

    def cleanup() -> None:
        with db_session() as db:
            if part_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'part' "
                        "and entity_id = :entity_id"
                    ),
                    {"entity_id": part_id},
                )
                db.execute(
                    text(
                        "delete from stock_movements "
                        "where part_id = :part_id"
                    ),
                    {"part_id": part_id},
                )
                db.execute(
                    text(
                        "delete from part_field_values "
                        "where part_id = :part_id"
                    ),
                    {"part_id": part_id},
                )
                db.execute(
                    text("delete from parts where id = :part_id"),
                    {"part_id": part_id},
                )

            for location_id in (
                first_location_id,
                second_location_id,
            ):
                if location_id is None:
                    continue
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'location' "
                        "and entity_id = :entity_id"
                    ),
                    {"entity_id": location_id},
                )
                db.execute(
                    text("delete from locations where id = :location_id"),
                    {"location_id": location_id},
                )

            db.execute(
                text(
                    "delete from sessions where user_id in "
                    "(select id from users where username = :username)"
                ),
                {"username": username},
            )
            db.execute(
                text("delete from users where username = :username"),
                {"username": username},
            )
            db.commit()

    cleanup()
    client = TestClient(fastapi_app)

    try:
        with db_session() as db:
            user = create_user(
                db,
                username=username,
                display_name="Part Location Smoke User",
                password=password,
                commit=True,
            )
            user_id = user.id
            session_token = create_session(
                db,
                user=user,
                commit=True,
            )
            part_type_id = db.execute(
                text(
                    "select pt.id from part_types pt "
                    "where pt.is_active = 1 "
                    "and not exists ("
                    "select 1 from part_type_fields f "
                    "where f.part_type_id = pt.id "
                    "and f.is_required = 1"
                    ") order by pt.id limit 1"
                )
            ).scalar()

        if part_type_id is None:
            fail(
                "Part location smoke test requires one active part type "
                "without required template fields."
            )

        headers = {
            "Authorization": f"Bearer {session_token.token}",
        }

        first_response = client.post(
            "/api/locations",
            headers=headers,
            json={"name": first_name, "note": None},
        )
        if first_response.status_code != 201:
            fail(
                "Creating the first location returned "
                f"{first_response.status_code}: {first_response.text}"
            )
        first_location_id = first_response.json().get("id")
        if not isinstance(first_location_id, int):
            fail(
                "The first location response did not contain an integer id."
            )

        second_response = client.post(
            "/api/locations",
            headers=headers,
            json={"name": second_name, "note": None},
        )
        if second_response.status_code != 201:
            fail(
                "Creating the second location returned "
                f"{second_response.status_code}: {second_response.text}"
            )
        second_location_id = second_response.json().get("id")
        if not isinstance(second_location_id, int):
            fail(
                "The second location response did not contain an integer id."
            )

        base_payload = {
            "part_type_id": int(part_type_id),
            "manufacturer_id": None,
            "part_number": part_number,
            "name": "Part location smoke component",
            "description": None,
            "package": None,
            "notes": None,
            "total_quantity": 4,
            "unit_price": None,
            "purchase_link": None,
            "low_stock_enabled": False,
            "low_stock_threshold": None,
            "field_values": [],
        }

        invalid_create = client.post(
            "/api/parts",
            headers=headers,
            json={
                **base_payload,
                "part_number": f"{part_number}-INVALID",
                "location_id": 2147483647,
            },
        )
        if invalid_create.status_code != 422:
            fail(
                "Creating a part with a missing location should return 422, "
                f"got {invalid_create.status_code}: {invalid_create.text}"
            )

        create_response = client.post(
            "/api/parts",
            headers=headers,
            json={
                **base_payload,
                "location_id": first_location_id,
            },
        )
        if create_response.status_code != 201:
            fail(
                "Creating a located part returned "
                f"{create_response.status_code}: {create_response.text}"
            )
        created = create_response.json()
        part_id = created.get("id")
        if (
            not isinstance(part_id, int)
            or created.get("location_id") != first_location_id
            or created.get("location_name") != first_name
            or created.get("total_quantity") != 4
            or created.get("reserved_quantity") != 0
        ):
            fail(f"Unexpected located-part response: {created}")

        get_response = client.get(
            f"/api/parts/{part_id}",
            headers=headers,
        )
        if get_response.status_code != 200:
            fail(
                "Reading the located part returned "
                f"{get_response.status_code}: {get_response.text}"
            )
        if (
            get_response.json().get("location_id")
            != first_location_id
            or get_response.json().get("location_name") != first_name
        ):
            fail(
                "Part detail did not serialize the created location: "
                f"{get_response.json()}"
            )

        update_payload = {
            "part_type_id": int(part_type_id),
            "manufacturer_id": None,
            "location_id": second_location_id,
            "part_number": part_number,
            "name": "Part location smoke component",
            "description": None,
            "package": None,
            "notes": None,
            "unit_price": None,
            "purchase_link": None,
            "low_stock_enabled": False,
            "low_stock_threshold": None,
            "field_values": [],
        }

        invalid_update = client.put(
            f"/api/parts/{part_id}",
            headers=headers,
            json={
                **update_payload,
                "location_id": 2147483647,
            },
        )
        if invalid_update.status_code != 422:
            fail(
                "Updating a part to a missing location should return 422, "
                f"got {invalid_update.status_code}: {invalid_update.text}"
            )

        with db_session() as db:
            movement_count_before = int(
                db.execute(
                    text(
                        "select count(*) from stock_movements "
                        "where part_id = :part_id"
                    ),
                    {"part_id": part_id},
                ).scalar_one()
            )

        update_response = client.put(
            f"/api/parts/{part_id}",
            headers=headers,
            json=update_payload,
        )
        if update_response.status_code != 200:
            fail(
                "Updating a part location returned "
                f"{update_response.status_code}: {update_response.text}"
            )
        updated = update_response.json()
        if (
            updated.get("location_id") != second_location_id
            or updated.get("location_name") != second_name
            or updated.get("total_quantity") != 4
            or updated.get("reserved_quantity") != 0
        ):
            fail(f"Unexpected updated location response: {updated}")

        clear_response = client.put(
            f"/api/parts/{part_id}",
            headers=headers,
            json={
                **update_payload,
                "location_id": None,
            },
        )
        if clear_response.status_code != 200:
            fail(
                "Clearing a part location returned "
                f"{clear_response.status_code}: {clear_response.text}"
            )
        cleared = clear_response.json()
        if (
            cleared.get("location_id") is not None
            or cleared.get("location_name") is not None
            or cleared.get("total_quantity") != 4
            or cleared.get("reserved_quantity") != 0
        ):
            fail(f"Unexpected cleared location response: {cleared}")

        with db_session() as db:
            persisted = db.execute(
                text(
                    "select location_id, total_quantity, reserved_quantity "
                    "from parts where id = :part_id"
                ),
                {"part_id": part_id},
            ).one_or_none()
            movement_count_after = int(
                db.execute(
                    text(
                        "select count(*) from stock_movements "
                        "where part_id = :part_id"
                    ),
                    {"part_id": part_id},
                ).scalar_one()
            )
            audits = db.execute(
                text(
                    "select event_type, actor_user_id, before_json, "
                    "after_json, metadata_json from audit_log "
                    "where entity_type = 'part' "
                    "and entity_id = :part_id order by id"
                ),
                {"part_id": part_id},
            ).all()

        if (
            persisted is None
            or persisted[0] is not None
            or persisted[1] != 4
            or persisted[2] != 0
        ):
            fail(
                "Cleared location or quantities were not persisted correctly: "
                f"{persisted!r}"
            )
        if movement_count_after != movement_count_before:
            fail(
                "Metadata location changes must not create stock movements: "
                f"before={movement_count_before}, "
                f"after={movement_count_after}"
            )

        creation_audit = next(
            (row for row in audits if row[0] == "part.created"),
            None,
        )
        metadata_audits = [
            row
            for row in audits
            if row[0] == "part.metadata_updated"
        ]
        if creation_audit is None or len(metadata_audits) != 2:
            fail(
                "Expected one creation and two metadata audit events, got "
                f"{[row[0] for row in audits]}"
            )

        for row in audits:
            if row[1] != user_id:
                fail(
                    "Part location audit actor does not match the "
                    f"authenticated user: {row!r}"
                )

        creation_after = (
            json_module.loads(creation_audit[3])
            if isinstance(creation_audit[3], str)
            else creation_audit[3]
        )
        if (
            creation_after.get("location_id") != first_location_id
            or creation_after.get("location_name") != first_name
        ):
            fail(
                "Part creation audit omitted location data: "
                f"{creation_after!r}"
            )

        first_metadata = metadata_audits[0]
        second_metadata = metadata_audits[1]
        first_before = (
            json_module.loads(first_metadata[2])
            if isinstance(first_metadata[2], str)
            else first_metadata[2]
        )
        first_after = (
            json_module.loads(first_metadata[3])
            if isinstance(first_metadata[3], str)
            else first_metadata[3]
        )
        first_meta = (
            json_module.loads(first_metadata[4])
            if isinstance(first_metadata[4], str)
            else first_metadata[4]
        )
        second_after = (
            json_module.loads(second_metadata[3])
            if isinstance(second_metadata[3], str)
            else second_metadata[3]
        )
        second_meta = (
            json_module.loads(second_metadata[4])
            if isinstance(second_metadata[4], str)
            else second_metadata[4]
        )

        if (
            first_before.get("location_id") != first_location_id
            or first_after.get("location_id") != second_location_id
            or first_after.get("location_name") != second_name
            or not {
                "location_id",
                "location_name",
            }.issubset(set(first_meta.get("changed_fields", [])))
        ):
            fail(
                "Location change audit snapshots are incomplete: "
                f"{first_metadata!r}"
            )
        if (
            second_after.get("location_id") is not None
            or second_after.get("location_name") is not None
            or not {
                "location_id",
                "location_name",
            }.issubset(set(second_meta.get("changed_fields", [])))
        ):
            fail(
                "Location clearing audit snapshots are incomplete: "
                f"{second_metadata!r}"
            )

    finally:
        cleanup()

    ok(
        "Part creation and metadata editing support reusable location "
        "assignment, change, clearing, serialization, and complete audits"
    )


# PATCH 169: Stored Parts location filter API smoke test
def check_part_location_list_filter_api() -> None:
    from datetime import datetime, timezone

    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app
    from app.models import Location

    username = "smoke_location_filter_user"
    password = "location-filter-smoke-password"
    suffix = uuid4().hex[:10]
    first_location_name = f"Smoke Filter Drawer {suffix}"
    second_location_name = f"Smoke Filter Shelf {suffix}"
    part_ids: list[int] = []
    location_ids: list[int] = []
    user_id: int | None = None

    def cleanup() -> None:
        with db_session() as db:
            for part_id in part_ids:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'part' "
                        "and entity_id = :entity_id"
                    ),
                    {"entity_id": part_id},
                )
                db.execute(
                    text(
                        "delete from stock_movements "
                        "where part_id = :part_id"
                    ),
                    {"part_id": part_id},
                )
                db.execute(
                    text(
                        "delete from part_field_values "
                        "where part_id = :part_id"
                    ),
                    {"part_id": part_id},
                )
                db.execute(
                    text("delete from parts where id = :part_id"),
                    {"part_id": part_id},
                )

            for location_id in location_ids:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'location' "
                        "and entity_id = :entity_id"
                    ),
                    {"entity_id": location_id},
                )
                db.execute(
                    text(
                        "delete from locations "
                        "where id = :location_id"
                    ),
                    {"location_id": location_id},
                )

            db.execute(
                text(
                    "delete from sessions where user_id in "
                    "(select id from users where username = :username)"
                ),
                {"username": username},
            )
            db.execute(
                text("delete from users where username = :username"),
                {"username": username},
            )
            db.commit()

    cleanup()
    client = TestClient(fastapi_app)

    try:
        with db_session() as db:
            user = create_user(
                db,
                username=username,
                display_name="Location Filter Smoke User",
                password=password,
                commit=True,
            )
            user_id = user.id
            session_token = create_session(
                db,
                user=user,
                commit=True,
            )

            part_type_id = db.execute(
                text(
                    "select id from part_types "
                    "where is_active = 1 "
                    "order by id limit 1"
                )
            ).scalar()
            if part_type_id is None:
                fail(
                    "Location filter smoke test requires an active part type."
                )

            first_location = Location(
                name=first_location_name,
                normalized_name=normalize_location_name(
                    first_location_name
                ),
                note="Location filter smoke test",
            )
            second_location = Location(
                name=second_location_name,
                normalized_name=normalize_location_name(
                    second_location_name
                ),
                note="Location filter smoke test",
            )
            db.add_all([first_location, second_location])
            db.flush()
            location_ids.extend(
                [first_location.id, second_location.id]
            )

            parts = [
                Part(
                    part_type_id=int(part_type_id),
                    location_id=first_location.id,
                    part_number=f"SMOKE-LOC-FILTER-A-{suffix}",
                    name="Location filter first A",
                    total_quantity=5,
                    reserved_quantity=0,
                    is_deleted=False,
                ),
                Part(
                    part_type_id=int(part_type_id),
                    location_id=first_location.id,
                    part_number=f"SMOKE-LOC-FILTER-B-{suffix}",
                    name="Location filter first B",
                    total_quantity=3,
                    reserved_quantity=0,
                    is_deleted=False,
                ),
                Part(
                    part_type_id=int(part_type_id),
                    location_id=second_location.id,
                    part_number=f"SMOKE-LOC-FILTER-C-{suffix}",
                    name="Location filter second",
                    total_quantity=7,
                    reserved_quantity=0,
                    is_deleted=False,
                ),
                Part(
                    part_type_id=int(part_type_id),
                    location_id=None,
                    part_number=f"SMOKE-LOC-FILTER-U-{suffix}",
                    name="Location filter unassigned",
                    total_quantity=4,
                    reserved_quantity=0,
                    is_deleted=False,
                ),
                Part(
                    part_type_id=int(part_type_id),
                    location_id=first_location.id,
                    part_number=f"SMOKE-LOC-FILTER-D-{suffix}",
                    name="Location filter deleted",
                    total_quantity=2,
                    reserved_quantity=0,
                    is_deleted=True,
                    deleted_at=datetime.now(timezone.utc).replace(
                        tzinfo=None
                    ),
                ),
            ]
            db.add_all(parts)
            db.commit()
            for part in parts:
                db.refresh(part)
            part_ids.extend(part.id for part in parts)

            first_location_id = first_location.id
            second_location_id = second_location.id
            active_first_ids = {parts[0].id, parts[1].id}
            active_second_id = parts[2].id
            unassigned_id = parts[3].id
            deleted_id = parts[4].id

        unauthenticated = client.get(
            f"/api/parts?location_id={first_location_id}"
        )
        if unauthenticated.status_code not in (401, 403):
            fail(
                "Unauthenticated location filtering should be protected, "
                f"got {unauthenticated.status_code}: "
                f"{unauthenticated.text}"
            )

        headers = {
            "Authorization": f"Bearer {session_token.token}",
        }

        first_page = client.get(
            (
                f"/api/parts?location_id={first_location_id}"
                "&limit=1&offset=0"
            ),
            headers=headers,
        )
        if first_page.status_code != 200:
            fail(
                "First location filter page returned "
                f"{first_page.status_code}: {first_page.text}"
            )
        first_json = first_page.json()
        if (
            first_json.get("total") != 2
            or first_json.get("limit") != 1
            or first_json.get("offset") != 0
            or len(first_json.get("parts", [])) != 1
        ):
            fail(
                "First location filter page metadata is incorrect: "
                f"{first_json}"
            )

        second_page = client.get(
            (
                f"/api/parts?location_id={first_location_id}"
                "&limit=1&offset=1"
            ),
            headers=headers,
        )
        if second_page.status_code != 200:
            fail(
                "Second location filter page returned "
                f"{second_page.status_code}: {second_page.text}"
            )
        second_json = second_page.json()
        if (
            second_json.get("total") != 2
            or second_json.get("limit") != 1
            or second_json.get("offset") != 1
            or len(second_json.get("parts", [])) != 1
        ):
            fail(
                "Second location filter page metadata is incorrect: "
                f"{second_json}"
            )

        first_page_part = first_json["parts"][0]
        second_page_part = second_json["parts"][0]
        paged_ids = {
            first_page_part.get("id"),
            second_page_part.get("id"),
        }
        if paged_ids != active_first_ids:
            fail(
                "First-location pagination returned unexpected parts: "
                f"{paged_ids}, expected {active_first_ids}"
            )

        for item in (first_page_part, second_page_part):
            if (
                item.get("location_id") != first_location_id
                or item.get("location_name") != first_location_name
            ):
                fail(
                    "First-location response serialization is incorrect: "
                    f"{item}"
                )
            if item.get("id") == deleted_id:
                fail("Deleted part appeared in location-filter results.")

        second_response = client.get(
            f"/api/parts?location_id={second_location_id}",
            headers=headers,
        )
        if second_response.status_code != 200:
            fail(
                "Second location filter returned "
                f"{second_response.status_code}: {second_response.text}"
            )
        second_location_json = second_response.json()
        second_parts = second_location_json.get("parts", [])
        if (
            second_location_json.get("total") != 1
            or len(second_parts) != 1
            or second_parts[0].get("id") != active_second_id
            or second_parts[0].get("location_id")
            != second_location_id
            or second_parts[0].get("location_name")
            != second_location_name
        ):
            fail(
                "Second location filter returned unexpected data: "
                f"{second_location_json}"
            )

        missing_response = client.get(
            "/api/parts?location_id=2147483647",
            headers=headers,
        )
        if missing_response.status_code != 200:
            fail(
                "Missing numeric location filter should return 200, got "
                f"{missing_response.status_code}: "
                f"{missing_response.text}"
            )
        missing_json = missing_response.json()
        if (
            missing_json.get("total") != 0
            or missing_json.get("parts") != []
        ):
            fail(
                "Missing numeric location filter should be empty: "
                f"{missing_json}"
            )

        invalid_response = client.get(
            "/api/parts?location_id=0",
            headers=headers,
        )
        if invalid_response.status_code != 422:
            fail(
                "Non-positive location_id should return 422, got "
                f"{invalid_response.status_code}: "
                f"{invalid_response.text}"
            )

        combined_response = client.get(
            (
                f"/api/parts?location_id={first_location_id}"
                f"&part_type_id={int(part_type_id)}"
                "&limit=250"
            ),
            headers=headers,
        )
        if combined_response.status_code != 200:
            fail(
                "Combined part-type/location filter returned "
                f"{combined_response.status_code}: "
                f"{combined_response.text}"
            )
        combined_json = combined_response.json()
        if (
            combined_json.get("total") != 2
            or {
                item.get("id")
                for item in combined_json.get("parts", [])
            }
            != active_first_ids
        ):
            fail(
                "Combined part-type/location filter is incorrect: "
                f"{combined_json}"
            )

        unfiltered_response = client.get(
            "/api/parts?limit=250",
            headers=headers,
        )
        if unfiltered_response.status_code != 200:
            fail(
                "Unfiltered part collection returned "
                f"{unfiltered_response.status_code}: "
                f"{unfiltered_response.text}"
            )
        unfiltered_json = unfiltered_response.json()
        returned_ids = {
            item.get("id")
            for item in unfiltered_json.get("parts", [])
        }
        required_active_ids = active_first_ids | {
            active_second_id,
            unassigned_id,
        }
        if not required_active_ids.issubset(returned_ids):
            fail(
                "Unfiltered collection omitted active located/unassigned "
                f"smoke parts: returned={returned_ids}, "
                f"required={required_active_ids}"
            )
        if deleted_id in returned_ids:
            fail("Unfiltered collection included a deleted smoke part.")

        unassigned_row = next(
            (
                item
                for item in unfiltered_json.get("parts", [])
                if item.get("id") == unassigned_id
            ),
            None,
        )
        if (
            unassigned_row is None
            or unassigned_row.get("location_id") is not None
            or unassigned_row.get("location_name") is not None
        ):
            fail(
                "Unassigned part serialization is incorrect: "
                f"{unassigned_row}"
            )

        if user_id is None:
            fail("Location filter smoke user id was not recorded.")

    finally:
        cleanup()

    ok(
        "Stored Parts supports authenticated location filtering with correct "
        "totals, pagination, combined filters, serialization, unassigned "
        "parts, and deleted-part exclusion"
    )


# PATCH 182: protected search settings and low-stock summary smoke test
def check_low_stock_and_search_settings_api() -> None:
    import json as json_module
    from datetime import datetime, timezone

    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app
    from app.models import AppSetting, Location

    setting_key = "search.show_out_of_stock_section"
    suffix = uuid4().hex[:10]
    username = f"smoke_low_stock_{suffix}"
    password = "low-stock-smoke-password"
    location_name = f"Smoke Low Stock Drawer {suffix}"
    part_ids: list[int] = []
    location_id: int | None = None
    user_id: int | None = None

    with db_session() as db:
        original_setting_row = (
            db.query(AppSetting)
            .filter(AppSetting.key == setting_key)
            .one_or_none()
        )
        original_setting = (
            None
            if original_setting_row is None
            else (
                original_setting_row.value_json,
                original_setting_row.value_text,
            )
        )

    def cleanup() -> None:
        with db_session() as db:
            if user_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where event_type = 'settings.search_updated' "
                        "and actor_user_id = :actor_user_id"
                    ),
                    {"actor_user_id": user_id},
                )
            for part_id in part_ids:
                db.execute(
                    text(
                        "delete from stock_movements "
                        "where part_id = :part_id"
                    ),
                    {"part_id": part_id},
                )
                db.execute(
                    text(
                        "delete from part_field_values "
                        "where part_id = :part_id"
                    ),
                    {"part_id": part_id},
                )
                db.execute(
                    text("delete from parts where id = :part_id"),
                    {"part_id": part_id},
                )
            if location_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'location' "
                        "and entity_id = :entity_id"
                    ),
                    {"entity_id": location_id},
                )
                db.execute(
                    text(
                        "delete from locations where id = :location_id"
                    ),
                    {"location_id": location_id},
                )
            db.execute(
                text(
                    "delete from sessions where user_id in "
                    "(select id from users where username = :username)"
                ),
                {"username": username},
            )
            db.execute(
                text("delete from users where username = :username"),
                {"username": username},
            )

            setting = (
                db.query(AppSetting)
                .filter(AppSetting.key == setting_key)
                .one_or_none()
            )
            if original_setting is None:
                if setting is not None:
                    db.delete(setting)
            elif setting is None:
                db.add(
                    AppSetting(
                        key=setting_key,
                        value_json=original_setting[0],
                        value_text=original_setting[1],
                    )
                )
            else:
                setting.value_json = original_setting[0]
                setting.value_text = original_setting[1]

            db.commit()

    client = TestClient(fastapi_app)

    try:
        unauthenticated_settings = client.get(
            "/api/settings/search"
        )
        if unauthenticated_settings.status_code not in {401, 403}:
            fail(
                "GET /api/settings/search should require authentication, "
                f"got {unauthenticated_settings.status_code}: "
                f"{unauthenticated_settings.text}"
            )
        unauthenticated_patch = client.patch(
            "/api/settings/search",
            json={"show_out_of_stock_section": False},
        )
        if unauthenticated_patch.status_code not in {401, 403}:
            fail(
                "PATCH /api/settings/search should require authentication, "
                f"got {unauthenticated_patch.status_code}: "
                f"{unauthenticated_patch.text}"
            )
        unauthenticated_low_stock = client.get(
            "/api/parts/low-stock"
        )
        if unauthenticated_low_stock.status_code not in {401, 403}:
            fail(
                "GET /api/parts/low-stock should require authentication, "
                f"got {unauthenticated_low_stock.status_code}: "
                f"{unauthenticated_low_stock.text}"
            )

        with db_session() as db:
            set_app_setting(
                db,
                setting_key,
                True,
                commit=True,
            )
            user = create_user(
                db,
                username=username,
                display_name="Low Stock Smoke User",
                password=password,
                commit=True,
            )
            user_id = user.id
            session_token = create_session(
                db,
                user=user,
                commit=True,
            )
            part_type_id = db.execute(
                text(
                    "select id from part_types "
                    "where is_active = 1 order by id limit 1"
                )
            ).scalar()
            if part_type_id is None:
                fail(
                    "Low-stock smoke test requires an active part type."
                )

            location = Location(
                name=location_name,
                normalized_name=normalize_location_name(
                    location_name
                ),
                note="Patch 182 low-stock smoke isolation",
            )
            db.add(location)
            db.flush()
            location_id = location.id

            parts = [
                Part(
                    part_type_id=int(part_type_id),
                    location_id=location.id,
                    part_number=f"SMOKE-LOW-ZERO-{suffix}",
                    name="Out of stock smoke part",
                    total_quantity=0,
                    reserved_quantity=0,
                    low_stock_enabled=True,
                    low_stock_threshold=2,
                    is_deleted=False,
                ),
                Part(
                    part_type_id=int(part_type_id),
                    location_id=location.id,
                    part_number=f"SMOKE-LOW-RESERVED-{suffix}",
                    name="Reserved low-stock smoke part",
                    total_quantity=5,
                    reserved_quantity=4,
                    low_stock_enabled=True,
                    low_stock_threshold=1,
                    is_deleted=False,
                ),
                Part(
                    part_type_id=int(part_type_id),
                    location_id=location.id,
                    part_number=f"SMOKE-LOW-THRESHOLD-{suffix}",
                    name="Threshold low-stock smoke part",
                    total_quantity=5,
                    reserved_quantity=3,
                    low_stock_enabled=True,
                    low_stock_threshold=2,
                    is_deleted=False,
                ),
                # PATCH 189: unconfigured zero-stock contract
                Part(
                    part_type_id=int(part_type_id),
                    location_id=location.id,
                    part_number=f"SMOKE-LOW-UNCONFIGURED-ZERO-{suffix}",
                    name="Unconfigured zero-stock smoke part",
                    total_quantity=0,
                    reserved_quantity=0,
                    low_stock_enabled=False,
                    low_stock_threshold=None,
                    is_deleted=False,
                ),
                Part(
                    part_type_id=int(part_type_id),
                    location_id=location.id,
                    part_number=f"SMOKE-LOW-ABOVE-{suffix}",
                    name="Above-threshold smoke part",
                    total_quantity=5,
                    reserved_quantity=0,
                    low_stock_enabled=True,
                    low_stock_threshold=2,
                    is_deleted=False,
                ),
                Part(
                    part_type_id=int(part_type_id),
                    location_id=location.id,
                    part_number=f"SMOKE-LOW-DELETED-{suffix}",
                    name="Deleted low-stock smoke part",
                    total_quantity=0,
                    reserved_quantity=0,
                    low_stock_enabled=True,
                    low_stock_threshold=2,
                    is_deleted=True,
                    deleted_at=datetime.now(
                        timezone.utc
                    ).replace(tzinfo=None),
                ),
            ]
            db.add_all(parts)
            db.commit()
            for part in parts:
                db.refresh(part)
            part_ids.extend(part.id for part in parts)

            zero_id = parts[0].id
            reserved_id = parts[1].id
            threshold_id = parts[2].id
            unconfigured_zero_id = parts[3].id
            above_id = parts[4].id
            deleted_id = parts[5].id

        headers = {
            "Authorization": f"Bearer {session_token.token}",
        }

        initial_settings = client.get(
            "/api/settings/search",
            headers=headers,
        )
        if initial_settings.status_code != 200:
            fail(
                "GET /api/settings/search returned "
                f"{initial_settings.status_code}: "
                f"{initial_settings.text}"
            )
        if (
            initial_settings.json().get(
                "show_out_of_stock_section"
            )
            is not True
        ):
            fail(
                "GET /api/settings/search did not return the seeded "
                f"enabled value: {initial_settings.json()}"
            )

        disable_response = client.patch(
            "/api/settings/search",
            headers=headers,
            json={"show_out_of_stock_section": False},
        )
        if disable_response.status_code != 200:
            fail(
                "PATCH /api/settings/search returned "
                f"{disable_response.status_code}: "
                f"{disable_response.text}"
            )
        if (
            disable_response.json().get(
                "show_out_of_stock_section"
            )
            is not False
        ):
            fail(
                "PATCH /api/settings/search did not disable the "
                f"setting: {disable_response.json()}"
            )

        persisted_disabled = client.get(
            "/api/settings/search",
            headers=headers,
        )
        if (
            persisted_disabled.status_code != 200
            or persisted_disabled.json().get(
                "show_out_of_stock_section"
            )
            is not False
        ):
            fail(
                "Disabled search setting was not persisted: "
                f"{persisted_disabled.status_code} "
                f"{persisted_disabled.text}"
            )

        repeat_disable = client.patch(
            "/api/settings/search",
            headers=headers,
            json={"show_out_of_stock_section": False},
        )
        if repeat_disable.status_code != 200:
            fail(
                "Idempotent search-setting PATCH returned "
                f"{repeat_disable.status_code}: "
                f"{repeat_disable.text}"
            )

        enable_response = client.patch(
            "/api/settings/search",
            headers=headers,
            json={"show_out_of_stock_section": True},
        )
        if (
            enable_response.status_code != 200
            or enable_response.json().get(
                "show_out_of_stock_section"
            )
            is not True
        ):
            fail(
                "Re-enabling the search setting failed: "
                f"{enable_response.status_code} "
                f"{enable_response.text}"
            )

        with db_session() as db:
            setting_row = (
                db.query(AppSetting)
                .filter(AppSetting.key == setting_key)
                .one_or_none()
            )
            if (
                setting_row is None
                or setting_row.value_json is not True
            ):
                fail(
                    "Search setting database row is incorrect after "
                    f"re-enable: {setting_row!r}"
                )
            audit_rows = db.execute(
                text(
                    "select actor_user_id, before_json, after_json, "
                    "metadata_json from audit_log "
                    "where event_type = 'settings.search_updated' "
                    "and actor_user_id = :actor_user_id "
                    "order by id"
                ),
                {"actor_user_id": user_id},
            ).all()

        if len(audit_rows) != 2:
            fail(
                "Search settings should create one audit per actual "
                f"change and none for idempotent updates, got "
                f"{len(audit_rows)}."
            )

        decoded_audits: list[tuple[dict, dict, dict]] = []
        for row in audit_rows:
            if row[0] != user_id:
                fail(
                    "Search-setting audit actor is incorrect: "
                    f"{row!r}"
                )
            before_json = (
                json_module.loads(row[1])
                if isinstance(row[1], str)
                else row[1]
            )
            after_json = (
                json_module.loads(row[2])
                if isinstance(row[2], str)
                else row[2]
            )
            metadata_json = (
                json_module.loads(row[3])
                if isinstance(row[3], str)
                else row[3]
            )
            decoded_audits.append(
                (before_json, after_json, metadata_json)
            )

        if (
            decoded_audits[0][0].get(
                "show_out_of_stock_section"
            )
            is not True
            or decoded_audits[0][1].get(
                "show_out_of_stock_section"
            )
            is not False
            or decoded_audits[1][0].get(
                "show_out_of_stock_section"
            )
            is not False
            or decoded_audits[1][1].get(
                "show_out_of_stock_section"
            )
            is not True
        ):
            fail(
                "Search-setting audit before/after snapshots are "
                f"incorrect: {decoded_audits!r}"
            )
        for _, _, metadata_json in decoded_audits:
            if (
                metadata_json.get("setting_key") != setting_key
                or "show_out_of_stock_section"
                not in metadata_json.get("changed_fields", [])
            ):
                fail(
                    "Search-setting audit metadata is incomplete: "
                    f"{metadata_json!r}"
                )

        full_response = client.get(
            (
                "/api/parts/low-stock"
                f"?location_id={location_id}"
                f"&part_type_id={int(part_type_id)}"
                "&limit=10"
            ),
            headers=headers,
        )
        if full_response.status_code != 200:
            fail(
                "GET /api/parts/low-stock returned "
                f"{full_response.status_code}: "
                f"{full_response.text}"
            )
        full_json = full_response.json()
        returned_parts = full_json.get("parts", [])
        returned_ids = [
            item.get("id")
            for item in returned_parts
        ]
        if (
            full_json.get("total") != 4
            or full_json.get("low_stock_count") != 2
            or full_json.get("out_of_stock_count") != 2
            or full_json.get("limit") != 10
            or returned_ids
            != [
                unconfigured_zero_id,
                zero_id,
                reserved_id,
                threshold_id,
            ]
        ):
            fail(
                "Low-stock summary totals or severity ordering are "
                f"incorrect: {full_json}"
            )

        expected_available = {
            unconfigured_zero_id: 0,
            zero_id: 0,
            reserved_id: 1,
            threshold_id: 2,
        }
        expected_is_low_stock = {
            unconfigured_zero_id: False,
            zero_id: True,
            reserved_id: True,
            threshold_id: True,
        }
        for item in returned_parts:
            item_id = item.get("id")
            if (
                item.get("available_quantity")
                != expected_available.get(item_id)
                or item.get("is_low_stock")
                is not expected_is_low_stock.get(item_id)
                or item.get("location_id") != location_id
                or item.get("location_name") != location_name
            ):
                fail(
                    "Low-stock part serialization is incorrect: "
                    f"{item}"
                )

        excluded_ids = {
            above_id,
            deleted_id,
        }
        if excluded_ids.intersection(returned_ids):
            fail(
                "Low-stock summary included above-threshold or deleted "
                f"rows: {returned_ids}"
            )
        if unconfigured_zero_id not in returned_ids:
            fail(
                "Low-stock summary excluded an active zero-stock row "
                "without a configured threshold."
            )

        limited_response = client.get(
            (
                "/api/parts/low-stock"
                f"?location_id={location_id}"
                "&limit=2"
            ),
            headers=headers,
        )
        limited_json = limited_response.json()
        if (
            limited_response.status_code != 200
            or limited_json.get("total") != 4
            or limited_json.get("low_stock_count") != 2
            or limited_json.get("out_of_stock_count") != 2
            or [
                item.get("id")
                for item in limited_json.get("parts", [])
            ]
            != [unconfigured_zero_id, zero_id]
        ):
            fail(
                "Limited low-stock response should retain full counts "
                f"and severity order: {limited_response.status_code} "
                f"{limited_json}"
            )

        empty_response = client.get(
            (
                "/api/parts/low-stock"
                "?location_id=2147483647"
            ),
            headers=headers,
        )
        empty_json = empty_response.json()
        if (
            empty_response.status_code != 200
            or empty_json.get("total") != 0
            or empty_json.get("low_stock_count") != 0
            or empty_json.get("out_of_stock_count") != 0
            or empty_json.get("parts") != []
        ):
            fail(
                "Missing-location low-stock response should be empty: "
                f"{empty_response.status_code} {empty_json}"
            )

        invalid_location = client.get(
            "/api/parts/low-stock?location_id=0",
            headers=headers,
        )
        if invalid_location.status_code != 422:
            fail(
                "Non-positive low-stock location_id should return 422, "
                f"got {invalid_location.status_code}: "
                f"{invalid_location.text}"
            )

        invalid_limit = client.get(
            "/api/parts/low-stock?limit=0",
            headers=headers,
        )
        if invalid_limit.status_code != 422:
            fail(
                "Non-positive low-stock limit should return 422, got "
                f"{invalid_limit.status_code}: "
                f"{invalid_limit.text}"
            )

    finally:
        cleanup()

    ok(
        "Protected search settings persist and audit actual changes; "
        "low-stock summary handles configured and unconfigured zero stock, "
        "reservations, thresholds, disabled positive stock, deleted rows, "
        "filters, limits, counts, and deterministic severity ordering"
    )


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
        check_phase4_part_types_service,
        check_phase4_part_types_api,
        check_custom_part_type_creation,
        check_custom_part_type_update_api,
        check_custom_part_type_delete_api,
        check_inventory_part_creation_api,
        check_manufacturer_catalogue_api,
        check_package_catalogue_api,
        check_location_catalogue_api,
        check_part_location_assignment_api,
        check_part_location_list_filter_api,
        check_low_stock_and_search_settings_api,
        check_stock_quantity_adjustment_api,
        check_part_metadata_update_api,
        check_part_soft_delete_restore_api,
    ]

    for check in checks:
        check()

    print("[PASS] Phase 4 part type management smoke test completed")


if __name__ == "__main__":
    main()
