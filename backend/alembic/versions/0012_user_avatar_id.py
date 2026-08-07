"""add built-in avatar selection to users

Revision ID: 0012_user_avatar_id
Revises: 0011_mcp_oauth_client_ownership
Create Date: 2026-08-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# PARTPILOT:CURRENT_USER_AVATAR_MIGRATION:V572
revision = "0012_user_avatar_id"
down_revision = "0011_mcp_oauth_client_ownership"
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
    violations = connection.exec_driver_sql(
        "PRAGMA foreign_key_check"
    ).fetchall()
    if violations:
        raise RuntimeError(
            f"0012_user_avatar_id {label} created foreign-key "
            f"violations: {violations[:20]}"
        )


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "avatar_id",
            sa.String(length=40),
            nullable=False,
            server_default="initials",
        ),
    )
    _verify_sqlite_foreign_keys("upgrade")


def downgrade() -> None:
    _set_sqlite_foreign_keys(False)
    try:
        with op.batch_alter_table("users", recreate="always") as batch_op:
            batch_op.drop_column("avatar_id")
    finally:
        _set_sqlite_foreign_keys(True)
    _verify_sqlite_foreign_keys("downgrade")
