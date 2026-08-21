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
EXPECTED_AUTH_SCHEMA_HEAD = "0010_mcp_trusted_networks"
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
    "mcp.tool_permissions",
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

    expected_project_statuses = {
        "draft",
        "reserved",
        "consumed",
        "cancelled",
    }
    expected_reservation_statuses = {
        "active",
        "consumed",
        "cancelled",
        "expired",
    }
    if PROJECT_STATUSES != expected_project_statuses:
        fail(
            "PROJECT_STATUSES does not match the canonical contract: "
            f"{sorted(PROJECT_STATUSES)}"
        )
    if RESERVATION_STATUSES != expected_reservation_statuses:
        fail(
            "RESERVATION_STATUSES does not match the canonical contract: "
            f"{sorted(RESERVATION_STATUSES)}"
        )

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
# PARTPILOT:PROJECTS_CONTRACT_SMOKE:V368
def check_projects_contract_schema() -> None:
    expected_statuses = {
        "draft",
        "reserved",
        "consumed",
        "cancelled",
    }
    if PROJECT_STATUSES != expected_statuses:
        fail(
            "PROJECT_STATUSES does not match the canonical contract: "
            f"{sorted(PROJECT_STATUSES)}"
        )

    with db_session() as db:
        project_sql = db.execute(
            text(
                "select sql from sqlite_master "
                "where type = 'table' and name = 'projects'"
            )
        ).scalar()
        item_sql = db.execute(
            text(
                "select sql from sqlite_master "
                "where type = 'table' and name = 'project_items'"
            )
        ).scalar()
        if not project_sql or not item_sql:
            fail("Projects contract tables are missing")
        for name in {
            "ck_projects_status",
            "ck_projects_created_by",
            "ck_projects_estimated_total_value_nonnegative",
        }:
            if name not in project_sql:
                fail(f"projects is missing constraint {name}")
        for name in {
            "ck_project_items_quantity_positive",
            "ck_project_items_unit_price_snapshot_nonnegative",
        }:
            if name not in item_sql:
                fail(f"project_items is missing constraint {name}")

        project_indexes = {
            row[1] for row in db.execute(text("PRAGMA index_list(projects)"))
        }
        expected_project_indexes = {"ix_projects_name", "ix_projects_status"}
        if not expected_project_indexes.issubset(project_indexes):
            fail(f"projects indexes are incomplete: {sorted(project_indexes)}")
        item_indexes = {
            row[1]
            for row in db.execute(text("PRAGMA index_list(project_items)"))
        }
        expected_item_indexes = {
            "ix_project_items_project_id",
            "ix_project_items_part_id",
            "ix_project_items_project_part",
        }
        if not expected_item_indexes.issubset(item_indexes):
            fail(f"project_items indexes are incomplete: {sorted(item_indexes)}")
        composite = [
            row[2]
            for row in db.execute(
                text("PRAGMA index_info(ix_project_items_project_part)")
            )
        ]
        if composite != ["project_id", "part_id"]:
            fail(f"Project item composite index is incorrect: {composite}")

        item_foreign_keys = db.execute(
            text("PRAGMA foreign_key_list(project_items)")
        ).fetchall()
        project_matches = [
            row
            for row in item_foreign_keys
            if row[2] == "projects"
            and row[3] == "project_id"
            and row[4] == "id"
            and str(row[6]).upper() == "CASCADE"
        ]
        part_matches = [
            row
            for row in item_foreign_keys
            if row[2] == "parts"
            and row[3] == "part_id"
            and row[4] == "id"
            and str(row[6]).upper() == "SET NULL"
        ]
        if len(project_matches) != 1 or len(part_matches) != 1:
            fail(f"Project item foreign keys are incorrect: {item_foreign_keys}")

        invalid_projects = db.execute(
            text(
                "select count(*) from projects where "
                "status not in ('draft','reserved','consumed','cancelled') "
                "or created_by not in ('manual','ai','mcp','system') "
                "or estimated_total_value < 0"
            )
        ).scalar()
        invalid_items = db.execute(
            text(
                "select count(*) from project_items where "
                "quantity <= 0 or unit_price_snapshot < 0"
            )
        ).scalar()
        if invalid_projects or invalid_items:
            fail(
                "Existing Projects data violates the canonical contract: "
                f"projects={invalid_projects}, items={invalid_items}"
            )

    for column, value in (
        ("status", "active"),
        ("created_by", "import"),
        ("estimated_total_value", -1),
    ):
        with db_session() as db:
            try:
                db.execute(
                    text(
                        "insert into projects "
                        "(name,status,created_by,estimated_total_value) "
                        "values (:name,:status,:created_by,:estimated_total_value)"
                    ),
                    {
                        "name": f"Invalid Project {column}",
                        "status": value if column == "status" else "draft",
                        "created_by": (
                            value if column == "created_by" else "system"
                        ),
                        "estimated_total_value": (
                            value if column == "estimated_total_value" else None
                        ),
                    },
                )
                db.flush()
            except exc.IntegrityError:
                db.rollback()
            else:
                db.rollback()
                fail(f"projects accepted invalid {column}: {value!r}")

    with db_session() as db:
        try:
            project_id = db.execute(
                text(
                    "insert into projects (name,status,created_by) "
                    "values ('Project item constraint fixture','draft','system') "
                    "returning id"
                )
            ).scalar_one()
            db.execute(
                text(
                    "insert into project_items "
                    "(project_id,part_id,quantity,unit_price_snapshot) "
                    "values (:project_id,null,1,-1)"
                ),
                {"project_id": project_id},
            )
            db.flush()
        except exc.IntegrityError:
            db.rollback()
        else:
            db.rollback()
            fail("project_items accepted a negative unit-price snapshot")

    with db_session() as db:
        try:
            for project_status in sorted(expected_statuses):
                db.execute(
                    text(
                        "insert into projects (name,status,created_by) "
                        "values (:name,:status,'system')"
                    ),
                    {
                        "name": f"Valid Project {project_status}",
                        "status": project_status,
                    },
                )
            db.flush()
            db.rollback()
        except Exception:
            db.rollback()
            raise

    ok(
        "Project lifecycle statuses, constraints, foreign keys, and indexes are aligned"
    )


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
# PARTPILOT:PROJECT_CREATION_SERVICE_SMOKE:V371
def check_project_creation_service() -> None:
    from decimal import Decimal

    from pydantic import ValidationError

    from app.models import Part
    from app.schemas.projects import (
        ProjectCreateRequest,
        ProjectItemCreateRequest,
    )
    from app.services.projects import (
        ProjectNotFoundError,
        ProjectValidationError,
        create_project,
        get_project,
        list_projects,
    )

    suffix = uuid4().hex[:12]
    part_numbers = [
        f"SMOKE-PROJECT-A-{suffix}",
        f"SMOKE-PROJECT-B-{suffix}",
        f"SMOKE-PROJECT-C-{suffix}",
    ]
    part_ids: list[int] = []
    project_ids: list[int] = []

    def cleanup() -> None:
        with db_session() as db:
            if project_ids:
                placeholders = ", ".join(
                    f":project_id_{index}"
                    for index, _project_id in enumerate(project_ids)
                )
                parameters = {
                    f"project_id_{index}": project_id
                    for index, project_id in enumerate(project_ids)
                }
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'project' "
                        f"and entity_id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(
                        "delete from project_items "
                        f"where project_id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(
                        "delete from projects "
                        f"where id in ({placeholders})"
                    ),
                    parameters,
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
        try:
            ProjectCreateRequest(
                name="Invalid",
                items=[
                    ProjectItemCreateRequest(
                        part_id=1,
                        quantity=0,
                    )
                ],
            )
        except ValidationError:
            pass
        else:
            fail("Project schema accepted a non-positive quantity")

        with db_session() as db:
            part_type_id = db.execute(
                text(
                    "select id from part_types "
                    "where is_active = 1 order by id limit 1"
                )
            ).scalar()
            if part_type_id is None:
                fail("Cannot test Projects without an active part type")
            fixtures = [
                Part(
                    part_type_id=part_type_id,
                    part_number=part_numbers[0],
                    name="Project service smoke part A",
                    total_quantity=2,
                    reserved_quantity=1,
                    unit_price=Decimal("2.5000"),
                    is_deleted=False,
                    deleted_at=None,
                ),
                Part(
                    part_type_id=part_type_id,
                    part_number=part_numbers[1],
                    name="Project service smoke part B",
                    total_quantity=0,
                    reserved_quantity=0,
                    unit_price=Decimal("1.2500"),
                    is_deleted=False,
                    deleted_at=None,
                ),
                Part(
                    part_type_id=part_type_id,
                    part_number=part_numbers[2],
                    name="Project service smoke part C",
                    total_quantity=4,
                    reserved_quantity=0,
                    unit_price=None,
                    is_deleted=False,
                    deleted_at=None,
                ),
            ]
            db.add_all(fixtures)
            db.commit()
            for part in fixtures:
                db.refresh(part)
                part_ids.append(part.id)

        with db_session() as db:
            inventory_before = {
                row["id"]: (
                    int(row["total_quantity"]),
                    int(row["reserved_quantity"]),
                    row["updated_at"],
                )
                for row in db.execute(
                    text(
                        "select id,total_quantity,reserved_quantity,updated_at "
                        "from parts where id in (:a,:b,:c)"
                    ),
                    {"a": part_ids[0], "b": part_ids[1], "c": part_ids[2]},
                ).mappings()
            }
            counts_before = {
                "reservations": db.execute(
                    text("select count(*) from reservations")
                ).scalar(),
                "reservation_items": db.execute(
                    text("select count(*) from reservation_items")
                ).scalar(),
                "stock_movements": db.execute(
                    text("select count(*) from stock_movements")
                ).scalar(),
            }

            response = create_project(
                db,
                ProjectCreateRequest(
                    name="  Smoke Project service  ",
                    description="  Inventory neutral planning  ",
                    notes="  Snapshot contract  ",
                    items=[
                        ProjectItemCreateRequest(
                            part_id=part_ids[0],
                            quantity=1,
                            note="Primary line",
                        ),
                        ProjectItemCreateRequest(
                            part_id=part_ids[0],
                            quantity=2,
                            note="Primary line",
                        ),
                        ProjectItemCreateRequest(
                            part_id=part_ids[1],
                            quantity=5,
                        ),
                    ],
                ),
                commit=True,
            )
            project_ids.append(response.id)

            if response.name != "Smoke Project service":
                fail(f"Project name was not normalised: {response.name!r}")
            if response.description != "Inventory neutral planning":
                fail("Project description was not normalised")
            if response.notes != "Snapshot contract":
                fail("Project notes were not normalised")
            if response.status != "draft" or response.created_by != "manual":
                fail("Project creation returned the wrong lifecycle metadata")
            if response.item_count != 2 or response.total_units != 8:
                fail(
                    "Project duplicate normalisation totals are wrong: "
                    f"items={response.item_count}, units={response.total_units}"
                )
            if response.estimated_total_value != Decimal("13.7500"):
                fail(
                    "Project snapshot total is incorrect: "
                    f"{response.estimated_total_value!r}"
                )

            by_part = {item.part_id: item for item in response.items}
            if by_part[part_ids[0]].quantity != 3:
                fail("Merged Project quantity is incorrect")
            if by_part[part_ids[1]].quantity != 5:
                fail("Project planning quantity is incorrect")
            if by_part[part_ids[1]].available_quantity != 0:
                fail("Project response current availability is incorrect")
            if by_part[part_ids[1]].quantity <= by_part[part_ids[1]].available_quantity:
                fail("Project smoke did not exercise planning beyond availability")

            stored_items = db.execute(
                text(
                    "select part_id,quantity,unit_price_snapshot,currency_snapshot,note "
                    "from project_items where project_id=:project_id order by part_id"
                ),
                {"project_id": response.id},
            ).mappings().all()
            if len(stored_items) != 2:
                fail("Project item normalization did not persist exactly two rows")
            stored_by_part = {int(row["part_id"]): row for row in stored_items}
            if int(stored_by_part[part_ids[0]]["quantity"]) != 3:
                fail("Persisted merged Project quantity is incorrect")
            if Decimal(stored_by_part[part_ids[0]]["unit_price_snapshot"]) != Decimal("2.5000"):
                fail("Project item price snapshot is incorrect")

            inventory_after = {
                row["id"]: (
                    int(row["total_quantity"]),
                    int(row["reserved_quantity"]),
                    row["updated_at"],
                )
                for row in db.execute(
                    text(
                        "select id,total_quantity,reserved_quantity,updated_at "
                        "from parts where id in (:a,:b,:c)"
                    ),
                    {"a": part_ids[0], "b": part_ids[1], "c": part_ids[2]},
                ).mappings()
            }
            if inventory_after != inventory_before:
                fail(
                    "Draft Project creation changed inventory: "
                    f"before={inventory_before}, after={inventory_after}"
                )
            counts_after = {
                "reservations": db.execute(
                    text("select count(*) from reservations")
                ).scalar(),
                "reservation_items": db.execute(
                    text("select count(*) from reservation_items")
                ).scalar(),
                "stock_movements": db.execute(
                    text("select count(*) from stock_movements")
                ).scalar(),
            }
            if counts_after != counts_before:
                fail(
                    "Draft Project creation created inventory lifecycle rows: "
                    f"before={counts_before}, after={counts_after}"
                )

            audit = db.execute(
                text(
                    "select actor_type,after_json,metadata_json from audit_log "
                    "where event_type='project.created' and entity_type='project' "
                    "and entity_id=:project_id"
                ),
                {"project_id": response.id},
            ).mappings().all()
            if len(audit) != 1:
                fail(f"Project creation audit count is wrong: {len(audit)}")
            if audit[0]["actor_type"] != "system":
                fail("Project creation audit actor is incorrect")
            if '"source": "manual"' not in str(audit[0]["metadata_json"]):
                fail("Project creation audit source metadata is missing")

            detail = get_project(db, response.id)
            if detail.model_dump() != response.model_dump():
                fail("Project detail serialization differs from create response")
            listing = list_projects(db, status_filter="draft", limit=10, offset=0)
            if response.id not in [project.id for project in listing.projects]:
                fail("Project list did not include the created Draft")

            unknown = create_project(
                db,
                ProjectCreateRequest(
                    name="Unknown price Project",
                    items=[
                        ProjectItemCreateRequest(
                            part_id=part_ids[2],
                            quantity=2,
                        )
                    ],
                ),
                commit=True,
            )
            project_ids.append(unknown.id)
            if unknown.estimated_total_value is not None:
                fail("Project with an unknown price understated its total")

        with db_session() as db:
            before_projects = db.execute(
                text("select count(*) from projects")
            ).scalar()
            try:
                create_project(
                    db,
                    ProjectCreateRequest(
                        name="Conflicting duplicate note Project",
                        items=[
                            ProjectItemCreateRequest(
                                part_id=part_ids[0],
                                quantity=1,
                                note="First",
                            ),
                            ProjectItemCreateRequest(
                                part_id=part_ids[0],
                                quantity=1,
                                note="Second",
                            ),
                        ],
                    ),
                )
            except ProjectValidationError:
                pass
            else:
                fail("Project service accepted conflicting duplicate notes")
            if db.execute(text("select count(*) from projects")).scalar() != before_projects:
                fail("Failed Project creation left a partial Project row")

            try:
                get_project(db, 2147483647)
            except ProjectNotFoundError:
                pass
            else:
                fail("Missing Project detail did not raise not-found")
            for kwargs in (
                {"status_filter": "active"},
                {"limit": 0},
                {"limit": 101},
                {"offset": -1},
            ):
                try:
                    list_projects(db, **kwargs)
                except ProjectValidationError:
                    pass
                else:
                    fail(f"Project list accepted invalid arguments: {kwargs}")

            transient = create_project(
                db,
                ProjectCreateRequest(
                    name="Transient Project",
                    items=[
                        ProjectItemCreateRequest(
                            part_id=part_ids[0],
                            quantity=1,
                        )
                    ],
                ),
                commit=False,
            )
            transient_id = transient.id
            db.rollback()
        with db_session() as db:
            if db.execute(
                text("select count(*) from projects where id=:id"),
                {"id": transient_id},
            ).scalar() != 0:
                fail("commit=False Project creation persisted after rollback")

    finally:
        cleanup()

    ok(
        "Project schemas and read/create service normalise Draft items, snapshot totals, audit once, and preserve inventory"
    )


