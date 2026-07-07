from __future__ import annotations

from contextlib import contextmanager

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import exc, text

from app.db.session import SessionLocal, engine
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
        db.begin()
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
        transaction = db.begin()
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

            transaction.rollback()

            remaining = db.execute(
                text("select count(*) from parts where part_number = 'SMOKE-TEST-IRFZ44N'")
            ).scalar()
            if remaining != 0:
                fail("Smoke test sample part was not rolled back")
        except Exception:
            if transaction.is_active:
                transaction.rollback()
            raise

    ok("Valid sample part can be inserted and rolled back")


def main() -> None:
    checks = [
        check_db_connects,
        check_sqlite_foreign_keys,
        check_alembic_at_head,
        check_seed_data,
        check_invalid_part_rejected,
        check_valid_part_insert_rolls_back,
    ]

    for check in checks:
        check()

    print("[PASS] Phase 2 database smoke test completed")


if __name__ == "__main__":
    main()
