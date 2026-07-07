"""schema hardening

Revision ID: 0002_schema_hardening
Revises: 0001_database_foundation
Create Date: 2026-07-07

"""

from alembic import op


revision = "0002_schema_hardening"
down_revision = "0001_database_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite cannot add CHECK constraints to existing tables without rebuilding them.
    # Keep additive hardening here: indexes and FK enforcement in app connection setup.
    op.create_index("ix_parts_part_number", "parts", ["part_number"], unique=False)
    op.create_index("ix_parts_package", "parts", ["package"], unique=False)
    op.create_index("ix_parts_part_type_deleted", "parts", ["part_type_id", "is_deleted"], unique=False)
    op.create_index("ix_parts_location_deleted", "parts", ["location_id", "is_deleted"], unique=False)

    op.create_index("ix_stock_movements_part_created", "stock_movements", ["part_id", "created_at"], unique=False)
    op.create_index("ix_project_items_project_part", "project_items", ["project_id", "part_id"], unique=False)
    op.create_index("ix_reservation_items_reservation_part", "reservation_items", ["reservation_id", "part_id"], unique=False)

    op.create_index("ix_audit_log_entity", "audit_log", ["entity_type", "entity_id"], unique=False)
    op.create_index("ix_audit_log_event_created", "audit_log", ["event_type", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_log_event_created", table_name="audit_log")
    op.drop_index("ix_audit_log_entity", table_name="audit_log")

    op.drop_index("ix_reservation_items_reservation_part", table_name="reservation_items")
    op.drop_index("ix_project_items_project_part", table_name="project_items")
    op.drop_index("ix_stock_movements_part_created", table_name="stock_movements")

    op.drop_index("ix_parts_location_deleted", table_name="parts")
    op.drop_index("ix_parts_part_type_deleted", table_name="parts")
    op.drop_index("ix_parts_package", table_name="parts")
    op.drop_index("ix_parts_part_number", table_name="parts")
