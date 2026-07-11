"""add user display name

Revision ID: 0003_user_display_name
Revises: 0002_schema_hardening
Create Date: 2026-07-07

"""

from alembic import op
import sqlalchemy as sa


revision = "0003_user_display_name"
down_revision = "0002_schema_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "display_name",
            sa.String(length=160),
            nullable=False,
            server_default="Local User",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "display_name")
