"""add scoped REST API keys

Revision ID: 0014_api_keys
Revises: 0013_user_avatar_image
Create Date: 2026-08-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# PARTPILOT:REST_API_KEY_MIGRATION:V615
revision = "0014_api_keys"
down_revision = "0013_user_avatar_image"
branch_labels = None
depends_on = None


def _verify_sqlite_foreign_keys(label: str) -> None:
    connection = op.get_bind()
    if connection.dialect.name != "sqlite":
        return
    violations = connection.exec_driver_sql(
        "PRAGMA foreign_key_check"
    ).fetchall()
    if violations:
        raise RuntimeError(
            f"0014_api_keys {label} created foreign-key violations: "
            f"{violations[:20]}"
        )


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey(
                "users.id",
                ondelete="CASCADE",
                name="fk_api_keys_user_id",
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("key_digest", sa.String(length=64), nullable=False),
        sa.Column("key_prefix", sa.String(length=32), nullable=False),
        sa.Column("scopes_json", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(trim(name)) >= 1 AND length(name) <= 120",
            name="ck_api_keys_name_length",
        ),
        sa.CheckConstraint(
            "length(key_digest) = 64",
            name="ck_api_keys_digest_length",
        ),
        sa.CheckConstraint(
            "length(key_prefix) >= 12 AND length(key_prefix) <= 32",
            name="ck_api_keys_prefix_length",
        ),
        sa.UniqueConstraint("key_digest", name="uq_api_keys_key_digest"),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"], unique=False)
    op.create_index("ix_api_keys_revoked_at", "api_keys", ["revoked_at"], unique=False)
    op.create_index("ix_api_keys_expires_at", "api_keys", ["expires_at"], unique=False)
    op.create_index("ix_api_keys_last_used_at", "api_keys", ["last_used_at"], unique=False)
    _verify_sqlite_foreign_keys("upgrade")


def downgrade() -> None:
    op.drop_index("ix_api_keys_last_used_at", table_name="api_keys")
    op.drop_index("ix_api_keys_expires_at", table_name="api_keys")
    op.drop_index("ix_api_keys_revoked_at", table_name="api_keys")
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_table("api_keys")
    _verify_sqlite_foreign_keys("downgrade")
