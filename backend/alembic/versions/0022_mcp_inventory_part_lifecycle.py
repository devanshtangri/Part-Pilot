"""add MCP reversible inventory part lifecycle permissions

Revision ID: 0022_mcp_inventory_part_lifecycle
Revises: 0021_mcp_inventory_part_metadata_update
Create Date: 2026-08-24
"""
from __future__ import annotations
import json
from alembic import op
import sqlalchemy as sa

# PARTPILOT:MCP_INVENTORY_PART_LIFECYCLE_MIGRATION:V762
revision = "0022_mcp_inventory_part_lifecycle"
down_revision = "0021_mcp_inventory_part_metadata_update"
branch_labels = None
depends_on = None
TOOL_PERMISSIONS_KEY = "mcp.tool_permissions"
OLD_TOOLS = (
    "search_parts", "get_part_details", "list_projects", "get_project_details",
    "list_reservations", "get_reservation_details", "reserve_project",
    "consume_reservation", "cancel_reservation", "adjust_part_quantity",
    "create_part", "update_part_metadata",
)
NEW_TOOLS = ("soft_delete_part", "restore_part")

def _verify_sqlite_foreign_keys(label: str) -> None:
    connection = op.get_bind()
    if connection.dialect.name != "sqlite": return
    violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    if violations: raise RuntimeError(f"0022_mcp_inventory_part_lifecycle {label} created foreign-key violations: {violations[:20]}")

def _load_policy(connection, expected_keys: set[str]) -> dict[str, bool]:
    row = connection.execute(sa.text("SELECT value_json FROM app_settings WHERE key=:key"), {"key": TOOL_PERMISSIONS_KEY}).first()
    if row is None: raise RuntimeError("0022_mcp_inventory_part_lifecycle requires the MCP tool-permissions setting")
    raw=row[0]
    if isinstance(raw,str):
        try: raw=json.loads(raw)
        except json.JSONDecodeError as exc: raise RuntimeError("MCP tool-permissions setting is not valid JSON") from exc
    if not isinstance(raw,dict) or set(raw)!=expected_keys or any(type(v) is not bool for v in raw.values()):
        raise RuntimeError("MCP tool-permissions setting does not match the expected schema")
    return dict(raw)

def _store_policy(connection, policy: dict[str,bool]) -> None:
    statement=sa.text("UPDATE app_settings SET value_json=:value_json WHERE key=:key").bindparams(sa.bindparam("value_json",type_=sa.JSON()))
    connection.execute(statement,{"key":TOOL_PERMISSIONS_KEY,"value_json":policy})

def upgrade() -> None:
    c=op.get_bind(); policy=_load_policy(c,set(OLD_TOOLS))
    for name in NEW_TOOLS: policy[name]=False
    _store_policy(c,{name:policy[name] for name in OLD_TOOLS+NEW_TOOLS}); _verify_sqlite_foreign_keys("upgrade")

def downgrade() -> None:
    c=op.get_bind(); policy=_load_policy(c,set(OLD_TOOLS+NEW_TOOLS))
    _store_policy(c,{name:policy[name] for name in OLD_TOOLS}); _verify_sqlite_foreign_keys("downgrade")
