"""add multi-user roles

Revision ID: 0017_user_roles
Revises: 0016_mcp_tool_permissions
Create Date: 2026-08-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# PARTPILOT:USER_ROLE_MIGRATION:V732
revision = "0017_user_roles"
down_revision = "0016_mcp_tool_permissions"
branch_labels = None
depends_on = None

ROLE_CHECK = "role IN ('owner','administrator','operator','viewer')"


def _verify_sqlite_foreign_keys(label: str) -> None:
    connection = op.get_bind()
    if connection.dialect.name != "sqlite":
        return
    violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(
            f"0017_user_roles {label} created foreign-key violations: {violations[:20]}"
        )


def upgrade() -> None:
    connection = op.get_bind()
    # Never batch-recreate users on SQLite: dropping/replacing the parent table
    # would fire real ON DELETE actions against sessions, API keys and OAuth rows.
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=20),
            sa.CheckConstraint(ROLE_CHECK, name="ck_users_role"),
            nullable=False,
            server_default="viewer",
        ),
    )
    # Every account predating multi-user administration had full single-user
    # authority. Preserve that access explicitly rather than silently demoting it.
    connection.execute(sa.text("UPDATE users SET role='owner'"))
    op.create_index("ix_users_role", "users", ["role"], unique=False)
    _verify_sqlite_foreign_keys("upgrade")


def downgrade() -> None:
    connection = op.get_bind()
    op.drop_index("ix_users_role", table_name="users")
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql("ALTER TABLE users DROP COLUMN role")
    else:
        op.drop_column("users", "role")
    _verify_sqlite_foreign_keys("downgrade")
