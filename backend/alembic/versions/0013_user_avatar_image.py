"""add normalized custom avatar image storage to users

Revision ID: 0013_user_avatar_image
Revises: 0012_user_avatar_id
Create Date: 2026-08-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# PARTPILOT:CUSTOM_AVATAR_MIGRATION:V598
revision = "0013_user_avatar_image"
down_revision = "0012_user_avatar_id"
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
            f"0013_user_avatar_image {label} created foreign-key "
            f"violations: {violations[:20]}"
        )


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("avatar_image_data", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("avatar_image_mime", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("avatar_image_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("avatar_image_size_bytes", sa.Integer(), nullable=True),
    )
    _verify_sqlite_foreign_keys("upgrade")


def downgrade() -> None:
    _set_sqlite_foreign_keys(False)
    try:
        with op.batch_alter_table("users", recreate="always") as batch_op:
            batch_op.drop_column("avatar_image_size_bytes")
            batch_op.drop_column("avatar_image_sha256")
            batch_op.drop_column("avatar_image_mime")
            batch_op.drop_column("avatar_image_data")
    finally:
        _set_sqlite_foreign_keys(True)
    _verify_sqlite_foreign_keys("downgrade")
