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
EXPECTED_AUTH_SCHEMA_HEAD = "0006_reservation_contract"
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



# PARTPILOT:RESERVATION_CONTRACT_SMOKE:V298
def check_reservation_contract_schema() -> None:
    expected_statuses = {
        "active",
        "consumed",
        "cancelled",
        "expired",
    }
    if RESERVATION_STATUSES != expected_statuses:
        fail(
            "RESERVATION_STATUSES does not match the canonical contract: "
            f"{sorted(RESERVATION_STATUSES)}"
        )

    required_movement_types = {"reserve", "release", "consume"}
    if not required_movement_types.issubset(MOVEMENT_TYPES):
        fail(
            "MOVEMENT_TYPES is missing reservation lifecycle values: "
            f"{sorted(required_movement_types - MOVEMENT_TYPES)}"
        )

    with db_session() as db:
        reservation_sql = db.execute(
            text(
                "select sql from sqlite_master "
                "where type = 'table' and name = 'reservations'"
            )
        ).scalar()
        item_sql = db.execute(
            text(
                "select sql from sqlite_master "
                "where type = 'table' and name = 'reservation_items'"
            )
        ).scalar()
        movement_sql = db.execute(
            text(
                "select sql from sqlite_master "
                "where type = 'table' and name = 'stock_movements'"
            )
        ).scalar()

        if not reservation_sql or not item_sql or not movement_sql:
            fail("Reservation contract tables are missing")

        for constraint_name in {
            "ck_reservations_status",
            "ck_reservations_created_by",
            "ck_reservations_estimated_reserved_value_nonnegative",
        }:
            if constraint_name not in reservation_sql:
                fail(
                    "reservations is missing constraint "
                    f"{constraint_name}"
                )

        if (
            "ck_reservation_items_unit_price_snapshot_nonnegative"
            not in item_sql
        ):
            fail(
                "reservation_items is missing its unit-price constraint"
            )

        movement_constraints = {
            "ck_stock_movements_quantity_before_nonnegative",
            "ck_stock_movements_quantity_after_nonnegative",
            "ck_stock_movements_unit_price_snapshot_nonnegative",
            (
                "ck_stock_movements_reserved_quantity_before_"
                "nonnegative"
            ),
            (
                "ck_stock_movements_reserved_quantity_after_"
                "nonnegative"
            ),
            (
                "ck_stock_movements_available_quantity_before_"
                "nonnegative"
            ),
            (
                "ck_stock_movements_available_quantity_after_"
                "nonnegative"
            ),
        }
        for constraint_name in movement_constraints:
            if constraint_name not in movement_sql:
                fail(
                    "stock_movements is missing constraint "
                    f"{constraint_name}"
                )

        movement_columns = {
            row[1]
            for row in db.execute(
                text("PRAGMA table_info(stock_movements)")
            ).fetchall()
        }
        required_columns = {
            "reservation_id",
            "reserved_quantity_before",
            "reserved_quantity_after",
            "available_quantity_before",
            "available_quantity_after",
        }
        missing_columns = required_columns - movement_columns
        if missing_columns:
            fail(
                "stock_movements is missing reservation columns: "
                f"{sorted(missing_columns)}"
            )

        foreign_keys = db.execute(
            text("PRAGMA foreign_key_list(stock_movements)")
        ).fetchall()
        reservation_foreign_keys = [
            row
            for row in foreign_keys
            if row[2] == "reservations"
            and row[3] == "reservation_id"
            and row[4] == "id"
            and str(row[6]).upper() == "SET NULL"
        ]
        if len(reservation_foreign_keys) != 1:
            fail(
                "stock_movements reservation foreign key is incorrect: "
                f"{reservation_foreign_keys}"
            )

        index_names = {
            row[1]
            for row in db.execute(
                text("PRAGMA index_list(stock_movements)")
            ).fetchall()
        }
        required_indexes = {
            "ix_stock_movements_reservation_id",
            "ix_stock_movements_reservation_created",
        }
        if not required_indexes.issubset(index_names):
            fail(
                "stock_movements is missing reservation indexes: "
                f"{sorted(required_indexes - index_names)}"
            )

        composite_columns = [
            row[2]
            for row in db.execute(
                text(
                    "PRAGMA index_info("
                    "ix_stock_movements_reservation_created)"
                )
            ).fetchall()
        ]
        if composite_columns != ["reservation_id", "created_at"]:
            fail(
                "Reservation movement index columns are incorrect: "
                f"{composite_columns}"
            )

        invalid_status_count = db.execute(
            text(
                "select count(*) from reservations "
                "where status not in ("
                "'active', 'consumed', 'cancelled', 'expired'"
                ")"
            )
        ).scalar()
        if invalid_status_count != 0:
            fail(
                "Existing reservations contain invalid statuses: "
                f"{invalid_status_count}"
            )

        invalid_snapshot_count = db.execute(
            text(
                "select count(*) from stock_movements where "
                "reserved_quantity_before < 0 or "
                "reserved_quantity_after < 0 or "
                "available_quantity_before < 0 or "
                "available_quantity_after < 0"
            )
        ).scalar()
        if invalid_snapshot_count != 0:
            fail(
                "Existing movements contain invalid reservation "
                f"snapshots: {invalid_snapshot_count}"
            )

    with db_session() as db:
        try:
            db.execute(
                text(
                    "insert into reservations "
                    "(label, status, created_by) "
                    "values (:label, :status, :created_by)"
                ),
                {
                    "label": "Invalid reservation contract smoke row",
                    "status": "released",
                    "created_by": "system",
                },
            )
            db.flush()
        except exc.IntegrityError:
            db.rollback()
        else:
            db.rollback()
            fail("reservations accepted the obsolete released status")

    with db_session() as db:
        try:
            db.execute(
                text(
                    "insert into stock_movements ("
                    "movement_type, quantity_delta, source, "
                    "reserved_quantity_before"
                    ") values ("
                    ":movement_type, :quantity_delta, :source, "
                    ":reserved_quantity_before"
                    ")"
                ),
                {
                    "movement_type": "reserve",
                    "quantity_delta": 0,
                    "source": "system",
                    "reserved_quantity_before": -1,
                },
            )
            db.flush()
        except exc.IntegrityError:
            db.rollback()
        else:
            db.rollback()
            fail(
                "stock_movements accepted a negative reserved snapshot"
            )

    ok(
        "Reservation lifecycle schema, statuses, movement snapshots, "
        "constraints, foreign keys, and indexes are aligned"
    )


# PARTPILOT:RESERVATION_CREATION_SERVICE_SMOKE:V301
def check_reservation_creation_service() -> None:
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal

    from app.models import Part
    from app.schemas.reservations import (
        ReservationCreateRequest,
        ReservationItemCreateRequest,
    )
    from app.services.reservations import (
        ReservationConflictError,
        create_reservation,
    )

    suffix = uuid4().hex[:12]
    part_number_one = f"SMOKE-RESERVE-A-{suffix}"
    part_number_two = f"SMOKE-RESERVE-B-{suffix}"
    part_ids: list[int] = []
    reservation_id: int | None = None

    def cleanup() -> None:
        with db_session() as db:
            if reservation_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'reservation' "
                        "and entity_id = :reservation_id"
                    ),
                    {"reservation_id": reservation_id},
                )
                db.execute(
                    text(
                        "delete from stock_movements "
                        "where reservation_id = :reservation_id"
                    ),
                    {"reservation_id": reservation_id},
                )
                db.execute(
                    text(
                        "delete from reservation_items "
                        "where reservation_id = :reservation_id"
                    ),
                    {"reservation_id": reservation_id},
                )
                db.execute(
                    text(
                        "delete from reservations "
                        "where id = :reservation_id"
                    ),
                    {"reservation_id": reservation_id},
                )

            if part_ids:
                placeholders = ", ".join(
                    f":part_id_{index}"
                    for index, _part_id in enumerate(part_ids)
                )
                parameters = {
                    f"part_id_{index}": part_id
                    for index, part_id in enumerate(part_ids)
                }
                db.execute(
                    text(
                        "delete from stock_movements "
                        f"where part_id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'part' "
                        f"and entity_id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(
                        "delete from parts "
                        f"where id in ({placeholders})"
                    ),
                    parameters,
                )
            db.commit()

    cleanup()
    try:
        with db_session() as db:
            part_type_id = db.execute(
                text(
                    "select id from part_types "
                    "where is_active = 1 "
                    "order by id limit 1"
                )
            ).scalar()
            if part_type_id is None:
                fail(
                    "Cannot test reservation creation without an "
                    "active part type"
                )

            first = Part(
                part_type_id=part_type_id,
                part_number=part_number_one,
                name="Reservation service smoke part A",
                total_quantity=7,
                reserved_quantity=0,
                unit_price=Decimal("2.5000"),
                is_deleted=False,
                deleted_at=None,
            )
            second = Part(
                part_type_id=part_type_id,
                part_number=part_number_two,
                name="Reservation service smoke part B",
                total_quantity=4,
                reserved_quantity=0,
                unit_price=None,
                is_deleted=False,
                deleted_at=None,
            )
            db.add(first)
            db.add(second)
            db.commit()
            db.refresh(first)
            db.refresh(second)
            part_ids.extend([first.id, second.id])

        with db_session() as db:
            response = create_reservation(
                db,
                ReservationCreateRequest(
                    label="  Smoke reservation service  ",
                    notes="  Atomic allocation smoke test  ",
                    expiry_at=(
                        datetime.now(timezone.utc)
                        + timedelta(days=1)
                    ),
                    items=[
                        ReservationItemCreateRequest(
                            part_id=part_ids[0],
                            quantity=1,
                            note="Primary allocation",
                        ),
                        ReservationItemCreateRequest(
                            part_id=part_ids[0],
                            quantity=2,
                            note="Primary allocation",
                        ),
                        ReservationItemCreateRequest(
                            part_id=part_ids[1],
                            quantity=2,
                        ),
                    ],
                ),
                commit=True,
            )
            reservation_id = response.id

            if response.label != "Smoke reservation service":
                fail(
                    "Reservation service did not normalise the label: "
                    f"{response.label!r}"
                )
            if response.notes != "Atomic allocation smoke test":
                fail(
                    "Reservation service did not normalise notes: "
                    f"{response.notes!r}"
                )
            if response.status != "active":
                fail(
                    "Reservation service returned the wrong status: "
                    f"{response.status!r}"
                )
            if response.project_id is not None:
                fail(
                    "Reservation creation unexpectedly attached a project"
                )
            if response.estimated_reserved_value is not None:
                fail(
                    "Reservation estimate should be unknown when one "
                    "part has no unit price"
                )
            if len(response.items) != 2:
                fail(
                    "Reservation service did not merge duplicate parts: "
                    f"{len(response.items)} items"
                )

            by_part = {
                item.part_id: item
                for item in response.items
            }
            if by_part[part_ids[0]].quantity != 3:
                fail(
                    "Merged reservation quantity is incorrect for "
                    "the first part"
                )
            if by_part[part_ids[1]].quantity != 2:
                fail(
                    "Reservation quantity is incorrect for the "
                    "second part"
                )
            if by_part[part_ids[0]].reserved_quantity != 3:
                fail(
                    "First part response has the wrong reserved quantity"
                )
            if by_part[part_ids[0]].available_quantity != 4:
                fail(
                    "First part response has the wrong available quantity"
                )
            if by_part[part_ids[1]].reserved_quantity != 2:
                fail(
                    "Second part response has the wrong reserved quantity"
                )
            if by_part[part_ids[1]].available_quantity != 2:
                fail(
                    "Second part response has the wrong available quantity"
                )

            stored_parts = db.execute(
                text(
                    "select id, total_quantity, reserved_quantity "
                    "from parts where id in (:first_id, :second_id) "
                    "order by id"
                ),
                {
                    "first_id": part_ids[0],
                    "second_id": part_ids[1],
                },
            ).mappings().all()
            stored_by_id = {
                int(row["id"]): row
                for row in stored_parts
            }
            if int(
                stored_by_id[part_ids[0]]["total_quantity"]
            ) != 7:
                fail(
                    "Reservation creation changed physical stock for "
                    "the first part"
                )
            if int(
                stored_by_id[part_ids[1]]["total_quantity"]
            ) != 4:
                fail(
                    "Reservation creation changed physical stock for "
                    "the second part"
                )
            if int(
                stored_by_id[part_ids[0]]["reserved_quantity"]
            ) != 3:
                fail(
                    "First part reserved quantity was not persisted"
                )
            if int(
                stored_by_id[part_ids[1]]["reserved_quantity"]
            ) != 2:
                fail(
                    "Second part reserved quantity was not persisted"
                )

            items = db.execute(
                text(
                    "select part_id, quantity, note "
                    "from reservation_items "
                    "where reservation_id = :reservation_id "
                    "order by part_id"
                ),
                {"reservation_id": reservation_id},
            ).mappings().all()
            if len(items) != 2:
                fail(
                    "Reservation item row count is incorrect: "
                    f"{len(items)}"
                )

            movements = db.execute(
                text(
                    "select part_id, movement_type, quantity_delta, "
                    "quantity_before, quantity_after, "
                    "reserved_quantity_before, "
                    "reserved_quantity_after, "
                    "available_quantity_before, "
                    "available_quantity_after "
                    "from stock_movements "
                    "where reservation_id = :reservation_id "
                    "order by part_id"
                ),
                {"reservation_id": reservation_id},
            ).mappings().all()
            if len(movements) != 2:
                fail(
                    "Reservation movement row count is incorrect: "
                    f"{len(movements)}"
                )

            movement_by_id = {
                int(row["part_id"]): row
                for row in movements
            }
            expected = {
                part_ids[0]: {
                    "total": 7,
                    "reserved_before": 0,
                    "reserved_after": 3,
                    "available_before": 7,
                    "available_after": 4,
                },
                part_ids[1]: {
                    "total": 4,
                    "reserved_before": 0,
                    "reserved_after": 2,
                    "available_before": 4,
                    "available_after": 2,
                },
            }
            for part_id, values in expected.items():
                row = movement_by_id[part_id]
                if row["movement_type"] != "reserve":
                    fail(
                        "Reservation movement type is incorrect: "
                        f"{row['movement_type']!r}"
                    )
                if int(row["quantity_delta"]) != 0:
                    fail(
                        "Reservation movement changed physical quantity"
                    )
                if (
                    int(row["quantity_before"]) != values["total"]
                    or int(row["quantity_after"]) != values["total"]
                    or int(row["reserved_quantity_before"])
                    != values["reserved_before"]
                    or int(row["reserved_quantity_after"])
                    != values["reserved_after"]
                    or int(row["available_quantity_before"])
                    != values["available_before"]
                    or int(row["available_quantity_after"])
                    != values["available_after"]
                ):
                    fail(
                        "Reservation movement snapshots are incorrect "
                        f"for part {part_id}: {dict(row)}"
                    )

            audit_count = db.execute(
                text(
                    "select count(*) from audit_log "
                    "where event_type = 'reservation.created' "
                    "and entity_type = 'reservation' "
                    "and entity_id = :reservation_id"
                ),
                {"reservation_id": reservation_id},
            ).scalar()
            if audit_count != 1:
                fail(
                    "Reservation creation audit count is incorrect: "
                    f"{audit_count}"
                )

        with db_session() as db:
            before_counts = {
                "reservations": db.execute(
                    text(
                        "select count(*) from reservations"
                    )
                ).scalar(),
                "reservation_items": db.execute(
                    text(
                        "select count(*) from reservation_items"
                    )
                ).scalar(),
                "stock_movements": db.execute(
                    text(
                        "select count(*) from stock_movements "
                        "where reservation_id = :reservation_id"
                    ),
                    {"reservation_id": reservation_id},
                ).scalar(),
            }
            try:
                create_reservation(
                    db,
                    ReservationCreateRequest(
                        label="Insufficient stock smoke reservation",
                        items=[
                            ReservationItemCreateRequest(
                                part_id=part_ids[1],
                                quantity=3,
                            )
                        ],
                    ),
                    commit=True,
                )
            except ReservationConflictError:
                pass
            else:
                fail(
                    "Reservation service accepted more than the "
                    "available quantity"
                )

        with db_session() as db:
            after_counts = {
                "reservations": db.execute(
                    text(
                        "select count(*) from reservations"
                    )
                ).scalar(),
                "reservation_items": db.execute(
                    text(
                        "select count(*) from reservation_items"
                    )
                ).scalar(),
                "stock_movements": db.execute(
                    text(
                        "select count(*) from stock_movements "
                        "where reservation_id = :reservation_id"
                    ),
                    {"reservation_id": reservation_id},
                ).scalar(),
            }
            if after_counts != before_counts:
                fail(
                    "Failed reservation creation left partial rows: "
                    f"before={before_counts}, after={after_counts}"
                )

            reserved_quantity = db.execute(
                text(
                    "select reserved_quantity from parts "
                    "where id = :part_id"
                ),
                {"part_id": part_ids[1]},
            ).scalar()
            if reserved_quantity != 2:
                fail(
                    "Failed reservation creation changed reserved stock: "
                    f"{reserved_quantity}"
                )

    finally:
        cleanup()

    ok(
        "Reservation creation service normalises items and reserves "
        "stock atomically"
    )


