"""add MCP OAuth client ownership

Revision ID: 0011_mcp_oauth_client_ownership
Revises: 0010_mcp_trusted_networks
Create Date: 2026-08-07
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

# PARTPILOT:MCP_OAUTH_CLIENT_OWNERSHIP_MIGRATION:V555
revision = "0011_mcp_oauth_client_ownership"
down_revision = "0010_mcp_trusted_networks"
branch_labels = None
depends_on = None


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
            f"0011_mcp_oauth_client_ownership {label} created foreign-key "
            f"violations: {violations[:20]}"
        )


def upgrade() -> None:
    _set_sqlite_foreign_keys(False)
    try:
        with op.batch_alter_table("mcp_oauth_clients", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("registered_by_user_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_mcp_oauth_clients_registered_by_user_id", "users",
                ["registered_by_user_id"], ["id"], ondelete="SET NULL",
            )
            batch_op.create_index(
                "ix_mcp_oauth_clients_registered_by_user_id",
                ["registered_by_user_id"], unique=False,
            )
    finally:
        _set_sqlite_foreign_keys(True)
    _verify_sqlite_foreign_keys("upgrade")


def downgrade() -> None:
    _set_sqlite_foreign_keys(False)
    try:
        with op.batch_alter_table("mcp_oauth_clients", recreate="always") as batch_op:
            batch_op.drop_index("ix_mcp_oauth_clients_registered_by_user_id")
            batch_op.drop_constraint(
                "fk_mcp_oauth_clients_registered_by_user_id", type_="foreignkey"
            )
            batch_op.drop_column("registered_by_user_id")
    finally:
        _set_sqlite_foreign_keys(True)
    _verify_sqlite_foreign_keys("downgrade")