# PARTPILOT:PROJECT_READ_CREATE_API_SMOKE:V374
def check_project_read_create_api() -> None:
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app
    from app.models import Part
    from app.services.auth import create_session, create_user

    suffix = uuid4().hex[:12]
    username = f"smoke_project_api_{suffix}"
    password = "project-api-smoke-password"
    part_numbers = [
        f"SMOKE-PROJECT-API-A-{suffix}",
        f"SMOKE-PROJECT-API-B-{suffix}",
    ]
    part_ids: list[int] = []
    project_ids: list[int] = []
    user_id: int | None = None

    def cleanup() -> None:
        with db_session() as db:
            if project_ids:
                placeholders = ", ".join(
                    f":project_id_{index}"
                    for index, _value in enumerate(project_ids)
                )
                parameters = {
                    f"project_id_{index}": value
                    for index, value in enumerate(project_ids)
                }
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'project' "
                        f"and entity_id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(
                        "delete from project_items "
                        f"where project_id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(
                        "delete from projects "
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
        openapi_response = client.get("/openapi.json")
        if openapi_response.status_code != 200:
            fail(
                "Projects OpenAPI lookup failed: "
                f"{openapi_response.status_code}: {openapi_response.text}"
            )
        paths = openapi_response.json().get("paths", {})
        if set(paths.get("/api/projects", {})) != {"get", "post"}:
            fail(
                "Projects collection OpenAPI methods are incorrect: "
                f"{paths.get('/api/projects')}"
            )
        if set(paths.get("/api/projects/{project_id}", {})) != {"get", "put"}:
            fail(
                "Project detail OpenAPI methods are incorrect: "
                f"{paths.get('/api/projects/{project_id}')}"
            )

        for method, path, payload in (
            ("get", "/api/projects", None),
            ("get", "/api/projects/999999999", None),
            (
                "post",
                "/api/projects",
                {
                    "name": "Unauthenticated Project",
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
                fail("Project API smoke requires an active part type")

            user = create_user(
                db,
                username=username,
                display_name="Project API Smoke User",
                password=password,
                commit=True,
            )
            user_id = user.id
            session_token = create_session(
                db,
                user=user,
                commit=True,
            )
            fixtures = [
                Part(
                    part_type_id=int(part_type_id),
                    part_number=part_numbers[0],
                    name="Project API smoke part A",
                    total_quantity=2,
                    reserved_quantity=0,
                    unit_price=Decimal("2.5000"),
                    is_deleted=False,
                    deleted_at=None,
                ),
                Part(
                    part_type_id=int(part_type_id),
                    part_number=part_numbers[1],
                    name="Project API smoke part B",
                    total_quantity=0,
                    reserved_quantity=0,
                    unit_price=Decimal("1.2500"),
                    is_deleted=False,
                    deleted_at=None,
                ),
            ]
            db.add_all(fixtures)
            db.commit()
            for part in fixtures:
                db.refresh(part)
                part_ids.append(part.id)

            inventory_before = {
                row["id"]: (
                    int(row["total_quantity"]),
                    int(row["reserved_quantity"]),
                    row["updated_at"],
                )
                for row in db.execute(
                    text(
                        "select id,total_quantity,reserved_quantity,updated_at "
                        "from parts where id in (:a,:b)"
                    ),
                    {"a": part_ids[0], "b": part_ids[1]},
                ).mappings()
            }
            lifecycle_before = {
                "reservations": int(
                    db.execute(text("select count(*) from reservations")).scalar()
                    or 0
                ),
                "reservation_items": int(
                    db.execute(
                        text("select count(*) from reservation_items")
                    ).scalar()
                    or 0
                ),
                "stock_movements": int(
                    db.execute(
                        text("select count(*) from stock_movements")
                    ).scalar()
                    or 0
                ),
            }
            existing_drafts = int(
                db.execute(
                    text("select count(*) from projects where status = 'draft'")
                ).scalar()
                or 0
            )

        headers = {
            "Authorization": f"Bearer {session_token.token}"
        }
        requests = [
            {
                "name": "  First API Project  ",
                "description": "  Existing-data-safe first Draft  ",
                "notes": "  First note  ",
                "items": [
                    {
                        "part_id": part_ids[0],
                        "quantity": 1,
                        "note": "Primary",
                    },
                    {
                        "part_id": part_ids[0],
                        "quantity": 2,
                        "note": "Primary",
                    },
                ],
            },
            {
                "name": "Second API Project",
                "items": [
                    {
                        "part_id": part_ids[1],
                        "quantity": 5,
                    }
                ],
            },
        ]
        created_payloads: list[dict[str, object]] = []
        for request_payload in requests:
            response = client.post(
                "/api/projects",
                headers=headers,
                json=request_payload,
            )
            if response.status_code != 201:
                fail(
                    "POST /api/projects returned "
                    f"{response.status_code}: {response.text}"
                )
            payload = response.json()
            project_id = int(payload["id"])
            project_ids.append(project_id)
            created_payloads.append(payload)

        first_payload, second_payload = created_payloads
        first_id, second_id = project_ids
        if (
            first_payload.get("name") != "First API Project"
            or first_payload.get("description")
            != "Existing-data-safe first Draft"
            or first_payload.get("notes") != "First note"
            or first_payload.get("status") != "draft"
            or first_payload.get("item_count") != 1
            or first_payload.get("total_units") != 3
            or len(first_payload.get("items", [])) != 1
            or first_payload["items"][0].get("quantity") != 3
        ):
            fail(f"First Project API payload is incorrect: {first_payload}")
        if (
            second_payload.get("status") != "draft"
            or second_payload.get("item_count") != 1
            or second_payload.get("total_units") != 5
            or second_payload["items"][0].get("available_quantity") != 0
        ):
            fail(f"Second Project API payload is incorrect: {second_payload}")

        with db_session() as db:
            db.execute(
                text(
                    "update projects set created_at = :created_at, "
                    "updated_at = :created_at where id = :project_id"
                ),
                {
                    "created_at": "2099-01-01 00:00:01.000000",
                    "project_id": first_id,
                },
            )
            db.execute(
                text(
                    "update projects set created_at = :created_at, "
                    "updated_at = :created_at where id = :project_id"
                ),
                {
                    "created_at": "2099-01-01 00:00:02.000000",
                    "project_id": second_id,
                },
            )
            db.commit()

        first_page = client.get(
            "/api/projects",
            headers=headers,
            params={"status": "draft", "limit": 1, "offset": 0},
        )
        if first_page.status_code != 200:
            fail(
                "GET /api/projects first page returned "
                f"{first_page.status_code}: {first_page.text}"
            )
        first_page_json = first_page.json()
        first_page_projects = first_page_json.get("projects", [])
        if (
            first_page_json.get("total") != existing_drafts + 2
            or first_page_json.get("limit") != 1
            or first_page_json.get("offset") != 0
            or len(first_page_projects) != 1
            or int(first_page_projects[0]["id"]) != second_id
        ):
            fail(
                "Project list ordering or first-page metadata is incorrect: "
                f"{first_page_json}"
            )

        second_page = client.get(
            "/api/projects",
            headers=headers,
            params={"status": "draft", "limit": 1, "offset": 1},
        )
        if second_page.status_code != 200:
            fail(
                "GET /api/projects second page returned "
                f"{second_page.status_code}: {second_page.text}"
            )
        second_page_json = second_page.json()
        second_page_projects = second_page_json.get("projects", [])
        if (
            second_page_json.get("total") != existing_drafts + 2
            or second_page_json.get("offset") != 1
            or len(second_page_projects) != 1
            or int(second_page_projects[0]["id"]) != first_id
        ):
            fail(
                "Project list pagination is incorrect: "
                f"{second_page_json}"
            )

        detail_response = client.get(
            f"/api/projects/{first_id}",
            headers=headers,
        )
        if detail_response.status_code != 200:
            fail(
                "GET /api/projects/{id} returned "
                f"{detail_response.status_code}: {detail_response.text}"
            )
        detail_json = detail_response.json()
        if (
            int(detail_json.get("id", 0)) != first_id
            or detail_json.get("name") != "First API Project"
            or detail_json.get("item_count") != 1
            or detail_json.get("total_units") != 3
        ):
            fail(f"Project detail response is incorrect: {detail_json}")

        missing_response = client.get(
            f"/api/projects/{second_id + 999999}",
            headers=headers,
        )
        if missing_response.status_code != 404:
            fail(
                "Missing Project detail should return 404, got "
                f"{missing_response.status_code}: {missing_response.text}"
            )

        for params in (
            {"status": "active"},
            {"limit": 0},
            {"limit": 101},
            {"offset": -1},
        ):
            invalid_list = client.get(
                "/api/projects",
                headers=headers,
                params=params,
            )
            if invalid_list.status_code != 422:
                fail(
                    "Invalid Project list parameters should return 422: "
                    f"params={params}, status={invalid_list.status_code}, "
                    f"body={invalid_list.text}"
                )

        invalid_quantity = client.post(
            "/api/projects",
            headers=headers,
            json={
                "name": "Invalid quantity Project",
                "items": [{"part_id": part_ids[0], "quantity": 0}],
            },
        )
        if invalid_quantity.status_code != 422:
            fail(
                "Invalid Project quantity should return 422, got "
                f"{invalid_quantity.status_code}: {invalid_quantity.text}"
            )

        missing_part = client.post(
            "/api/projects",
            headers=headers,
            json={
                "name": "Missing part Project",
                "items": [
                    {
                        "part_id": max(part_ids) + 999999,
                        "quantity": 1,
                    }
                ],
            },
        )
        if missing_part.status_code != 422:
            fail(
                "Missing Project part should return 422, got "
                f"{missing_part.status_code}: {missing_part.text}"
            )

        conflicting_notes = client.post(
            "/api/projects",
            headers=headers,
            json={
                "name": "Conflicting notes Project",
                "items": [
                    {
                        "part_id": part_ids[0],
                        "quantity": 1,
                        "note": "First",
                    },
                    {
                        "part_id": part_ids[0],
                        "quantity": 1,
                        "note": "Second",
                    },
                ],
            },
        )
        if conflicting_notes.status_code != 422:
            fail(
                "Conflicting duplicate Project notes should return 422, got "
                f"{conflicting_notes.status_code}: {conflicting_notes.text}"
            )

        with db_session() as db:
            inventory_after = {
                row["id"]: (
                    int(row["total_quantity"]),
                    int(row["reserved_quantity"]),
                    row["updated_at"],
                )
                for row in db.execute(
                    text(
                        "select id,total_quantity,reserved_quantity,updated_at "
                        "from parts where id in (:a,:b)"
                    ),
                    {"a": part_ids[0], "b": part_ids[1]},
                ).mappings()
            }
            if inventory_after != inventory_before:
                fail(
                    "Project API changed fixture inventory: "
                    f"before={inventory_before}, after={inventory_after}"
                )

            lifecycle_after = {
                "reservations": int(
                    db.execute(text("select count(*) from reservations")).scalar()
                    or 0
                ),
                "reservation_items": int(
                    db.execute(
                        text("select count(*) from reservation_items")
                    ).scalar()
                    or 0
                ),
                "stock_movements": int(
                    db.execute(
                        text("select count(*) from stock_movements")
                    ).scalar()
                    or 0
                ),
            }
            if lifecycle_after != lifecycle_before:
                fail(
                    "Project API created inventory lifecycle rows: "
                    f"before={lifecycle_before}, after={lifecycle_after}"
                )

            counts = {
                "projects": int(
                    db.execute(
                        text(
                            "select count(*) from projects "
                            "where id in (:first_id,:second_id)"
                        ),
                        {"first_id": first_id, "second_id": second_id},
                    ).scalar()
                    or 0
                ),
                "items": int(
                    db.execute(
                        text(
                            "select count(*) from project_items "
                            "where project_id in (:first_id,:second_id)"
                        ),
                        {"first_id": first_id, "second_id": second_id},
                    ).scalar()
                    or 0
                ),
                "audits": int(
                    db.execute(
                        text(
                            "select count(*) from audit_log "
                            "where event_type = 'project.created' "
                            "and entity_type = 'project' "
                            "and entity_id in (:first_id,:second_id) "
                            "and actor_type = 'user' "
                            "and actor_user_id = :user_id"
                        ),
                        {
                            "first_id": first_id,
                            "second_id": second_id,
                            "user_id": user_id,
                        },
                    ).scalar()
                    or 0
                ),
            }
            if counts != {"projects": 2, "items": 2, "audits": 2}:
                fail(
                    "Project API persistence or actor audit counts are "
                    f"incorrect: {counts}"
                )
    finally:
        cleanup()

    ok(
        "Protected Project list, detail, and Draft creation APIs enforce "
        "authentication, OpenAPI registration, ordering, pagination, "
        "validation, actor audits, inventory neutrality, and exact cleanup"
    )

# PARTPILOT:PROJECT_DRAFT_UPDATE_API_SMOKE:V379
def check_project_draft_update_api() -> None:
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app
    from app.models import Part
    from app.services.auth import create_session, create_user

    suffix = uuid4().hex[:12]
    username = f"smoke_project_update_{suffix}"
    password = "project-update-smoke-password"
    part_numbers = [
        f"SMOKE-PROJECT-UPDATE-A-{suffix}",
        f"SMOKE-PROJECT-UPDATE-B-{suffix}",
        f"SMOKE-PROJECT-UPDATE-C-{suffix}",
    ]
    part_ids: list[int] = []
    project_id: int | None = None
    user_id: int | None = None

    def cleanup() -> None:
        with db_session() as db:
            if project_id is not None:
                db.execute(
                    text(
                        "delete from audit_log where entity_type='project' "
                        "and entity_id=:project_id"
                    ),
                    {"project_id": project_id},
                )
                db.execute(
                    text("delete from project_items where project_id=:project_id"),
                    {"project_id": project_id},
                )
                db.execute(
                    text("delete from projects where id=:project_id"),
                    {"project_id": project_id},
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
                        "delete from stock_movements "
                        f"where part_id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(
                        "delete from audit_log where entity_type='part' "
                        f"and entity_id in ({placeholders})"
                    ),
                    parameters,
                )
                db.execute(
                    text(f"delete from parts where id in ({placeholders})"),
                    parameters,
                )
            db.execute(
                text(
                    "delete from sessions where user_id in "
                    "(select id from users where username=:username)"
                ),
                {"username": username},
            )
            db.execute(
                text("delete from users where username=:username"),
                {"username": username},
            )
            db.commit()

    cleanup()
    client = TestClient(fastapi_app)
    try:
        paths = client.get("/openapi.json").json().get("paths", {})
        if set(paths.get("/api/projects/{project_id}", {})) != {"get", "put"}:
            fail(
                "Project detail OpenAPI methods are incorrect after update: "
                f"{paths.get('/api/projects/{project_id}')}"
            )
        unauthenticated = client.put(
            "/api/projects/999999999",
            json={
                "name": "Unauthenticated Project update",
                "items": [{"part_id": 1, "quantity": 1}],
            },
        )
        if unauthenticated.status_code != 401:
            fail(
                "Unauthenticated Project update should return 401, got "
                f"{unauthenticated.status_code}"
            )

        with db_session() as db:
            part_type_id = db.execute(
                text(
                    "select id from part_types where is_active=1 "
                    "order by id limit 1"
                )
            ).scalar()
            if part_type_id is None:
                fail("Project update smoke requires an active part type")
            user = create_user(
                db,
                username=username,
                display_name="Project Update Smoke User",
                password=password,
                commit=True,
            )
            user_id = user.id
            session_token = create_session(db, user=user, commit=True)
            fixtures = [
                Part(
                    part_type_id=int(part_type_id),
                    part_number=part_numbers[0],
                    name="Project update part A",
                    total_quantity=4,
                    reserved_quantity=0,
                    unit_price=Decimal("2.0000"),
                    is_deleted=False,
                    deleted_at=None,
                ),
                Part(
                    part_type_id=int(part_type_id),
                    part_number=part_numbers[1],
                    name="Project update part B",
                    total_quantity=1,
                    reserved_quantity=0,
                    unit_price=Decimal("3.5000"),
                    is_deleted=False,
                    deleted_at=None,
                ),
                Part(
                    part_type_id=int(part_type_id),
                    part_number=part_numbers[2],
                    name="Project update part C",
                    total_quantity=0,
                    reserved_quantity=0,
                    unit_price=Decimal("1.2500"),
                    is_deleted=False,
                    deleted_at=None,
                ),
            ]
            db.add_all(fixtures)
            db.commit()
            for part in fixtures:
                db.refresh(part)
                part_ids.append(part.id)
            inventory_before = {
                row["id"]: (
                    int(row["total_quantity"]),
                    int(row["reserved_quantity"]),
                    row["updated_at"],
                )
                for row in db.execute(
                    text(
                        "select id,total_quantity,reserved_quantity,updated_at "
                        "from parts where id in (:a,:b,:c)"
                    ),
                    {"a": part_ids[0], "b": part_ids[1], "c": part_ids[2]},
                ).mappings()
            }
            lifecycle_before = {
                "reservations": int(db.execute(text("select count(*) from reservations")).scalar() or 0),
                "reservation_items": int(db.execute(text("select count(*) from reservation_items")).scalar() or 0),
                "stock_movements": int(db.execute(text("select count(*) from stock_movements")).scalar() or 0),
            }

        headers = {"Authorization": f"Bearer {session_token.token}"}
        created = client.post(
            "/api/projects",
            headers=headers,
            json={
                "name": "Project update original",
                "description": "Original description",
                "notes": "Original notes",
                "items": [
                    {"part_id": part_ids[0], "quantity": 2, "note": "Keep"},
                    {"part_id": part_ids[1], "quantity": 1, "note": "Remove"},
                ],
            },
        )
        if created.status_code != 201:
            fail(f"Project update fixture creation failed: {created.status_code}: {created.text}")
        created_body = created.json()
        project_id = int(created_body["id"])
        retained_id = next(
            int(item["id"])
            for item in created_body["items"]
            if int(item["part_id"]) == part_ids[0]
        )

        missing = client.put(
            "/api/projects/999999999",
            headers=headers,
            json={
                "name": "Missing Project",
                "items": [{"part_id": part_ids[0], "quantity": 1}],
            },
        )
        if missing.status_code != 404:
            fail(f"Missing Project update should return 404, got {missing.status_code}")

        updated = client.put(
            f"/api/projects/{project_id}",
            headers=headers,
            json={
                "name": "  Project update revised  ",
                "description": "  Revised description  ",
                "notes": "  Revised notes  ",
                "items": [
                    {"part_id": part_ids[0], "quantity": 3, "note": "  Keep revised  "},
                    {"part_id": part_ids[2], "quantity": 2, "note": "  Add  "},
                    {"part_id": part_ids[2], "quantity": 1, "note": "Add"},
                ],
            },
        )
        if updated.status_code != 200:
            fail(f"Draft Project update failed: {updated.status_code}: {updated.text}")
        body = updated.json()
        if (
            body["name"] != "Project update revised"
            or body["description"] != "Revised description"
            or body["notes"] != "Revised notes"
            or body["status"] != "draft"
            or body["item_count"] != 2
            or body["total_units"] != 6
            or Decimal(str(body["estimated_total_value"])) != Decimal("9.7500")
        ):
            fail(f"Updated Project response is incorrect: {body}")
        by_part = {int(item["part_id"]): item for item in body["items"]}
        if set(by_part) != {part_ids[0], part_ids[2]}:
            fail(f"Project item reconciliation is incorrect: {by_part}")
        if int(by_part[part_ids[0]]["id"]) != retained_id:
            fail("Retained Project item did not preserve its row identity")
        if int(by_part[part_ids[2]]["quantity"]) != 3:
            fail("Duplicate submitted Project items were not normalised")

        with db_session() as db:
            audit_before_noop = int(
                db.execute(
                    text(
                        "select count(*) from audit_log where entity_type='project' "
                        "and entity_id=:project_id and event_type='project.updated'"
                    ),
                    {"project_id": project_id},
                ).scalar() or 0
            )
            updated_at_before_noop = db.execute(
                text("select updated_at from projects where id=:project_id"),
                {"project_id": project_id},
            ).scalar()
            audit = db.execute(
                text(
                    "select actor_type,actor_user_id,before_json,after_json "
                    "from audit_log where entity_type='project' "
                    "and entity_id=:project_id and event_type='project.updated'"
                ),
                {"project_id": project_id},
            ).mappings().one()
            if audit["actor_type"] != "user" or int(audit["actor_user_id"]) != user_id:
                fail(f"Project update actor audit is incorrect: {audit}")
            if not audit["before_json"] or not audit["after_json"]:
                fail("Project update audit snapshots are missing")

        noop_payload = {
            "name": "Project update revised",
            "description": "Revised description",
            "notes": "Revised notes",
            "items": [
                {"part_id": part_ids[0], "quantity": 3, "note": "Keep revised"},
                {"part_id": part_ids[2], "quantity": 3, "note": "Add"},
            ],
        }
        noop = client.put(
            f"/api/projects/{project_id}",
            headers=headers,
            json=noop_payload,
        )
        if noop.status_code != 200:
            fail(f"No-op Project update failed: {noop.status_code}: {noop.text}")
        with db_session() as db:
            audit_after_noop = int(
                db.execute(
                    text(
                        "select count(*) from audit_log where entity_type='project' "
                        "and entity_id=:project_id and event_type='project.updated'"
                    ),
                    {"project_id": project_id},
                ).scalar() or 0
            )
            updated_at_after_noop = db.execute(
                text("select updated_at from projects where id=:project_id"),
                {"project_id": project_id},
            ).scalar()
            if audit_after_noop != audit_before_noop or updated_at_after_noop != updated_at_before_noop:
                fail("No-op Project update changed persistence or audit state")

            db.execute(
                text("update projects set status='reserved' where id=:project_id"),
                {"project_id": project_id},
            )
            db.commit()
        conflict = client.put(
            f"/api/projects/{project_id}",
            headers=headers,
            json=noop_payload,
        )
        if conflict.status_code != 409:
            fail(f"Non-Draft Project update should return 409, got {conflict.status_code}")
        with db_session() as db:
            db.execute(
                text("update projects set status='draft' where id=:project_id"),
                {"project_id": project_id},
            )
            db.commit()

        invalid = client.put(
            f"/api/projects/{project_id}",
            headers=headers,
            json={
                "name": "Invalid part update",
                "items": [{"part_id": 999999999, "quantity": 1}],
            },
        )
        if invalid.status_code != 422:
            fail(f"Invalid Project part should return 422, got {invalid.status_code}")

        with db_session() as db:
            inventory_after = {
                row["id"]: (
                    int(row["total_quantity"]),
                    int(row["reserved_quantity"]),
                    row["updated_at"],
                )
                for row in db.execute(
                    text(
                        "select id,total_quantity,reserved_quantity,updated_at "
                        "from parts where id in (:a,:b,:c)"
                    ),
                    {"a": part_ids[0], "b": part_ids[1], "c": part_ids[2]},
                ).mappings()
            }
            lifecycle_after = {
                "reservations": int(db.execute(text("select count(*) from reservations")).scalar() or 0),
                "reservation_items": int(db.execute(text("select count(*) from reservation_items")).scalar() or 0),
                "stock_movements": int(db.execute(text("select count(*) from stock_movements")).scalar() or 0),
            }
            if inventory_after != inventory_before:
                fail("Project update changed inventory rows")
            if lifecycle_after != lifecycle_before:
                fail("Project update changed reservation or movement counts")
    finally:
        cleanup()

    ok(
        "Draft Project updates are authenticated, reconciled, snapshot-aware, "
        "no-op safe, status-guarded, audited once, and inventory-neutral"
    )


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
            "role",
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
    audit_floor = 0

    def cleanup() -> None:
        with db_session() as db:
            if custom_type_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where entity_type = 'part_type' "
                        "and entity_id = :entity_id "
                        "and id > :audit_floor"
                    ),
                    {
                        "entity_id": custom_type_id,
                        "audit_floor": audit_floor,
                    },
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
    with db_session() as db:
        audit_floor = db.execute(
            text("select coalesce(max(id), 0) from audit_log")
        ).scalar()
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
                    "and entity_id = :entity_id "
                    "and id > :audit_floor"
                ),
                {
                    "entity_id": custom_type_id,
                    "audit_floor": audit_floor,
                },
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
    audit_floor = 0
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
                        "and entity_id = :entity_id "
                        "and id > :audit_floor"
                    ),
                    {
                        "entity_id": custom_type_id,
                        "audit_floor": audit_floor,
                    },
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
    with db_session() as db:
        audit_floor = db.execute(
            text("select coalesce(max(id), 0) from audit_log")
        ).scalar()
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
                    "and entity_id = :entity_id "
                    "and id > :audit_floor"
                ),
                {
                    "entity_id": custom_type_id,
                    "audit_floor": audit_floor,
                },
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
# PARTPILOT:RESERVATION_SETTINGS_SMOKE:V361
def check_reservation_settings_api() -> None:
    import json as json_module
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app
    from app.models import AppSetting
    from app.schemas.app_settings import ReservationSettingsUpdateRequest
    from app.services import app_settings as app_settings_service

    mode_key = "reservations.expiry.mode"
    days_key = "reservations.expiry.default_days"
    setting_keys = (mode_key, days_key)
    suffix = uuid4().hex[:10]
    username = f"smoke_reservation_settings_{suffix}"
    password = "reservation-settings-smoke-password"
    user_id: int | None = None

    with db_session() as db:
        original_settings: dict[str, tuple[object, str | None] | None] = {}
        for key in setting_keys:
            row = (
                db.query(AppSetting)
                .filter(AppSetting.key == key)
                .one_or_none()
            )
            original_settings[key] = (
                None
                if row is None
                else (row.value_json, row.value_text)
            )

    def restore_settings(db) -> None:
        for key in setting_keys:
            original = original_settings[key]
            row = (
                db.query(AppSetting)
                .filter(AppSetting.key == key)
                .one_or_none()
            )
            if original is None:
                if row is not None:
                    db.delete(row)
            elif row is None:
                db.add(
                    AppSetting(
                        key=key,
                        value_json=original[0],
                        value_text=original[1],
                    )
                )
            else:
                row.value_json = original[0]
                row.value_text = original[1]

    def cleanup() -> None:
        with db_session() as db:
            if user_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where event_type = 'settings.reservations_updated' "
                        "and actor_user_id = :actor_user_id"
                    ),
                    {"actor_user_id": user_id},
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
            restore_settings(db)
            db.commit()

    client = TestClient(fastapi_app)

    try:
        unauthenticated_get = client.get("/api/settings/reservations")
        if unauthenticated_get.status_code not in {401, 403}:
            fail(
                "GET /api/settings/reservations should require authentication, "
                f"got {unauthenticated_get.status_code}: "
                f"{unauthenticated_get.text}"
            )
        unauthenticated_patch = client.patch(
            "/api/settings/reservations",
            json={"expiry_mode": "none", "default_days": None},
        )
        if unauthenticated_patch.status_code not in {401, 403}:
            fail(
                "PATCH /api/settings/reservations should require authentication, "
                f"got {unauthenticated_patch.status_code}: "
                f"{unauthenticated_patch.text}"
            )

        openapi = client.get("/openapi.json")
        openapi_methods = (
            openapi.json()
            .get("paths", {})
            .get("/api/settings/reservations", {})
        )
        if (
            openapi.status_code != 200
            or "get" not in openapi_methods
            or "patch" not in openapi_methods
        ):
            fail(
                "Reservation settings GET/PATCH routes are missing from OpenAPI: "
                f"{openapi.status_code} {openapi_methods}"
            )

        with db_session() as db:
            set_app_setting(db, mode_key, "none", text_value="none", commit=False)
            set_app_setting(db, days_key, None, text_value=None, commit=False)
            user = create_user(
                db,
                username=username,
                display_name="Reservation Settings Smoke User",
                password=password,
                commit=False,
            )
            db.commit()
            db.refresh(user)
            user_id = user.id
            session_token = create_session(db, user=user, commit=True)

        headers = {"Authorization": f"Bearer {session_token.token}"}

        seeded = client.get("/api/settings/reservations", headers=headers)
        if (
            seeded.status_code != 200
            or seeded.json()
            != {"expiry_mode": "none", "default_days": None}
        ):
            fail(
                "Seeded reservation settings should read as none/null: "
                f"{seeded.status_code} {seeded.text}"
            )

        with db_session() as db:
            set_app_setting(
                db, mode_key, "legacy-corrupt", text_value="legacy-corrupt",
                commit=False,
            )
            set_app_setting(db, days_key, 44, text_value=None, commit=False)
            db.commit()
        corrupt_read = client.get(
            "/api/settings/reservations", headers=headers
        )
        if (
            corrupt_read.status_code != 200
            or corrupt_read.json()
            != {"expiry_mode": "none", "default_days": None}
        ):
            fail(
                "Corrupt reservation settings should defensively read as "
                f"none/null: {corrupt_read.status_code} {corrupt_read.text}"
            )
        with db_session() as db:
            raw_mode = get_str_setting(db, mode_key, "")
            raw_days = db.query(AppSetting).filter(
                AppSetting.key == days_key
            ).one().value_json
            if raw_mode != "legacy-corrupt" or raw_days != 44:
                fail(
                    "Reservation settings GET silently rewrote corrupt values: "
                    f"{raw_mode!r}/{raw_days!r}"
                )
            set_app_setting(db, mode_key, "none", text_value="none", commit=False)
            set_app_setting(db, days_key, None, text_value=None, commit=False)
            db.commit()

        invalid_payloads = [
            {"expiry_mode": "invalid", "default_days": None},
            {"expiry_mode": "default"},
            {"expiry_mode": "default", "default_days": 0},
            {"expiry_mode": "default", "default_days": -1},
            {"expiry_mode": "default", "default_days": 1.5},
            {"expiry_mode": "default", "default_days": True},
            {"expiry_mode": "default", "default_days": "7"},
            {"expiry_mode": "default", "default_days": 3651},
            {
                "expiry_mode": "none",
                "default_days": None,
                "unexpected": True,
            },
        ]
        for payload in invalid_payloads:
            response = client.patch(
                "/api/settings/reservations",
                headers=headers,
                json=payload,
            )
            if response.status_code != 422:
                fail(
                    "Invalid reservation settings payload should return 422, "
                    f"got {response.status_code}: {payload!r} {response.text}"
                )

        default_one = client.patch(
            "/api/settings/reservations",
            headers=headers,
            json={"expiry_mode": "default", "default_days": 1},
        )
        if (
            default_one.status_code != 200
            or default_one.json()
            != {"expiry_mode": "default", "default_days": 1}
        ):
            fail(
                "Reservation default day lower boundary failed: "
                f"{default_one.status_code} {default_one.text}"
            )

        repeat_one = client.patch(
            "/api/settings/reservations",
            headers=headers,
            json={"expiry_mode": "default", "default_days": 1},
        )
        if repeat_one.status_code != 200:
            fail(
                "Idempotent reservation settings PATCH failed: "
                f"{repeat_one.status_code} {repeat_one.text}"
            )

        default_max = client.patch(
            "/api/settings/reservations",
            headers=headers,
            json={"expiry_mode": "default", "default_days": 3650},
        )
        if (
            default_max.status_code != 200
            or default_max.json()
            != {"expiry_mode": "default", "default_days": 3650}
        ):
            fail(
                "Reservation default day upper boundary failed: "
                f"{default_max.status_code} {default_max.text}"
            )

        with db_session() as db:
            mode_row = db.query(AppSetting).filter(
                AppSetting.key == mode_key
            ).one()
            days_row = db.query(AppSetting).filter(
                AppSetting.key == days_key
            ).one()
            if (
                mode_row.value_json != "default"
                or mode_row.value_text != "default"
                or days_row.value_json != 3650
                or days_row.value_text is not None
            ):
                fail(
                    "Reservation settings database values are incorrect: "
                    f"{mode_row.value_json!r}/{mode_row.value_text!r}/"
                    f"{days_row.value_json!r}/{days_row.value_text!r}"
                )

        none_with_stale_days = client.patch(
            "/api/settings/reservations",
            headers=headers,
            json={"expiry_mode": "none", "default_days": 99},
        )
        if (
            none_with_stale_days.status_code != 200
            or none_with_stale_days.json()
            != {"expiry_mode": "none", "default_days": None}
        ):
            fail(
                "None mode should normalize stale default_days to null: "
                f"{none_with_stale_days.status_code} "
                f"{none_with_stale_days.text}"
            )

        repeat_none = client.patch(
            "/api/settings/reservations",
            headers=headers,
            json={"expiry_mode": "none", "default_days": 123},
        )
        if repeat_none.status_code != 200:
            fail(
                "Normalized idempotent none-mode PATCH failed: "
                f"{repeat_none.status_code} {repeat_none.text}"
            )

        with db_session() as db:
            mode_setting_id = db.query(AppSetting).filter(
                AppSetting.key == mode_key
            ).one().id
            audit_rows = db.execute(
                text(
                    "select entity_id, actor_type, actor_user_id, "
                    "before_json, after_json, metadata_json "
                    "from audit_log "
                    "where event_type = 'settings.reservations_updated' "
                    "and actor_user_id = :actor_user_id order by id"
                ),
                {"actor_user_id": user_id},
            ).all()

        if len(audit_rows) != 3:
            fail(
                "Reservation settings should create one audit per real change "
                f"and none for no-op updates, got {len(audit_rows)}."
            )

        decoded_audits: list[tuple[dict, dict, dict]] = []
        for row in audit_rows:
            if (
                row[0] != mode_setting_id
                or row[1] != "user"
                or row[2] != user_id
            ):
                fail(
                    "Reservation settings audit attribution is incorrect: "
                    f"{row!r}"
                )
            before_json = (
                json_module.loads(row[3])
                if isinstance(row[3], str)
                else row[3]
            )
            after_json = (
                json_module.loads(row[4])
                if isinstance(row[4], str)
                else row[4]
            )
            metadata_json = (
                json_module.loads(row[5])
                if isinstance(row[5], str)
                else row[5]
            )
            decoded_audits.append(
                (before_json, after_json, metadata_json)
            )

        expected_snapshots = [
            (
                {"expiry_mode": "none", "default_days": None},
                {"expiry_mode": "default", "default_days": 1},
                ["expiry_mode", "default_days"],
            ),
            (
                {"expiry_mode": "default", "default_days": 1},
                {"expiry_mode": "default", "default_days": 3650},
                ["default_days"],
            ),
            (
                {"expiry_mode": "default", "default_days": 3650},
                {"expiry_mode": "none", "default_days": None},
                ["expiry_mode", "default_days"],
            ),
        ]
        for decoded, expected in zip(decoded_audits, expected_snapshots):
            before_json, after_json, metadata_json = decoded
            expected_before, expected_after, expected_fields = expected
            if before_json != expected_before or after_json != expected_after:
                fail(
                    "Reservation settings audit snapshots are incorrect: "
                    f"{decoded_audits!r}"
                )
            if (
                metadata_json.get("setting_keys")
                != [mode_key, days_key]
                or metadata_json.get("changed_fields") != expected_fields
            ):
                fail(
                    "Reservation settings audit metadata is incorrect: "
                    f"{metadata_json!r}"
                )

        real_set_app_setting = app_settings_service.set_app_setting
        call_count = 0

        def fail_second_setting_write(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("injected second reservation setting failure")
            return real_set_app_setting(*args, **kwargs)

        with db_session() as db:
            try:
                with patch.object(
                    app_settings_service,
                    "set_app_setting",
                    side_effect=fail_second_setting_write,
                ):
                    app_settings_service.update_reservation_settings(
                        db,
                        ReservationSettingsUpdateRequest(
                            expiry_mode="default",
                            default_days=30,
                        ),
                        actor_user_id=user_id,
                        commit=True,
                    )
            except RuntimeError as exc:
                if "injected second reservation setting failure" not in str(exc):
                    raise
            else:
                fail("Injected reservation settings failure did not raise")

        with db_session() as db:
            after_failure = app_settings_service.get_reservation_settings(db)
            audit_count_after_failure = db.execute(
                text(
                    "select count(*) from audit_log "
                    "where event_type = 'settings.reservations_updated' "
                    "and actor_user_id = :actor_user_id"
                ),
                {"actor_user_id": user_id},
            ).scalar()
            mode_row = db.query(AppSetting).filter(
                AppSetting.key == mode_key
            ).one()
            days_row = db.query(AppSetting).filter(
                AppSetting.key == days_key
            ).one()
        if (
            after_failure.model_dump()
            != {"expiry_mode": "none", "default_days": None}
            or mode_row.value_json != "none"
            or mode_row.value_text != "none"
            or days_row.value_json is not None
            or days_row.value_text is not None
            or audit_count_after_failure != 3
        ):
            fail(
                "Injected reservation settings failure was not atomic: "
                f"{after_failure.model_dump()} audits={audit_count_after_failure}"
            )

    finally:
        cleanup()

    ok(
        "Protected reservation defaults validate none/default modes, strict day "
        "boundaries, corrupt-read normalization, atomic two-key persistence, "
        "no-op suppression, actor-attributed audit snapshots, injected rollback, "
        "OpenAPI exposure, authentication, and exact fixture cleanup"
    )


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

# PARTPILOT:PROJECT_RESERVATION_SMOKE:V383
def check_project_reservation_api() -> None:
    from decimal import Decimal
    from uuid import uuid4

    from fastapi.testclient import TestClient
    from sqlalchemy import func, select

    from app.db.constants import (
        MOVEMENT_TYPE_RESERVE,
        PROJECT_STATUS_DRAFT,
        PROJECT_STATUS_RESERVED,
        RESERVATION_STATUS_ACTIVE,
    )
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import (
        AuditLog,
        Part,
        PartType,
        Project,
        ProjectItem,
        Reservation,
        ReservationItem,
        StockMovement,
    )
    from app.services.projects import (
        ProjectConflictError,
        reserve_project,
    )

    client = TestClient(app)
    unauthenticated = client.post("/api/projects/999999999/reserve")
    if unauthenticated.status_code not in (401, 403):
        fail(
            "Unauthenticated Project reservation should return 401/403, got "
            f"{unauthenticated.status_code}: {unauthenticated.text}"
        )

    openapi = client.get("/openapi.json")
    reserve_methods = set(
        openapi.json()
        .get("paths", {})
        .get("/api/projects/{project_id}/reserve", {})
    )
    if openapi.status_code != 200 or reserve_methods != {"post"}:
        fail(
            "Project reservation OpenAPI contract is incorrect: "
            f"{openapi.status_code}, {sorted(reserve_methods)}"
        )

    db = SessionLocal()
    suffix = uuid4().hex[:12]
    try:
        part_type_id = db.execute(
            select(PartType.id)
            .where(PartType.is_active.is_(True))
            .order_by(PartType.id.asc())
            .limit(1)
        ).scalar_one_or_none()
        if part_type_id is None:
            fail("Project reservation smoke requires an active part type")

        part = Part(
            part_type_id=part_type_id,
            part_number=f"PP383-{suffix}",
            name=f"Project reservation smoke {suffix}",
            total_quantity=5,
            reserved_quantity=1,
            unit_price=Decimal("2.5000"),
            is_deleted=False,
        )
        project = Project(
            name=f"Project reservation {suffix}",
            description="Atomic Project reservation smoke fixture",
            status=PROJECT_STATUS_DRAFT,
            notes="Preserve Project item notes",
            created_by="manual",
            estimated_total_value=Decimal("5.0000"),
            currency_snapshot="USD",
        )
        db.add_all([part, project])
        db.flush()
        project_item = ProjectItem(
            project_id=project.id,
            part_id=part.id,
            quantity=2,
            unit_price_snapshot=Decimal("2.5000"),
            currency_snapshot="USD",
            note="Reserve this exact Project quantity",
        )
        db.add(project_item)
        db.flush()

        total_before = int(part.total_quantity)
        reserved_before = int(part.reserved_quantity)
        response = reserve_project(
            db,
            project.id,
            actor_user_id=None,
            commit=False,
        )
        db.flush()

        if response.status != PROJECT_STATUS_RESERVED:
            fail(f"Project reserve response status is incorrect: {response}")
        if project.status != PROJECT_STATUS_RESERVED:
            fail("Project persistence did not transition to reserved")
        if int(part.total_quantity) != total_before:
            fail("Project reservation changed physical total quantity")
        if int(part.reserved_quantity) != reserved_before + 2:
            fail("Project reservation did not increment reserved quantity")

        reservation = db.execute(
            select(Reservation).where(Reservation.project_id == project.id)
        ).scalar_one_or_none()
        if reservation is None:
            fail("Project reservation did not create a linked Reservation")
        if reservation.status != RESERVATION_STATUS_ACTIVE:
            fail(f"Linked Reservation status is incorrect: {reservation.status}")

        reservation_item = db.execute(
            select(ReservationItem).where(
                ReservationItem.reservation_id == reservation.id
            )
        ).scalar_one_or_none()
        if (
            reservation_item is None
            or reservation_item.part_id != part.id
            or int(reservation_item.quantity) != 2
            or reservation_item.note != project_item.note
        ):
            fail("Linked Reservation item did not preserve the Project plan")

        movement = db.execute(
            select(StockMovement).where(
                StockMovement.reservation_id == reservation.id
            )
        ).scalar_one_or_none()
        if (
            movement is None
            or movement.movement_type != MOVEMENT_TYPE_RESERVE
            or movement.quantity_delta != 0
            or movement.quantity_before != total_before
            or movement.quantity_after != total_before
            or movement.reserved_quantity_before != reserved_before
            or movement.reserved_quantity_after != reserved_before + 2
        ):
            fail(f"Project reserve movement is incorrect: {movement}")

        project_audits = int(
            db.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.event_type == "project.reserved",
                    AuditLog.entity_type == "project",
                    AuditLog.entity_id == project.id,
                )
            ).scalar_one()
        )
        reservation_audits = int(
            db.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.event_type == "reservation.created",
                    AuditLog.entity_type == "reservation",
                    AuditLog.entity_id == reservation.id,
                )
            ).scalar_one()
        )
        if project_audits != 1 or reservation_audits != 1:
            fail(
                "Project reservation did not create exactly one Project and "
                "one Reservation audit"
            )

        db.rollback()

        conflict_part = Part(
            part_type_id=part_type_id,
            part_number=f"PP383-CONFLICT-{suffix}",
            name=f"Project reservation conflict {suffix}",
            total_quantity=1,
            reserved_quantity=1,
            unit_price=Decimal("1.0000"),
            is_deleted=False,
        )
        conflict_project = Project(
            name=f"Project reservation conflict {suffix}",
            status=PROJECT_STATUS_DRAFT,
            created_by="manual",
            estimated_total_value=Decimal("1.0000"),
            currency_snapshot="USD",
        )
        db.add_all([conflict_part, conflict_project])
        db.flush()
        db.add(
            ProjectItem(
                project_id=conflict_project.id,
                part_id=conflict_part.id,
                quantity=1,
                unit_price_snapshot=Decimal("1.0000"),
                currency_snapshot="USD",
            )
        )
        db.flush()
        try:
            reserve_project(
                db,
                conflict_project.id,
                actor_user_id=None,
                commit=False,
            )
        except ProjectConflictError:
            pass
        else:
            fail("Project reservation accepted insufficient available stock")
        db.rollback()
    finally:
        db.close()

    ok(
        "Draft Projects reserve atomically through linked Reservations, "
        "stock movements, audits, status guards, and inventory-safe rollback"
    )

