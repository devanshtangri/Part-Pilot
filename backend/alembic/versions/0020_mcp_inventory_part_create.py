"""add MCP inventory part-create permission

Revision ID: 0020_mcp_inventory_part_create
Revises: 0019_mcp_inventory_stock_write
Create Date: 2026-08-24
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

# PARTPILOT:MCP_INVENTORY_PART_CREATE_MIGRATION:V755
revision = "0020_mcp_inventory_part_create"
down_revision = "0019_mcp_inventory_stock_write"
branch_labels = None
depends_on = None

TOOL_PERMISSIONS_KEY = "mcp.tool_permissions"
OLD_TOOLS = (
    "search_parts",
    "get_part_details",
    "list_projects",
    "get_project_details",
    "list_reservations",
    "get_reservation_details",
    "reserve_project",
    "consume_reservation",
    "cancel_reservation",
    "adjust_part_quantity",
)
NEW_TOOL = "create_part"


def _verify_sqlite_foreign_keys(label: str) -> None:
    connection = op.get_bind()
    if connection.dialect.name != "sqlite":
        return
    violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(
            f"0020_mcp_inventory_part_create {label} created foreign-key violations: "
            f"{violations[:20]}"
        )


def _load_policy(connection, expected_keys: set[str]) -> dict[str, bool]:
    row = connection.execute(
        sa.text("SELECT value_json FROM app_settings WHERE key=:key"),
        {"key": TOOL_PERMISSIONS_KEY},
    ).first()
    if row is None:
        raise RuntimeError(
            "0020_mcp_inventory_part_create requires the MCP tool-permissions setting"
        )
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
        raise RuntimeError(
            "MCP tool-permissions setting does not match the expected schema"
        )
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
    policy = _load_policy(connection, set(OLD_TOOLS))
    policy[NEW_TOOL] = False
    ordered = {name: policy[name] for name in OLD_TOOLS + (NEW_TOOL,)}
    _store_policy(connection, ordered)
    _verify_sqlite_foreign_keys("upgrade")


def downgrade() -> None:
    connection = op.get_bind()
    policy = _load_policy(connection, set(OLD_TOOLS + (NEW_TOOL,)))
    ordered = {name: policy[name] for name in OLD_TOOLS}
    _store_policy(connection, ordered)
    _verify_sqlite_foreign_keys("downgrade")