# PARTPILOT:RESERVATION_READ_CREATE_API_SMOKE:V303
def check_reservation_read_create_api() -> None:
    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app
    from app.models import Part
    from app.services.auth import create_session, create_user

    suffix = uuid4().hex[:12]
    username = f"smoke_reservation_api_{suffix}"
    password = "reservation-api-smoke-password"
    part_number = f"SMOKE-RESERVATION-API-{suffix}"
    part_id: int | None = None
    user_id: int | None = None
    reservation_ids: list[int] = []

    def cleanup() -> None:
        with db_session() as db:
            if reservation_ids:
                placeholders = ", ".join(
                    f":reservation_id_{index}"
                    for index, _value in enumerate(reservation_ids)
                )
                parameters = {
                    f"reservation_id_{index}": value
                    for index, value in enumerate(reservation_ids)
                }
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'reservation' "
                        f"and entity_id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(
                        "delete from stock_movements "
                        f"where reservation_id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(
                        "delete from reservation_items "
                        f"where reservation_id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(
                        "delete from reservations "
                        f"where id in ({placeholders})"
                    ),
                    parameters,
                )

            if part_id is not None:
                db.execute(
                    text(
                        "update parts set reserved_quantity = 0 "
                        "where id = :part_id"
                    ),
                    {"part_id": part_id},
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
                        "delete from audit_log "
                        "where entity_type = 'part' "
                        "and entity_id = :part_id"
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
        for method, path, payload in (
            ("get", "/api/reservations", None),
            ("get", "/api/reservations/999999999", None),
            (
                "post",
                "/api/reservations",
                {
                    "label": "Unauthenticated reservation",
                    "items": [{"part_id": 1, "quantity": 1}],
                },
            ),
        ):
            response = getattr(client, method)(
                path,
                **({"json": payload} if payload is not None else {}),
            )
            if response.status_code != 401:
                fail(
                    f"{method.upper()} {path} should require "
                    f"authentication, got {response.status_code}"
                )

        with db_session() as db:
            part_type_id = db.execute(
                text(
                    "select id from part_types "
                    "where is_active = 1 order by id limit 1"
                )
            ).scalar()
            if part_type_id is None:
                fail(
                    "Reservation API smoke requires an active part type"
                )

            user = create_user(
                db,
                username=username,
                display_name="Reservation API Smoke User",
                password=password,
                commit=True,
            )
            user_id = user.id
            session_token = create_session(
                db,
                user=user,
                commit=True,
            )
            part = Part(
                part_type_id=int(part_type_id),
                part_number=part_number,
                name="Reservation API smoke part",
                total_quantity=5,
                reserved_quantity=0,
                is_deleted=False,
                deleted_at=None,
            )
            db.add(part)
            db.commit()
            db.refresh(part)
            part_id = part.id

        headers = {
            "Authorization": f"Bearer {session_token.token}"
        }
        created_ids: list[int] = []
        for label, quantity in (
            ("First API reservation", 2),
            ("Second API reservation", 1),
        ):
            response = client.post(
                "/api/reservations",
                headers=headers,
                json={
                    "label": label,
                    "items": [
                        {
                            "part_id": part_id,
                            "quantity": quantity,
                        }
                    ],
                },
            )
            if response.status_code != 201:
                fail(
                    f"POST /api/reservations returned "
                    f"{response.status_code}: {response.text}"
                )
            payload = response.json()
            reservation_id = int(payload["id"])
            reservation_ids.append(reservation_id)
            created_ids.append(reservation_id)

        first_id, second_id = created_ids

        # PARTPILOT:RESERVATION_READ_CREATE_EXISTING_DATA_SAFE:V329
        with db_session() as db:
            existing_active_count = int(
                db.execute(
                    text(
                        "select count(*) from reservations "
                        "where status = 'active' "
                        "and id not in (:first_id, :second_id)"
                    ),
                    {
                        "first_id": first_id,
                        "second_id": second_id,
                    },
                ).scalar()
                or 0
            )
        expected_active_total = existing_active_count + 2

        first_page = client.get(
            "/api/reservations",
            headers=headers,
            params={"status": "active", "limit": 1, "offset": 0},
        )
        if first_page.status_code != 200:
            fail(
                "GET /api/reservations first page returned "
                f"{first_page.status_code}: {first_page.text}"
            )
        first_page_json = first_page.json()
        first_items = first_page_json.get("reservations", [])
        if (
            first_page_json.get("total") != expected_active_total
            or first_page_json.get("limit") != 1
            or len(first_items) != 1
            or int(first_items[0]["id"]) != second_id
        ):
            fail(
                "Reservation list ordering or first-page metadata is "
                f"incorrect: {first_page_json}"
            )

        second_page = client.get(
            "/api/reservations",
            headers=headers,
            params={"status": "active", "limit": 1, "offset": 1},
        )
        if second_page.status_code != 200:
            fail(
                "GET /api/reservations second page returned "
                f"{second_page.status_code}: {second_page.text}"
            )
        second_page_json = second_page.json()
        second_items = second_page_json.get("reservations", [])
        if (
            second_page_json.get("total") != expected_active_total
            or len(second_items) != 1
            or int(second_items[0]["id"]) != first_id
        ):
            fail(
                "Reservation list pagination is incorrect: "
                f"{second_page_json}"
            )

        detail_response = client.get(
            f"/api/reservations/{first_id}",
            headers=headers,
        )
        if detail_response.status_code != 200:
            fail(
                "GET /api/reservations/{id} returned "
                f"{detail_response.status_code}: "
                f"{detail_response.text}"
            )
        detail_json = detail_response.json()
        if (
            int(detail_json.get("id", 0)) != first_id
            or detail_json.get("label") != "First API reservation"
            or len(detail_json.get("items", [])) != 1
        ):
            fail(
                "Reservation detail response is incorrect: "
                f"{detail_json}"
            )

        missing_response = client.get(
            f"/api/reservations/{second_id + 999999}",
            headers=headers,
        )
        if missing_response.status_code != 404:
            fail(
                "Missing reservation detail should return 404, got "
                f"{missing_response.status_code}"
            )

        conflict_response = client.post(
            "/api/reservations",
            headers=headers,
            json={
                "label": "Insufficient API reservation",
                "items": [{"part_id": part_id, "quantity": 3}],
            },
        )
        if conflict_response.status_code != 409:
            fail(
                "Insufficient reservation should return 409, got "
                f"{conflict_response.status_code}: "
                f"{conflict_response.text}"
            )

        invalid_part_response = client.post(
            "/api/reservations",
            headers=headers,
            json={
                "label": "Missing part API reservation",
                "items": [
                    {
                        "part_id": part_id + 999999,
                        "quantity": 1,
                    }
                ],
            },
        )
        if invalid_part_response.status_code != 422:
            fail(
                "Missing reservation part should return 422, got "
                f"{invalid_part_response.status_code}: "
                f"{invalid_part_response.text}"
            )

        with db_session() as db:
            counts = {
                "reservations": db.execute(
                    text(
                        "select count(*) from reservations "
                        "where id in (:first_id, :second_id)"
                    ),
                    {
                        "first_id": first_id,
                        "second_id": second_id,
                    },
                ).scalar(),
                "items": db.execute(
                    text(
                        "select count(*) from reservation_items "
                        "where reservation_id in "
                        "(:first_id, :second_id)"
                    ),
                    {
                        "first_id": first_id,
                        "second_id": second_id,
                    },
                ).scalar(),
                "movements": db.execute(
                    text(
                        "select count(*) from stock_movements "
                        "where reservation_id in "
                        "(:first_id, :second_id)"
                    ),
                    {
                        "first_id": first_id,
                        "second_id": second_id,
                    },
                ).scalar(),
                "audits": db.execute(
                    text(
                        "select count(*) from audit_log "
                        "where event_type = 'reservation.created' "
                        "and entity_id in (:first_id, :second_id) "
                        "and actor_user_id = :user_id"
                    ),
                    {
                        "first_id": first_id,
                        "second_id": second_id,
                        "user_id": user_id,
                    },
                ).scalar(),
            }
            if counts != {
                "reservations": 2,
                "items": 2,
                "movements": 2,
                "audits": 2,
            }:
                fail(
                    "Reservation API persistence counts are incorrect: "
                    f"{counts}"
                )

            reserved_quantity = db.execute(
                text(
                    "select reserved_quantity from parts "
                    "where id = :part_id"
                ),
                {"part_id": part_id},
            ).scalar()
            if reserved_quantity != 3:
                fail(
                    "Failed reservation API requests changed stock: "
                    f"{reserved_quantity}"
                )

    finally:
        cleanup()

    ok(
        "Protected reservation list, detail, and creation APIs "
        "enforce authentication, ordering, pagination, validation, "
        "conflicts, persistence, and cleanup"
    )




# PARTPILOT:RESERVATION_EDIT_API_SMOKE:V346
def check_reservation_edit_api() -> None:
    import json
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app
    from app.models import Part
    from app.services.auth import create_session, create_user

    suffix = uuid4().hex[:12]
    username = f"smoke_reservation_edit_{suffix}"
    password = "reservation-edit-smoke-password"
    part_ids: list[int] = []
    reservation_id: int | None = None
    user_id: int | None = None

    def cleanup() -> None:
        with db_session() as db:
            if reservation_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'reservation' "
                        "and entity_id = :reservation_id"
                    ),
                    {"reservation_id": reservation_id},
                )
                db.execute(
                    text(
                        "delete from stock_movements "
                        "where reservation_id = :reservation_id"
                    ),
                    {"reservation_id": reservation_id},
                )
                db.execute(
                    text(
                        "delete from reservation_items "
                        "where reservation_id = :reservation_id"
                    ),
                    {"reservation_id": reservation_id},
                )
                db.execute(
                    text(
                        "delete from reservations "
                        "where id = :reservation_id"
                    ),
                    {"reservation_id": reservation_id},
                )

            if part_ids:
                placeholders = ", ".join(
                    f":part_id_{index}"
                    for index, _value in enumerate(part_ids)
                )
                params = {
                    f"part_id_{index}": value
                    for index, value in enumerate(part_ids)
                }
                db.execute(
                    text(
                        "update parts set reserved_quantity = 0 "
                        f"where id in ({placeholders})"
                    ),
                    params,
                )
                db.execute(
                    text(
                        "delete from stock_movements "
                        f"where part_id in ({placeholders})"
                    ),
                    params,
                )
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'part' "
                        f"and entity_id in ({placeholders})"
                    ),
                    params,
                )
                db.execute(
                    text(
                        "delete from parts "
                        f"where id in ({placeholders})"
                    ),
                    params,
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

    def fixture_state() -> dict[str, object]:
        if reservation_id is None:
            fail("Reservation edit fixture ID is unresolved")
        with db_session() as db:
            return {
                "reservation": [
                    dict(row)
                    for row in db.execute(
                        text(
                            "select * from reservations "
                            "where id = :reservation_id"
                        ),
                        {"reservation_id": reservation_id},
                    ).mappings()
                ],
                "items": [
                    dict(row)
                    for row in db.execute(
                        text(
                            "select * from reservation_items "
                            "where reservation_id = :reservation_id "
                            "order by id"
                        ),
                        {"reservation_id": reservation_id},
                    ).mappings()
                ],
                "movements": [
                    dict(row)
                    for row in db.execute(
                        text(
                            "select * from stock_movements "
                            "where reservation_id = :reservation_id "
                            "order by id"
                        ),
                        {"reservation_id": reservation_id},
                    ).mappings()
                ],
                "audits": [
                    dict(row)
                    for row in db.execute(
                        text(
                            "select * from audit_log "
                            "where entity_type = 'reservation' "
                            "and entity_id = :reservation_id "
                            "order by id"
                        ),
                        {"reservation_id": reservation_id},
                    ).mappings()
                ],
                "parts": [
                    dict(row)
                    for row in db.execute(
                        text(
                            "select id, total_quantity, reserved_quantity, "
                            "updated_at from parts "
                            "where id in (:first, :second, :third) "
                            "order by id"
                        ),
                        {
                            "first": part_ids[0],
                            "second": part_ids[1],
                            "third": part_ids[2],
                        },
                    ).mappings()
                ],
            }

    cleanup()
    client = TestClient(fastapi_app)

    try:
        unauthenticated = client.put(
            "/api/reservations/999999999",
            json={
                "label": "Unauthenticated edit",
                "items": [{"part_id": 1, "quantity": 1}],
            },
        )
        if unauthenticated.status_code != 401:
            fail(
                "Reservation editing should require authentication, got "
                f"{unauthenticated.status_code}"
            )

        with db_session() as db:
            part_type_id = db.execute(
                text(
                    "select id from part_types "
                    "where is_active = 1 order by id limit 1"
                )
            ).scalar()
            if part_type_id is None:
                fail("Reservation edit smoke requires an active part type")

            user = create_user(
                db,
                username=username,
                display_name="Reservation Edit Smoke User",
                password=password,
                commit=True,
            )
            user_id = user.id
            token = create_session(db, user=user, commit=True)

            fixtures = [
                Part(
                    part_type_id=int(part_type_id),
                    part_number=f"SMOKE-EDIT-A-{suffix}",
                    name="Reservation edit smoke part A",
                    total_quantity=10,
                    reserved_quantity=0,
                    unit_price=Decimal("2.50"),
                    is_deleted=False,
                    deleted_at=None,
                ),
                Part(
                    part_type_id=int(part_type_id),
                    part_number=f"SMOKE-EDIT-B-{suffix}",
                    name="Reservation edit smoke part B",
                    total_quantity=8,
                    reserved_quantity=0,
                    unit_price=Decimal("4.00"),
                    is_deleted=False,
                    deleted_at=None,
                ),
                Part(
                    part_type_id=int(part_type_id),
                    part_number=f"SMOKE-EDIT-C-{suffix}",
                    name="Reservation edit smoke part C",
                    total_quantity=1,
                    reserved_quantity=0,
                    unit_price=Decimal("6.00"),
                    is_deleted=False,
                    deleted_at=None,
                ),
            ]
            db.add_all(fixtures)
            db.commit()
            for fixture in fixtures:
                db.refresh(fixture)
                part_ids.append(fixture.id)

        headers = {"Authorization": f"Bearer {token.token}"}
        created = client.post(
            "/api/reservations",
            headers=headers,
            json={
                "label": "Reservation edit original",
                "notes": "Original reservation notes",
                "items": [
                    {
                        "part_id": part_ids[0],
                        "quantity": 2,
                        "note": "Original A note",
                    },
                    {
                        "part_id": part_ids[1],
                        "quantity": 2,
                        "note": "Original B note",
                    },
                ],
            },
        )
        if created.status_code != 201:
            fail(
                "Reservation edit fixture creation failed: "
                f"{created.status_code}: {created.text}"
            )
        reservation_id = int(created.json()["id"])

        expiry = datetime.now(timezone.utc) + timedelta(days=4)
        edit_payload = {
            "label": "Reservation edit updated",
            "notes": "Updated reservation notes",
            "expiry_at": expiry.isoformat(),
            "items": [
                {
                    "part_id": part_ids[0],
                    "quantity": 1,
                    "note": "Updated A note",
                },
                {
                    "part_id": part_ids[0],
                    "quantity": 3,
                    "note": "Updated A note",
                },
                {
                    "part_id": part_ids[2],
                    "quantity": 1,
                    "note": "New C note",
                },
            ],
        }
        updated = client.put(
            f"/api/reservations/{reservation_id}",
            headers=headers,
            json=edit_payload,
        )
        if updated.status_code != 200:
            fail(
                "Reservation edit returned "
                f"{updated.status_code}: {updated.text}"
            )
        payload = updated.json()
        items = payload.get("items", [])
        item_by_part = {
            int(item["part_id"]): item for item in items
        }
        if (
            payload.get("label") != "Reservation edit updated"
            or payload.get("notes") != "Updated reservation notes"
            or payload.get("status") != "active"
            or len(items) != 2
            or set(item_by_part) != {part_ids[0], part_ids[2]}
            or int(item_by_part[part_ids[0]]["quantity"]) != 4
            or item_by_part[part_ids[0]].get("note") != "Updated A note"
            or int(item_by_part[part_ids[2]]["quantity"]) != 1
            or item_by_part[part_ids[2]].get("note") != "New C note"
            or Decimal(str(payload.get("estimated_reserved_value")))
            != Decimal("16.0000")
        ):
            fail(f"Reservation edit response is incorrect: {payload}")

        with db_session() as db:
            stocks = {
                int(row["id"]): int(row["reserved_quantity"])
                for row in db.execute(
                    text(
                        "select id, reserved_quantity from parts "
                        "where id in (:first, :second, :third)"
                    ),
                    {
                        "first": part_ids[0],
                        "second": part_ids[1],
                        "third": part_ids[2],
                    },
                ).mappings()
            }
            if stocks != {
                part_ids[0]: 4,
                part_ids[1]: 0,
                part_ids[2]: 1,
            }:
                fail(f"Reservation edit stock reconciliation is wrong: {stocks}")

            edit_movements = [
                dict(row)
                for row in db.execute(
                    text(
                        "select * from stock_movements "
                        "where reservation_id = :reservation_id "
                        "order by id desc limit 3"
                    ),
                    {"reservation_id": reservation_id},
                ).mappings()
            ]
            expected_movement = {
                (part_ids[0], "reserve"): (2, 4, 8, 6),
                (part_ids[1], "release"): (2, 0, 6, 8),
                (part_ids[2], "reserve"): (0, 1, 1, 0),
            }
            actual_movement = {
                (int(row["part_id"]), str(row["movement_type"])): (
                    int(row["reserved_quantity_before"]),
                    int(row["reserved_quantity_after"]),
                    int(row["available_quantity_before"]),
                    int(row["available_quantity_after"]),
                )
                for row in edit_movements
            }
            if actual_movement != expected_movement:
                fail(
                    "Reservation edit movements are incorrect: "
                    f"{actual_movement}"
                )

            audits = [
                dict(row)
                for row in db.execute(
                    text(
                        "select * from audit_log "
                        "where entity_type = 'reservation' "
                        "and entity_id = :reservation_id "
                        "and event_type = 'reservation.updated'"
                    ),
                    {"reservation_id": reservation_id},
                ).mappings()
            ]
            if len(audits) != 1:
                fail(f"Reservation edit audit count is incorrect: {audits}")
            audit = audits[0]
            before_json = audit["before_json"]
            after_json = audit["after_json"]
            if isinstance(before_json, str):
                before_json = json.loads(before_json)
            if isinstance(after_json, str):
                after_json = json.loads(after_json)
            if (
                user_id is None
                or int(audit["actor_user_id"]) != int(user_id)
                or audit["actor_type"] != "user"
                or not str(audit["summary"]).startswith(
                    "Updated reservation Reservation edit updated"
                )
                or before_json.get("label")
                != "Reservation edit original"
                or after_json.get("label")
                != "Reservation edit updated"
            ):
                fail(f"Reservation edit audit is incorrect: {audit}")

        activity = client.get(
            f"/api/reservations/{reservation_id}/activity",
            headers=headers,
        )
        if activity.status_code != 200:
            fail(
                "Edited reservation activity returned "
                f"{activity.status_code}: {activity.text}"
            )
        activity_payload = activity.json()
        if activity_payload.get("total") != 7:
            fail(
                "Edited reservation activity count is incorrect: "
                f"{activity_payload}"
            )
        event_types = [
            entry.get("event_type")
            for entry in activity_payload.get("activities", [])
        ]
        if "reservation.updated" not in event_types:
            fail(
                "Edited reservation activity lacks reservation.updated: "
                f"{event_types}"
            )

        before_noop = fixture_state()
        noop = client.put(
            f"/api/reservations/{reservation_id}",
            headers=headers,
            json=edit_payload,
        )
        if noop.status_code != 200:
            fail(
                f"No-op reservation edit failed: {noop.status_code}: {noop.text}"
            )
        if fixture_state() != before_noop:
            fail("No-op reservation edit changed fixture data")

        invalid_requests = [
            (
                "insufficient stock",
                {
                    **edit_payload,
                    "items": [
                        {
                            "part_id": part_ids[0],
                            "quantity": 4,
                            "note": "Updated A note",
                        },
                        {
                            "part_id": part_ids[2],
                            "quantity": 2,
                            "note": "New C note",
                        },
                    ],
                },
                409,
            ),
            (
                "missing part",
                {
                    **edit_payload,
                    "items": [
                        {"part_id": part_ids[0], "quantity": 4},
                        {"part_id": part_ids[2] + 999999, "quantity": 1},
                    ],
                },
                422,
            ),
            (
                "conflicting duplicate notes",
                {
                    **edit_payload,
                    "items": [
                        {
                            "part_id": part_ids[0],
                            "quantity": 2,
                            "note": "First note",
                        },
                        {
                            "part_id": part_ids[0],
                            "quantity": 2,
                            "note": "Second note",
                        },
                    ],
                },
                422,
            ),
            (
                "past expiry",
                {
                    **edit_payload,
                    "expiry_at": (
                        datetime.now(timezone.utc) - timedelta(days=1)
                    ).isoformat(),
                },
                422,
            ),
        ]
        for name, request_payload, expected_status in invalid_requests:
            before_invalid = fixture_state()
            response = client.put(
                f"/api/reservations/{reservation_id}",
                headers=headers,
                json=request_payload,
            )
            if response.status_code != expected_status:
                fail(
                    f"Reservation edit {name} should return "
                    f"{expected_status}, got {response.status_code}: "
                    f"{response.text}"
                )
            if fixture_state() != before_invalid:
                fail(f"Reservation edit {name} changed fixture data")

        missing = client.put(
            f"/api/reservations/{reservation_id + 999999}",
            headers=headers,
            json=edit_payload,
        )
        if missing.status_code != 404:
            fail(
                "Missing reservation edit should return 404, got "
                f"{missing.status_code}: {missing.text}"
            )

        cancelled = client.post(
            f"/api/reservations/{reservation_id}/cancel",
            headers=headers,
        )
        if cancelled.status_code != 200:
            fail(
                "Reservation edit fixture cancellation failed: "
                f"{cancelled.status_code}: {cancelled.text}"
            )
        before_non_active = fixture_state()
        non_active = client.put(
            f"/api/reservations/{reservation_id}",
            headers=headers,
            json=edit_payload,
        )
        if non_active.status_code != 409:
            fail(
                "Non-active reservation edit should return 409, got "
                f"{non_active.status_code}: {non_active.text}"
            )
        if fixture_state() != before_non_active:
            fail("Rejected non-active reservation edit changed fixture data")

    finally:
        cleanup()

    ok(
        "Protected active reservation editing reconciles metadata, expiry, "
        "items, reserve/release movements, value snapshots, audit history, "
        "conflicts, authentication, no-op requests, and cleanup"
    )


# PARTPILOT:RESERVATION_DELETE_API_SMOKE:V351
def check_reservation_delete_api() -> None:
    import json

    from datetime import datetime, timedelta, timezone
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app
    from app.models import Part, Reservation
    from app.services.auth import create_session, create_user

    suffix = uuid4().hex[:12]
    username = f"smoke_reservation_delete_{suffix}"
    password = "reservation-delete-smoke-password"
    part_number = f"SMOKE-RESERVATION-DELETE-{suffix}"
    part_id: int | None = None
    reservation_ids: list[int] = []
    movement_ids: list[int] = []

    def cleanup() -> None:
        with db_session() as db:
            if reservation_ids:
                placeholders = ", ".join(
                    f":reservation_id_{index}"
                    for index, _value in enumerate(reservation_ids)
                )
                params = {
                    f"reservation_id_{index}": value
                    for index, value in enumerate(reservation_ids)
                }
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'reservation' "
                        f"and entity_id in ({placeholders})"
                    ),
                    params,
                )
                db.execute(
                    text(
                        "delete from reservation_items "
                        f"where reservation_id in ({placeholders})"
                    ),
                    params,
                )
                db.execute(
                    text(
                        "delete from reservations "
                        f"where id in ({placeholders})"
                    ),
                    params,
                )
            if movement_ids:
                placeholders = ", ".join(
                    f":movement_id_{index}"
                    for index, _value in enumerate(movement_ids)
                )
                params = {
                    f"movement_id_{index}": value
                    for index, value in enumerate(movement_ids)
                }
                db.execute(
                    text(
                        "delete from stock_movements "
                        f"where id in ({placeholders})"
                    ),
                    params,
                )
            if part_id is not None:
                db.execute(
                    text(
                        "update parts set reserved_quantity = 0 "
                        "where id = :part_id"
                    ),
                    {"part_id": part_id},
                )
                db.execute(
                    text("delete from stock_movements where part_id = :part_id"),
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

    def inventory_snapshot() -> dict[str, int]:
        with db_session() as db:
            row = db.execute(
                text(
                    "select count(*) active_parts, "
                    "coalesce(sum(total_quantity), 0) total_quantity, "
                    "coalesce(sum(reserved_quantity), 0) reserved_quantity, "
                    "coalesce(sum(total_quantity - reserved_quantity), 0) "
                    "available_quantity from parts where is_deleted = 0"
                )
            ).mappings().one()
            return {key: int(row[key]) for key in row.keys()}

    cleanup()
    client = TestClient(fastapi_app)

    try:
        unauthenticated = client.request(
            "DELETE",
            "/api/reservations/999999999",
            json={"confirmation_label": "Unauthenticated"},
        )
        if unauthenticated.status_code != 401:
            fail(
                "Reservation deletion should require authentication, got "
                f"{unauthenticated.status_code}"
            )

        with db_session() as db:
            part_type_id = db.execute(
                text(
                    "select id from part_types "
                    "where is_active = 1 order by id limit 1"
                )
            ).scalar()
            if part_type_id is None:
                fail("Reservation deletion smoke requires an active part type")
            user = create_user(
                db,
                username=username,
                display_name="Reservation Delete Smoke User",
                password=password,
                commit=True,
            )
            token = create_session(db, user=user, commit=True)
            fixture = Part(
                part_type_id=int(part_type_id),
                part_number=part_number,
                name="Reservation deletion smoke part",
                total_quantity=20,
                reserved_quantity=0,
                unit_price=Decimal("3.00"),
                is_deleted=False,
                deleted_at=None,
            )
            db.add(fixture)
            db.commit()
            db.refresh(fixture)
            part_id = fixture.id

        headers = {"Authorization": f"Bearer {token.token}"}
        fixtures: dict[str, dict[str, object]] = {}
        for status_name in ("active", "cancelled", "consumed", "expired"):
            label = f"Reservation delete {status_name} {suffix}"
            created = client.post(
                "/api/reservations",
                headers=headers,
                json={
                    "label": label,
                    "expiry_at": (
                        datetime.now(timezone.utc) + timedelta(days=2)
                    ).isoformat() if status_name == "expired" else None,
                    "items": [{"part_id": part_id, "quantity": 1}],
                },
            )
            if created.status_code != 201:
                fail(
                    f"Reservation deletion {status_name} fixture failed: "
                    f"{created.status_code}: {created.text}"
                )
            reservation_id = int(created.json()["id"])
            reservation_ids.append(reservation_id)
            fixtures[status_name] = {"id": reservation_id, "label": label}

        cancelled = client.post(
            f"/api/reservations/{fixtures['cancelled']['id']}/cancel",
            headers=headers,
        )
        if cancelled.status_code != 200:
            fail(f"Cancellation fixture failed: {cancelled.text}")
        consumed = client.post(
            f"/api/reservations/{fixtures['consumed']['id']}/consume",
            headers=headers,
        )
        if consumed.status_code != 200:
            fail(f"Consumption fixture failed: {consumed.text}")
        with db_session() as db:
            expiry_fixture = db.get(
                Reservation,
                int(fixtures["expired"]["id"]),
            )
            if expiry_fixture is None:
                fail("Expiry deletion fixture disappeared")
            expiry_fixture.expiry_at = (
                datetime.now(timezone.utc) - timedelta(minutes=5)
            )
            db.commit()
        expired = client.post(
            f"/api/reservations/{fixtures['expired']['id']}/expire",
            headers=headers,
        )
        if expired.status_code != 200:
            fail(f"Expiry fixture failed: {expired.status_code}: {expired.text}")

        missing = client.request(
            "DELETE",
            "/api/reservations/999999999",
            headers=headers,
            json={"confirmation_label": "Missing reservation"},
        )
        if missing.status_code != 404:
            fail(
                "Missing reservation deletion should return 404, got "
                f"{missing.status_code}: {missing.text}"
            )

        active_id = int(fixtures["active"]["id"])
        before_active = inventory_snapshot()
        active = client.request(
            "DELETE",
            f"/api/reservations/{active_id}",
            headers=headers,
            json={"confirmation_label": fixtures["active"]["label"]},
        )
        if active.status_code != 409:
            fail(
                "Active reservation deletion should return 409, got "
                f"{active.status_code}: {active.text}"
            )
        if inventory_snapshot() != before_active:
            fail("Rejected active reservation deletion changed inventory")

        cancelled_id = int(fixtures["cancelled"]["id"])
        before_wrong = inventory_snapshot()
        wrong = client.request(
            "DELETE",
            f"/api/reservations/{cancelled_id}",
            headers=headers,
            json={"confirmation_label": "Wrong confirmation label"},
        )
        if wrong.status_code != 422:
            fail(
                "Wrong reservation confirmation should return 422, got "
                f"{wrong.status_code}: {wrong.text}"
            )
        if inventory_snapshot() != before_wrong:
            fail("Rejected confirmation changed inventory")

        for status_name in ("cancelled", "consumed", "expired"):
            reservation_id = int(fixtures[status_name]["id"])
            label = str(fixtures[status_name]["label"])
            with db_session() as db:
                before_movements = [
                    int(value)
                    for value in db.execute(
                        text(
                            "select id from stock_movements "
                            "where reservation_id = :reservation_id order by id"
                        ),
                        {"reservation_id": reservation_id},
                    ).scalars()
                ]
                movement_ids.extend(before_movements)
                before_audits = int(
                    db.execute(
                        text(
                            "select count(*) from audit_log "
                            "where entity_type = 'reservation' "
                            "and entity_id = :reservation_id"
                        ),
                        {"reservation_id": reservation_id},
                    ).scalar_one()
                )
                before_items = int(
                    db.execute(
                        text(
                            "select count(*) from reservation_items "
                            "where reservation_id = :reservation_id"
                        ),
                        {"reservation_id": reservation_id},
                    ).scalar_one()
                )
            before_inventory = inventory_snapshot()
            deleted = client.request(
                "DELETE",
                f"/api/reservations/{reservation_id}",
                headers=headers,
                json={"confirmation_label": label},
            )
            if deleted.status_code != 200:
                fail(
                    f"{status_name.title()} reservation deletion failed: "
                    f"{deleted.status_code}: {deleted.text}"
                )
            payload = deleted.json()
            if (
                int(payload.get("id", -1)) != reservation_id
                or payload.get("label") != label
                or payload.get("previous_status") != status_name
                or payload.get("deleted") is not True
                or int(payload.get("removed_item_count", -1)) != before_items
                or int(payload.get("detached_movement_count", -1))
                != len(before_movements)
                or not payload.get("deleted_at")
            ):
                fail(f"Reservation deletion response is wrong: {payload}")
            if inventory_snapshot() != before_inventory:
                fail(f"Deleting {status_name} reservation changed inventory")

            with db_session() as db:
                if db.execute(
                    text("select 1 from reservations where id = :id"),
                    {"id": reservation_id},
                ).scalar() is not None:
                    fail("Deleted reservation row remains")
                if int(db.execute(
                    text(
                        "select count(*) from reservation_items "
                        "where reservation_id = :id"
                    ),
                    {"id": reservation_id},
                ).scalar_one()) != 0:
                    fail("Deleted reservation items remain")
                detached = [
                    dict(row)
                    for row in db.execute(
                        text(
                            "select id, reservation_id from stock_movements "
                            "where id in ("
                            + ", ".join(
                                f":movement_{index}"
                                for index, _value in enumerate(before_movements)
                            )
                            + ") order by id"
                        ),
                        {
                            f"movement_{index}": value
                            for index, value in enumerate(before_movements)
                        },
                    ).mappings()
                ] if before_movements else []
                if (
                    [int(row["id"]) for row in detached] != before_movements
                    or any(row["reservation_id"] is not None for row in detached)
                ):
                    fail(f"Stock movements were not detached: {detached}")
                audits = [
                    dict(row)
                    for row in db.execute(
                        text(
                            "select * from audit_log "
                            "where entity_type = 'reservation' "
                            "and entity_id = :reservation_id order by id"
                        ),
                        {"reservation_id": reservation_id},
                    ).mappings()
                ]
                if len(audits) != before_audits + 1:
                    fail(f"Reservation audit history was not retained: {audits}")
                deletion_audits = [
                    row for row in audits
                    if row["event_type"] == "reservation.deleted"
                ]
                if len(deletion_audits) != 1:
                    fail(f"Deletion audit count is wrong: {audits}")
                audit = deletion_audits[0]
                before_json = audit["before_json"]
                after_json = audit["after_json"]
                metadata_json = audit["metadata_json"]
                if isinstance(before_json, str):
                    before_json = json.loads(before_json)
                if isinstance(after_json, str):
                    after_json = json.loads(after_json)
                if isinstance(metadata_json, str):
                    metadata_json = json.loads(metadata_json)
                if (
                    before_json.get("id") != reservation_id
                    or before_json.get("status") != status_name
                    or before_json.get("label") != label
                    or len(before_json.get("items", [])) != before_items
                    or before_json.get("movement_ids") != before_movements
                    or after_json.get("deleted") is not True
                    or metadata_json.get("retained_stock_movement_ids")
                    != before_movements
                    or metadata_json.get("inventory_unchanged") is not True
                ):
                    fail(f"Deletion audit is incomplete: {audit}")

            repeated = client.request(
                "DELETE",
                f"/api/reservations/{reservation_id}",
                headers=headers,
                json={"confirmation_label": label},
            )
            if repeated.status_code != 404:
                fail(
                    "Repeated reservation deletion should return 404, got "
                    f"{repeated.status_code}: {repeated.text}"
                )
            with db_session() as db:
                deletion_count = int(
                    db.execute(
                        text(
                            "select count(*) from audit_log "
                            "where entity_type = 'reservation' "
                            "and entity_id = :reservation_id "
                            "and event_type = 'reservation.deleted'"
                        ),
                        {"reservation_id": reservation_id},
                    ).scalar_one()
                )
                if deletion_count != 1:
                    fail("Repeated delete created duplicate deletion audit")

        active_cancel = client.post(
            f"/api/reservations/{active_id}/cancel",
            headers=headers,
        )
        if active_cancel.status_code != 200:
            fail(f"Active cleanup cancellation failed: {active_cancel.text}")

    finally:
        cleanup()

    ok(
        "Protected inactive reservation deletion requires exact confirmation, "
        "rejects active and missing records, removes items, detaches immutable "
        "movements, retains complete audit history, preserves inventory, "
        "supports cancelled/consumed/expired records, and cleans fixture IDs"
    )


# PARTPILOT:RESERVATION_CANCELLATION_API_SMOKE:V306
def check_reservation_cancellation_api() -> None:
    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app
    from app.models import Part, Reservation
    from app.services.auth import create_session, create_user

    suffix = uuid4().hex[:12]
    username = f"smoke_reservation_cancel_{suffix}"
    password = "reservation-cancel-smoke-password"
    part_number = f"SMOKE-RESERVATION-CANCEL-{suffix}"
    part_id: int | None = None
    user_id: int | None = None
    reservation_ids: list[int] = []

    def cleanup() -> None:
        with db_session() as db:
            if reservation_ids:
                placeholders = ", ".join(
                    f":reservation_id_{index}"
                    for index, _value in enumerate(reservation_ids)
                )
                parameters = {
                    f"reservation_id_{index}": value
                    for index, value in enumerate(reservation_ids)
                }
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'reservation' "
                        f"and entity_id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(
                        "delete from stock_movements "
                        f"where reservation_id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(
                        "delete from reservation_items "
                        f"where reservation_id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(
                        "delete from reservations "
                        f"where id in ({placeholders})"
                    ),
                    parameters,
                )

            if part_id is not None:
                db.execute(
                    text(
                        "update parts set reserved_quantity = 0 "
                        "where id = :part_id"
                    ),
                    {"part_id": part_id},
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
                        "delete from audit_log "
                        "where entity_type = 'part' "
                        "and entity_id = :part_id"
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
        unauthenticated = client.post(
            "/api/reservations/999999999/cancel"
        )
        if unauthenticated.status_code != 401:
            fail(
                "Reservation cancellation should require authentication, "
                f"got {unauthenticated.status_code}"
            )

        with db_session() as db:
            part_type_id = db.execute(
                text(
                    "select id from part_types "
                    "where is_active = 1 order by id limit 1"
                )
            ).scalar()
            if part_type_id is None:
                fail(
                    "Reservation cancellation smoke requires an active "
                    "part type"
                )

            user = create_user(
                db,
                username=username,
                display_name="Reservation Cancellation Smoke User",
                password=password,
                commit=True,
            )
            user_id = user.id
            session_token = create_session(
                db,
                user=user,
                commit=True,
            )
            part = Part(
                part_type_id=int(part_type_id),
                part_number=part_number,
                name="Reservation cancellation smoke part",
                total_quantity=8,
                reserved_quantity=0,
                is_deleted=False,
                deleted_at=None,
            )
            db.add(part)
            db.commit()
            db.refresh(part)
            part_id = part.id

        headers = {
            "Authorization": f"Bearer {session_token.token}"
        }
        create_response = client.post(
            "/api/reservations",
            headers=headers,
            json={
                "label": "Cancellation smoke reservation",
                "items": [{"part_id": part_id, "quantity": 3}],
            },
        )
        if create_response.status_code != 201:
            fail(
                "Reservation creation before cancellation returned "
                f"{create_response.status_code}: {create_response.text}"
            )
        reservation_id = int(create_response.json()["id"])
        reservation_ids.append(reservation_id)

        cancel_response = client.post(
            f"/api/reservations/{reservation_id}/cancel",
            headers=headers,
        )
        if cancel_response.status_code != 200:
            fail(
                "Reservation cancellation returned "
                f"{cancel_response.status_code}: {cancel_response.text}"
            )
        cancel_json = cancel_response.json()
        cancel_items = cancel_json.get("items", [])
        if (
            cancel_json.get("status") != "cancelled"
            or len(cancel_items) != 1
            or int(cancel_items[0]["total_quantity"]) != 8
            or int(cancel_items[0]["reserved_quantity"]) != 0
            or int(cancel_items[0]["available_quantity"]) != 8
        ):
            fail(
                "Reservation cancellation response is incorrect: "
                f"{cancel_json}"
            )

        second_cancel = client.post(
            f"/api/reservations/{reservation_id}/cancel",
            headers=headers,
        )
        if second_cancel.status_code != 409:
            fail(
                "Cancelling an already cancelled reservation should "
                f"return 409, got {second_cancel.status_code}"
            )

        missing_cancel = client.post(
            f"/api/reservations/{reservation_id + 999999}/cancel",
            headers=headers,
        )
        if missing_cancel.status_code != 404:
            fail(
                "Cancelling a missing reservation should return 404, got "
                f"{missing_cancel.status_code}"
            )

        with db_session() as db:
            for status_name in ("consumed", "expired"):
                row = Reservation(
                    project_id=None,
                    label=f"{status_name.title()} cancellation smoke",
                    status=status_name,
                    notes=None,
                    created_by="manual",
                    expiry_at=None,
                    estimated_reserved_value=None,
                    currency_snapshot=None,
                )
                db.add(row)
                db.flush()
                reservation_ids.append(row.id)
            db.commit()
            consumed_id, expired_id = reservation_ids[-2:]

        for state_name, state_id in (
            ("consumed", consumed_id),
            ("expired", expired_id),
        ):
            response = client.post(
                f"/api/reservations/{state_id}/cancel",
                headers=headers,
            )
            if response.status_code != 409:
                fail(
                    f"Cancelling a {state_name} reservation should "
                    f"return 409, got {response.status_code}"
                )

        inconsistent_create = client.post(
            "/api/reservations",
            headers=headers,
            json={
                "label": "Inconsistent cancellation smoke",
                "items": [{"part_id": part_id, "quantity": 2}],
            },
        )
        if inconsistent_create.status_code != 201:
            fail(
                "Inconsistent cancellation fixture creation returned "
                f"{inconsistent_create.status_code}: "
                f"{inconsistent_create.text}"
            )
        inconsistent_id = int(inconsistent_create.json()["id"])
        reservation_ids.append(inconsistent_id)

        with db_session() as db:
            db.execute(
                text(
                    "update parts set reserved_quantity = 1 "
                    "where id = :part_id"
                ),
                {"part_id": part_id},
            )
            db.commit()

        inconsistent_cancel = client.post(
            f"/api/reservations/{inconsistent_id}/cancel",
            headers=headers,
        )
        if inconsistent_cancel.status_code != 409:
            fail(
                "Cancellation with inconsistent reserved stock should "
                f"return 409, got {inconsistent_cancel.status_code}: "
                f"{inconsistent_cancel.text}"
            )

        with db_session() as db:
            stored = db.execute(
                text(
                    "select status from reservations where id = :id"
                ),
                {"id": inconsistent_id},
            ).scalar()
            reserved = db.execute(
                text(
                    "select reserved_quantity from parts where id = :id"
                ),
                {"id": part_id},
            ).scalar()
            release_count = db.execute(
                text(
                    "select count(*) from stock_movements "
                    "where reservation_id = :id "
                    "and movement_type = 'release'"
                ),
                {"id": inconsistent_id},
            ).scalar()
            cancel_audit_count = db.execute(
                text(
                    "select count(*) from audit_log "
                    "where entity_type = 'reservation' "
                    "and entity_id = :id "
                    "and event_type = 'reservation.cancelled'"
                ),
                {"id": inconsistent_id},
            ).scalar()
            if (
                stored != "active"
                or reserved != 1
                or release_count != 0
                or cancel_audit_count != 0
            ):
                fail(
                    "Failed cancellation did not roll back cleanly: "
                    f"status={stored}, reserved={reserved}, "
                    f"release_count={release_count}, "
                    f"cancel_audit_count={cancel_audit_count}"
                )

            successful_status = db.execute(
                text(
                    "select status from reservations where id = :id"
                ),
                {"id": reservation_id},
            ).scalar()
            physical = db.execute(
                text(
                    "select total_quantity, reserved_quantity "
                    "from parts where id = :id"
                ),
                {"id": part_id},
            ).mappings().one()
            release = db.execute(
                text(
                    "select movement_type, quantity_delta, "
                    "quantity_before, quantity_after, "
                    "reserved_quantity_before, reserved_quantity_after, "
                    "available_quantity_before, available_quantity_after, "
                    "actor_user_id "
                    "from stock_movements "
                    "where reservation_id = :id "
                    "and movement_type = 'release'"
                ),
                {"id": reservation_id},
            ).mappings().one()
            audit_count = db.execute(
                text(
                    "select count(*) from audit_log "
                    "where entity_type = 'reservation' "
                    "and entity_id = :id "
                    "and event_type = 'reservation.cancelled' "
                    "and actor_user_id = :user_id"
                ),
                {"id": reservation_id, "user_id": user_id},
            ).scalar()

            if successful_status != "cancelled":
                fail(
                    "Successful cancellation status was not persisted: "
                    f"{successful_status}"
                )
            if int(physical["total_quantity"]) != 8:
                fail("Cancellation changed physical total quantity")
            if (
                release["movement_type"] != "release"
                or int(release["quantity_delta"]) != 0
                or int(release["quantity_before"]) != 8
                or int(release["quantity_after"]) != 8
                or int(release["reserved_quantity_before"]) != 3
                or int(release["reserved_quantity_after"]) != 0
                or int(release["available_quantity_before"]) != 5
                or int(release["available_quantity_after"]) != 8
                or int(release["actor_user_id"]) != int(user_id)
            ):
                fail(
                    "Cancellation release movement snapshots are "
                    f"incorrect: {dict(release)}"
                )
            if audit_count != 1:
                fail(
                    "Cancellation audit attribution is incorrect: "
                    f"{audit_count}"
                )

    finally:
        cleanup()

    ok(
        "Reservation cancellation is authenticated, state-guarded, "
        "atomic, inventory-safe, movement-backed, and audited"
    )


# PARTPILOT:RESERVATION_CONSUMPTION_API_SMOKE:V315
def check_reservation_consumption_api() -> None:
    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app
    from app.models import Part, Reservation
    from app.services.auth import create_session, create_user

    suffix = uuid4().hex[:12]
    username = f"smoke_reservation_consume_{suffix}"
    password = "reservation-consume-smoke-password"
    part_numbers = [
        f"SMOKE-RESERVATION-CONSUME-A-{suffix}",
        f"SMOKE-RESERVATION-CONSUME-B-{suffix}",
    ]
    part_ids: list[int] = []
    user_id: int | None = None
    reservation_ids: list[int] = []

    def cleanup() -> None:
        with db_session() as db:
            if reservation_ids:
                placeholders = ", ".join(
                    f":reservation_id_{index}"
                    for index, _value in enumerate(reservation_ids)
                )
                parameters = {
                    f"reservation_id_{index}": value
                    for index, value in enumerate(reservation_ids)
                }
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'reservation' "
                        f"and entity_id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(
                        "delete from stock_movements "
                        f"where reservation_id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(
                        "delete from reservation_items "
                        f"where reservation_id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(
                        "delete from reservations "
                        f"where id in ({placeholders})"
                    ),
                    parameters,
                )

            if part_ids:
                placeholders = ", ".join(
                    f":part_id_{index}"
                    for index, _value in enumerate(part_ids)
                )
                parameters = {
                    f"part_id_{index}": value
                    for index, value in enumerate(part_ids)
                }
                db.execute(
                    text(
                        "update parts set reserved_quantity = 0 "
                        f"where id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(
                        "delete from stock_movements "
                        f"where part_id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'part' "
                        f"and entity_id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(
                        "delete from parts "
                        f"where id in ({placeholders})"
                    ),
                    parameters,
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
        unauthenticated = client.post(
            "/api/reservations/999999999/consume"
        )
        if unauthenticated.status_code != 401:
            fail(
                "Reservation consumption should require authentication, "
                f"got {unauthenticated.status_code}"
            )

        with db_session() as db:
            part_type_id = db.execute(
                text(
                    "select id from part_types "
                    "where is_active = 1 order by id limit 1"
                )
            ).scalar()
            if part_type_id is None:
                fail(
                    "Reservation consumption smoke requires an active "
                    "part type"
                )

            user = create_user(
                db,
                username=username,
                display_name="Reservation Consumption Smoke User",
                password=password,
                commit=True,
            )
            user_id = user.id
            session_token = create_session(
                db,
                user=user,
                commit=True,
            )
            for index, (part_number, total_quantity) in enumerate(
                zip(part_numbers, (8, 5), strict=True)
            ):
                part = Part(
                    part_type_id=int(part_type_id),
                    part_number=part_number,
                    name=(
                        "Reservation consumption smoke part "
                        f"{index + 1}"
                    ),
                    total_quantity=total_quantity,
                    reserved_quantity=0,
                    is_deleted=False,
                    deleted_at=None,
                )
                db.add(part)
                db.flush()
                part_ids.append(part.id)
            db.commit()

        headers = {
            "Authorization": f"Bearer {session_token.token}"
        }
        create_response = client.post(
            "/api/reservations",
            headers=headers,
            json={
                "label": "Consumption smoke reservation",
                "items": [
                    {"part_id": part_ids[0], "quantity": 3},
                    {"part_id": part_ids[1], "quantity": 2},
                ],
            },
        )
        if create_response.status_code != 201:
            fail(
                "Reservation creation before consumption returned "
                f"{create_response.status_code}: "
                f"{create_response.text}"
            )
        reservation_id = int(create_response.json()["id"])
        reservation_ids.append(reservation_id)

        consume_response = client.post(
            f"/api/reservations/{reservation_id}/consume",
            headers=headers,
        )
        if consume_response.status_code != 200:
            fail(
                "Reservation consumption returned "
                f"{consume_response.status_code}: "
                f"{consume_response.text}"
            )
        consume_json = consume_response.json()
        expected_response = {
            part_ids[0]: (5, 0, 5),
            part_ids[1]: (3, 0, 3),
        }
        if (
            consume_json.get("status") != "consumed"
            or len(consume_json.get("items", [])) != 2
        ):
            fail(
                "Reservation consumption response has incorrect "
                f"status/items: {consume_json}"
            )
        for item in consume_json["items"]:
            part_id = int(item["part_id"])
            actual = (
                int(item["total_quantity"]),
                int(item["reserved_quantity"]),
                int(item["available_quantity"]),
            )
            if expected_response.get(part_id) != actual:
                fail(
                    "Reservation consumption response item is "
                    f"incorrect: {item}"
                )

        second_consume = client.post(
            f"/api/reservations/{reservation_id}/consume",
            headers=headers,
        )
        if second_consume.status_code != 409:
            fail(
                "Consuming an already consumed reservation should "
                f"return 409, got {second_consume.status_code}"
            )

        missing_consume = client.post(
            f"/api/reservations/{reservation_id + 999999}/consume",
            headers=headers,
        )
        if missing_consume.status_code != 404:
            fail(
                "Consuming a missing reservation should return 404, "
                f"got {missing_consume.status_code}"
            )

        with db_session() as db:
            for status_name in ("cancelled", "expired"):
                row = Reservation(
                    project_id=None,
                    label=f"{status_name.title()} consumption smoke",
                    status=status_name,
                    notes=None,
                    created_by="manual",
                    expiry_at=None,
                    estimated_reserved_value=None,
                    currency_snapshot=None,
                )
                db.add(row)
                db.flush()
                reservation_ids.append(row.id)
            db.commit()
            cancelled_id, expired_id = reservation_ids[-2:]

        for state_name, state_id in (
            ("cancelled", cancelled_id),
            ("expired", expired_id),
        ):
            response = client.post(
                f"/api/reservations/{state_id}/consume",
                headers=headers,
            )
            if response.status_code != 409:
                fail(
                    f"Consuming a {state_name} reservation should "
                    f"return 409, got {response.status_code}"
                )

        inconsistent_create = client.post(
            "/api/reservations",
            headers=headers,
            json={
                "label": "Inconsistent consumption smoke",
                "items": [
                    {"part_id": part_ids[0], "quantity": 1},
                    {"part_id": part_ids[1], "quantity": 1},
                ],
            },
        )
        if inconsistent_create.status_code != 201:
            fail(
                "Inconsistent consumption fixture creation returned "
                f"{inconsistent_create.status_code}: "
                f"{inconsistent_create.text}"
            )
        inconsistent_id = int(inconsistent_create.json()["id"])
        reservation_ids.append(inconsistent_id)

        with db_session() as db:
            db.execute(
                text(
                    "update parts set reserved_quantity = 0 "
                    "where id = :part_id"
                ),
                {"part_id": part_ids[1]},
            )
            db.commit()

        inconsistent_consume = client.post(
            f"/api/reservations/{inconsistent_id}/consume",
            headers=headers,
        )
        if inconsistent_consume.status_code != 409:
            fail(
                "Consumption with inconsistent reserved stock should "
                f"return 409, got {inconsistent_consume.status_code}: "
                f"{inconsistent_consume.text}"
            )

        with db_session() as db:
            inconsistent_status = db.execute(
                text(
                    "select status from reservations where id = :id"
                ),
                {"id": inconsistent_id},
            ).scalar()
            current_parts = {
                int(row["id"]): (
                    int(row["total_quantity"]),
                    int(row["reserved_quantity"]),
                )
                for row in db.execute(
                    text(
                        "select id, total_quantity, reserved_quantity "
                        "from parts where id in (:first_id, :second_id)"
                    ),
                    {
                        "first_id": part_ids[0],
                        "second_id": part_ids[1],
                    },
                ).mappings()
            }
            inconsistent_movements = db.execute(
                text(
                    "select count(*) from stock_movements "
                    "where reservation_id = :id "
                    "and movement_type = 'consume'"
                ),
                {"id": inconsistent_id},
            ).scalar()
            inconsistent_audits = db.execute(
                text(
                    "select count(*) from audit_log "
                    "where entity_type = 'reservation' "
                    "and entity_id = :id "
                    "and event_type = 'reservation.consumed'"
                ),
                {"id": inconsistent_id},
            ).scalar()
            expected_parts = {
                part_ids[0]: (5, 1),
                part_ids[1]: (3, 0),
            }
            if (
                inconsistent_status != "active"
                or current_parts != expected_parts
                or inconsistent_movements != 0
                or inconsistent_audits != 0
            ):
                fail(
                    "Failed consumption did not roll back atomically: "
                    f"status={inconsistent_status}, "
                    f"parts={current_parts}, "
                    f"movements={inconsistent_movements}, "
                    f"audits={inconsistent_audits}"
                )

            movements = list(
                db.execute(
                    text(
                        "select part_id, movement_type, quantity_delta, "
                        "quantity_before, quantity_after, "
                        "reserved_quantity_before, "
                        "reserved_quantity_after, "
                        "available_quantity_before, "
                        "available_quantity_after, actor_user_id "
                        "from stock_movements "
                        "where reservation_id = :id "
                        "and movement_type = 'consume' "
                        "order by part_id"
                    ),
                    {"id": reservation_id},
                ).mappings()
            )
            expected_movements = {
                part_ids[0]: (-3, 8, 5, 3, 0, 5, 5),
                part_ids[1]: (-2, 5, 3, 2, 0, 3, 3),
            }
            if len(movements) != 2:
                fail(
                    "Successful consumption movement count is "
                    f"incorrect: {movements}"
                )
            for movement in movements:
                part_id = int(movement["part_id"])
                actual = (
                    int(movement["quantity_delta"]),
                    int(movement["quantity_before"]),
                    int(movement["quantity_after"]),
                    int(movement["reserved_quantity_before"]),
                    int(movement["reserved_quantity_after"]),
                    int(movement["available_quantity_before"]),
                    int(movement["available_quantity_after"]),
                )
                if (
                    movement["movement_type"] != "consume"
                    or int(movement["actor_user_id"]) != int(user_id)
                    or expected_movements.get(part_id) != actual
                ):
                    fail(
                        "Consumption movement snapshot is incorrect: "
                        f"{dict(movement)}"
                    )

            audit_count = db.execute(
                text(
                    "select count(*) from audit_log "
                    "where entity_type = 'reservation' "
                    "and entity_id = :id "
                    "and event_type = 'reservation.consumed' "
                    "and actor_user_id = :user_id"
                ),
                {"id": reservation_id, "user_id": user_id},
            ).scalar()
            if audit_count != 1:
                fail(
                    "Consumption audit attribution is incorrect: "
                    f"{audit_count}"
                )

    finally:
        cleanup()

    ok(
        "Reservation consumption is authenticated, state-guarded, atomic, "
        "availability-preserving, movement-backed, and audited"
    )


# PARTPILOT:RESERVATION_EXPIRY_API_SMOKE:V320
def check_reservation_expiry_api() -> None:
    from datetime import datetime, timedelta, timezone

    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app
    from app.models import Part, Reservation
    from app.services.auth import create_session, create_user

    suffix = uuid4().hex[:12]
    username = f"smoke_reservation_expiry_{suffix}"
    password = "reservation-expiry-smoke-password"
    part_ids: list[int] = []
    reservation_ids: list[int] = []
    user_id: int | None = None

    def cleanup() -> None:
        with db_session() as db:
            if reservation_ids:
                placeholders = ", ".join(
                    f":reservation_id_{index}"
                    for index, _value in enumerate(reservation_ids)
                )
                params = {
                    f"reservation_id_{index}": value
                    for index, value in enumerate(reservation_ids)
                }
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'reservation' "
                        f"and entity_id in ({placeholders})"
                    ),
                    params,
                )
                db.execute(
                    text(
                        "delete from stock_movements "
                        f"where reservation_id in ({placeholders})"
                    ),
                    params,
                )
                db.execute(
                    text(
                        "delete from reservation_items "
                        f"where reservation_id in ({placeholders})"
                    ),
                    params,
                )
                db.execute(
                    text(
                        "delete from reservations "
                        f"where id in ({placeholders})"
                    ),
                    params,
                )
            if part_ids:
                placeholders = ", ".join(
                    f":part_id_{index}"
                    for index, _value in enumerate(part_ids)
                )
                params = {
                    f"part_id_{index}": value
                    for index, value in enumerate(part_ids)
                }
                db.execute(
                    text(
                        "update parts set reserved_quantity = 0 "
                        f"where id in ({placeholders})"
                    ),
                    params,
                )
                db.execute(
                    text(
                        "delete from stock_movements "
                        f"where part_id in ({placeholders})"
                    ),
                    params,
                )
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'part' "
                        f"and entity_id in ({placeholders})"
                    ),
                    params,
                )
                db.execute(
                    text(
                        "delete from parts "
                        f"where id in ({placeholders})"
                    ),
                    params,
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
        unauthenticated = client.post(
            "/api/reservations/999999999/expire"
        )
        if unauthenticated.status_code != 401:
            fail(
                "Reservation expiry should require authentication, "
                f"got {unauthenticated.status_code}"
            )

        with db_session() as db:
            part_type_id = db.execute(
                text(
                    "select id from part_types "
                    "where is_active = 1 order by id limit 1"
                )
            ).scalar()
            if part_type_id is None:
                fail("Expiry smoke requires an active part type")
            user = create_user(
                db,
                username=username,
                display_name="Reservation Expiry Smoke User",
                password=password,
                commit=True,
            )
            user_id = user.id
            token = create_session(db, user=user, commit=True)
            for index, total in enumerate((8, 5, 6)):
                part = Part(
                    part_type_id=int(part_type_id),
                    part_number=(
                        f"SMOKE-RESERVATION-EXPIRY-{index}-{suffix}"
                    ),
                    name=f"Reservation expiry smoke part {index + 1}",
                    total_quantity=total,
                    reserved_quantity=0,
                    is_deleted=False,
                    deleted_at=None,
                )
                db.add(part)
                db.flush()
                part_ids.append(part.id)
            db.commit()

        headers = {"Authorization": f"Bearer {token.token}"}
        future = (
            datetime.now(timezone.utc) + timedelta(hours=1)
        ).isoformat()
        created = client.post(
            "/api/reservations",
            headers=headers,
            json={
                "label": "Expiry smoke reservation",
                "expiry_at": future,
                "items": [
                    {"part_id": part_ids[0], "quantity": 3},
                    {"part_id": part_ids[1], "quantity": 2},
                ],
            },
        )
        if created.status_code != 201:
            fail(
                "Expiry fixture creation failed: "
                f"{created.status_code}: {created.text}"
            )
        reservation_id = int(created.json()["id"])
        reservation_ids.append(reservation_id)
        with db_session() as db:
            row = db.get(Reservation, reservation_id)
            if row is None:
                fail("Expiry fixture disappeared")
            row.expiry_at = (
                datetime.now(timezone.utc) - timedelta(minutes=5)
            )
            db.commit()

        expired = client.post(
            f"/api/reservations/{reservation_id}/expire",
            headers=headers,
        )
        if expired.status_code != 200:
            fail(
                "Reservation expiry failed: "
                f"{expired.status_code}: {expired.text}"
            )
        payload = expired.json()
        expected = {
            part_ids[0]: (8, 0, 8),
            part_ids[1]: (5, 0, 5),
        }
        if payload.get("status") != "expired":
            fail(f"Expiry status is incorrect: {payload}")
        for item in payload.get("items", []):
            actual = (
                int(item["total_quantity"]),
                int(item["reserved_quantity"]),
                int(item["available_quantity"]),
            )
            if expected.get(int(item["part_id"])) != actual:
                fail(f"Expiry response item is incorrect: {item}")

        if client.post(
            f"/api/reservations/{reservation_id}/expire",
            headers=headers,
        ).status_code != 409:
            fail("Second expiry should return 409")
        if client.post(
            f"/api/reservations/{reservation_id + 999999}/expire",
            headers=headers,
        ).status_code != 404:
            fail("Missing expiry should return 404")

        no_expiry = client.post(
            "/api/reservations",
            headers=headers,
            json={
                "label": "No-expiry smoke",
                "items": [{"part_id": part_ids[2], "quantity": 1}],
            },
        )
        if no_expiry.status_code != 201:
            fail("No-expiry fixture creation failed")
        no_expiry_id = int(no_expiry.json()["id"])
        reservation_ids.append(no_expiry_id)
        if client.post(
            f"/api/reservations/{no_expiry_id}/expire",
            headers=headers,
        ).status_code != 409:
            fail("Reservation without expiry should return 409")

        future_row = client.post(
            "/api/reservations",
            headers=headers,
            json={
                "label": "Future-expiry smoke",
                "expiry_at": (
                    datetime.now(timezone.utc) + timedelta(hours=2)
                ).isoformat(),
                "items": [{"part_id": part_ids[2], "quantity": 1}],
            },
        )
        if future_row.status_code != 201:
            fail("Future-expiry fixture creation failed")
        future_id = int(future_row.json()["id"])
        reservation_ids.append(future_id)
        if client.post(
            f"/api/reservations/{future_id}/expire",
            headers=headers,
        ).status_code != 409:
            fail("Future expiry should return 409")

        with db_session() as db:
            for state in ("cancelled", "consumed", "expired"):
                row = Reservation(
                    project_id=None,
                    label=f"{state.title()} expiry smoke",
                    status=state,
                    notes=None,
                    created_by="manual",
                    expiry_at=(
                        datetime.now(timezone.utc)
                        - timedelta(minutes=10)
                    ),
                    estimated_reserved_value=None,
                    currency_snapshot=None,
                )
                db.add(row)
                db.flush()
                reservation_ids.append(row.id)
            db.commit()
            terminal_ids = reservation_ids[-3:]
        for state, row_id in zip(
            ("cancelled", "consumed", "expired"),
            terminal_ids,
            strict=True,
        ):
            if client.post(
                f"/api/reservations/{row_id}/expire",
                headers=headers,
            ).status_code != 409:
                fail(f"{state} expiry should return 409")

        inconsistent = client.post(
            "/api/reservations",
            headers=headers,
            json={
                "label": "Inconsistent expiry smoke",
                "expiry_at": future,
                "items": [
                    {"part_id": part_ids[0], "quantity": 1},
                    {"part_id": part_ids[1], "quantity": 1},
                ],
            },
        )
        if inconsistent.status_code != 201:
            fail("Inconsistent expiry fixture creation failed")
        inconsistent_id = int(inconsistent.json()["id"])
        reservation_ids.append(inconsistent_id)
        with db_session() as db:
            row = db.get(Reservation, inconsistent_id)
            if row is None:
                fail("Inconsistent expiry fixture disappeared")
            row.expiry_at = (
                datetime.now(timezone.utc) - timedelta(minutes=5)
            )
            db.execute(
                text(
                    "update parts set reserved_quantity = 0 "
                    "where id = :part_id"
                ),
                {"part_id": part_ids[1]},
            )
            db.commit()

        failed = client.post(
            f"/api/reservations/{inconsistent_id}/expire",
            headers=headers,
        )
        if failed.status_code != 409:
            fail(
                "Inconsistent expiry should return 409, got "
                f"{failed.status_code}: {failed.text}"
            )

        with db_session() as db:
            status_name = db.execute(
                text(
                    "select status from reservations where id = :id"
                ),
                {"id": inconsistent_id},
            ).scalar()
            part_state = {
                int(row["id"]): (
                    int(row["total_quantity"]),
                    int(row["reserved_quantity"]),
                )
                for row in db.execute(
                    text(
                        "select id, total_quantity, reserved_quantity "
                        "from parts where id in (:a, :b)"
                    ),
                    {"a": part_ids[0], "b": part_ids[1]},
                ).mappings()
            }
            failed_movements = db.execute(
                text(
                    "select count(*) from stock_movements "
                    "where reservation_id = :id "
                    "and movement_type = 'release'"
                ),
                {"id": inconsistent_id},
            ).scalar()
            failed_audits = db.execute(
                text(
                    "select count(*) from audit_log "
                    "where entity_type = 'reservation' "
                    "and entity_id = :id "
                    "and event_type = 'reservation.expired'"
                ),
                {"id": inconsistent_id},
            ).scalar()
            if (
                status_name != "active"
                or part_state != {
                    part_ids[0]: (8, 1),
                    part_ids[1]: (5, 0),
                }
                or failed_movements != 0
                or failed_audits != 0
            ):
                fail(
                    "Failed expiry did not roll back atomically: "
                    f"status={status_name}, parts={part_state}, "
                    f"movements={failed_movements}, "
                    f"audits={failed_audits}"
                )

            movements = list(
                db.execute(
                    text(
                        "select part_id, quantity_delta, "
                        "quantity_before, quantity_after, "
                        "reserved_quantity_before, "
                        "reserved_quantity_after, "
                        "available_quantity_before, "
                        "available_quantity_after, source, actor_user_id "
                        "from stock_movements "
                        "where reservation_id = :id "
                        "and movement_type = 'release' "
                        "order by part_id"
                    ),
                    {"id": reservation_id},
                ).mappings()
            )
            expected_movements = {
                part_ids[0]: (0, 8, 8, 3, 0, 5, 8),
                part_ids[1]: (0, 5, 5, 2, 0, 3, 5),
            }
            if len(movements) != 2:
                fail(f"Expiry movement count is incorrect: {movements}")
            for movement in movements:
                actual = (
                    int(movement["quantity_delta"]),
                    int(movement["quantity_before"]),
                    int(movement["quantity_after"]),
                    int(movement["reserved_quantity_before"]),
                    int(movement["reserved_quantity_after"]),
                    int(movement["available_quantity_before"]),
                    int(movement["available_quantity_after"]),
                )
                if (
                    expected_movements.get(
                        int(movement["part_id"])
                    ) != actual
                    or movement["source"] != "system"
                    or int(movement["actor_user_id"]) != int(user_id)
                ):
                    fail(
                        "Expiry movement snapshot is incorrect: "
                        f"{dict(movement)}"
                    )
            audit_count = db.execute(
                text(
                    "select count(*) from audit_log "
                    "where entity_type = 'reservation' "
                    "and entity_id = :id "
                    "and event_type = 'reservation.expired' "
                    "and actor_user_id = :user_id"
                ),
                {"id": reservation_id, "user_id": user_id},
            ).scalar()
            if audit_count != 1:
                fail(
                    "Expiry audit attribution is incorrect: "
                    f"{audit_count}"
                )
    finally:
        cleanup()

    ok(
        "Reservation expiry is authenticated, due-time-guarded, atomic, "
        "release-backed, inventory-safe, and audited"
    )



# PARTPILOT:RESERVATION_ACTIVITY_API_SMOKE:V338
def check_reservation_activity_api() -> None:
    from datetime import datetime

    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app
    from app.models import Part
    from app.services.auth import create_session, create_user

    suffix = uuid4().hex[:12]
    username = f"smoke_reservation_activity_{suffix}"
    password = "reservation-activity-smoke-password"
    part_ids: list[int] = []
    reservation_id: int | None = None

    def cleanup() -> None:
        with db_session() as db:
            if reservation_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'reservation' "
                        "and entity_id = :reservation_id"
                    ),
                    {"reservation_id": reservation_id},
                )
                db.execute(
                    text(
                        "delete from stock_movements "
                        "where reservation_id = :reservation_id"
                    ),
                    {"reservation_id": reservation_id},
                )
                db.execute(
                    text(
                        "delete from reservation_items "
                        "where reservation_id = :reservation_id"
                    ),
                    {"reservation_id": reservation_id},
                )
                db.execute(
                    text(
                        "delete from reservations "
                        "where id = :reservation_id"
                    ),
                    {"reservation_id": reservation_id},
                )

            if part_ids:
                placeholders = ", ".join(
                    f":part_id_{index}"
                    for index, _value in enumerate(part_ids)
                )
                params = {
                    f"part_id_{index}": value
                    for index, value in enumerate(part_ids)
                }
                db.execute(
                    text(
                        "delete from stock_movements "
                        f"where part_id in ({placeholders})"
                    ),
                    params,
                )
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'part' "
                        f"and entity_id in ({placeholders})"
                    ),
                    params,
                )
                db.execute(
                    text(
                        "delete from parts "
                        f"where id in ({placeholders})"
                    ),
                    params,
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

    def reservation_rows() -> dict[str, list[dict]]:
        if reservation_id is None:
            fail("Reservation activity fixture ID is unresolved")
        with db_session() as db:
            return {
                "reservation": [
                    dict(row)
                    for row in db.execute(
                        text(
                            "select * from reservations "
                            "where id = :reservation_id"
                        ),
                        {"reservation_id": reservation_id},
                    ).mappings()
                ],
                "items": [
                    dict(row)
                    for row in db.execute(
                        text(
                            "select * from reservation_items "
                            "where reservation_id = :reservation_id "
                            "order by id"
                        ),
                        {"reservation_id": reservation_id},
                    ).mappings()
                ],
                "movements": [
                    dict(row)
                    for row in db.execute(
                        text(
                            "select * from stock_movements "
                            "where reservation_id = :reservation_id "
                            "order by id"
                        ),
                        {"reservation_id": reservation_id},
                    ).mappings()
                ],
                "audits": [
                    dict(row)
                    for row in db.execute(
                        text(
                            "select * from audit_log "
                            "where entity_type = 'reservation' "
                            "and entity_id = :reservation_id "
                            "order by id"
                        ),
                        {"reservation_id": reservation_id},
                    ).mappings()
                ],
                "parts": [
                    dict(row)
                    for row in db.execute(
                        text(
                            "select id, total_quantity, "
                            "reserved_quantity, updated_at "
                            "from parts where id in (:first, :second) "
                            "order by id"
                        ),
                        {
                            "first": part_ids[0],
                            "second": part_ids[1],
                        },
                    ).mappings()
                ],
            }

    cleanup()
    client = TestClient(fastapi_app)

    try:
        unauthenticated = client.get(
            "/api/reservations/999999999/activity"
        )
        if unauthenticated.status_code != 401:
            fail(
                "Reservation activity should require authentication, "
                f"got {unauthenticated.status_code}"
            )

        with db_session() as db:
            part_type_id = db.execute(
                text(
                    "select id from part_types "
                    "where is_active = 1 order by id limit 1"
                )
            ).scalar()
            if part_type_id is None:
                fail(
                    "Reservation activity smoke requires an active "
                    "part type"
                )

            user = create_user(
                db,
                username=username,
                display_name="Reservation Activity Smoke User",
                password=password,
                commit=True,
            )
            token = create_session(db, user=user, commit=True)

            first = Part(
                part_type_id=int(part_type_id),
                part_number=f"SMOKE-ACTIVITY-A-{suffix}",
                name="Reservation activity smoke part A",
                total_quantity=9,
                reserved_quantity=0,
                is_deleted=False,
                deleted_at=None,
            )
            second = Part(
                part_type_id=int(part_type_id),
                part_number=f"SMOKE-ACTIVITY-B-{suffix}",
                name="Reservation activity smoke part B",
                total_quantity=6,
                reserved_quantity=0,
                is_deleted=False,
                deleted_at=None,
            )
            db.add(first)
            db.add(second)
            db.commit()
            db.refresh(first)
            db.refresh(second)
            part_ids.extend([first.id, second.id])

        headers = {
            "Authorization": f"Bearer {token.token}"
        }
        created = client.post(
            "/api/reservations",
            headers=headers,
            json={
                "label": "Reservation activity smoke",
                "notes": "Read-only activity contract",
                "items": [
                    {
                        "part_id": part_ids[0],
                        "quantity": 2,
                        "note": "Primary activity fixture",
                    },
                    {
                        "part_id": part_ids[1],
                        "quantity": 1,
                    },
                ],
            },
        )
        if created.status_code != 201:
            fail(
                "Reservation activity fixture creation failed: "
                f"{created.status_code}: {created.text}"
            )
        reservation_id = int(created.json()["id"])
        before = reservation_rows()

        response = client.get(
            f"/api/reservations/{reservation_id}/activity",
            headers=headers,
        )
        if response.status_code != 200:
            fail(
                "Reservation activity returned "
                f"{response.status_code}: {response.text}"
            )
        payload = response.json()
        activities = payload.get("activities", [])
        if (
            int(payload.get("reservation_id", 0)) != reservation_id
            or int(payload.get("total", -1)) != 3
            or int(payload.get("limit", -1)) != 100
            or int(payload.get("offset", -1)) != 0
            or len(activities) != 3
        ):
            fail(
                "Reservation activity collection is incorrect: "
                f"{payload}"
            )

        keys = [str(item.get("key")) for item in activities]
        if len(keys) != len(set(keys)):
            fail(
                "Reservation activity keys are not unique: "
                f"{keys}"
            )

        audit_entries = [
            item for item in activities
            if item.get("kind") == "audit"
        ]
        movement_entries = [
            item for item in activities
            if item.get("kind") == "stock_movement"
        ]
        if (
            len(audit_entries) != 1
            or len(movement_entries) != 2
        ):
            fail(
                "Reservation activity source counts are incorrect: "
                f"{activities}"
            )

        audit = audit_entries[0]
        if (
            audit.get("event_type") != "reservation.created"
            or audit.get("actor_type") != "user"
            or audit.get("actor_display_name")
            != "Reservation Activity Smoke User"
            or not str(audit.get("summary", "")).startswith(
                "Created reservation Reservation activity smoke"
            )
        ):
            fail(
                "Reservation activity audit entry is incorrect: "
                f"{audit}"
            )

        expected_movements = {
            part_ids[0]: {
                "part_number": f"SMOKE-ACTIVITY-A-{suffix}",
                "quantity": 2,
                "quantity_before": 9,
                "quantity_after": 9,
                "reserved_quantity_before": 0,
                "reserved_quantity_after": 2,
                "available_quantity_before": 9,
                "available_quantity_after": 7,
                "note": "Primary activity fixture",
            },
            part_ids[1]: {
                "part_number": f"SMOKE-ACTIVITY-B-{suffix}",
                "quantity": 1,
                "quantity_before": 6,
                "quantity_after": 6,
                "reserved_quantity_before": 0,
                "reserved_quantity_after": 1,
                "available_quantity_before": 6,
                "available_quantity_after": 5,
                "note": None,
            },
        }
        for movement in movement_entries:
            part_id = int(movement.get("part_id", 0))
            expected = expected_movements.get(part_id)
            actual = {
                key: movement.get(key)
                for key in expected
            } if expected is not None else None
            if (
                expected is None
                or movement.get("event_type") != "stock.reserve"
                or movement.get("movement_type") != "reserve"
                or movement.get("quantity_delta") != 0
                or movement.get("source") != "manual"
                or movement.get("actor_type") != "user"
                or movement.get("actor_display_name")
                != "Reservation Activity Smoke User"
                or actual != expected
            ):
                fail(
                    "Reservation activity movement entry is incorrect: "
                    f"{movement}"
                )

        timestamps = [
            datetime.fromisoformat(
                str(item["occurred_at"]).replace("Z", "+00:00")
            )
            for item in activities
        ]
        if timestamps != sorted(timestamps, reverse=True):
            fail(
                "Reservation activity is not newest-first: "
                f"{timestamps}"
            )

        paged = client.get(
            f"/api/reservations/{reservation_id}/activity",
            headers=headers,
            params={"limit": 2, "offset": 1},
        )
        if paged.status_code != 200:
            fail(
                "Reservation activity pagination returned "
                f"{paged.status_code}: {paged.text}"
            )
        paged_payload = paged.json()
        if (
            paged_payload.get("total") != 3
            or paged_payload.get("limit") != 2
            or paged_payload.get("offset") != 1
            or paged_payload.get("activities")
            != activities[1:3]
        ):
            fail(
                "Reservation activity pagination is incorrect: "
                f"{paged_payload}"
            )

        missing = client.get(
            f"/api/reservations/{reservation_id + 999999}/activity",
            headers=headers,
        )
        if missing.status_code != 404:
            fail(
                "Missing reservation activity should return 404, got "
                f"{missing.status_code}: {missing.text}"
            )

        invalid = client.get(
            f"/api/reservations/{reservation_id}/activity",
            headers=headers,
            params={"limit": 0},
        )
        if invalid.status_code != 422:
            fail(
                "Invalid reservation activity limit should return 422, "
                f"got {invalid.status_code}: {invalid.text}"
            )

        after = reservation_rows()
        if after != before:
            fail(
                "Reservation activity reads changed fixture data"
            )
    finally:
        cleanup()

    ok(
        "Protected reservation activity is read-only, newest-first, "
        "paginated, actor-attributed, part-aware, and existing-data-safe"
    )


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


# PATCH 213: protected universal part search smoke test
def check_universal_part_search_api() -> None:
    from datetime import datetime, timezone
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app
    from app.models import (
        Location,
        Manufacturer,
        PartAlias,
        PartFieldValue,
        PartTag,
        PartType,
        PartTypeField,
        Tag,
    )

    suffix = uuid4().hex[:10]
    username = f"smoke_search_{suffix}"
    password = "universal-search-smoke-password"

    type_name = f"Search Fixture {suffix}"
    type_slug = f"search-fixture-{suffix}"
    manufacturer_name = f"Search Manufacturer {suffix}"
    location_name = f"Search Drawer {suffix}"
    tag_name = f"Search Tag {suffix}"

    shared_token = f"shared{suffix}"
    duplicate_token = f"duplicate{suffix}"
    alias_token = f"alias{suffix}"
    tag_token = f"tag{suffix}"
    text_token = f"textvalue{suffix}"
    description_token = f"nebula{suffix}"
    package_token = f"package{suffix}"
    notes_token = f"quasar{suffix}"
    wildcard_token = f"%_literal{suffix}"
    # PATCH 215: stable numeric universal-search smoke fixture
    # -7319.25 is small, unique inside the temporary part type, and exactly
    # representable when SQLite casts the numeric value back to text.
    numeric_token = "-7319.25"

    part_ids: list[int] = []
    field_ids: list[int] = []
    type_id: int | None = None
    manufacturer_id: int | None = None
    location_id: int | None = None
    tag_id: int | None = None
    user_id: int | None = None

    def cleanup() -> None:
        with db_session() as db:
            for part_id in part_ids:
                db.execute(
                    text("delete from part_tags where part_id = :part_id"),
                    {"part_id": part_id},
                )
                db.execute(
                    text("delete from aliases where part_id = :part_id"),
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
                    text(
                        "delete from stock_movements "
                        "where part_id = :part_id"
                    ),
                    {"part_id": part_id},
                )
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'part' "
                        "and entity_id = :part_id"
                    ),
                    {"part_id": part_id},
                )
                db.execute(
                    text("delete from parts where id = :part_id"),
                    {"part_id": part_id},
                )

            if tag_id is not None:
                db.execute(
                    text("delete from tags where id = :tag_id"),
                    {"tag_id": tag_id},
                )
            if manufacturer_id is not None:
                db.execute(
                    text(
                        "delete from manufacturers "
                        "where id = :manufacturer_id"
                    ),
                    {"manufacturer_id": manufacturer_id},
                )
            if location_id is not None:
                db.execute(
                    text(
                        "delete from locations "
                        "where id = :location_id"
                    ),
                    {"location_id": location_id},
                )
            if type_id is not None:
                db.execute(
                    text(
                        "delete from part_type_fields "
                        "where part_type_id = :part_type_id"
                    ),
                    {"part_type_id": type_id},
                )
                db.execute(
                    text(
                        "delete from part_types "
                        "where id = :part_type_id"
                    ),
                    {"part_type_id": type_id},
                )

            if user_id is not None:
                db.execute(
                    text(
                        "delete from sessions where user_id = :user_id"
                    ),
                    {"user_id": user_id},
                )
                db.execute(
                    text("delete from users where id = :user_id"),
                    {"user_id": user_id},
                )
            else:
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
                display_name="Universal Search Smoke User",
                password=password,
                commit=True,
            )
            user_id = user.id
            session_token = create_session(
                db,
                user=user,
                commit=True,
            )

            part_type = PartType(
                name=type_name,
                slug=type_slug,
                description=f"Unique component subtype {suffix}",
                is_builtin=False,
                is_active=True,
                template_version=1,
            )
            manufacturer = Manufacturer(
                name=manufacturer_name,
                normalized_name=manufacturer_name.casefold(),
                is_builtin=False,
                is_active=True,
            )
            location = Location(
                name=location_name,
                normalized_name=normalize_location_name(location_name),
                note="Universal search smoke location",
            )
            tag = Tag(
                name=tag_name,
                normalized_name=tag_token,
            )
            db.add_all([part_type, manufacturer, location, tag])
            db.flush()

            type_id = part_type.id
            manufacturer_id = manufacturer.id
            location_id = location.id
            tag_id = tag.id

            text_field = PartTypeField(
                part_type_id=part_type.id,
                field_key=f"text_key_{suffix}",
                label=f"Search text field {suffix}",
                field_type="text",
                is_required=False,
                sort_order=0,
            )
            number_field = PartTypeField(
                part_type_id=part_type.id,
                field_key=f"number_key_{suffix}",
                label=f"Search numeric field {suffix}",
                field_type="number",
                is_required=False,
                sort_order=1,
            )
            bool_field = PartTypeField(
                part_type_id=part_type.id,
                field_key=f"bool_key_{suffix}",
                label=f"Search boolean field {suffix}",
                field_type="boolean",
                is_required=False,
                sort_order=2,
            )
            db.add_all([text_field, number_field, bool_field])
            db.flush()
            field_ids.extend(
                [text_field.id, number_field.id, bool_field.id]
            )

            core = Part(
                part_type_id=part_type.id,
                manufacturer_id=manufacturer.id,
                location_id=location.id,
                part_number=f"PP213-{suffix}-IRFZ44N",
                name=f"Avalanche MOSFET {suffix}",
                description=f"Description {description_token}",
                package=package_token,
                notes=f"Gate note {notes_token} {wildcard_token}",
                total_quantity=9,
                reserved_quantity=2,
                is_deleted=False,
            )
            shared_available = Part(
                part_type_id=part_type.id,
                location_id=location.id,
                part_number=f"PP213-{suffix}-AVAILABLE",
                name=f"Available {shared_token}",
                total_quantity=5,
                reserved_quantity=0,
                low_stock_enabled=True,
                low_stock_threshold=5,
                is_deleted=False,
            )
            shared_available_unassigned = Part(
                part_type_id=part_type.id,
                location_id=None,
                part_number=f"PP213-{suffix}-UNASSIGNED",
                name=f"Unassigned {shared_token}",
                total_quantity=3,
                reserved_quantity=1,
                is_deleted=False,
            )
            shared_out = Part(
                part_type_id=part_type.id,
                location_id=location.id,
                part_number=f"PP213-{suffix}-OUT",
                name=f"Out {shared_token}",
                total_quantity=0,
                reserved_quantity=0,
                is_deleted=False,
            )
            deleted = Part(
                part_type_id=part_type.id,
                location_id=location.id,
                part_number=f"PP213-{suffix}-DELETED",
                name=f"Deleted {shared_token}",
                total_quantity=4,
                reserved_quantity=0,
                is_deleted=True,
                deleted_at=datetime.now(timezone.utc),
            )
            alias_part = Part(
                part_type_id=part_type.id,
                part_number=f"PP213-{suffix}-ALIAS",
                name=f"Alias fixture {suffix}",
                total_quantity=2,
                reserved_quantity=0,
                is_deleted=False,
            )
            tag_part = Part(
                part_type_id=part_type.id,
                part_number=f"PP213-{suffix}-TAG",
                name=f"Tag fixture {suffix}",
                total_quantity=2,
                reserved_quantity=0,
                is_deleted=False,
            )
            text_part = Part(
                part_type_id=part_type.id,
                part_number=f"PP213-{suffix}-TEXT",
                name=f"Text fixture {suffix}",
                total_quantity=2,
                reserved_quantity=0,
                is_deleted=False,
            )
            number_part = Part(
                part_type_id=part_type.id,
                part_number=f"PP213-{suffix}-NUMBER",
                name=f"Number fixture {suffix}",
                total_quantity=2,
                reserved_quantity=0,
                is_deleted=False,
            )
            bool_part = Part(
                part_type_id=part_type.id,
                part_number=f"PP213-{suffix}-BOOL",
                name=f"Boolean fixture {suffix}",
                total_quantity=2,
                reserved_quantity=0,
                is_deleted=False,
            )
            db.add_all(
                [
                    core,
                    shared_available,
                    shared_available_unassigned,
                    shared_out,
                    deleted,
                    alias_part,
                    tag_part,
                    text_part,
                    number_part,
                    bool_part,
                ]
            )
            db.flush()

            fixtures = [
                core,
                shared_available,
                shared_available_unassigned,
                shared_out,
                deleted,
                alias_part,
                tag_part,
                text_part,
                number_part,
                bool_part,
            ]
            part_ids.extend(part.id for part in fixtures)

            db.add_all(
                [
                    PartAlias(
                        part_id=alias_part.id,
                        alias=alias_token,
                    ),
                    PartAlias(
                        part_id=core.id,
                        alias=duplicate_token,
                    ),
                    PartTag(
                        part_id=tag_part.id,
                        tag_id=tag.id,
                    ),
                    PartTag(
                        part_id=core.id,
                        tag_id=tag.id,
                    ),
                    PartFieldValue(
                        part_id=text_part.id,
                        field_id=text_field.id,
                        value_text=text_token,
                    ),
                    PartFieldValue(
                        part_id=core.id,
                        field_id=text_field.id,
                        value_text=duplicate_token,
                    ),
                    PartFieldValue(
                        part_id=number_part.id,
                        field_id=number_field.id,
                        value_number=Decimal(numeric_token),
                    ),
                    PartFieldValue(
                        part_id=bool_part.id,
                        field_id=bool_field.id,
                        value_bool=True,
                    ),
                ]
            )
            db.commit()

            ids = {
                "core": core.id,
                "shared_available": shared_available.id,
                "shared_available_unassigned": (
                    shared_available_unassigned.id
                ),
                "shared_out": shared_out.id,
                "deleted": deleted.id,
                "alias": alias_part.id,
                "tag": tag_part.id,
                "text": text_part.id,
                "number": number_part.id,
                "bool": bool_part.id,
            }

        headers = {"Authorization": f"Bearer {session_token.token}"}

        unauthenticated = client.get(
            "/api/parts",
            params={"search": suffix},
        )
        if unauthenticated.status_code != 401:
            fail(
                "Universal search route should require authentication, got "
                f"{unauthenticated.status_code}: {unauthenticated.text}"
            )

        def response_for(
            search: str,
            *,
            limit: int = 100,
            offset: int = 0,
            selected_type_id: int | None = None,
            selected_location_id: int | None = None,
            stock_status: str = "all",
            sort_by: str = "default",
            sort_direction: str = "asc",
            available_sort_by: str | None = None,
            available_sort_direction: str | None = None,
            out_of_stock_sort_by: str | None = None,
            out_of_stock_sort_direction: str | None = None,
        ):
            params: dict[str, str | int] = {
                "search": search,
                "stock_status": stock_status,
                "sort_by": sort_by,
                "sort_direction": sort_direction,
                "limit": limit,
                "offset": offset,
            }
            if selected_type_id is not None:
                params["part_type_id"] = selected_type_id
            if selected_location_id is not None:
                params["location_id"] = selected_location_id
            if available_sort_by is not None:
                params["available_sort_by"] = available_sort_by
            if available_sort_direction is not None:
                params[
                    "available_sort_direction"
                ] = available_sort_direction
            if out_of_stock_sort_by is not None:
                params["out_of_stock_sort_by"] = out_of_stock_sort_by
            if out_of_stock_sort_direction is not None:
                params[
                    "out_of_stock_sort_direction"
                ] = out_of_stock_sort_direction
            response = client.get(
                "/api/parts",
                params=params,
                headers=headers,
            )
            if response.status_code != 200:
                fail(
                    f"Universal search failed for {search!r}: "
                    f"{response.status_code} {response.text}"
                )
            payload = response.json()
            returned_ids = [
                item.get("id")
                for item in payload.get("parts", [])
            ]
            if len(returned_ids) != len(set(returned_ids)):
                fail(
                    f"Universal search returned duplicate rows for "
                    f"{search!r}: {returned_ids}"
                )
            if payload.get("limit") != limit:
                fail(
                    f"Universal search returned the wrong limit for "
                    f"{search!r}: {payload}"
                )
            if payload.get("offset") != offset:
                fail(
                    f"Universal search returned the wrong offset for "
                    f"{search!r}: {payload}"
                )
            return payload, returned_ids

        exact_checks = (
            (f"{suffix}-irfz44n", ids["core"], "part number"),
            (f"avalanche mosfet {suffix}".upper(), ids["core"], "name"),
            (description_token.upper(), ids["core"], "description"),
            (package_token.upper(), ids["core"], "package"),
            (notes_token.upper(), ids["core"], "notes"),
            (manufacturer_name.upper(), ids["core"], "manufacturer"),
            (alias_token.upper(), ids["alias"], "alias"),
            (text_token.upper(), ids["text"], "custom text value"),
            (numeric_token, ids["number"], "custom numeric value"),
            (wildcard_token, ids["core"], "literal SQL wildcard text"),
        )
        for query, expected_id, label in exact_checks:
            payload, returned_ids = response_for(
                query,
                selected_type_id=type_id,
            )
            if payload.get("total") != 1 or returned_ids != [expected_id]:
                fail(
                    f"Universal search {label} coverage is incorrect for "
                    f"{query!r}: {payload}"
                )

        location_search_payload, location_search_ids = response_for(
            location_name.upper(),
            selected_type_id=type_id,
        )
        expected_location_search_ids = {
            ids["core"],
            ids["shared_available"],
            ids["shared_out"],
        }
        if (
            location_search_payload.get("total") != 3
            or set(location_search_ids) != expected_location_search_ids
            or location_search_ids[-1] != ids["shared_out"]
            or ids["shared_available_unassigned"] in location_search_ids
            or ids["deleted"] in location_search_ids
        ):
            fail(
                "Universal search shared-location coverage, exclusion, or "
                f"available-first ordering is incorrect: "
                f"{location_search_payload}"
            )

        type_payload, type_ids = response_for(
            type_name.upper(),
            selected_type_id=type_id,
        )
        expected_active_fixture_ids = {
            value
            for key, value in ids.items()
            if key != "deleted"
        }
        if (
            type_payload.get("total") != len(expected_active_fixture_ids)
            or set(type_ids) != expected_active_fixture_ids
        ):
            fail(
                "Universal search part-type coverage is incorrect: "
                f"{type_payload}"
            )

        tag_payload, tag_ids = response_for(
            tag_token.upper(),
            selected_type_id=type_id,
        )
        if (
            tag_payload.get("total") != 2
            or set(tag_ids) != {ids["core"], ids["tag"]}
        ):
            fail(
                "Universal search tag coverage is incorrect: "
                f"{tag_payload}"
            )

        duplicate_payload, duplicate_ids = response_for(
            duplicate_token,
            selected_type_id=type_id,
        )
        if (
            duplicate_payload.get("total") != 1
            or duplicate_ids != [ids["core"]]
        ):
            fail(
                "Universal search duplicate suppression is incorrect: "
                f"{duplicate_payload}"
            )

        bool_payload, bool_ids = response_for(
            "true",
            selected_type_id=type_id,
        )
        if (
            bool_payload.get("total") != 1
            or bool_ids != [ids["bool"]]
        ):
            fail(
                "Universal search boolean custom-value coverage is incorrect: "
                f"{bool_payload}"
            )

        bool_label_payload, bool_label_ids = response_for(
            f"Search boolean field {suffix}",
            selected_type_id=type_id,
        )
        if (
            bool_label_payload.get("total") != 1
            or bool_label_ids != [ids["bool"]]
        ):
            fail(
                "Universal search custom-field label coverage is incorrect: "
                f"{bool_label_payload}"
            )

        trimmed_payload, trimmed_ids = response_for(
            f"   avalanche   mosfet   {suffix}   ",
            selected_type_id=type_id,
        )
        if (
            trimmed_payload.get("total") != 1
            or trimmed_ids != [ids["core"]]
        ):
            fail(
                "Universal search whitespace normalization is incorrect: "
                f"{trimmed_payload}"
            )

        baseline = client.get(
            "/api/parts",
            params={"part_type_id": type_id},
            headers=headers,
        )
        whitespace = client.get(
            "/api/parts",
            params={
                "search": "      ",
                "part_type_id": type_id,
            },
            headers=headers,
        )
        if (
            baseline.status_code != 200
            or whitespace.status_code != 200
            or baseline.json().get("total")
            != whitespace.json().get("total")
        ):
            fail(
                "Whitespace-only universal search should preserve unfiltered "
                f"totals: baseline={baseline.text} whitespace={whitespace.text}"
            )

        shared_payload, shared_ids = response_for(
            shared_token,
            selected_type_id=type_id,
        )
        expected_shared_ids = {
            ids["shared_available"],
            ids["shared_available_unassigned"],
            ids["shared_out"],
        }
        if (
            shared_payload.get("total") != 3
            or set(shared_ids) != expected_shared_ids
            or shared_ids[-1] != ids["shared_out"]
            or ids["deleted"] in shared_ids
        ):
            fail(
                "Universal search available-first ordering or deleted "
                f"exclusion is incorrect: {shared_payload}"
            )

        first_page, first_page_ids = response_for(
            shared_token,
            limit=2,
            offset=0,
            selected_type_id=type_id,
        )
        second_page, second_page_ids = response_for(
            shared_token,
            limit=2,
            offset=2,
            selected_type_id=type_id,
        )
        if (
            first_page.get("total") != 3
            or second_page.get("total") != 3
            or len(first_page_ids) != 2
            or second_page_ids != [ids["shared_out"]]
            or ids["shared_out"] in first_page_ids
        ):
            fail(
                "Universal search pagination or available-first ordering is "
                f"incorrect: first={first_page} second={second_page}"
            )

        location_payload, location_ids = response_for(
            shared_token,
            selected_type_id=type_id,
            selected_location_id=location_id,
        )
        if (
            location_payload.get("total") != 2
            or set(location_ids)
            != {ids["shared_available"], ids["shared_out"]}
        ):
            fail(
                "Universal search location-filter composition is incorrect: "
                f"{location_payload}"
            )

        type_filter_payload, type_filter_ids = response_for(
            shared_token,
            selected_type_id=type_id,
        )
        if (
            type_filter_payload.get("total") != 3
            or set(type_filter_ids) != expected_shared_ids
        ):
            fail(
                "Universal search part-type filter composition is incorrect: "
                f"{type_filter_payload}"
            )

        # PATCH 229: PARTPILOT_STORED_PARTS_STOCK_FILTER_V229
        all_stock_response = client.get(
            "/api/parts",
            params={
                "part_type_id": type_id,
                "stock_status": "all",
                "limit": 100,
            },
            headers=headers,
        )
        all_stock_payload = all_stock_response.json()
        all_stock_ids = [
            item.get("id")
            for item in all_stock_payload.get("parts", [])
        ]
        if (
            all_stock_response.status_code != 200
            or all_stock_payload.get("total")
            != len(expected_active_fixture_ids)
            or set(all_stock_ids) != expected_active_fixture_ids
            or all_stock_ids[-1] != ids["shared_out"]
            or ids["deleted"] in all_stock_ids
        ):
            fail(
                "Unsearched stock_status=all totals, exclusion, or "
                "available-first ordering is incorrect: "
                f"{all_stock_payload}"
            )

        low_payload, low_ids = response_for(
            shared_token,
            selected_type_id=type_id,
            stock_status="low",
        )
        if (
            low_payload.get("total") != 1
            or low_ids != [ids["shared_available"]]
        ):
            fail(
                "Universal search positive low-stock filtering is "
                f"incorrect: {low_payload}"
            )

        in_payload, in_ids = response_for(
            shared_token,
            selected_type_id=type_id,
            stock_status="in",
        )
        if (
            in_payload.get("total") != 1
            or in_ids != [ids["shared_available_unassigned"]]
        ):
            fail(
                "Universal search in-stock filtering is incorrect: "
                f"{in_payload}"
            )

        out_payload, out_ids = response_for(
            shared_token,
            selected_type_id=type_id,
            stock_status="out",
        )
        if (
            out_payload.get("total") != 1
            or out_ids != [ids["shared_out"]]
        ):
            fail(
                "Universal search out-of-stock filtering is incorrect: "
                f"{out_payload}"
            )

        combined_payload, combined_ids = response_for(
            shared_token,
            selected_type_id=type_id,
            selected_location_id=location_id,
            stock_status="low",
        )
        if (
            combined_payload.get("total") != 1
            or combined_ids != [ids["shared_available"]]
        ):
            fail(
                "Universal search stock, type, and location "
                "composition is incorrect: "
                f"{combined_payload}"
            )

        # PATCH 267: PARTPILOT_STORED_PARTS_SORT_V267
        def sort_value(item: dict[str, object], sort_by: str):
            if sort_by == "part":
                return str(
                    item.get("name")
                    or item.get("part_number")
                    or ""
                ).casefold()
            if sort_by == "type":
                return str(item.get("part_type_name") or "").casefold()
            if sort_by == "manufacturer":
                raw = item.get("manufacturer_name")
                return None if raw is None else str(raw).casefold()
            if sort_by == "location":
                raw = item.get("location_name")
                return None if raw is None else str(raw).casefold()
            if sort_by == "available":
                return int(item.get("available_quantity") or 0)
            if sort_by == "total":
                return int(item.get("total_quantity") or 0)

            available = int(item.get("available_quantity") or 0)
            if available <= 0:
                return 2
            return 1 if item.get("is_low_stock") is True else 0

        def assert_group_sorted(
            items: list[dict[str, object]],
            sort_by: str,
            direction: str,
        ) -> None:
            reverse = direction == "desc"
            if sort_by in {"manufacturer", "location"}:
                present: list[object] = []
                missing_started = False
                for item in items:
                    value = sort_value(item, sort_by)
                    if value is None:
                        missing_started = True
                    else:
                        if missing_started:
                            fail(
                                f"Missing {sort_by} values were not placed "
                                f"last: {items}"
                            )
                        present.append(value)
                if present != sorted(present, reverse=reverse):
                    fail(
                        f"Incorrect {sort_by} {direction} ordering: "
                        f"{items}"
                    )
                return

            values = [sort_value(item, sort_by) for item in items]
            if values != sorted(values, reverse=reverse):
                fail(
                    f"Incorrect {sort_by} {direction} ordering: {items}"
                )

        def assert_sorted_payload(
            payload: dict[str, object],
            sort_by: str,
            direction: str,
        ) -> None:
            items = list(payload.get("parts", []))
            available_items = [
                item
                for item in items
                if int(item.get("available_quantity") or 0) > 0
            ]
            out_items = [
                item
                for item in items
                if int(item.get("available_quantity") or 0) <= 0
            ]
            if items != available_items + out_items:
                fail(
                    "Explicit sorting did not preserve Available-first "
                    f"grouping: {payload}"
                )
            assert_group_sorted(available_items, sort_by, direction)
            assert_group_sorted(out_items, sort_by, direction)

        for sort_by in (
            "part",
            "type",
            "manufacturer",
            "location",
            "available",
            "total",
            "status",
        ):
            for direction in ("asc", "desc"):
                sorted_payload, sorted_ids = response_for(
                    shared_token,
                    selected_type_id=type_id,
                    sort_by=sort_by,
                    sort_direction=direction,
                )
                assert_sorted_payload(
                    sorted_payload,
                    sort_by,
                    direction,
                )

                first_page, first_ids = response_for(
                    shared_token,
                    limit=2,
                    offset=0,
                    selected_type_id=type_id,
                    sort_by=sort_by,
                    sort_direction=direction,
                )
                remaining_page, remaining_ids = response_for(
                    shared_token,
                    limit=100,
                    offset=2,
                    selected_type_id=type_id,
                    sort_by=sort_by,
                    sort_direction=direction,
                )
                if (
                    first_page.get("total") != sorted_payload.get("total")
                    or remaining_page.get("total")
                    != sorted_payload.get("total")
                    or first_ids + remaining_ids != sorted_ids
                ):
                    fail(
                        f"Sorted pagination is inconsistent for "
                        f"{sort_by}/{direction}: "
                        f"full={sorted_ids}, first={first_ids}, "
                        f"remaining={remaining_ids}"
                    )

        # PATCH 271: PARTPILOT_INDEPENDENT_SECTION_SORT_V272
        independent_payload, _ = response_for(
            shared_token,
            selected_type_id=type_id,
            available_sort_by="part",
            available_sort_direction="asc",
            out_of_stock_sort_by="part",
            out_of_stock_sort_direction="desc",
        )
        independent_items = list(
            independent_payload.get("parts", [])
        )
        independent_available = [
            item
            for item in independent_items
            if int(item.get("available_quantity") or 0) > 0
        ]
        independent_out = [
            item
            for item in independent_items
            if int(item.get("available_quantity") or 0) <= 0
        ]
        if (
            independent_items
            != independent_available + independent_out
        ):
            fail(
                "Independent sorting did not preserve Available-first "
                f"grouping: {independent_payload}"
            )
        assert_group_sorted(
            independent_available,
            "part",
            "asc",
        )
        assert_group_sorted(
            independent_out,
            "part",
            "desc",
        )

        reversed_payload, _ = response_for(
            shared_token,
            selected_type_id=type_id,
            available_sort_by="part",
            available_sort_direction="desc",
            out_of_stock_sort_by="part",
            out_of_stock_sort_direction="asc",
        )
        reversed_items = list(reversed_payload.get("parts", []))
        reversed_available = [
            item
            for item in reversed_items
            if int(item.get("available_quantity") or 0) > 0
        ]
        reversed_out = [
            item
            for item in reversed_items
            if int(item.get("available_quantity") or 0) <= 0
        ]
        assert_group_sorted(
            reversed_available,
            "part",
            "desc",
        )
        assert_group_sorted(
            reversed_out,
            "part",
            "asc",
        )

        invalid_available_sort = client.get(
            "/api/parts",
            params={
                "part_type_id": type_id,
                "available_sort_by": "missing",
            },
            headers=headers,
        )
        if invalid_available_sort.status_code != 422:
            fail(
                "Invalid available_sort_by should return 422, got "
                f"{invalid_available_sort.status_code}: "
                f"{invalid_available_sort.text}"
            )

        invalid_out_direction = client.get(
            "/api/parts",
            params={
                "part_type_id": type_id,
                "out_of_stock_sort_direction": "sideways",
            },
            headers=headers,
        )
        if invalid_out_direction.status_code != 422:
            fail(
                "Invalid out_of_stock_sort_direction should return 422, "
                f"got {invalid_out_direction.status_code}: "
                f"{invalid_out_direction.text}"
            )

        ok(
            "Stored Parts independently sorts Available and Out of stock sections without changing the other section"
        )

        invalid_sort_by = client.get(
            "/api/parts",
            params={
                "part_type_id": type_id,
                "sort_by": "missing",
            },
            headers=headers,
        )
        if invalid_sort_by.status_code != 422:
            fail(
                "Invalid sort_by should return 422, got "
                f"{invalid_sort_by.status_code}: "
                f"{invalid_sort_by.text}"
            )

        invalid_sort_direction = client.get(
            "/api/parts",
            params={
                "part_type_id": type_id,
                "sort_direction": "sideways",
            },
            headers=headers,
        )
        if invalid_sort_direction.status_code != 422:
            fail(
                "Invalid sort_direction should return 422, got "
                f"{invalid_sort_direction.status_code}: "
                f"{invalid_sort_direction.text}"
            )

        ok(
            "Stored Parts server-backed sorting covers every supported column, both directions, pagination, and validation"
        )

        invalid_stock_status = client.get(
            "/api/parts",
            params={
                "part_type_id": type_id,
                "stock_status": "missing",
            },
            headers=headers,
        )
        if invalid_stock_status.status_code != 422:
            fail(
                "Invalid stock_status should return 422, got "
                f"{invalid_stock_status.status_code}: "
                f"{invalid_stock_status.text}"
            )

        empty_payload, empty_ids = response_for(
            f"no-match-{suffix}-absent",
            selected_type_id=type_id,
        )
        if empty_payload.get("total") != 0 or empty_ids != []:
            fail(
                "Universal search empty result is incorrect: "
                f"{empty_payload}"
            )

        invalid_length = client.get(
            "/api/parts",
            params={
                "search": "x" * 181,
                "part_type_id": type_id,
            },
            headers=headers,
        )
        if invalid_length.status_code != 422:
            fail(
                "Universal search terms longer than 180 characters should "
                f"return 422, got {invalid_length.status_code}: "
                f"{invalid_length.text}"
            )

    finally:
        cleanup()

    ok(
        "Protected universal part search covers metadata, type, manufacturer, "
        "location, aliases, tags, custom text/numeric/boolean values and "
        "field labels; preserves type, location, and stock-status filters, "
        "totals, pagination, literal wildcards, case-insensitive partial "
        "matching, duplicate suppression, deleted exclusion, and "
        "available-first deterministic ordering and server-backed "
        "sortable columns"
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
        check_reservation_contract_schema,
        check_reservation_creation_service,
        check_reservation_read_create_api,
        check_reservation_cancellation_api,
        check_reservation_consumption_api,
        check_reservation_expiry_api,
        check_reservation_activity_api,
        check_reservation_edit_api,
        check_reservation_delete_api,
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
        check_universal_part_search_api,
        check_stock_quantity_adjustment_api,
        check_part_metadata_update_api,
        check_part_soft_delete_restore_api,
    ]

    for check in checks:
        check()

    print("[PASS] Phase 4 part type management smoke test completed")


if __name__ == "__main__":
    main()