# PARTPILOT:PROJECT_CONSUMPTION_SMOKE:V394
def check_project_consumption_api() -> None:
    from decimal import Decimal
    from uuid import uuid4

    from fastapi.testclient import TestClient
    from sqlalchemy import func, select

    from app.db.constants import (
        MOVEMENT_TYPE_CONSUME,
        PROJECT_STATUS_CONSUMED,
        PROJECT_STATUS_DRAFT,
        PROJECT_STATUS_RESERVED,
        RESERVATION_STATUS_ACTIVE,
        RESERVATION_STATUS_CONSUMED,
    )
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import (
        AuditLog,
        Part,
        PartType,
        Project,
        ProjectItem,
        Reservation,
        StockMovement,
    )
    from app.services.projects import (
        ProjectConflictError,
        consume_project,
        reserve_project,
    )

    client = TestClient(app)
    unauthenticated = client.post(
        "/api/projects/999999999/consume"
    )
    if unauthenticated.status_code not in (401, 403):
        fail(
            "Unauthenticated Project consumption should return 401/403, "
            f"got {unauthenticated.status_code}: "
            f"{unauthenticated.text}"
        )

    openapi = client.get("/openapi.json")
    consume_methods = set(
        openapi.json()
        .get("paths", {})
        .get("/api/projects/{project_id}/consume", {})
    )
    if openapi.status_code != 200 or consume_methods != {"post"}:
        fail(
            "Project consumption OpenAPI contract is incorrect: "
            f"{openapi.status_code}, {sorted(consume_methods)}"
        )

    db = SessionLocal()
    suffix = uuid4().hex[:12]
    try:
        part_type_id = db.execute(
            select(PartType.id)
            .where(PartType.is_active.is_(True))
            .order_by(PartType.id.asc())
            .limit(1)
        ).scalar_one_or_none()
        if part_type_id is None:
            fail(
                "Project consumption smoke requires an active part type"
            )

        part = Part(
            part_type_id=part_type_id,
            part_number=f"PP394-{suffix}",
            name=f"Project consumption smoke {suffix}",
            total_quantity=7,
            reserved_quantity=0,
            unit_price=Decimal("3.2500"),
            is_deleted=False,
        )
        project = Project(
            name=f"Project consumption {suffix}",
            description="Atomic Project consumption smoke fixture",
            status=PROJECT_STATUS_DRAFT,
            notes="Consume this linked Project reservation",
            created_by="manual",
            estimated_total_value=Decimal("6.5000"),
            currency_snapshot="USD",
        )
        db.add_all([part, project])
        db.flush()
        db.add(
            ProjectItem(
                project_id=project.id,
                part_id=part.id,
                quantity=2,
                unit_price_snapshot=Decimal("3.2500"),
                currency_snapshot="USD",
                note="Consume this exact Project quantity",
            )
        )
        db.flush()

        reserve_project(
            db,
            project.id,
            actor_user_id=None,
            commit=False,
        )
        db.flush()

        reservation = db.execute(
            select(Reservation).where(
                Reservation.project_id == project.id
            )
        ).scalar_one_or_none()
        if reservation is None:
            fail(
                "Project consumption fixture has no linked Reservation"
            )
        if reservation.status != RESERVATION_STATUS_ACTIVE:
            fail(
                "Project consumption fixture Reservation is not active"
            )

        total_before = int(part.total_quantity)
        reserved_before = int(part.reserved_quantity)
        available_before = total_before - reserved_before
        if reserved_before != 2:
            fail(
                "Project consumption fixture did not reserve two units"
            )

        response = consume_project(
            db,
            project.id,
            actor_user_id=None,
            commit=False,
        )
        db.flush()
        db.refresh(project)
        db.refresh(reservation)
        db.refresh(part)

        if response.status != PROJECT_STATUS_CONSUMED:
            fail(
                "Project consume response did not transition to consumed"
            )
        if project.status != PROJECT_STATUS_CONSUMED:
            fail(
                "Project persistence did not transition to consumed"
            )
        if reservation.status != RESERVATION_STATUS_CONSUMED:
            fail(
                "Linked Reservation did not transition to consumed"
            )
        if int(part.total_quantity) != total_before - 2:
            fail(
                "Project consumption did not reduce physical total quantity"
            )
        if int(part.reserved_quantity) != reserved_before - 2:
            fail(
                "Project consumption did not reduce reserved quantity"
            )
        if (
            int(part.total_quantity) - int(part.reserved_quantity)
            != available_before
        ):
            fail(
                "Project consumption changed available quantity"
            )

        movement = db.execute(
            select(StockMovement).where(
                StockMovement.reservation_id == reservation.id,
                StockMovement.movement_type == MOVEMENT_TYPE_CONSUME,
            )
        ).scalar_one_or_none()
        if (
            movement is None
            or int(movement.quantity_delta) != -2
            or int(movement.quantity_before) != total_before
            or int(movement.quantity_after) != total_before - 2
            or int(movement.reserved_quantity_before)
            != reserved_before
            or int(movement.reserved_quantity_after)
            != reserved_before - 2
            or int(movement.available_quantity_before)
            != available_before
            or int(movement.available_quantity_after)
            != available_before
        ):
            fail(
                f"Project consume movement is incorrect: {movement}"
            )

        project_audit = db.execute(
            select(AuditLog).where(
                AuditLog.event_type == "project.consumed",
                AuditLog.entity_type == "project",
                AuditLog.entity_id == project.id,
            )
        ).scalar_one_or_none()
        reservation_audit_count = int(
            db.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.event_type == "reservation.consumed",
                    AuditLog.entity_type == "reservation",
                    AuditLog.entity_id == reservation.id,
                )
            ).scalar_one()
        )
        if project_audit is None or reservation_audit_count != 1:
            fail(
                "Project consumption did not create exactly one Project "
                "and one Reservation consumption audit"
            )
        if (
            project_audit.before_json.get("status")
            != PROJECT_STATUS_RESERVED
            or project_audit.after_json.get("status")
            != PROJECT_STATUS_CONSUMED
            or project_audit.after_json.get("reservation_id")
            != reservation.id
            or project_audit.after_json.get("consumed_units") != 2
            or project_audit.metadata_json.get("movement_type")
            != MOVEMENT_TYPE_CONSUME
        ):
            fail(
                "Project consumption audit payload is incorrect: "
                f"{project_audit.after_json}"
            )

        try:
            consume_project(
                db,
                project.id,
                actor_user_id=None,
                commit=False,
            )
        except ProjectConflictError:
            pass
        else:
            fail(
                "Already-consumed Project accepted a second consumption"
            )

        db.rollback()

        orphan_part = Part(
            part_type_id=part_type_id,
            part_number=f"PP394-ORPHAN-{suffix}",
            name=f"Project consumption orphan {suffix}",
            total_quantity=3,
            reserved_quantity=1,
            unit_price=Decimal("1.0000"),
            is_deleted=False,
        )
        orphan_project = Project(
            name=f"Project consumption orphan {suffix}",
            status=PROJECT_STATUS_RESERVED,
            created_by="manual",
            estimated_total_value=Decimal("1.0000"),
            currency_snapshot="USD",
        )
        db.add_all([orphan_part, orphan_project])
        db.flush()
        db.add(
            ProjectItem(
                project_id=orphan_project.id,
                part_id=orphan_part.id,
                quantity=1,
                unit_price_snapshot=Decimal("1.0000"),
                currency_snapshot="USD",
            )
        )
        db.flush()

        try:
            consume_project(
                db,
                orphan_project.id,
                actor_user_id=None,
                commit=False,
            )
        except ProjectConflictError:
            pass
        else:
            fail(
                "Reserved Project without a linked Reservation was consumed"
            )

        if (
            orphan_project.status != PROJECT_STATUS_RESERVED
            or int(orphan_part.total_quantity) != 3
            or int(orphan_part.reserved_quantity) != 1
        ):
            fail(
                "Rejected orphan Project consumption changed Project "
                "or inventory state"
            )
        db.rollback()
    finally:
        db.close()

    ok(
        "Reserved Projects consume atomically through their linked "
        "Reservations, preserving available quantity, synchronising terminal "
        "statuses, movements, audits, guards, and rollback"
    )

