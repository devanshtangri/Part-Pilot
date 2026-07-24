# add reusable manufacturers
#
# Revision ID: 0004_manufacturers
# Revises: 0003_user_display_name
# Create Date: 2026-07-24

from __future__ import annotations

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "0004_manufacturers"
down_revision = "0003_user_display_name"
branch_labels = None
depends_on = None


SEEDED_MANUFACTURERS = (
    "Espressif Systems",
    "Arduino",
    "NXP Semiconductors",
    "STMicroelectronics",
    "Texas Instruments",
    "Microchip Technology",
    "Nordic Semiconductor",
    "Raspberry Pi",
)


def _normalize_name(value: str) -> str:
    return " ".join(value.split()).casefold()


def upgrade() -> None:
    op.create_table(
        "manufacturers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column(
            "normalized_name",
            sa.String(length=220),
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
        sa.UniqueConstraint(
            "name",
            name="uq_manufacturers_name",
        ),
        sa.UniqueConstraint(
            "normalized_name",
            name="uq_manufacturers_normalized_name",
        ),
    )
    op.create_index(
        "ix_manufacturers_name",
        "manufacturers",
        ["name"],
        unique=False,
    )
    op.create_index(
        "ix_manufacturers_normalized_name",
        "manufacturers",
        ["normalized_name"],
        unique=True,
    )

    with op.batch_alter_table(
        "parts",
        recreate="always",
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "manufacturer_id",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.create_index(
            "ix_parts_manufacturer_id",
            ["manufacturer_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_parts_manufacturer_id_manufacturers",
            "manufacturers",
            ["manufacturer_id"],
            ["id"],
            ondelete="SET NULL",
        )

    bind = op.get_bind()
    now = datetime.now(timezone.utc)

    manufacturer_table = sa.table(
        "manufacturers",
        sa.column("name", sa.String()),
        sa.column("normalized_name", sa.String()),
        sa.column("is_builtin", sa.Boolean()),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    op.bulk_insert(
        manufacturer_table,
        [
            {
                "name": name,
                "normalized_name": _normalize_name(name),
                "is_builtin": True,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            for name in SEEDED_MANUFACTURERS
        ],
    )

    legacy_rows = bind.execute(
        sa.text(
            "\n            select\n                pfv.part_id as part_id,\n                trim(pfv.value_text) as manufacturer_name\n            from part_field_values as pfv\n            join part_type_fields as ptf\n              on ptf.id = pfv.field_id\n            join parts as p\n              on p.id = pfv.part_id\n            where lower(replace(trim(ptf.field_key), ' ', '_'))\n                  in ('manufacturer', 'manufacturer_name')\n              and pfv.value_text is not null\n              and length(trim(pfv.value_text)) > 0\n              and p.manufacturer_id is null\n            order by pfv.part_id\n            "
        )
    ).mappings().all()

    for row in legacy_rows:
        display_name = " ".join(
            str(row["manufacturer_name"]).split()
        )
        normalized = _normalize_name(display_name)

        manufacturer_id = bind.execute(
            sa.text(
                '\n                select id\n                from manufacturers\n                where normalized_name = :normalized_name\n                '
            ),
            {"normalized_name": normalized},
        ).scalar_one_or_none()

        if manufacturer_id is None:
            result = bind.execute(
                sa.text(
                    '\n                    insert into manufacturers (\n                        name,\n                        normalized_name,\n                        is_builtin,\n                        is_active,\n                        created_at,\n                        updated_at\n                    )\n                    values (\n                        :name,\n                        :normalized_name,\n                        0,\n                        1,\n                        :created_at,\n                        :updated_at\n                    )\n                    '
                ),
                {
                    "name": display_name,
                    "normalized_name": normalized,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            manufacturer_id = result.lastrowid

        bind.execute(
            sa.text(
                '\n                update parts\n                set manufacturer_id = :manufacturer_id\n                where id = :part_id\n                  and manufacturer_id is null\n                '
            ),
            {
                "manufacturer_id": manufacturer_id,
                "part_id": row["part_id"],
            },
        )


def downgrade() -> None:
    with op.batch_alter_table(
        "parts",
        recreate="always",
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_parts_manufacturer_id_manufacturers",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_parts_manufacturer_id")
        batch_op.drop_column("manufacturer_id")

    op.drop_index(
        "ix_manufacturers_normalized_name",
        table_name="manufacturers",
    )
    op.drop_index(
        "ix_manufacturers_name",
        table_name="manufacturers",
    )
    op.drop_table("manufacturers")
