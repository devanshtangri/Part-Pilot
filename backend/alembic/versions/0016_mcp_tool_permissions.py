"""add MCP individual-tool and per-client permissions

Revision ID: 0016_mcp_tool_permissions
Revises: 0015_mcp_direct_clients
Create Date: 2026-08-08
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

# PARTPILOT:MCP_TOOL_PERMISSIONS_MIGRATION:V644
revision = "0016_mcp_tool_permissions"
down_revision = "0015_mcp_direct_clients"
branch_labels = None
depends_on = None

TOOL_PERMISSIONS_KEY = "mcp.tool_permissions"
DEFAULT_TOOL_PERMISSIONS = {
    "search_parts": True,
    "get_part_details": True,
    "list_projects": True,
    "get_project_details": True,
    "list_reservations": True,
    "get_reservation_details": True,
}


def _verify_sqlite_foreign_keys(label: str) -> None:
    connection = op.get_bind()
    if connection.dialect.name != "sqlite":
        return
    violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(
            f"0016_mcp_tool_permissions {label} created foreign-key violations: "
            f"{violations[:20]}"
        )


def upgrade() -> None:
    connection = op.get_bind()
    op.add_column(
        "mcp_direct_auth",
        sa.Column("denied_tools_json", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "mcp_oauth_clients",
        sa.Column("denied_tools_json", sa.JSON(), nullable=False, server_default="[]"),
    )
    existing = connection.execute(
        sa.text("SELECT 1 FROM app_settings WHERE key=:key"),
        {"key": TOOL_PERMISSIONS_KEY},
    ).first()
    if existing is None:
        connection.execute(
            sa.text(
                "INSERT INTO app_settings "
                "(key,value_json,value_text,created_at,updated_at) "
                "VALUES (:key,:value_json,NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            ),
            {
                "key": TOOL_PERMISSIONS_KEY,
                "value_json": json.dumps(DEFAULT_TOOL_PERMISSIONS, separators=(",", ":")),
            },
        )
    _verify_sqlite_foreign_keys("upgrade")


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("DELETE FROM app_settings WHERE key=:key"),
        {"key": TOOL_PERMISSIONS_KEY},
    )
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql(
            "ALTER TABLE mcp_oauth_clients DROP COLUMN denied_tools_json"
        )
        connection.exec_driver_sql(
            "ALTER TABLE mcp_direct_auth DROP COLUMN denied_tools_json"
        )
    else:
        op.drop_column("mcp_oauth_clients", "denied_tools_json")
        op.drop_column("mcp_direct_auth", "denied_tools_json")
    _verify_sqlite_foreign_keys("downgrade")