# PARTPILOT:PROJECT_CANCELLATION_SMOKE:V397
def check_project_cancellation_api() -> None:
    from decimal import Decimal
    from uuid import uuid4

    from fastapi.testclient import TestClient
    from sqlalchemy import func, select, text

    from app.db.constants import (
        MOVEMENT_TYPE_RELEASE,
        PROJECT_STATUS_CANCELLED,
        PROJECT_STATUS_DRAFT,
        PROJECT_STATUS_RESERVED,
        RESERVATION_STATUS_ACTIVE,
        RESERVATION_STATUS_CANCELLED,
    )
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import (
        AuditLog,
        Part,
        PartType,
        Project,
        ProjectItem,
        Reservation,
        StockMovement,
    )
    from app.services.projects import (
        ProjectConflictError,
        ProjectNotFoundError,
        cancel_project,
        reserve_project,
    )

    client = TestClient(app)
    unauthenticated = client.post(
        "/api/projects/999999999/cancel"
    )
    if unauthenticated.status_code not in (401, 403):
        fail(
            "Unauthenticated Project cancellation should return 401/403, "
            f"got {unauthenticated.status_code}: "
            f"{unauthenticated.text}"
        )

    openapi = client.get("/openapi.json")
    cancel_methods = set(
        openapi.json()
        .get("paths", {})
        .get("/api/projects/{project_id}/cancel", {})
    )
    if openapi.status_code != 200 or cancel_methods != {"post"}:
        fail(
            "Project cancellation OpenAPI contract is incorrect: "
            f"{openapi.status_code}, {sorted(cancel_methods)}"
        )

    suffix = uuid4().hex[:12]
    db = SessionLocal()
    try:
        part_type_id = db.execute(
            select(PartType.id)
            .where(PartType.is_active.is_(True))
            .order_by(PartType.id.asc())
            .limit(1)
        ).scalar_one_or_none()
        if part_type_id is None:
            fail(
                "Project cancellation smoke requires an active part type"
            )

        part = Part(
            part_type_id=part_type_id,
            part_number=f"PP397-{suffix}",
            name=f"Project cancellation smoke {suffix}",
            total_quantity=7,
            reserved_quantity=0,
            unit_price=Decimal("3.2500"),
            is_deleted=False,
        )
        project = Project(
            name=f"Project cancellation {suffix}",
            description="Atomic Project cancellation smoke fixture",
            status=PROJECT_STATUS_DRAFT,
            notes="Cancel this linked Project reservation",
            created_by="manual",
            estimated_total_value=Decimal("6.5000"),
            currency_snapshot="USD",
        )
        db.add_all([part, project])
        db.flush()
        db.add(
            ProjectItem(
                project_id=project.id,
                part_id=part.id,
                quantity=2,
                unit_price_snapshot=Decimal("3.2500"),
                currency_snapshot="USD",
                note="Release this exact Project quantity",
            )
        )
        db.flush()

        reserve_project(
            db,
            project.id,
            actor_user_id=None,
            commit=False,
        )
        db.flush()

        reservation = db.execute(
            select(Reservation).where(
                Reservation.project_id == project.id
            )
        ).scalar_one_or_none()
        if reservation is None:
            fail(
                "Project cancellation fixture has no linked Reservation"
            )
        if reservation.status != RESERVATION_STATUS_ACTIVE:
            fail(
                "Project cancellation fixture Reservation is not active"
            )

        total_before = int(part.total_quantity)
        reserved_before = int(part.reserved_quantity)
        available_before = total_before - reserved_before
        if reserved_before != 2:
            fail(
                "Project cancellation fixture did not reserve two units"
            )

        response = cancel_project(
            db,
            project.id,
            actor_user_id=None,
            commit=False,
        )
        db.flush()
        db.refresh(project)
        db.refresh(reservation)
        db.refresh(part)

        if response.status != PROJECT_STATUS_CANCELLED:
            fail(
                "Project cancel response did not transition to cancelled"
            )
        if project.status != PROJECT_STATUS_CANCELLED:
            fail(
                "Project persistence did not transition to cancelled"
            )
        if reservation.status != RESERVATION_STATUS_CANCELLED:
            fail(
                "Linked Reservation did not transition to cancelled"
            )
        if int(part.total_quantity) != total_before:
            fail(
                "Project cancellation changed physical total quantity"
            )
        if int(part.reserved_quantity) != reserved_before - 2:
            fail(
                "Project cancellation did not release reserved quantity"
            )
        if (
            int(part.total_quantity) - int(part.reserved_quantity)
            != available_before + 2
        ):
            fail(
                "Project cancellation did not increase available quantity"
            )

        release_movements = list(
            db.execute(
                select(StockMovement)
                .where(
                    StockMovement.reservation_id == reservation.id,
                    StockMovement.movement_type == MOVEMENT_TYPE_RELEASE,
                )
                .order_by(StockMovement.id.asc())
            ).scalars()
        )
        if len(release_movements) != 1:
            fail(
                "Project cancellation did not create exactly one release "
                f"movement: {len(release_movements)}"
            )
        movement = release_movements[0]
        if (
            int(movement.quantity_delta) != 0
            or int(movement.quantity_before) != total_before
            or int(movement.quantity_after) != total_before
            or int(movement.reserved_quantity_before)
            != reserved_before
            or int(movement.reserved_quantity_after)
            != reserved_before - 2
            or int(movement.available_quantity_before)
            != available_before
            or int(movement.available_quantity_after)
            != available_before + 2
        ):
            fail(
                f"Project release movement is incorrect: {movement}"
            )

        project_audit = db.execute(
            select(AuditLog).where(
                AuditLog.event_type == "project.cancelled",
                AuditLog.entity_type == "project",
                AuditLog.entity_id == project.id,
            )
        ).scalar_one_or_none()
        reservation_audit_count = int(
            db.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.event_type == "reservation.cancelled",
                    AuditLog.entity_type == "reservation",
                    AuditLog.entity_id == reservation.id,
                )
            ).scalar_one()
        )
        if project_audit is None or reservation_audit_count != 1:
            fail(
                "Project cancellation did not create exactly one Project "
                "and one Reservation cancellation audit"
            )
        if (
            project_audit.before_json.get("status")
            != PROJECT_STATUS_RESERVED
            or project_audit.before_json.get("reservation_id")
            != reservation.id
            or project_audit.before_json.get("reservation_status")
            != RESERVATION_STATUS_ACTIVE
            or project_audit.after_json.get("status")
            != PROJECT_STATUS_CANCELLED
            or project_audit.after_json.get("reservation_id")
            != reservation.id
            or project_audit.after_json.get("reservation_status")
            != RESERVATION_STATUS_CANCELLED
            or project_audit.after_json.get("released_units") != 2
            or project_audit.after_json.get("stock_movement_ids")
            != [movement.id]
            or project_audit.metadata_json.get("movement_type")
            != MOVEMENT_TYPE_RELEASE
        ):
            fail(
                "Project cancellation audit payload is incorrect: "
                f"{project_audit.after_json}"
            )

        try:
            cancel_project(
                db,
                project.id,
                actor_user_id=None,
                commit=False,
            )
        except ProjectConflictError:
            pass
        else:
            fail(
                "Already-cancelled Project accepted a second cancellation"
            )

        try:
            cancel_project(
                db,
                999999999,
                actor_user_id=None,
                commit=False,
            )
        except ProjectNotFoundError:
            pass
        else:
            fail("Missing Project was accepted for cancellation")

        db.rollback()

        draft_project = Project(
            name=f"Project cancellation draft guard {suffix}",
            status=PROJECT_STATUS_DRAFT,
            created_by="manual",
        )
        db.add(draft_project)
        db.flush()
        try:
            cancel_project(
                db,
                draft_project.id,
                actor_user_id=None,
                commit=False,
            )
        except ProjectConflictError:
            pass
        else:
            fail("Draft Project was accepted for cancellation")
        if draft_project.status != PROJECT_STATUS_DRAFT:
            fail("Rejected Draft Project cancellation changed status")
        db.rollback()

        orphan_part = Part(
            part_type_id=part_type_id,
            part_number=f"PP397-ORPHAN-{suffix}",
            name=f"Project cancellation orphan {suffix}",
            total_quantity=3,
            reserved_quantity=1,
            unit_price=Decimal("1.0000"),
            is_deleted=False,
        )
        orphan_project = Project(
            name=f"Project cancellation orphan {suffix}",
            status=PROJECT_STATUS_RESERVED,
            created_by="manual",
            estimated_total_value=Decimal("1.0000"),
            currency_snapshot="USD",
        )
        db.add_all([orphan_part, orphan_project])
        db.flush()
        db.add(
            ProjectItem(
                project_id=orphan_project.id,
                part_id=orphan_part.id,
                quantity=1,
                unit_price_snapshot=Decimal("1.0000"),
                currency_snapshot="USD",
            )
        )
        db.flush()
        try:
            cancel_project(
                db,
                orphan_project.id,
                actor_user_id=None,
                commit=False,
            )
        except ProjectConflictError:
            pass
        else:
            fail(
                "Reserved Project without a linked Reservation was cancelled"
            )
        if (
            orphan_project.status != PROJECT_STATUS_RESERVED
            or int(orphan_part.total_quantity) != 3
            or int(orphan_part.reserved_quantity) != 1
        ):
            fail(
                "Rejected orphan Project cancellation changed Project "
                "or inventory state"
            )
        db.rollback()

        duplicate_project = Project(
            name=f"Project cancellation duplicate link {suffix}",
            status=PROJECT_STATUS_RESERVED,
            created_by="manual",
        )
        db.add(duplicate_project)
        db.flush()
        duplicate_reservations = [
            Reservation(
                project_id=duplicate_project.id,
                label=f"Duplicate link {index} {suffix}",
                status=RESERVATION_STATUS_ACTIVE,
                notes=None,
                created_by="manual",
                expiry_at=None,
                estimated_reserved_value=None,
                currency_snapshot=None,
            )
            for index in (1, 2)
        ]
        db.add_all(duplicate_reservations)
        db.flush()
        try:
            cancel_project(
                db,
                duplicate_project.id,
                actor_user_id=None,
                commit=False,
            )
        except ProjectConflictError:
            pass
        else:
            fail(
                "Project with duplicate linked Reservations was cancelled"
            )
        if (
            duplicate_project.status != PROJECT_STATUS_RESERVED
            or any(
                row.status != RESERVATION_STATUS_ACTIVE
                for row in duplicate_reservations
            )
        ):
            fail(
                "Rejected duplicate-link cancellation changed lifecycle state"
            )
        db.rollback()

        inactive_project = Project(
            name=f"Project cancellation inactive link {suffix}",
            status=PROJECT_STATUS_RESERVED,
            created_by="manual",
        )
        db.add(inactive_project)
        db.flush()
        inactive_reservation = Reservation(
            project_id=inactive_project.id,
            label=f"Inactive cancellation link {suffix}",
            status=RESERVATION_STATUS_CANCELLED,
            notes=None,
            created_by="manual",
            expiry_at=None,
            estimated_reserved_value=None,
            currency_snapshot=None,
        )
        db.add(inactive_reservation)
        db.flush()
        try:
            cancel_project(
                db,
                inactive_project.id,
                actor_user_id=None,
                commit=False,
            )
        except ProjectConflictError:
            pass
        else:
            fail(
                "Project with an inactive linked Reservation was cancelled"
            )
        if (
            inactive_project.status != PROJECT_STATUS_RESERVED
            or inactive_reservation.status
            != RESERVATION_STATUS_CANCELLED
        ):
            fail(
                "Rejected inactive-link cancellation changed lifecycle state"
            )
        db.rollback()
    finally:
        db.close()

    conflict_part_id: int | None = None
    conflict_project_id: int | None = None
    conflict_reservation_id: int | None = None
    db = SessionLocal()
    try:
        part_type_id = db.execute(
            select(PartType.id)
            .where(PartType.is_active.is_(True))
            .order_by(PartType.id.asc())
            .limit(1)
        ).scalar_one()
        conflict_part = Part(
            part_type_id=part_type_id,
            part_number=f"PP397-CONFLICT-{suffix}",
            name=f"Project cancellation conflict {suffix}",
            total_quantity=7,
            reserved_quantity=0,
            unit_price=Decimal("2.0000"),
            is_deleted=False,
        )
        conflict_project = Project(
            name=f"Project cancellation conflict {suffix}",
            status=PROJECT_STATUS_DRAFT,
            created_by="manual",
            estimated_total_value=Decimal("4.0000"),
            currency_snapshot="USD",
        )
        db.add_all([conflict_part, conflict_project])
        db.flush()
        db.add(
            ProjectItem(
                project_id=conflict_project.id,
                part_id=conflict_part.id,
                quantity=2,
                unit_price_snapshot=Decimal("2.0000"),
                currency_snapshot="USD",
            )
        )
        db.flush()
        reserve_project(
            db,
            conflict_project.id,
            actor_user_id=None,
            commit=False,
        )
        db.flush()
        conflict_reservation = db.execute(
            select(Reservation).where(
                Reservation.project_id == conflict_project.id
            )
        ).scalar_one()
        conflict_part_id = conflict_part.id
        conflict_project_id = conflict_project.id
        conflict_reservation_id = conflict_reservation.id
        db.commit()

        db.execute(
            text(
                "update parts set reserved_quantity = 1 "
                "where id = :part_id"
            ),
            {"part_id": conflict_part_id},
        )
        db.commit()

        try:
            cancel_project(
                db,
                conflict_project_id,
                actor_user_id=None,
                commit=True,
            )
        except ProjectConflictError:
            pass
        else:
            fail(
                "Concurrent reserved-stock change was accepted during "
                "Project cancellation"
            )

        conflict_state = db.execute(
            text(
                "select p.status as project_status, "
                "r.status as reservation_status, "
                "pt.total_quantity, pt.reserved_quantity "
                "from projects p "
                "join reservations r on r.project_id = p.id "
                "join project_items pi on pi.project_id = p.id "
                "join parts pt on pt.id = pi.part_id "
                "where p.id = :project_id"
            ),
            {"project_id": conflict_project_id},
        ).mappings().one()
        release_count = int(
            db.execute(
                select(func.count())
                .select_from(StockMovement)
                .where(
                    StockMovement.reservation_id
                    == conflict_reservation_id,
                    StockMovement.movement_type
                    == MOVEMENT_TYPE_RELEASE,
                )
            ).scalar_one()
        )
        cancellation_audit_count = int(
            db.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.event_type.in_(
                        (
                            "reservation.cancelled",
                            "project.cancelled",
                        )
                    ),
                    (
                        (
                            AuditLog.entity_type == "reservation"
                        )
                        & (
                            AuditLog.entity_id
                            == conflict_reservation_id
                        )
                    )
                    | (
                        (
                            AuditLog.entity_type == "project"
                        )
                        & (
                            AuditLog.entity_id
                            == conflict_project_id
                        )
                    ),
                )
            ).scalar_one()
        )
        if (
            conflict_state["project_status"]
            != PROJECT_STATUS_RESERVED
            or conflict_state["reservation_status"]
            != RESERVATION_STATUS_ACTIVE
            or int(conflict_state["total_quantity"]) != 7
            or int(conflict_state["reserved_quantity"]) != 1
            or release_count != 0
            or cancellation_audit_count != 0
        ):
            fail(
                "Failed Project cancellation did not roll back atomically: "
                f"{dict(conflict_state)}, release_count={release_count}, "
                f"audit_count={cancellation_audit_count}"
            )
    finally:
        db.rollback()
        if conflict_project_id is not None:
            db.execute(
                text(
                    "delete from audit_log where "
                    "(entity_type = 'project' and entity_id = :project_id) "
                    "or (entity_type = 'reservation' "
                    "and entity_id = :reservation_id)"
                ),
                {
                    "project_id": conflict_project_id,
                    "reservation_id": conflict_reservation_id,
                },
            )
        if conflict_reservation_id is not None:
            db.execute(
                text(
                    "delete from stock_movements "
                    "where reservation_id = :reservation_id"
                ),
                {"reservation_id": conflict_reservation_id},
            )
            db.execute(
                text(
                    "delete from reservation_items "
                    "where reservation_id = :reservation_id"
                ),
                {"reservation_id": conflict_reservation_id},
            )
            db.execute(
                text(
                    "delete from reservations "
                    "where id = :reservation_id"
                ),
                {"reservation_id": conflict_reservation_id},
            )
        if conflict_project_id is not None:
            db.execute(
                text(
                    "delete from project_items "
                    "where project_id = :project_id"
                ),
                {"project_id": conflict_project_id},
            )
            db.execute(
                text(
                    "delete from projects where id = :project_id"
                ),
                {"project_id": conflict_project_id},
            )
        if conflict_part_id is not None:
            db.execute(
                text(
                    "delete from stock_movements where part_id = :part_id"
                ),
                {"part_id": conflict_part_id},
            )
            db.execute(
                text("delete from parts where id = :part_id"),
                {"part_id": conflict_part_id},
            )
        db.commit()
        db.close()

    ok(
        "Reserved Projects cancel atomically through their linked "
        "Reservations, release stock without changing physical totals, "
        "synchronise terminal statuses, preserve movements and audits, "
        "reject invalid links and repeated actions, and roll back conflicts"
    )


