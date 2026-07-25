# add reusable package and form-factor catalogue
#
# Revision ID: 0005_packages
# Revises: 0004_manufacturers
# Create Date: 2026-07-25

from __future__ import annotations

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "0005_packages"
down_revision = "0004_manufacturers"
branch_labels = None
depends_on = None


SEEDED_PACKAGES = (
    "TO-92",
    "TO-220",
    "TO-247",
    "SOT-23",
    "SOT-223",
    "SOIC-8",
    "TSSOP",
    "QFN",
    "DIP",
    "SIP",
    "BGA",
    "LQFP",
    "TQFP",
    "0603",
    "0805",
    "1206",
    "Axial",
    "Radial",
    "Module",
    "Breakout Board",
    "Development Board",
)


def _normalize_name(value: str) -> str:
    return " ".join(value.split()).casefold()


def upgrade() -> None:
    op.create_table(
        "packages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "normalized_name",
            sa.String(length=160),
            nullable=False,
        ),
        sa.Column(
            "is_builtin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.UniqueConstraint("name", name="uq_packages_name"),
        sa.UniqueConstraint(
            "normalized_name",
            name="uq_packages_normalized_name",
        ),
    )
    op.create_index(
        "ix_packages_name",
        "packages",
        ["name"],
        unique=False,
    )
    op.create_index(
        "ix_packages_normalized_name",
        "packages",
        ["normalized_name"],
        unique=True,
    )

    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    package_table = sa.table(
        "packages",
        sa.column("name", sa.String()),
        sa.column("normalized_name", sa.String()),
        sa.column("is_builtin", sa.Boolean()),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    op.bulk_insert(
        package_table,
        [
            {
                "name": name,
                "normalized_name": _normalize_name(name),
                "is_builtin": True,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            for name in SEEDED_PACKAGES
        ],
    )

    existing_names = bind.execute(
        sa.text(
            "select distinct trim(package) from parts "
            "where package is not null "
            "and length(trim(package)) > 0 "
            "order by lower(trim(package))"
        )
    ).scalars().all()

    for raw_name in existing_names:
        display_name = " ".join(str(raw_name).split())
        normalized_name = _normalize_name(display_name)
        exists = bind.execute(
            sa.text(
                "select id from packages "
                "where normalized_name = :normalized_name"
            ),
            {"normalized_name": normalized_name},
        ).scalar_one_or_none()
        if exists is not None:
            continue

        bind.execute(
            sa.text(
                "insert into packages ("
                "name, normalized_name, is_builtin, is_active, "
                "created_at, updated_at"
                ") values ("
                ":name, :normalized_name, 0, 1, "
                ":created_at, :updated_at"
                ")"
            ),
            {
                "name": display_name,
                "normalized_name": normalized_name,
                "created_at": now,
                "updated_at": now,
            },
        )


def downgrade() -> None:
    op.drop_index(
        "ix_packages_normalized_name",
        table_name="packages",
    )
    op.drop_index("ix_packages_name", table_name="packages")
    op.drop_table("packages")
