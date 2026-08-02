"""add MCP OAuth persistence tables

Revision ID: 0008_mcp_oauth
Revises: 0007_projects_contract
Create Date: 2026-08-02

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# PARTPILOT:MCP_OAUTH_MIGRATION:V465
revision = "0008_mcp_oauth"
down_revision = "0007_projects_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_oauth_clients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=160), nullable=False),
        sa.Column("client_secret_hash", sa.String(length=255), nullable=True),
        sa.Column("client_name", sa.String(length=200), nullable=False),
        sa.Column("client_uri", sa.Text(), nullable=True),
        sa.Column("redirect_uris_json", sa.JSON(), nullable=False),
        sa.Column("grant_types_json", sa.JSON(), nullable=False),
        sa.Column("response_types_json", sa.JSON(), nullable=False),
        sa.Column("token_endpoint_auth_method", sa.String(length=40), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "token_endpoint_auth_method IN ('none','client_secret_post','client_secret_basic')",
            name="ck_mcp_oauth_clients_auth_method",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", name="uq_mcp_oauth_clients_client_id"),
        sa.UniqueConstraint("client_secret_hash", name="uq_mcp_oauth_clients_secret_hash"),
    )
    op.create_index("ix_mcp_oauth_clients_client_id", "mcp_oauth_clients", ["client_id"], unique=False)
    op.create_index("ix_mcp_oauth_clients_revoked_at", "mcp_oauth_clients", ["revoked_at"], unique=False)

    op.create_table(
        "mcp_oauth_authorization_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("scopes_json", sa.JSON(), nullable=False),
        sa.Column("code_challenge", sa.String(length=160), nullable=False),
        sa.Column("code_challenge_method", sa.String(length=20), nullable=False),
        sa.Column("resource_uri", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("code_challenge_method = 'S256'", name="ck_mcp_oauth_codes_pkce_method"),
        sa.ForeignKeyConstraint(["client_id"], ["mcp_oauth_clients.id"], name="fk_mcp_oauth_codes_client_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_mcp_oauth_codes_user_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash", name="uq_mcp_oauth_codes_code_hash"),
    )
    op.create_index("ix_mcp_oauth_codes_client_id", "mcp_oauth_authorization_codes", ["client_id"], unique=False)
    op.create_index("ix_mcp_oauth_codes_user_id", "mcp_oauth_authorization_codes", ["user_id"], unique=False)
    op.create_index("ix_mcp_oauth_codes_expires_at", "mcp_oauth_authorization_codes", ["expires_at"], unique=False)
    op.create_index("ix_mcp_oauth_codes_consumed_at", "mcp_oauth_authorization_codes", ["consumed_at"], unique=False)

    op.create_table(
        "mcp_oauth_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("access_token_hash", sa.String(length=255), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=255), nullable=True),
        sa.Column("token_family_id", sa.String(length=160), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scopes_json", sa.JSON(), nullable=False),
        sa.Column("resource_uri", sa.Text(), nullable=False),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_token_id", sa.Integer(), nullable=True),
        sa.Column("replay_detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "(refresh_token_hash IS NULL AND refresh_expires_at IS NULL) OR "
            "(refresh_token_hash IS NOT NULL AND refresh_expires_at IS NOT NULL)",
            name="ck_mcp_oauth_tokens_refresh_pair",
        ),
        sa.ForeignKeyConstraint(["client_id"], ["mcp_oauth_clients.id"], name="fk_mcp_oauth_tokens_client_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_mcp_oauth_tokens_user_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["replaced_by_token_id"], ["mcp_oauth_tokens.id"], name="fk_mcp_oauth_tokens_replaced_by", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("access_token_hash", name="uq_mcp_oauth_tokens_access_hash"),
        sa.UniqueConstraint("refresh_token_hash", name="uq_mcp_oauth_tokens_refresh_hash"),
    )
    op.create_index("ix_mcp_oauth_tokens_client_id", "mcp_oauth_tokens", ["client_id"], unique=False)
    op.create_index("ix_mcp_oauth_tokens_user_id", "mcp_oauth_tokens", ["user_id"], unique=False)
    op.create_index("ix_mcp_oauth_tokens_family_id", "mcp_oauth_tokens", ["token_family_id"], unique=False)
    op.create_index("ix_mcp_oauth_tokens_access_expires", "mcp_oauth_tokens", ["access_expires_at"], unique=False)
    op.create_index("ix_mcp_oauth_tokens_refresh_expires", "mcp_oauth_tokens", ["refresh_expires_at"], unique=False)
    op.create_index("ix_mcp_oauth_tokens_revoked_at", "mcp_oauth_tokens", ["revoked_at"], unique=False)

    op.create_table(
        "mcp_oauth_consents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("approved_scopes_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["mcp_oauth_clients.id"], name="fk_mcp_oauth_consents_client_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_mcp_oauth_consents_user_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "client_id", name="uq_mcp_oauth_consents_user_client"),
    )
    op.create_index("ix_mcp_oauth_consents_user_id", "mcp_oauth_consents", ["user_id"], unique=False)
    op.create_index("ix_mcp_oauth_consents_client_id", "mcp_oauth_consents", ["client_id"], unique=False)
    op.create_index("ix_mcp_oauth_consents_revoked_at", "mcp_oauth_consents", ["revoked_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mcp_oauth_consents_revoked_at", table_name="mcp_oauth_consents")
    op.drop_index("ix_mcp_oauth_consents_client_id", table_name="mcp_oauth_consents")
    op.drop_index("ix_mcp_oauth_consents_user_id", table_name="mcp_oauth_consents")
    op.drop_table("mcp_oauth_consents")

    op.drop_index("ix_mcp_oauth_tokens_revoked_at", table_name="mcp_oauth_tokens")
    op.drop_index("ix_mcp_oauth_tokens_refresh_expires", table_name="mcp_oauth_tokens")
    op.drop_index("ix_mcp_oauth_tokens_access_expires", table_name="mcp_oauth_tokens")
    op.drop_index("ix_mcp_oauth_tokens_family_id", table_name="mcp_oauth_tokens")
    op.drop_index("ix_mcp_oauth_tokens_user_id", table_name="mcp_oauth_tokens")
    op.drop_index("ix_mcp_oauth_tokens_client_id", table_name="mcp_oauth_tokens")
    op.drop_table("mcp_oauth_tokens")

    op.drop_index("ix_mcp_oauth_codes_consumed_at", table_name="mcp_oauth_authorization_codes")
    op.drop_index("ix_mcp_oauth_codes_expires_at", table_name="mcp_oauth_authorization_codes")
    op.drop_index("ix_mcp_oauth_codes_user_id", table_name="mcp_oauth_authorization_codes")
    op.drop_index("ix_mcp_oauth_codes_client_id", table_name="mcp_oauth_authorization_codes")
    op.drop_table("mcp_oauth_authorization_codes")

    op.drop_index("ix_mcp_oauth_clients_revoked_at", table_name="mcp_oauth_clients")
    op.drop_index("ix_mcp_oauth_clients_client_id", table_name="mcp_oauth_clients")
    op.drop_table("mcp_oauth_clients")
