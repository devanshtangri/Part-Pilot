"""add safeguarded MCP write intents

Revision ID: 0018_mcp_write_intents
Revises: 0017_user_roles
Create Date: 2026-08-23
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

# PARTPILOT:MCP_WRITE_INTENT_MIGRATION:V734
revision = "0018_mcp_write_intents"
down_revision = "0017_user_roles"
branch_labels = None
depends_on = None

TOOL_PERMISSIONS_KEY = "mcp.tool_permissions"
READ_TOOLS = (
    "search_parts",
    "get_part_details",
    "list_projects",
    "get_project_details",
    "list_reservations",
    "get_reservation_details",
)
WRITE_TOOLS = (
    "reserve_project",
    "consume_reservation",
    "cancel_reservation",
)


def _verify_sqlite_foreign_keys(label: str) -> None:
    connection = op.get_bind()
    if connection.dialect.name != "sqlite":
        return
    violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(
            f"0018_mcp_write_intents {label} created foreign-key violations: {violations[:20]}"
        )


def _load_policy(connection, expected_keys: set[str]) -> dict[str, bool]:
    row = connection.execute(
        sa.text("SELECT value_json FROM app_settings WHERE key=:key"),
        {"key": TOOL_PERMISSIONS_KEY},
    ).first()
    if row is None:
        raise RuntimeError("0018_mcp_write_intents requires the MCP tool-permissions setting")
    raw = row[0]
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("MCP tool-permissions setting is not valid JSON") from exc
    if (
        not isinstance(raw, dict)
        or set(raw) != expected_keys
        or any(type(value) is not bool for value in raw.values())
    ):
        raise RuntimeError("MCP tool-permissions setting does not match the expected schema")
    return dict(raw)


def _store_policy(connection, policy: dict[str, bool]) -> None:
    statement = sa.text(
        "UPDATE app_settings SET value_json=:value_json WHERE key=:key"
    ).bindparams(sa.bindparam("value_json", type_=sa.JSON()))
    connection.execute(
        statement,
        {"key": TOOL_PERMISSIONS_KEY, "value_json": policy},
    )


def upgrade() -> None:
    connection = op.get_bind()
    op.create_table(
        "mcp_write_intents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("principal_key", sa.String(length=180), nullable=False),
        sa.Column(
            "authorization_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_mcp_write_intents_authorization_user_id"),
            nullable=True,
        ),
        sa.Column("tool_name", sa.String(length=120), nullable=False),
        sa.Column("argument_hash", sa.String(length=64), nullable=False),
        sa.Column("preview_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("confirmation_digest", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("preview_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error_type", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(
            "status IN ('pending','completed','failed','expired')",
            name="ck_mcp_write_intents_status",
        ),
        sa.UniqueConstraint(
            "principal_key",
            "tool_name",
            "idempotency_key",
            name="uq_mcp_write_intents_principal_tool_idempotency",
        ),
    )
    op.create_index(
        "ix_mcp_write_intents_status_expires",
        "mcp_write_intents",
        ["status", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_mcp_write_intents_authorization_user_id",
        "mcp_write_intents",
        ["authorization_user_id"],
        unique=False,
    )

    policy = _load_policy(connection, set(READ_TOOLS))
    for name in WRITE_TOOLS:
        policy[name] = False
    ordered = {name: policy[name] for name in READ_TOOLS + WRITE_TOOLS}
    _store_policy(connection, ordered)
    _verify_sqlite_foreign_keys("upgrade")


def downgrade() -> None:
    connection = op.get_bind()
    policy = _load_policy(connection, set(READ_TOOLS + WRITE_TOOLS))
    ordered = {name: policy[name] for name in READ_TOOLS}
    _store_policy(connection, ordered)
    op.drop_index("ix_mcp_write_intents_authorization_user_id", table_name="mcp_write_intents")
    op.drop_index("ix_mcp_write_intents_status_expires", table_name="mcp_write_intents")
    op.drop_table("mcp_write_intents")
    _verify_sqlite_foreign_keys("downgrade")