# PARTPILOT:PROJECT_LINKED_RESERVATION_TERMINAL_SMOKE:V399
def check_project_linked_reservation_terminal_sync() -> None:
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal
    from uuid import uuid4

    from sqlalchemy import func, select

    from app.db.constants import (
        MOVEMENT_TYPE_CONSUME,
        MOVEMENT_TYPE_RELEASE,
        PROJECT_STATUS_CANCELLED,
        PROJECT_STATUS_CONSUMED,
        PROJECT_STATUS_DRAFT,
        RESERVATION_STATUS_CANCELLED,
        RESERVATION_STATUS_CONSUMED,
        RESERVATION_STATUS_EXPIRED,
    )
    from app.db.session import SessionLocal
    from app.models import (
        AuditLog,
        Part,
        PartType,
        Project,
        ProjectItem,
        Reservation,
        StockMovement,
    )
    from app.services.projects import reserve_project
    from app.services.reservations import (
        cancel_reservation,
        consume_reservation,
        expire_reservation,
    )

    suffix = uuid4().hex[:12]
    db = SessionLocal()
    try:
        part_type_id = db.execute(
            select(PartType.id)
            .where(PartType.is_active.is_(True))
            .order_by(PartType.id.asc())
            .limit(1)
        ).scalar_one_or_none()
        if part_type_id is None:
            fail(
                "Project-linked Reservation terminal smoke requires an "
                "active part type"
            )

        cases = (
            (
                "consume",
                consume_reservation,
                PROJECT_STATUS_CONSUMED,
                RESERVATION_STATUS_CONSUMED,
                MOVEMENT_TYPE_CONSUME,
                "project.consumed",
                "reservation.consumed",
                "consumed_units",
                6,
                0,
                6,
                "manual",
            ),
            (
                "cancel",
                cancel_reservation,
                PROJECT_STATUS_CANCELLED,
                RESERVATION_STATUS_CANCELLED,
                MOVEMENT_TYPE_RELEASE,
                "project.cancelled",
                "reservation.cancelled",
                "released_units",
                8,
                0,
                8,
                "manual",
            ),
            (
                "expire",
                expire_reservation,
                PROJECT_STATUS_CANCELLED,
                RESERVATION_STATUS_EXPIRED,
                MOVEMENT_TYPE_RELEASE,
                "project.cancelled",
                "reservation.expired",
                "released_units",
                8,
                0,
                8,
                "system",
            ),
        )

        for index, (
            action,
            action_function,
            expected_project_status,
            expected_reservation_status,
            movement_type,
            project_event,
            reservation_event,
            units_key,
            expected_total,
            expected_reserved,
            expected_available,
            expected_source,
        ) in enumerate(cases, start=1):
            part = Part(
                part_type_id=part_type_id,
                part_number=f"PP399-{action.upper()}-{suffix}",
                name=f"Linked Reservation {action} smoke {suffix}",
                total_quantity=8,
                reserved_quantity=0,
                unit_price=Decimal("2.0000"),
                is_deleted=False,
            )
            project = Project(
                name=f"Linked Reservation {action} {suffix}",
                description=(
                    "Direct Reservation terminal action must synchronise "
                    "the linked Project"
                ),
                status=PROJECT_STATUS_DRAFT,
                created_by="manual",
                estimated_total_value=Decimal("4.0000"),
                currency_snapshot="USD",
            )
            db.add_all([part, project])
            db.flush()
            db.add(
                ProjectItem(
                    project_id=project.id,
                    part_id=part.id,
                    quantity=2,
                    unit_price_snapshot=Decimal("2.0000"),
                    currency_snapshot="USD",
                )
            )
            db.flush()
            reserve_project(
                db,
                project.id,
                actor_user_id=None,
                commit=False,
            )
            db.flush()

            reservation = db.execute(
                select(Reservation).where(
                    Reservation.project_id == project.id
                )
            ).scalar_one()
            if action == "expire":
                reservation.expiry_at = (
                    datetime.now(timezone.utc)
                    - timedelta(minutes=5)
                )
                db.flush()

            action_function(
                db,
                reservation.id,
                actor_user_id=None,
                commit=False,
            )
            db.flush()
            db.refresh(project)
            db.refresh(reservation)
            db.refresh(part)

            if project.status != expected_project_status:
                fail(
                    f"Direct {action} did not synchronise Project status: "
                    f"{project.status}"
                )
            if reservation.status != expected_reservation_status:
                fail(
                    f"Direct {action} did not persist Reservation status: "
                    f"{reservation.status}"
                )
            actual_stock = (
                int(part.total_quantity),
                int(part.reserved_quantity),
                int(part.total_quantity) - int(part.reserved_quantity),
            )
            expected_stock = (
                expected_total,
                expected_reserved,
                expected_available,
            )
            if actual_stock != expected_stock:
                fail(
                    f"Direct {action} stock result is incorrect: "
                    f"{actual_stock}, expected {expected_stock}"
                )

            movement = db.execute(
                select(StockMovement).where(
                    StockMovement.reservation_id == reservation.id,
                    StockMovement.movement_type == movement_type,
                )
            ).scalar_one_or_none()
            if movement is None:
                fail(
                    f"Direct {action} did not create its terminal movement"
                )

            project_audit = db.execute(
                select(AuditLog).where(
                    AuditLog.event_type == project_event,
                    AuditLog.entity_type == "project",
                    AuditLog.entity_id == project.id,
                )
            ).scalar_one_or_none()
            reservation_audit_count = int(
                db.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(
                        AuditLog.event_type == reservation_event,
                        AuditLog.entity_type == "reservation",
                        AuditLog.entity_id == reservation.id,
                    )
                ).scalar_one()
            )
            if project_audit is None or reservation_audit_count != 1:
                fail(
                    f"Direct {action} did not create exactly one linked "
                    "Project audit and one Reservation audit"
                )
            if (
                project_audit.before_json.get("status")
                != "reserved"
                or project_audit.after_json.get("status")
                != expected_project_status
                or project_audit.after_json.get("reservation_status")
                != expected_reservation_status
                or project_audit.after_json.get(units_key) != 2
                or project_audit.after_json.get("stock_movement_ids")
                != [movement.id]
                or project_audit.metadata_json.get("origin")
                != "reservation.lifecycle"
                or project_audit.metadata_json.get(
                    "reservation_terminal_action"
                )
                != action
                or project_audit.metadata_json.get("source")
                != expected_source
            ):
                fail(
                    f"Direct {action} linked Project audit is incorrect: "
                    f"{project_audit.after_json}, "
                    f"{project_audit.metadata_json}"
                )

            db.rollback()

    finally:
        db.rollback()
        db.close()

    ok(
        "Direct consume, cancel, and expiry actions on Project-linked "
        "Reservations synchronise terminal Project status, stock, "
        "movements, audits, and transaction ownership"
    )



