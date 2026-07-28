# align reservation lifecycle and movement snapshots
#
# Revision ID: 0006_reservation_contract
# Revises: 0005_packages
# Create Date: 2026-07-28
#
# PARTPILOT:RESERVATION_CONTRACT_MIGRATION:V298

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_reservation_contract"
down_revision = "0005_packages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table(
        "reservations",
        recreate="always",
    ) as batch_op:
        batch_op.create_check_constraint(
            "ck_reservations_status",
            "status IN ('active', 'consumed', 'cancelled', 'expired')",
        )
        batch_op.create_check_constraint(
            "ck_reservations_created_by",
            "created_by IN ('manual', 'ai', 'mcp', 'system')",
        )
        batch_op.create_check_constraint(
            "ck_reservations_estimated_reserved_value_nonnegative",
            (
                "estimated_reserved_value IS NULL OR "
                "estimated_reserved_value >= 0"
            ),
        )

    with op.batch_alter_table(
        "reservation_items",
        recreate="always",
    ) as batch_op:
        batch_op.create_check_constraint(
            "ck_reservation_items_unit_price_snapshot_nonnegative",
            "unit_price_snapshot IS NULL OR unit_price_snapshot >= 0",
        )

    with op.batch_alter_table(
        "stock_movements",
        recreate="always",
    ) as batch_op:
        batch_op.add_column(
            sa.Column("reservation_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "reserved_quantity_before",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "reserved_quantity_after",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "available_quantity_before",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "available_quantity_after",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.create_foreign_key(
            "fk_stock_movements_reservation_id_reservations",
            "reservations",
            ["reservation_id"],
            ["id"],
            ondelete="SET NULL",
        )

        checks = (
            (
                "ck_stock_movements_quantity_before_nonnegative",
                "quantity_before IS NULL OR quantity_before >= 0",
            ),
            (
                "ck_stock_movements_quantity_after_nonnegative",
                "quantity_after IS NULL OR quantity_after >= 0",
            ),
            (
                "ck_stock_movements_unit_price_snapshot_nonnegative",
                "unit_price_snapshot IS NULL OR unit_price_snapshot >= 0",
            ),
            (
                "ck_stock_movements_reserved_quantity_before_nonnegative",
                (
                    "reserved_quantity_before IS NULL OR "
                    "reserved_quantity_before >= 0"
                ),
            ),
            (
                "ck_stock_movements_reserved_quantity_after_nonnegative",
                (
                    "reserved_quantity_after IS NULL OR "
                    "reserved_quantity_after >= 0"
                ),
            ),
            (
                "ck_stock_movements_available_quantity_before_nonnegative",
                (
                    "available_quantity_before IS NULL OR "
                    "available_quantity_before >= 0"
                ),
            ),
            (
                "ck_stock_movements_available_quantity_after_nonnegative",
                (
                    "available_quantity_after IS NULL OR "
                    "available_quantity_after >= 0"
                ),
            ),
        )
        for name, expression in checks:
            batch_op.create_check_constraint(name, expression)

        batch_op.create_index(
            "ix_stock_movements_reservation_id",
            ["reservation_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_stock_movements_reservation_created",
            ["reservation_id", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table(
        "stock_movements",
        recreate="always",
    ) as batch_op:
        batch_op.drop_index("ix_stock_movements_reservation_created")
        batch_op.drop_index("ix_stock_movements_reservation_id")
        batch_op.drop_constraint(
            "fk_stock_movements_reservation_id_reservations",
            type_="foreignkey",
        )
        for name in (
            "ck_stock_movements_available_quantity_after_nonnegative",
            "ck_stock_movements_available_quantity_before_nonnegative",
            "ck_stock_movements_reserved_quantity_after_nonnegative",
            "ck_stock_movements_reserved_quantity_before_nonnegative",
            "ck_stock_movements_unit_price_snapshot_nonnegative",
            "ck_stock_movements_quantity_after_nonnegative",
            "ck_stock_movements_quantity_before_nonnegative",
        ):
            batch_op.drop_constraint(name, type_="check")
        batch_op.drop_column("available_quantity_after")
        batch_op.drop_column("available_quantity_before")
        batch_op.drop_column("reserved_quantity_after")
        batch_op.drop_column("reserved_quantity_before")
        batch_op.drop_column("reservation_id")

    with op.batch_alter_table(
        "reservation_items",
        recreate="always",
    ) as batch_op:
        batch_op.drop_constraint(
            "ck_reservation_items_unit_price_snapshot_nonnegative",
            type_="check",
        )

    with op.batch_alter_table(
        "reservations",
        recreate="always",
    ) as batch_op:
        batch_op.drop_constraint(
            "ck_reservations_estimated_reserved_value_nonnegative",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_reservations_created_by",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_reservations_status",
            type_="check",
        )
