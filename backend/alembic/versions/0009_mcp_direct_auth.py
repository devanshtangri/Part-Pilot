"""add MCP direct authentication persistence

Revision ID: 0009_mcp_direct_auth
Revises: 0008_mcp_oauth
Create Date: 2026-08-03

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# PARTPILOT:MCP_DIRECT_AUTH_MIGRATION:V482
revision = "0009_mcp_direct_auth"
down_revision = "0008_mcp_oauth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_direct_auth",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=40), server_default="disabled", nullable=False),
        sa.Column("key_ciphertext", sa.Text(), nullable=True),
        sa.Column("key_digest", sa.String(length=64), nullable=True),
        sa.Column("key_prefix", sa.String(length=32), nullable=True),
        sa.Column("custom_header_name", sa.String(length=120), nullable=True),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_mcp_direct_auth_singleton"),
        sa.CheckConstraint(
            "mode IN ('disabled','bearer_key','custom_header','trusted_network')",
            name="ck_mcp_direct_auth_mode",
        ),
        sa.CheckConstraint(
            "(key_ciphertext IS NULL AND key_digest IS NULL AND key_prefix IS NULL) OR "
            "(key_ciphertext IS NOT NULL AND key_digest IS NOT NULL AND key_prefix IS NOT NULL)",
            name="ck_mcp_direct_auth_key_bundle",
        ),
        sa.CheckConstraint(
            "(mode = 'bearer_key' AND key_ciphertext IS NOT NULL AND custom_header_name IS NULL) OR "
            "(mode = 'custom_header' AND key_ciphertext IS NOT NULL AND custom_header_name IS NOT NULL) OR "
            "(mode IN ('disabled','trusted_network') AND key_ciphertext IS NULL AND custom_header_name IS NULL)",
            name="ck_mcp_direct_auth_mode_fields",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_digest", name="uq_mcp_direct_auth_key_digest"),
    )
    op.create_index("ix_mcp_direct_auth_mode", "mcp_direct_auth", ["mode"], unique=False)
    op.create_index("ix_mcp_direct_auth_last_used_at", "mcp_direct_auth", ["last_used_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mcp_direct_auth_last_used_at", table_name="mcp_direct_auth")
    op.drop_index("ix_mcp_direct_auth_mode", table_name="mcp_direct_auth")
    op.drop_table("mcp_direct_auth")