# PARTPILOT:PROJECT_RESERVED_UPDATE_SMOKE:V400
def check_project_reserved_update_api() -> None:
    from decimal import Decimal
    from uuid import uuid4

    from fastapi.testclient import TestClient
    from sqlalchemy import delete, func, select

    from app.db.constants import (
        MOVEMENT_TYPE_RELEASE,
        MOVEMENT_TYPE_RESERVE,
        PROJECT_STATUS_DRAFT,
        PROJECT_STATUS_RESERVED,
        RESERVATION_STATUS_ACTIVE,
    )
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import (
        AuditLog,
        Part,
        PartType,
        Project,
        ProjectItem,
        Reservation,
        ReservationItem,
        StockMovement,
    )
    from app.schemas.projects import ProjectUpdateRequest
    from app.services.parts import list_part_movements
    from app.services.projects import (
        ProjectConflictError,
        reserve_project,
        update_project,
    )

    client = TestClient(app)
    unauthenticated = client.put(
        "/api/projects/999999999",
        json={
            "name": "Unauthenticated",
            "description": None,
            "notes": None,
            "items": [{"part_id": 1, "quantity": 1}],
        },
    )
    if unauthenticated.status_code not in (401, 403):
        fail(
            "Reserved Project update should require authentication, got "
            f"{unauthenticated.status_code}"
        )

    openapi = client.get("/openapi.json")
    movement_properties = (
        openapi.json()
        .get("components", {})
        .get("schemas", {})
        .get("StockMovementResponse", {})
        .get("properties", {})
    )
    required_snapshot_fields = {
        "reserved_quantity_before",
        "reserved_quantity_after",
        "available_quantity_before",
        "available_quantity_after",
    }
    if (
        openapi.status_code != 200
        or not required_snapshot_fields.issubset(movement_properties)
    ):
        fail(
            "Stock movement OpenAPI snapshots are incomplete: "
            f"{sorted(movement_properties)}"
        )

    suffix = uuid4().hex[:12]
    project_id: int | None = None
    reservation_id: int | None = None
    part_ids: list[int] = []

    def cleanup() -> None:
        cleanup_db = SessionLocal()
        try:
            if project_id is not None:
                cleanup_db.execute(
                    delete(AuditLog).where(
                        (
                            (AuditLog.entity_type == "project")
                            & (AuditLog.entity_id == project_id)
                        )
                        | (
                            (AuditLog.entity_type == "reservation")
                            & (AuditLog.entity_id == reservation_id)
                        )
                    )
                )
            if reservation_id is not None:
                cleanup_db.execute(
                    delete(StockMovement).where(
                        StockMovement.reservation_id == reservation_id
                    )
                )
                cleanup_db.execute(
                    delete(ReservationItem).where(
                        ReservationItem.reservation_id == reservation_id
                    )
                )
                cleanup_db.execute(
                    delete(Reservation).where(
                        Reservation.id == reservation_id
                    )
                )
            if project_id is not None:
                cleanup_db.execute(
                    delete(ProjectItem).where(
                        ProjectItem.project_id == project_id
                    )
                )
                cleanup_db.execute(
                    delete(Project).where(Project.id == project_id)
                )
            if part_ids:
                cleanup_db.execute(
                    delete(StockMovement).where(
                        StockMovement.part_id.in_(part_ids)
                    )
                )
                cleanup_db.execute(
                    delete(Part).where(Part.id.in_(part_ids))
                )
            cleanup_db.commit()
        finally:
            cleanup_db.close()

    cleanup()
    db = SessionLocal()
    try:
        part_type_id = db.execute(
            select(PartType.id)
            .where(PartType.is_active.is_(True))
            .order_by(PartType.id.asc())
            .limit(1)
        ).scalar_one_or_none()
        if part_type_id is None:
            fail("Reserved Project update smoke requires an active part type")

        parts = [
            Part(
                part_type_id=part_type_id,
                part_number=f"PP400-EDIT-{index}-{suffix}",
                name=f"Reserved Project edit part {index} {suffix}",
                total_quantity=total,
                reserved_quantity=0,
                unit_price=Decimal(price),
                is_deleted=False,
            )
            for index, total, price in (
                (1, 10, "2.0000"),
                (2, 8, "3.0000"),
                (3, 12, "4.0000"),
            )
        ]
        project = Project(
            name=f"Reserved Project edit {suffix}",
            description="Before reserved edit",
            status=PROJECT_STATUS_DRAFT,
            notes="Before notes",
            created_by="manual",
            estimated_total_value=Decimal("13.0000"),
            currency_snapshot="USD",
        )
        db.add_all([*parts, project])
        db.flush()
        part_ids.extend(part.id for part in parts)
        project_id = project.id
        db.add_all(
            [
                ProjectItem(
                    project_id=project.id,
                    part_id=parts[0].id,
                    quantity=2,
                    unit_price_snapshot=parts[0].unit_price,
                    currency_snapshot="USD",
                    note="Keep and increase",
                ),
                ProjectItem(
                    project_id=project.id,
                    part_id=parts[1].id,
                    quantity=3,
                    unit_price_snapshot=parts[1].unit_price,
                    currency_snapshot="USD",
                    note="Keep and decrease",
                ),
            ]
        )
        db.commit()

        reserve_project(
            db,
            project.id,
            actor_user_id=None,
            commit=True,
        )
        reservation = db.execute(
            select(Reservation).where(
                Reservation.project_id == project.id
            )
        ).scalar_one()
        reservation_id = reservation.id

        payload = ProjectUpdateRequest(
            name=f"Reserved Project updated {suffix}",
            description="After reserved edit",
            notes="After notes",
            items=[
                {
                    "part_id": parts[0].id,
                    "quantity": 4,
                    "note": "Keep and increase",
                },
                {
                    "part_id": parts[1].id,
                    "quantity": 1,
                    "note": "Keep and decrease",
                },
                {
                    "part_id": parts[2].id,
                    "quantity": 5,
                    "note": "New reserved part",
                },
            ],
        )
        response = update_project(
            db,
            project.id,
            payload,
            actor_user_id=None,
            commit=True,
        )
        db.refresh(project)
        db.refresh(reservation)
        for part in parts:
            db.refresh(part)

        if (
            response.status != PROJECT_STATUS_RESERVED
            or project.status != PROJECT_STATUS_RESERVED
            or reservation.status != RESERVATION_STATUS_ACTIVE
            or project.name != payload.name
            or reservation.label != payload.name
            or project.notes != payload.notes
            or reservation.notes != payload.notes
        ):
            fail(
                "Reserved Project metadata or lifecycle synchronization is "
                f"incorrect: {response}"
            )

        expected_stock = {
            parts[0].id: (10, 4, 6),
            parts[1].id: (8, 1, 7),
            parts[2].id: (12, 5, 7),
        }
        for part in parts:
            actual = (
                int(part.total_quantity),
                int(part.reserved_quantity),
                int(part.total_quantity) - int(part.reserved_quantity),
            )
            if actual != expected_stock[part.id]:
                fail(
                    f"Reserved Project edit stock is incorrect for "
                    f"{part.id}: {actual}"
                )

        project_items = {
            int(item.part_id): (int(item.quantity), item.note)
            for item in db.execute(
                select(ProjectItem).where(
                    ProjectItem.project_id == project.id
                )
            ).scalars()
            if item.part_id is not None
        }
        reservation_items = {
            int(item.part_id): (int(item.quantity), item.note)
            for item in db.execute(
                select(ReservationItem).where(
                    ReservationItem.reservation_id == reservation.id
                )
            ).scalars()
            if item.part_id is not None
        }
        expected_items = {
            parts[0].id: (4, "Keep and increase"),
            parts[1].id: (1, "Keep and decrease"),
            parts[2].id: (5, "New reserved part"),
        }
        if (
            project_items != expected_items
            or reservation_items != expected_items
        ):
            fail(
                "Reserved Project and Reservation items diverged: "
                f"{project_items}, {reservation_items}"
            )

        edit_movements = list(
            db.execute(
                select(StockMovement)
                .where(StockMovement.reservation_id == reservation.id)
                .order_by(StockMovement.id.asc())
            ).scalars()
        )[-3:]
        expected_movements = {
            parts[0].id: (
                MOVEMENT_TYPE_RESERVE,
                10,
                10,
                2,
                4,
                8,
                6,
            ),
            parts[1].id: (
                MOVEMENT_TYPE_RELEASE,
                8,
                8,
                3,
                1,
                5,
                7,
            ),
            parts[2].id: (
                MOVEMENT_TYPE_RESERVE,
                12,
                12,
                0,
                5,
                12,
                7,
            ),
        }
        if len(edit_movements) != 3:
            fail(
                "Reserved Project edit movement count is incorrect: "
                f"{len(edit_movements)}"
            )
        for movement in edit_movements:
            actual = (
                movement.movement_type,
                int(movement.quantity_before),
                int(movement.quantity_after),
                int(movement.reserved_quantity_before),
                int(movement.reserved_quantity_after),
                int(movement.available_quantity_before),
                int(movement.available_quantity_after),
            )
            if actual != expected_movements[int(movement.part_id)]:
                fail(
                    "Reserved Project edit movement snapshots are "
                    f"incorrect: {actual}"
                )

        movement_response = list_part_movements(
            db,
            parts[0].id,
            limit=10,
        ).movements[0]
        if (
            movement_response.reserved_quantity_before != 2
            or movement_response.reserved_quantity_after != 4
            or movement_response.available_quantity_before != 8
            or movement_response.available_quantity_after != 6
        ):
            fail(
                "Part movement API did not expose reservation snapshots: "
                f"{movement_response}"
            )

        project_audit_count = int(
            db.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.event_type == "project.updated",
                    AuditLog.entity_type == "project",
                    AuditLog.entity_id == project.id,
                )
            ).scalar_one()
        )
        reservation_audit_count = int(
            db.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.event_type == "reservation.updated",
                    AuditLog.entity_type == "reservation",
                    AuditLog.entity_id == reservation.id,
                )
            ).scalar_one()
        )
        if project_audit_count != 1 or reservation_audit_count != 1:
            fail(
                "Reserved Project edit did not create exactly one paired "
                "Project and Reservation audit"
            )

        movement_count_before_noop = int(
            db.execute(
                select(func.count())
                .select_from(StockMovement)
                .where(StockMovement.reservation_id == reservation.id)
            ).scalar_one()
        )
        update_project(
            db,
            project.id,
            payload,
            actor_user_id=None,
            commit=True,
        )
        movement_count_after_noop = int(
            db.execute(
                select(func.count())
                .select_from(StockMovement)
                .where(StockMovement.reservation_id == reservation.id)
            ).scalar_one()
        )
        if movement_count_after_noop != movement_count_before_noop:
            fail("No-op Reserved Project edit created a stock movement")

        conflict_payload = ProjectUpdateRequest(
            name=payload.name,
            description=payload.description,
            notes=payload.notes,
            items=[
                {
                    "part_id": parts[0].id,
                    "quantity": 999,
                    "note": "Insufficient stock",
                },
                {
                    "part_id": parts[1].id,
                    "quantity": 1,
                    "note": "Keep and decrease",
                },
                {
                    "part_id": parts[2].id,
                    "quantity": 5,
                    "note": "New reserved part",
                },
            ],
        )
        try:
            update_project(
                db,
                project.id,
                conflict_payload,
                actor_user_id=None,
                commit=True,
            )
        except ProjectConflictError:
            pass
        else:
            fail("Reserved Project edit accepted insufficient stock")

        persisted = db.execute(
            select(Project).where(Project.id == project.id)
        ).scalar_one()
        persisted_reservation = db.execute(
            select(Reservation).where(
                Reservation.id == reservation.id
            )
        ).scalar_one()
        persisted_parts = {
            part.id: (
                int(part.total_quantity),
                int(part.reserved_quantity),
            )
            for part in db.execute(
                select(Part).where(Part.id.in_(part_ids))
            ).scalars()
        }
        if (
            persisted.status != PROJECT_STATUS_RESERVED
            or persisted_reservation.status != RESERVATION_STATUS_ACTIVE
            or persisted_parts
            != {
                parts[0].id: (10, 4),
                parts[1].id: (8, 1),
                parts[2].id: (12, 5),
            }
        ):
            fail(
                "Failed Reserved Project edit did not roll back cleanly: "
                f"{persisted.status}, {persisted_reservation.status}, "
                f"{persisted_parts}"
            )
    finally:
        db.close()
        cleanup()

    ok(
        "Reserved Projects edit atomically through their linked "
        "Reservations, synchronise metadata and item plans, reserve and "
        "release only quantity deltas, expose physical/reserved/available "
        "movement snapshots, reject insufficient stock, preserve no-op "
        "semantics, and roll back conflicts"
    )



