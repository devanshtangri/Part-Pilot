"""align Projects lifecycle constraints

Revision ID: 0007_projects_contract
Revises: 0006_reservation_contract
Create Date: 2026-07-30

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# PARTPILOT:PROJECTS_CONTRACT_MIGRATION:V368
revision = "0007_projects_contract"
down_revision = "0006_reservation_contract"
branch_labels = None
depends_on = None


def _validate_existing_rows() -> None:
    connection = op.get_bind()
    invalid_statuses = connection.execute(
        sa.text(
            "select id, status from projects "
            "where status not in ('draft','reserved','consumed','cancelled') "
            "order by id limit 20"
        )
    ).fetchall()
    if invalid_statuses:
        raise RuntimeError(
            "Cannot apply 0007_projects_contract: projects contain unsupported "
            f"statuses: {[(row[0], row[1]) for row in invalid_statuses]}"
        )
    invalid_creators = connection.execute(
        sa.text(
            "select id, created_by from projects "
            "where created_by not in ('manual','ai','mcp','system') "
            "order by id limit 20"
        )
    ).fetchall()
    if invalid_creators:
        raise RuntimeError(
            "Cannot apply 0007_projects_contract: projects contain unsupported "
            f"created_by values: {[(row[0], row[1]) for row in invalid_creators]}"
        )
    negative_totals = connection.execute(
        sa.text(
            "select id, estimated_total_value from projects "
            "where estimated_total_value < 0 order by id limit 20"
        )
    ).fetchall()
    if negative_totals:
        raise RuntimeError(
            "Cannot apply 0007_projects_contract: projects contain negative "
            f"estimated totals: {[(row[0], row[1]) for row in negative_totals]}"
        )
    invalid_items = connection.execute(
        sa.text(
            "select id, quantity, unit_price_snapshot from project_items "
            "where quantity <= 0 or unit_price_snapshot < 0 order by id limit 20"
        )
    ).fetchall()
    if invalid_items:
        raise RuntimeError(
            "Cannot apply 0007_projects_contract: project_items contain invalid "
            "quantity or price snapshots: "
            f"{[(row[0], row[1], row[2]) for row in invalid_items]}"
        )


def _set_sqlite_foreign_keys(enabled: bool) -> None:
    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql(
            "PRAGMA foreign_keys=" + ("ON" if enabled else "OFF")
        )


def _verify_sqlite_foreign_keys(label: str) -> None:
    connection = op.get_bind()
    if connection.dialect.name != "sqlite":
        return
    violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(
            f"0007_projects_contract {label} created foreign-key violations: "
            f"{violations[:20]}"
        )


def upgrade() -> None:
    _validate_existing_rows()
    _set_sqlite_foreign_keys(False)
    try:
        with op.batch_alter_table("projects", recreate="always") as batch_op:
            batch_op.create_check_constraint(
                "ck_projects_status",
                "status IN ('draft', 'reserved', 'consumed', 'cancelled')",
            )
            batch_op.create_check_constraint(
                "ck_projects_created_by",
                "created_by IN ('manual', 'ai', 'mcp', 'system')",
            )
            batch_op.create_check_constraint(
                "ck_projects_estimated_total_value_nonnegative",
                "estimated_total_value IS NULL OR estimated_total_value >= 0",
            )

        with op.batch_alter_table("project_items", recreate="always") as batch_op:
            batch_op.create_check_constraint(
                "ck_project_items_unit_price_snapshot_nonnegative",
                "unit_price_snapshot IS NULL OR unit_price_snapshot >= 0",
            )
    finally:
        _set_sqlite_foreign_keys(True)
    _verify_sqlite_foreign_keys("upgrade")


def downgrade() -> None:
    _set_sqlite_foreign_keys(False)
    try:
        with op.batch_alter_table("project_items", recreate="always") as batch_op:
            batch_op.drop_constraint(
                "ck_project_items_unit_price_snapshot_nonnegative",
                type_="check",
            )

        with op.batch_alter_table("projects", recreate="always") as batch_op:
            batch_op.drop_constraint(
                "ck_projects_estimated_total_value_nonnegative",
                type_="check",
            )
            batch_op.drop_constraint("ck_projects_created_by", type_="check")
            batch_op.drop_constraint("ck_projects_status", type_="check")
    finally:
        _set_sqlite_foreign_keys(True)
    _verify_sqlite_foreign_keys("downgrade")
