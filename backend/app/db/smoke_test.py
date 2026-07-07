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


EXPECTED_PART_TYPES = 34
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
    ]

    for check in checks:
        check()

    print("[PASS] Phase 3 auth foundation smoke test completed")


if __name__ == "__main__":
    main()
