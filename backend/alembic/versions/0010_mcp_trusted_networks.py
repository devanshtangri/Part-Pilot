"""add MCP trusted-network persistence

Revision ID: 0010_mcp_trusted_networks
Revises: 0009_mcp_direct_auth
Create Date: 2026-08-04

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# PARTPILOT:MCP_TRUSTED_NETWORK_MIGRATION:V503
revision = "0010_mcp_trusted_networks"
down_revision = "0009_mcp_direct_auth"
branch_labels = None
depends_on = None


_NEW_MODE_FIELDS = (
    "(mode = 'bearer_key' AND key_ciphertext IS NOT NULL AND "
    "custom_header_name IS NULL AND trusted_networks_json IS NULL) OR "
    "(mode = 'custom_header' AND key_ciphertext IS NOT NULL AND "
    "custom_header_name IS NOT NULL AND trusted_networks_json IS NULL) OR "
    "(mode = 'trusted_network' AND key_ciphertext IS NULL AND "
    "custom_header_name IS NULL AND trusted_networks_json IS NOT NULL AND "
    "length(trusted_networks_json) > 2) OR "
    "(mode = 'disabled' AND key_ciphertext IS NULL AND "
    "custom_header_name IS NULL AND trusted_networks_json IS NULL)"
)

_OLD_MODE_FIELDS = (
    "(mode = 'bearer_key' AND key_ciphertext IS NOT NULL AND custom_header_name IS NULL) OR "
    "(mode = 'custom_header' AND key_ciphertext IS NOT NULL AND custom_header_name IS NOT NULL) OR "
    "(mode IN ('disabled','trusted_network') AND key_ciphertext IS NULL AND custom_header_name IS NULL)"
)


def upgrade() -> None:
    with op.batch_alter_table("mcp_direct_auth", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("trusted_networks_json", sa.Text(), nullable=True))
        batch_op.drop_constraint("ck_mcp_direct_auth_mode_fields", type_="check")
        batch_op.create_check_constraint("ck_mcp_direct_auth_mode_fields", _NEW_MODE_FIELDS)


def downgrade() -> None:
    with op.batch_alter_table("mcp_direct_auth", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_mcp_direct_auth_mode_fields", type_="check")
        batch_op.create_check_constraint("ck_mcp_direct_auth_mode_fields", _OLD_MODE_FIELDS)
        batch_op.drop_column("trusted_networks_json")