# PARTPILOT:LINKED_RESERVATION_EDIT_TERMINAL_SMOKE:V402
def check_linked_reservation_edit_and_terminal_delta() -> None:
    from decimal import Decimal
    from uuid import uuid4

    from sqlalchemy import select

    from app.db.constants import (
        MOVEMENT_TYPE_CONSUME,
        MOVEMENT_TYPE_RELEASE,
        PROJECT_STATUS_CANCELLED,
        PROJECT_STATUS_CONSUMED,
        PROJECT_STATUS_DRAFT,
        PROJECT_STATUS_RESERVED,
        RESERVATION_STATUS_ACTIVE,
        RESERVATION_STATUS_CANCELLED,
        RESERVATION_STATUS_CONSUMED,
    )
    from app.db.session import SessionLocal
    from app.models import (
        AuditLog,
        Part,
        PartType,
        Project,
        ProjectItem,
        Reservation,
        ReservationItem,
        StockMovement,
    )
    from app.schemas.reservations import ReservationUpdateRequest
    from app.services.projects import (
        cancel_project,
        consume_project,
        reserve_project,
    )
    from app.services.reservations import update_reservation

    suffix = uuid4().hex[:12]
    db = SessionLocal()
    try:
        part_type_id = db.execute(
            select(PartType.id)
            .where(PartType.is_active.is_(True))
            .order_by(PartType.id.asc())
            .limit(1)
        ).scalar_one_or_none()
        if part_type_id is None:
            fail(
                "Linked Reservation edit smoke requires an active part "
                "type"
            )

        for case_index, terminal_action in enumerate(
            ("cancel", "consume"),
            start=1,
        ):
            parts = [
                Part(
                    part_type_id=part_type_id,
                    part_number=(
                        f"PP402-{terminal_action.upper()}-"
                        f"{part_index}-{suffix}"
                    ),
                    name=(
                        f"Linked edit {terminal_action} part "
                        f"{part_index} {suffix}"
                    ),
                    total_quantity=total_quantity,
                    reserved_quantity=0,
                    unit_price=Decimal(unit_price),
                    is_deleted=False,
                )
                for part_index, total_quantity, unit_price in (
                    (1, 10, "2.0000"),
                    (2, 12, "3.0000"),
                    (3, 15, "4.0000"),
                )
            ]
            project = Project(
                name=(
                    f"Linked edit {terminal_action} "
                    f"{case_index} {suffix}"
                ),
                description="Description must remain Project-owned",
                status=PROJECT_STATUS_DRAFT,
                notes="Before linked Reservation edit",
                created_by="manual",
                estimated_total_value=Decimal("17.0000"),
                currency_snapshot="USD",
            )
            db.add_all([*parts, project])
            db.flush()
            db.add_all(
                [
                    ProjectItem(
                        project_id=project.id,
                        part_id=parts[0].id,
                        quantity=4,
                        unit_price_snapshot=parts[0].unit_price,
                        currency_snapshot="USD",
                        note="Decrease through Reservation",
                    ),
                    ProjectItem(
                        project_id=project.id,
                        part_id=parts[1].id,
                        quantity=3,
                        unit_price_snapshot=parts[1].unit_price,
                        currency_snapshot="USD",
                        note="Increase through Reservation",
                    ),
                ]
            )
            db.flush()

            reserve_project(
                db,
                project.id,
                actor_user_id=None,
                commit=False,
            )
            db.flush()
            reservation = db.execute(
                select(Reservation).where(
                    Reservation.project_id == project.id
                )
            ).scalar_one()

            updated_label = (
                f"Linked Reservation edited {terminal_action} "
                f"{suffix}"
            )
            payload = ReservationUpdateRequest(
                label=updated_label,
                notes="Updated from Reservations and synced to Project",
                expiry_at=None,
                items=[
                    {
                        "part_id": parts[0].id,
                        "quantity": 2,
                        "note": "Decrease through Reservation",
                    },
                    {
                        "part_id": parts[1].id,
                        "quantity": 4,
                        "note": "Increase through Reservation",
                    },
                    {
                        "part_id": parts[2].id,
                        "quantity": 5,
                        "note": "Added through Reservation",
                    },
                ],
            )
            updated = update_reservation(
                db,
                reservation.id,
                payload,
                actor_user_id=None,
                commit=False,
            )
            db.flush()
            db.refresh(project)
            db.refresh(reservation)
            for part in parts:
                db.refresh(part)

            if (
                updated.status != RESERVATION_STATUS_ACTIVE
                or reservation.status != RESERVATION_STATUS_ACTIVE
                or project.status != PROJECT_STATUS_RESERVED
                or project.name != updated_label
                or reservation.label != updated_label
                or project.notes != payload.notes
                or reservation.notes != payload.notes
                or project.description
                != "Description must remain Project-owned"
            ):
                fail(
                    "Direct linked Reservation edit did not synchronise "
                    f"Project metadata: {project.status}, "
                    f"{reservation.status}, {project.name}, "
                    f"{reservation.label}"
                )

            project_items = {
                int(item.part_id): (
                    int(item.quantity),
                    item.note,
                )
                for item in db.execute(
                    select(ProjectItem).where(
                        ProjectItem.project_id == project.id
                    )
                ).scalars()
                if item.part_id is not None
            }
            reservation_items = {
                int(item.part_id): (
                    int(item.quantity),
                    item.note,
                )
                for item in db.execute(
                    select(ReservationItem).where(
                        ReservationItem.reservation_id
                        == reservation.id
                    )
                ).scalars()
                if item.part_id is not None
            }
            expected_items = {
                parts[0].id: (
                    2,
                    "Decrease through Reservation",
                ),
                parts[1].id: (
                    4,
                    "Increase through Reservation",
                ),
                parts[2].id: (
                    5,
                    "Added through Reservation",
                ),
            }
            if (
                project_items != expected_items
                or reservation_items != expected_items
            ):
                fail(
                    "Direct linked Reservation edit left Project and "
                    f"Reservation plans out of sync: {project_items}, "
                    f"{reservation_items}"
                )

            expected_before_terminal = {
                parts[0].id: (10, 2, 8),
                parts[1].id: (12, 4, 8),
                parts[2].id: (15, 5, 10),
            }
            for part in parts:
                actual = (
                    int(part.total_quantity),
                    int(part.reserved_quantity),
                    int(part.total_quantity)
                    - int(part.reserved_quantity),
                )
                if actual != expected_before_terminal[part.id]:
                    fail(
                        "Direct linked Reservation edit stock delta is "
                        f"incorrect for part {part.id}: {actual}"
                    )

            edit_release_ids = set(
                db.execute(
                    select(StockMovement.id).where(
                        StockMovement.reservation_id == reservation.id,
                        StockMovement.movement_type
                        == MOVEMENT_TYPE_RELEASE,
                    )
                ).scalars()
            )
            if len(edit_release_ids) != 1:
                fail(
                    "Linked Reservation edit should create exactly one "
                    f"historical release movement, got "
                    f"{edit_release_ids}"
                )

            project_update_audit = db.execute(
                select(AuditLog).where(
                    AuditLog.event_type == "project.updated",
                    AuditLog.entity_type == "project",
                    AuditLog.entity_id == project.id,
                )
            ).scalar_one_or_none()
            reservation_update_audit = db.execute(
                select(AuditLog).where(
                    AuditLog.event_type == "reservation.updated",
                    AuditLog.entity_type == "reservation",
                    AuditLog.entity_id == reservation.id,
                )
            ).scalar_one_or_none()
            if (
                project_update_audit is None
                or reservation_update_audit is None
                or project_update_audit.metadata_json.get("origin")
                != "reservation.edit"
                or project_update_audit.metadata_json.get(
                    "reservation_id"
                )
                != reservation.id
            ):
                fail(
                    "Direct linked Reservation edit did not create paired "
                    "Project and Reservation audits"
                )

            if terminal_action == "cancel":
                result = cancel_project(
                    db,
                    project.id,
                    actor_user_id=None,
                    commit=False,
                )
                expected_project_status = PROJECT_STATUS_CANCELLED
                expected_reservation_status = (
                    RESERVATION_STATUS_CANCELLED
                )
                terminal_event = "project.cancelled"
                terminal_movement_type = MOVEMENT_TYPE_RELEASE
                expected_stock = {
                    parts[0].id: (10, 0, 10),
                    parts[1].id: (12, 0, 12),
                    parts[2].id: (15, 0, 15),
                }
            else:
                result = consume_project(
                    db,
                    project.id,
                    actor_user_id=None,
                    commit=False,
                )
                expected_project_status = PROJECT_STATUS_CONSUMED
                expected_reservation_status = (
                    RESERVATION_STATUS_CONSUMED
                )
                terminal_event = "project.consumed"
                terminal_movement_type = MOVEMENT_TYPE_CONSUME
                expected_stock = {
                    parts[0].id: (8, 0, 8),
                    parts[1].id: (8, 0, 8),
                    parts[2].id: (10, 0, 10),
                }

            db.flush()
            db.refresh(project)
            db.refresh(reservation)
            for part in parts:
                db.refresh(part)

            if (
                result.status != expected_project_status
                or project.status != expected_project_status
                or reservation.status
                != expected_reservation_status
            ):
                fail(
                    f"Project {terminal_action} after linked edit did not "
                    f"complete: {result.status}, {project.status}, "
                    f"{reservation.status}"
                )

            terminal_audit = db.execute(
                select(AuditLog).where(
                    AuditLog.event_type == terminal_event,
                    AuditLog.entity_type == "project",
                    AuditLog.entity_id == project.id,
                )
            ).scalar_one_or_none()
            if terminal_audit is None:
                fail(
                    f"Project {terminal_action} after linked edit did not "
                    "create its Project terminal audit"
                )
            terminal_movement_ids = set(
                terminal_audit.after_json.get(
                    "stock_movement_ids",
                    [],
                )
            )
            if len(terminal_movement_ids) != 3:
                fail(
                    f"Project {terminal_action} terminal audit contains "
                    f"the wrong movement set: {terminal_movement_ids}"
                )
            if terminal_movement_ids & edit_release_ids:
                fail(
                    f"Project {terminal_action} reused historical edit "
                    f"release movements: {terminal_movement_ids}, "
                    f"{edit_release_ids}"
                )

            terminal_movements = list(
                db.execute(
                    select(StockMovement).where(
                        StockMovement.id.in_(
                            terminal_movement_ids
                        )
                    )
                ).scalars()
            )
            if (
                len(terminal_movements) != 3
                or {
                    movement.movement_type
                    for movement in terminal_movements
                }
                != {terminal_movement_type}
            ):
                fail(
                    f"Project {terminal_action} terminal movements are "
                    f"incorrect: {terminal_movements}"
                )

            for part in parts:
                actual = (
                    int(part.total_quantity),
                    int(part.reserved_quantity),
                    int(part.total_quantity)
                    - int(part.reserved_quantity),
                )
                if actual != expected_stock[part.id]:
                    fail(
                        f"Project {terminal_action} after linked edit "
                        f"stock is incorrect for part {part.id}: "
                        f"{actual}"
                    )

        db.rollback()
    finally:
        db.rollback()
        db.close()

    ok(
        "Project-linked Reservations edit from Reservations with atomic "
        "two-way metadata, item-plan, value, stock-delta, and audit "
        "synchronisation; subsequent Project cancellation and consumption "
        "count only newly-created terminal movements and ignore historical "
        "edit releases"
    )



# PARTPILOT:SYSTEM_HISTORY_SMOKE:V406
def check_system_history_api() -> None:
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal
    from uuid import uuid4

    from fastapi.testclient import TestClient
    from sqlalchemy import delete, select

    from app.db.session import SessionLocal
    from app.main import app
    from app.models import (
        AuditLog,
        Part,
        PartType,
        Project,
        Reservation,
        StockMovement,
        User,
        UserSession,
    )
    from app.services.auth import create_session, create_user
    from app.services.history import (
        HistoryValidationError,
        list_history,
        list_history_filter_options,
    )

    suffix = uuid4().hex[:12]
    username = f"history_{suffix}"
    password = "HistorySmokePass123!"
    part_number = f"PP406-LITERAL%_-{suffix}"
    audit_event = f"project.history_smoke_{suffix}"
    secondary_event = f"part.history_smoke_{suffix}"

    user_id: int | None = None
    part_id: int | None = None
    project_id: int | None = None
    reservation_id: int | None = None
    movement_id: int | None = None
    audit_ids: list[int] = []

    def cleanup() -> None:
        cleanup_db = SessionLocal()
        try:
            if audit_ids:
                cleanup_db.execute(
                    delete(AuditLog).where(
                        AuditLog.id.in_(audit_ids)
                    )
                )
            if movement_id is not None:
                cleanup_db.execute(
                    delete(StockMovement).where(
                        StockMovement.id == movement_id
                    )
                )
            if reservation_id is not None:
                cleanup_db.execute(
                    delete(Reservation).where(
                        Reservation.id == reservation_id
                    )
                )
            if project_id is not None:
                cleanup_db.execute(
                    delete(Project).where(
                        Project.id == project_id
                    )
                )
            if part_id is not None:
                cleanup_db.execute(
                    delete(Part).where(Part.id == part_id)
                )
            if user_id is not None:
                cleanup_db.execute(
                    delete(UserSession).where(
                        UserSession.user_id == user_id
                    )
                )
                cleanup_db.execute(
                    delete(User).where(User.id == user_id)
                )
            cleanup_db.commit()
        finally:
            cleanup_db.close()

    cleanup()
    client = TestClient(app)

    for path in (
        "/api/history",
        "/api/history/filter-options",
    ):
        response = client.get(path)
        if response.status_code not in (401, 403):
            fail(
                f"Unauthenticated {path} should return 401/403, got "
                f"{response.status_code}: {response.text}"
            )

    openapi = client.get("/openapi.json")
    paths = openapi.json().get("paths", {})
    if (
        openapi.status_code != 200
        or set(paths.get("/api/history", {})) != {"get"}
        or set(
            paths.get(
                "/api/history/filter-options",
                {},
            )
        )
        != {"get"}
    ):
        fail(
            "System History OpenAPI contract is incorrect: "
            f"{openapi.status_code}, "
            f"{paths.get('/api/history')}, "
            f"{paths.get('/api/history/filter-options')}"
        )

    db = SessionLocal()
    try:
        part_type_id = db.execute(
            select(PartType.id)
            .where(PartType.is_active.is_(True))
            .order_by(PartType.id.asc())
            .limit(1)
        ).scalar_one_or_none()
        if part_type_id is None:
            fail(
                "System History smoke requires an active part type"
            )

        user = create_user(
            db,
            username=username,
            display_name="History Smoke User",
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
            part_type_id=part_type_id,
            part_number=part_number,
            name=f"History literal fixture {suffix}",
            total_quantity=9,
            reserved_quantity=2,
            unit_price=Decimal("4.2500"),
            is_deleted=False,
        )
        project = Project(
            name=f"History Project {suffix}",
            description="System History API smoke fixture",
            status="reserved",
            notes="History project notes",
            created_by="manual",
            estimated_total_value=Decimal("8.5000"),
            currency_snapshot="USD",
        )
        db.add_all([part, project])
        db.flush()
        part_id = part.id
        project_id = project.id

        reservation = Reservation(
            project_id=project.id,
            label=f"History Reservation {suffix}",
            status="active",
            notes="History reservation notes",
            created_by="manual",
            estimated_reserved_value=Decimal("8.5000"),
            currency_snapshot="USD",
        )
        db.add(reservation)
        db.flush()
        reservation_id = reservation.id

        base_time = datetime.now(timezone.utc) - timedelta(
            minutes=5
        )
        primary_audit = AuditLog(
            created_at=base_time,
            event_type=audit_event,
            entity_type="project",
            entity_id=project.id,
            actor_type="user",
            actor_user_id=user.id,
            summary=f"History primary {suffix}",
            before_json={"status": "draft"},
            after_json={
                "status": "reserved",
                "reservation_id": reservation.id,
            },
            metadata_json={
                "source": "manual",
                "reservation_id": reservation.id,
            },
        )
        secondary_audit = AuditLog(
            created_at=base_time + timedelta(seconds=1),
            event_type=secondary_event,
            entity_type="part",
            entity_id=part.id,
            actor_type="system",
            actor_user_id=None,
            summary=f"History secondary {suffix}",
            before_json={"quantity": 9},
            after_json={"quantity": 9},
            metadata_json={"source": "system"},
        )
        movement = StockMovement(
            part_id=part.id,
            reservation_id=reservation.id,
            movement_type="reserve",
            quantity_delta=0,
            quantity_before=9,
            quantity_after=9,
            reserved_quantity_before=0,
            reserved_quantity_after=2,
            available_quantity_before=9,
            available_quantity_after=7,
            unit_price_snapshot=Decimal("4.2500"),
            currency_snapshot="USD",
            reason=f"Literal%_Token {suffix}",
            note="History movement note",
            source="manual",
            actor_user_id=user.id,
            created_at=base_time + timedelta(seconds=2),
            updated_at=base_time + timedelta(seconds=2),
        )
        db.add_all([primary_audit, secondary_audit, movement])
        db.commit()
        for record in (
            primary_audit,
            secondary_audit,
            movement,
        ):
            db.refresh(record)
        audit_ids.extend(
            [primary_audit.id, secondary_audit.id]
        )
        movement_id = movement.id

        combined = list_history(
            db,
            query=suffix,
            limit=10,
            offset=0,
        )
        if (
            combined.total != 3
            or [entry.key for entry in combined.entries]
            != [
                f"movement:{movement.id}",
                f"audit:{secondary_audit.id}",
                f"audit:{primary_audit.id}",
            ]
        ):
            fail(
                "System History combined ordering is incorrect: "
                f"{combined}"
            )

        movement_entry = combined.entries[0]
        if (
            movement_entry.kind != "stock_movement"
            or movement_entry.event_type != "stock.reserve"
            or movement_entry.entity_type != "part"
            or movement_entry.entity_id != part.id
            or movement_entry.entity_label != part_number
            or movement_entry.actor_display_name
            != "History Smoke User"
            or movement_entry.reservation_id != reservation.id
            or movement_entry.reservation_label
            != reservation.label
            or movement_entry.project_id != project.id
            or movement_entry.project_label != project.name
            or movement_entry.quantity != 2
            or movement_entry.quantity_before != 9
            or movement_entry.quantity_after != 9
            or movement_entry.reserved_quantity_before != 0
            or movement_entry.reserved_quantity_after != 2
            or movement_entry.available_quantity_before != 9
            or movement_entry.available_quantity_after != 7
        ):
            fail(
                "System History movement hydration is incorrect: "
                f"{movement_entry}"
            )

        project_entry = combined.entries[2]
        if (
            project_entry.kind != "audit"
            or project_entry.entity_type != "project"
            or project_entry.entity_id != project.id
            or project_entry.entity_label != project.name
            or project_entry.actor_display_name
            != "History Smoke User"
            or project_entry.reservation_id != reservation.id
            or project_entry.project_id != project.id
            or project_entry.before_json
            != {"status": "draft"}
            or project_entry.after_json.get("status")
            != "reserved"
        ):
            fail(
                "System History audit hydration is incorrect: "
                f"{project_entry}"
            )

        checks = (
            (
                list_history(
                    db,
                    kind="audit",
                    query=suffix,
                    limit=10,
                ),
                2,
                {"audit"},
            ),
            (
                list_history(
                    db,
                    kind="stock_movement",
                    query=suffix,
                    limit=10,
                ),
                1,
                {"stock_movement"},
            ),
            (
                list_history(
                    db,
                    entity_type="project",
                    query=suffix,
                    limit=10,
                ),
                1,
                {"audit"},
            ),
            (
                list_history(
                    db,
                    event_type=audit_event,
                    limit=10,
                ),
                1,
                {"audit"},
            ),
            (
                list_history(
                    db,
                    movement_type="reserve",
                    query=suffix,
                    limit=10,
                ),
                1,
                {"stock_movement"},
            ),
            (
                list_history(
                    db,
                    actor_type="system",
                    query=suffix,
                    limit=10,
                ),
                1,
                {"audit"},
            ),
            (
                list_history(
                    db,
                    actor_user_id=user.id,
                    query=suffix,
                    limit=10,
                ),
                2,
                {"audit", "stock_movement"},
            ),
        )
        for response, expected_total, expected_kinds in checks:
            if (
                response.total != expected_total
                or {entry.kind for entry in response.entries}
                != expected_kinds
            ):
                fail(
                    "System History filter result is incorrect: "
                    f"{response}, expected total {expected_total} "
                    f"and kinds {expected_kinds}"
                )

        literal = list_history(
            db,
            query="Literal%_Token",
            limit=10,
        )
        if (
            literal.total != 1
            or literal.entries[0].key
            != f"movement:{movement.id}"
        ):
            fail(
                "System History search did not treat SQL wildcard "
                f"characters literally: {literal}"
            )

        paged = list_history(
            db,
            query=suffix,
            limit=1,
            offset=1,
        )
        if (
            paged.total != 3
            or len(paged.entries) != 1
            or paged.entries[0].key
            != f"audit:{secondary_audit.id}"
        ):
            fail(
                "System History pagination is incorrect: "
                f"{paged}"
            )

        bounded = list_history(
            db,
            query=suffix,
            from_time=base_time + timedelta(
                seconds=0.5
            ),
            to_time=base_time + timedelta(
                seconds=1.5
            ),
            limit=10,
        )
        if (
            bounded.total != 1
            or bounded.entries[0].key
            != f"audit:{secondary_audit.id}"
        ):
            fail(
                "System History date filtering is incorrect: "
                f"{bounded}"
            )

        try:
            list_history(
                db,
                from_time=base_time + timedelta(days=1),
                to_time=base_time,
            )
        except HistoryValidationError:
            pass
        else:
            fail(
                "System History accepted an inverted date range"
            )

        options = list_history_filter_options(db)
        event_options = {
            option.value: option.count
            for option in options.event_types
        }
        actor_options = {
            option.user_id: option
            for option in options.actors
        }
        if (
            event_options.get(audit_event, 0) != 1
            or event_options.get("stock.reserve", 0) < 1
            or user.id not in actor_options
            or actor_options[user.id].display_name
            != "History Smoke User"
            or options.earliest_at is None
            or options.latest_at is None
            or options.earliest_at > options.latest_at
        ):
            fail(
                "System History filter options are incorrect: "
                f"{options}"
            )

        headers = {
            "Authorization": f"Bearer {session_token.token}"
        }
        api_response = client.get(
            "/api/history",
            params={
                "q": suffix,
                "limit": 2,
                "offset": 0,
            },
            headers=headers,
        )
        if (
            api_response.status_code != 200
            or api_response.json().get("total") != 3
            or len(api_response.json().get("entries", [])) != 2
        ):
            fail(
                "Authenticated System History API response is "
                f"incorrect: {api_response.status_code}, "
                f"{api_response.text}"
            )

        options_response = client.get(
            "/api/history/filter-options",
            headers=headers,
        )
        if (
            options_response.status_code != 200
            or not options_response.json().get("event_types")
            or not options_response.json().get("kinds")
        ):
            fail(
                "Authenticated History filter-options response is "
                f"incorrect: {options_response.status_code}, "
                f"{options_response.text}"
            )

        invalid_range = client.get(
            "/api/history",
            params={
                "from": (
                    base_time + timedelta(days=1)
                ).isoformat(),
                "to": base_time.isoformat(),
            },
            headers=headers,
        )
        if invalid_range.status_code != 422:
            fail(
                "History API accepted an inverted date range: "
                f"{invalid_range.status_code}, "
                f"{invalid_range.text}"
            )
    finally:
        db.close()
        cleanup()

    ok(
        "Protected system-wide History merges audit and stock-movement "
        "events with deterministic pagination, entity/actor/relationship "
        "hydration, exact filters, literal search, date ranges, counted "
        "facets, OpenAPI coverage, and inventory-safe fixture cleanup"
    )



