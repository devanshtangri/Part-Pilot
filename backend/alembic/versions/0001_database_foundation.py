"""database foundation

Revision ID: 0001_database_foundation
Revises:
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_database_foundation"
down_revision = None
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("key", name="uq_app_settings_key"),
    )
    op.create_index("ix_app_settings_key", "app_settings", ["key"])

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=80), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"])

    op.create_table(
        "part_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=140), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("template_version", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.UniqueConstraint("name", name="uq_part_types_name"),
        sa.UniqueConstraint("slug", name="uq_part_types_slug"),
    )
    op.create_index("ix_part_types_name", "part_types", ["name"])
    op.create_index("ix_part_types_slug", "part_types", ["slug"])

    op.create_table(
        "part_type_fields",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("part_type_id", sa.Integer(), sa.ForeignKey("part_types.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_key", sa.String(length=120), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("field_type", sa.String(length=40), nullable=False),
        sa.Column("is_required", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("options_json", sa.JSON(), nullable=True),
        sa.Column("default_unit", sa.String(length=30), nullable=True),
        sa.Column("help_text", sa.Text(), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("part_type_id", "field_key", name="uq_part_type_fields_type_key"),
    )
    op.create_index("ix_part_type_fields_part_type_id", "part_type_fields", ["part_type_id"])

    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("normalized_name", sa.String(length=220), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("name", name="uq_locations_name"),
        sa.UniqueConstraint("normalized_name", name="uq_locations_normalized_name"),
    )
    op.create_index("ix_locations_name", "locations", ["name"])
    op.create_index("ix_locations_normalized_name", "locations", ["normalized_name"])

    op.create_table(
        "parts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("part_type_id", sa.Integer(), sa.ForeignKey("part_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("part_number", sa.String(length=160), nullable=True),
        sa.Column("name", sa.String(length=220), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("package", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("total_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reserved_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("total_purchase_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("quantity_purchased", sa.Integer(), nullable=True),
        sa.Column("purchase_link", sa.Text(), nullable=True),
        sa.Column("purchase_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("price_note", sa.Text(), nullable=True),
        sa.Column("low_stock_enabled", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("low_stock_threshold", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.CheckConstraint(
            "(name IS NOT NULL AND length(trim(name)) > 0) OR (part_number IS NOT NULL AND length(trim(part_number)) > 0)",
            name="ck_parts_name_or_part_number",
        ),
        sa.CheckConstraint("total_quantity >= 0", name="ck_parts_total_quantity_nonnegative"),
        sa.CheckConstraint("reserved_quantity >= 0", name="ck_parts_reserved_quantity_nonnegative"),
        sa.CheckConstraint("reserved_quantity <= total_quantity", name="ck_parts_reserved_lte_total"),
        sa.UniqueConstraint("part_number", name="uq_parts_part_number"),
    )
    op.create_index("ix_parts_part_type_id", "parts", ["part_type_id"])
    op.create_index("ix_parts_location_id", "parts", ["location_id"])
    op.create_index("ix_parts_name", "parts", ["name"])
    op.create_index("ix_parts_is_deleted", "parts", ["is_deleted"])

    op.create_table(
        "part_field_values",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("part_id", sa.Integer(), sa.ForeignKey("parts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_id", sa.Integer(), sa.ForeignKey("part_type_fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_number", sa.Numeric(18, 6), nullable=True),
        sa.Column("value_bool", sa.Boolean(), nullable=True),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column("unit", sa.String(length=30), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("part_id", "field_id", name="uq_part_field_values_part_field"),
    )
    op.create_index("ix_part_field_values_part_id", "part_field_values", ["part_id"])
    op.create_index("ix_part_field_values_field_id", "part_field_values", ["field_id"])

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("normalized_name", sa.String(length=120), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("name", name="uq_tags_name"),
        sa.UniqueConstraint("normalized_name", name="uq_tags_normalized_name"),
    )
    op.create_index("ix_tags_name", "tags", ["name"])
    op.create_index("ix_tags_normalized_name", "tags", ["normalized_name"])

    op.create_table(
        "part_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("part_id", sa.Integer(), sa.ForeignKey("parts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("part_id", "tag_id", name="uq_part_tags_part_tag"),
    )
    op.create_index("ix_part_tags_part_id", "part_tags", ["part_id"])
    op.create_index("ix_part_tags_tag_id", "part_tags", ["tag_id"])

    op.create_table(
        "aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("part_id", sa.Integer(), sa.ForeignKey("parts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias", sa.String(length=180), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("part_id", "alias", name="uq_aliases_part_alias"),
    )
    op.create_index("ix_aliases_part_id", "aliases", ["part_id"])
    op.create_index("ix_aliases_alias", "aliases", ["alias"])

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("part_id", sa.Integer(), sa.ForeignKey("parts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("movement_type", sa.String(length=60), nullable=False),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("quantity_before", sa.Integer(), nullable=True),
        sa.Column("quantity_after", sa.Integer(), nullable=True),
        sa.Column("unit_price_snapshot", sa.Numeric(12, 4), nullable=True),
        sa.Column("currency_snapshot", sa.String(length=12), nullable=True),
        sa.Column("reason", sa.String(length=180), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=40), server_default="manual", nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_stock_movements_part_id", "stock_movements", ["part_id"])
    op.create_index("ix_stock_movements_movement_type", "stock_movements", ["movement_type"])

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), server_default="draft", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=40), server_default="manual", nullable=False),
        sa.Column("estimated_total_value", sa.Numeric(14, 4), nullable=True),
        sa.Column("currency_snapshot", sa.String(length=12), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_projects_name", "projects", ["name"])
    op.create_index("ix_projects_status", "projects", ["status"])

    op.create_table(
        "project_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.Integer(), sa.ForeignKey("parts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_snapshot", sa.Numeric(12, 4), nullable=True),
        sa.Column("currency_snapshot", sa.String(length=12), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        *timestamps(),
        sa.CheckConstraint("quantity > 0", name="ck_project_items_quantity_positive"),
    )
    op.create_index("ix_project_items_project_id", "project_items", ["project_id"])
    op.create_index("ix_project_items_part_id", "project_items", ["part_id"])

    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("label", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=40), server_default="active", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=40), server_default="manual", nullable=False),
        sa.Column("expiry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_reserved_value", sa.Numeric(14, 4), nullable=True),
        sa.Column("currency_snapshot", sa.String(length=12), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_reservations_project_id", "reservations", ["project_id"])
    op.create_index("ix_reservations_label", "reservations", ["label"])
    op.create_index("ix_reservations_status", "reservations", ["status"])

    op.create_table(
        "reservation_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reservation_id", sa.Integer(), sa.ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.Integer(), sa.ForeignKey("parts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_snapshot", sa.Numeric(12, 4), nullable=True),
        sa.Column("currency_snapshot", sa.String(length=12), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        *timestamps(),
        sa.CheckConstraint("quantity > 0", name="ck_reservation_items_quantity_positive"),
    )
    op.create_index("ix_reservation_items_reservation_id", "reservation_items", ["reservation_id"])
    op.create_index("ix_reservation_items_part_id", "reservation_items", ["part_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("actor_type", sa.String(length=40), server_default="system", nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
    )
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])
    op.create_index("ix_audit_log_event_type", "audit_log", ["event_type"])
    op.create_index("ix_audit_log_entity_type", "audit_log", ["entity_type"])
    op.create_index("ix_audit_log_entity_id", "audit_log", ["entity_id"])

    op.create_table(
        "backups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=40), server_default="created", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index("ix_backups_created_at", "backups", ["created_at"])
    op.create_index("ix_backups_status", "backups", ["status"])


def downgrade() -> None:
    for table_name in [
        "backups",
        "audit_log",
        "reservation_items",
        "reservations",
        "project_items",
        "projects",
        "stock_movements",
        "aliases",
        "part_tags",
        "tags",
        "part_field_values",
        "parts",
        "locations",
        "part_type_fields",
        "part_types",
        "sessions",
        "users",
        "app_settings",
    ]:
        op.drop_table(table_name)