# PARTPILOT:APPEARANCE_SETTINGS_SMOKE:V411
def check_appearance_settings_api() -> None:
    import json as json_module
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app
    from app.models import AppSetting
    from app.schemas.app_settings import (
        AppearanceSettingsUpdateRequest,
    )
    from app.services import app_settings as app_settings_service

    theme_key = "appearance.theme"
    availability_key = "appearance.light_theme_available"
    setting_keys = (theme_key, availability_key)
    suffix = uuid4().hex[:10]
    username = f"smoke_appearance_{suffix}"
    password = "appearance-settings-smoke-password"
    user_id: int | None = None

    with db_session() as db:
        original_settings: dict[
            str,
            tuple[object, str | None] | None,
        ] = {}
        for key in setting_keys:
            row = (
                db.query(AppSetting)
                .filter(AppSetting.key == key)
                .one_or_none()
            )
            original_settings[key] = (
                None
                if row is None
                else (row.value_json, row.value_text)
            )

    def restore_settings(db) -> None:
        for key in setting_keys:
            original = original_settings[key]
            row = (
                db.query(AppSetting)
                .filter(AppSetting.key == key)
                .one_or_none()
            )
            if original is None:
                if row is not None:
                    db.delete(row)
            elif row is None:
                db.add(
                    AppSetting(
                        key=key,
                        value_json=original[0],
                        value_text=original[1],
                    )
                )
            else:
                row.value_json = original[0]
                row.value_text = original[1]

    def cleanup() -> None:
        with db_session() as db:
            if user_id is not None:
                db.execute(
                    text(
                        "delete from audit_log "
                        "where event_type = "
                        "'settings.appearance_updated' "
                        "and actor_user_id = :actor_user_id"
                    ),
                    {"actor_user_id": user_id},
                )
            db.execute(
                text(
                    "delete from sessions where user_id in "
                    "(select id from users "
                    "where username = :username)"
                ),
                {"username": username},
            )
            db.execute(
                text(
                    "delete from users where username = :username"
                ),
                {"username": username},
            )
            restore_settings(db)
            db.commit()

    client = TestClient(fastapi_app)

    try:
        unauthenticated_get = client.get(
            "/api/settings/appearance"
        )
        if unauthenticated_get.status_code not in {401, 403}:
            fail(
                "GET /api/settings/appearance should require "
                "authentication, got "
                f"{unauthenticated_get.status_code}: "
                f"{unauthenticated_get.text}"
            )
        unauthenticated_patch = client.patch(
            "/api/settings/appearance",
            json={"theme": "light"},
        )
        if unauthenticated_patch.status_code not in {401, 403}:
            fail(
                "PATCH /api/settings/appearance should require "
                "authentication, got "
                f"{unauthenticated_patch.status_code}: "
                f"{unauthenticated_patch.text}"
            )

        openapi = client.get("/openapi.json")
        openapi_methods = (
            openapi.json()
            .get("paths", {})
            .get("/api/settings/appearance", {})
        )
        if (
            openapi.status_code != 200
            or set(openapi_methods) != {"get", "patch"}
        ):
            fail(
                "Appearance settings GET/PATCH routes are missing "
                "from OpenAPI: "
                f"{openapi.status_code} {openapi_methods}"
            )

        schemas = (
            openapi.json()
            .get("components", {})
            .get("schemas", {})
        )
        for schema_name in (
            "AppearanceSettingsResponse",
            "AppearanceSettingsUpdateRequest",
        ):
            if schema_name not in schemas:
                fail(
                    "Appearance OpenAPI schema is missing: "
                    f"{schema_name}"
                )

        with db_session() as db:
            set_app_setting(
                db,
                theme_key,
                "dark",
                text_value="dark",
                commit=False,
            )
            set_app_setting(
                db,
                availability_key,
                True,
                text_value=None,
                commit=False,
            )
            user = create_user(
                db,
                username=username,
                display_name="Appearance Settings Smoke User",
                password=password,
                commit=False,
            )
            db.commit()
            db.refresh(user)
            user_id = user.id
            session_token = create_session(
                db,
                user=user,
                commit=True,
            )

        headers = {
            "Authorization": f"Bearer {session_token.token}",
        }

        seeded = client.get(
            "/api/settings/appearance",
            headers=headers,
        )
        if (
            seeded.status_code != 200
            or seeded.json()
            != {
                "theme": "dark",
                "light_theme_available": True,
            }
        ):
            fail(
                "Seeded appearance settings should read as "
                f"dark/available: {seeded.status_code} "
                f"{seeded.text}"
            )

        with db_session() as db:
            set_app_setting(
                db,
                theme_key,
                "legacy-neon",
                text_value="legacy-neon",
                commit=True,
            )

        corrupt_read = client.get(
            "/api/settings/appearance",
            headers=headers,
        )
        if (
            corrupt_read.status_code != 200
            or corrupt_read.json()
            != {
                "theme": "dark",
                "light_theme_available": True,
            }
        ):
            fail(
                "Corrupt appearance theme should defensively read "
                f"as dark: {corrupt_read.status_code} "
                f"{corrupt_read.text}"
            )

        with db_session() as db:
            raw_theme = get_str_setting(db, theme_key, "")
            if raw_theme != "legacy-neon":
                fail(
                    "Appearance GET silently rewrote the corrupt "
                    f"stored value: {raw_theme!r}"
                )
            set_app_setting(
                db,
                theme_key,
                "dark",
                text_value="dark",
                commit=True,
            )

        invalid_payloads = [
            {},
            {"theme": "sepia"},
            {"theme": None},
            {"theme": True},
            {"theme": 1},
            {"theme": "dark", "unexpected": True},
        ]
        for payload in invalid_payloads:
            response = client.patch(
                "/api/settings/appearance",
                headers=headers,
                json=payload,
            )
            if response.status_code != 422:
                fail(
                    "Invalid appearance payload should return 422, "
                    f"got {response.status_code}: "
                    f"{payload!r} {response.text}"
                )

        light = client.patch(
            "/api/settings/appearance",
            headers=headers,
            json={"theme": "light"},
        )
        if (
            light.status_code != 200
            or light.json()
            != {
                "theme": "light",
                "light_theme_available": True,
            }
        ):
            fail(
                "Appearance light update failed: "
                f"{light.status_code} {light.text}"
            )

        repeat_light = client.patch(
            "/api/settings/appearance",
            headers=headers,
            json={"theme": "light"},
        )
        if repeat_light.status_code != 200:
            fail(
                "Idempotent appearance update failed: "
                f"{repeat_light.status_code} "
                f"{repeat_light.text}"
            )

        system = client.patch(
            "/api/settings/appearance",
            headers=headers,
            json={"theme": "system"},
        )
        if (
            system.status_code != 200
            or system.json().get("theme") != "system"
        ):
            fail(
                "Appearance system update failed: "
                f"{system.status_code} {system.text}"
            )

        dark = client.patch(
            "/api/settings/appearance",
            headers=headers,
            json={"theme": "dark"},
        )
        if (
            dark.status_code != 200
            or dark.json()
            != {
                "theme": "dark",
                "light_theme_available": True,
            }
        ):
            fail(
                "Appearance dark update failed: "
                f"{dark.status_code} {dark.text}"
            )

        with db_session() as db:
            theme_row = (
                db.query(AppSetting)
                .filter(AppSetting.key == theme_key)
                .one()
            )
            audit_rows = db.execute(
                text(
                    "select entity_id, actor_type, actor_user_id, "
                    "before_json, after_json, metadata_json "
                    "from audit_log "
                    "where event_type = "
                    "'settings.appearance_updated' "
                    "and actor_user_id = :actor_user_id "
                    "order by id"
                ),
                {"actor_user_id": user_id},
            ).all()

        if (
            theme_row.value_json != "dark"
            or theme_row.value_text != "dark"
        ):
            fail(
                "Appearance setting database row is incorrect: "
                f"{theme_row.value_json!r}/"
                f"{theme_row.value_text!r}"
            )

        if len(audit_rows) != 3:
            fail(
                "Appearance settings should create one audit per "
                "real change and none for no-op updates, got "
                f"{len(audit_rows)}."
            )

        expected_transitions = [
            ("dark", "light"),
            ("light", "system"),
            ("system", "dark"),
        ]
        for row, expected in zip(
            audit_rows,
            expected_transitions,
        ):
            if (
                row[0] != theme_row.id
                or row[1] != "user"
                or row[2] != user_id
            ):
                fail(
                    "Appearance audit attribution is incorrect: "
                    f"{row!r}"
                )
            before_json = (
                json_module.loads(row[3])
                if isinstance(row[3], str)
                else row[3]
            )
            after_json = (
                json_module.loads(row[4])
                if isinstance(row[4], str)
                else row[4]
            )
            metadata_json = (
                json_module.loads(row[5])
                if isinstance(row[5], str)
                else row[5]
            )
            if (
                before_json != {"theme": expected[0]}
                or after_json != {"theme": expected[1]}
                or metadata_json.get("setting_key")
                != theme_key
                or metadata_json.get("changed_fields")
                != ["theme"]
                or metadata_json.get(
                    "light_theme_available"
                )
                is not True
            ):
                fail(
                    "Appearance audit snapshots/metadata are "
                    "incorrect: "
                    f"{before_json!r}/{after_json!r}/"
                    f"{metadata_json!r}"
                )

        with db_session() as db:
            set_app_setting(
                db,
                availability_key,
                False,
                text_value=None,
                commit=True,
            )

        unavailable_read = client.get(
            "/api/settings/appearance",
            headers=headers,
        )
        if (
            unavailable_read.status_code != 200
            or unavailable_read.json()
            != {
                "theme": "dark",
                "light_theme_available": False,
            }
        ):
            fail(
                "Unavailable light theme should read as "
                f"dark/unavailable: {unavailable_read.status_code} "
                f"{unavailable_read.text}"
            )

        for unavailable_theme in ("light", "system"):
            unavailable = client.patch(
                "/api/settings/appearance",
                headers=headers,
                json={"theme": unavailable_theme},
            )
            if (
                unavailable.status_code != 409
                or "not available"
                not in unavailable.text
            ):
                fail(
                    "Unavailable appearance mode should return 409: "
                    f"{unavailable_theme} "
                    f"{unavailable.status_code} "
                    f"{unavailable.text}"
                )

        with db_session() as db:
            audit_count = db.execute(
                text(
                    "select count(*) from audit_log "
                    "where event_type = "
                    "'settings.appearance_updated' "
                    "and actor_user_id = :actor_user_id"
                ),
                {"actor_user_id": user_id},
            ).scalar()
            stored_theme = get_str_setting(
                db,
                theme_key,
                "",
            )
            if audit_count != 3 or stored_theme != "dark":
                fail(
                    "Unavailable appearance attempts changed state: "
                    f"audits={audit_count}, theme={stored_theme!r}"
                )
            set_app_setting(
                db,
                availability_key,
                True,
                text_value=None,
                commit=True,
            )

        real_set_app_setting = (
            app_settings_service.set_app_setting
        )

        def write_then_fail(*args, **kwargs):
            real_set_app_setting(*args, **kwargs)
            raise RuntimeError(
                "injected appearance setting failure"
            )

        with db_session() as db:
            try:
                with patch.object(
                    app_settings_service,
                    "set_app_setting",
                    side_effect=write_then_fail,
                ):
                    app_settings_service.update_appearance_settings(
                        db,
                        AppearanceSettingsUpdateRequest(
                            theme="light"
                        ),
                        actor_user_id=user_id,
                        commit=True,
                    )
            except RuntimeError as exc:
                if (
                    "injected appearance setting failure"
                    not in str(exc)
                ):
                    raise
            else:
                fail(
                    "Injected appearance settings failure did "
                    "not raise"
                )

        with db_session() as db:
            after_failure = (
                app_settings_service.get_appearance_settings(db)
            )
            audit_count_after_failure = db.execute(
                text(
                    "select count(*) from audit_log "
                    "where event_type = "
                    "'settings.appearance_updated' "
                    "and actor_user_id = :actor_user_id"
                ),
                {"actor_user_id": user_id},
            ).scalar()
            theme_row = (
                db.query(AppSetting)
                .filter(AppSetting.key == theme_key)
                .one()
            )

        if (
            after_failure.model_dump()
            != {
                "theme": "dark",
                "light_theme_available": True,
            }
            or theme_row.value_json != "dark"
            or theme_row.value_text != "dark"
            or audit_count_after_failure != 3
        ):
            fail(
                "Injected appearance failure was not atomic: "
                f"{after_failure.model_dump()} "
                f"audits={audit_count_after_failure}"
            )

    finally:
        cleanup()

    ok(
        "Protected appearance settings expose dark/light/system "
        "modes, strict validation, corrupt-read recovery without "
        "silent rewrites, availability guards, no-op suppression, "
        "actor-attributed audit snapshots, injected rollback, "
        "OpenAPI coverage, authentication, and exact fixture cleanup"
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
        check_projects_contract_schema,
        check_project_creation_service,
        check_project_read_create_api,
        check_project_draft_update_api,
        check_project_reserved_update_api,
        check_linked_reservation_edit_and_terminal_delta,
        check_project_reservation_api,
        check_project_consumption_api,
        check_project_cancellation_api,
        check_project_linked_reservation_terminal_sync,
        check_reservation_contract_schema,
        check_reservation_creation_service,
        check_reservation_read_create_api,
        check_reservation_cancellation_api,
        check_reservation_consumption_api,
        check_reservation_expiry_api,
        check_reservation_activity_api,
        check_system_history_api,
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
        check_appearance_settings_api,
        check_reservation_settings_api,
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
