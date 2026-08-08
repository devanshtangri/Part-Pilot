"""evolve MCP direct auth into named clients

Revision ID: 0015_mcp_direct_clients
Revises: 0014_api_keys
Create Date: 2026-08-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# PARTPILOT:MCP_NAMED_DIRECT_CLIENTS_MIGRATION:V627
revision = "0015_mcp_direct_clients"
down_revision = "0014_api_keys"
branch_labels = None
depends_on = None

DIRECT_MASTER_KEY = "mcp.direct_clients_enabled"
DIRECT_NO_AUTH_KEY = "mcp.direct_no_auth_enabled"
OLD_MODE_FIELDS = (
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
NEW_MODE_FIELDS = (
    "(revoked_at IS NOT NULL AND enabled = 0 AND key_ciphertext IS NULL AND "
    "key_digest IS NULL AND key_prefix IS NULL AND custom_header_name IS NULL AND "
    "trusted_networks_json IS NULL) OR (revoked_at IS NULL AND (" + OLD_MODE_FIELDS + "))"
)


def _verify_sqlite_foreign_keys(label: str) -> None:
    connection = op.get_bind()
    if connection.dialect.name != "sqlite":
        return
    violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(
            f"0015_mcp_direct_clients {label} created foreign-key violations: "
            f"{violations[:20]}"
        )


def _insert_setting_if_missing(key: str, json_text: str) -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "INSERT INTO app_settings "
            "(key,value_json,value_text,created_at,updated_at) "
            "SELECT :key, json(:value_json), NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
            "WHERE NOT EXISTS (SELECT 1 FROM app_settings WHERE key=:key)"
        ),
        {"key": key, "value_json": json_text},
    )


def _upgrade_sqlite(connection) -> None:
    connection.exec_driver_sql("ALTER TABLE mcp_direct_auth RENAME TO mcp_direct_auth_0014")
    connection.exec_driver_sql(
        """
        CREATE TABLE mcp_direct_auth (
            id INTEGER NOT NULL,
            mode VARCHAR(40) DEFAULT 'disabled' NOT NULL,
            key_ciphertext TEXT,
            key_digest VARCHAR(64),
            key_prefix VARCHAR(32),
            custom_header_name VARCHAR(120),
            rotated_at DATETIME,
            last_used_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            trusted_networks_json TEXT,
            name VARCHAR(120) DEFAULT 'Legacy direct client' NOT NULL,
            enabled BOOLEAN DEFAULT 1 NOT NULL,
            created_by_user_id INTEGER,
            last_resolved_client_ip VARCHAR(80),
            revoked_at DATETIME,
            PRIMARY KEY (id),
            CONSTRAINT ck_mcp_direct_auth_mode CHECK (mode IN ('disabled','bearer_key','custom_header','trusted_network')),
            CONSTRAINT ck_mcp_direct_auth_key_bundle CHECK ((key_ciphertext IS NULL AND key_digest IS NULL AND key_prefix IS NULL) OR (key_ciphertext IS NOT NULL AND key_digest IS NOT NULL AND key_prefix IS NOT NULL)),
            CONSTRAINT ck_mcp_direct_auth_mode_fields CHECK ((revoked_at IS NOT NULL AND enabled = 0 AND key_ciphertext IS NULL AND key_digest IS NULL AND key_prefix IS NULL AND custom_header_name IS NULL AND trusted_networks_json IS NULL) OR (revoked_at IS NULL AND ((mode = 'bearer_key' AND key_ciphertext IS NOT NULL AND custom_header_name IS NULL AND trusted_networks_json IS NULL) OR (mode = 'custom_header' AND key_ciphertext IS NOT NULL AND custom_header_name IS NOT NULL AND trusted_networks_json IS NULL) OR (mode = 'trusted_network' AND key_ciphertext IS NULL AND custom_header_name IS NULL AND trusted_networks_json IS NOT NULL AND length(trusted_networks_json) > 2) OR (mode = 'disabled' AND key_ciphertext IS NULL AND custom_header_name IS NULL AND trusted_networks_json IS NULL)))),
            CONSTRAINT ck_mcp_direct_auth_name_length CHECK (length(trim(name)) >= 1 AND length(name) <= 120),
            CONSTRAINT uq_mcp_direct_auth_key_digest UNIQUE (key_digest),
            CONSTRAINT fk_mcp_direct_auth_created_by_user_id FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
        )
        """
    )
    connection.exec_driver_sql(
        """
        INSERT INTO mcp_direct_auth (
            id,mode,key_ciphertext,key_digest,key_prefix,custom_header_name,
            rotated_at,last_used_at,created_at,updated_at,trusted_networks_json,
            name,enabled,created_by_user_id,last_resolved_client_ip,revoked_at
        )
        SELECT
            id,mode,key_ciphertext,key_digest,key_prefix,custom_header_name,
            rotated_at,last_used_at,created_at,updated_at,trusted_networks_json,
            'Legacy direct client',CASE WHEN mode='disabled' THEN 0 ELSE 1 END,
            NULL,NULL,NULL
        FROM mcp_direct_auth_0014
        """
    )
    connection.exec_driver_sql("DROP TABLE mcp_direct_auth_0014")
    for statement in (
        "CREATE INDEX ix_mcp_direct_auth_mode ON mcp_direct_auth (mode)",
        "CREATE INDEX ix_mcp_direct_auth_last_used_at ON mcp_direct_auth (last_used_at)",
        "CREATE INDEX ix_mcp_direct_auth_enabled ON mcp_direct_auth (enabled)",
        "CREATE INDEX ix_mcp_direct_auth_revoked_at ON mcp_direct_auth (revoked_at)",
        "CREATE INDEX ix_mcp_direct_auth_created_by_user_id ON mcp_direct_auth (created_by_user_id)",
    ):
        connection.exec_driver_sql(statement)


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        _upgrade_sqlite(connection)
    else:
        with op.batch_alter_table("mcp_direct_auth", recreate="always") as batch_op:
            batch_op.drop_constraint("ck_mcp_direct_auth_singleton", type_="check")
            batch_op.add_column(sa.Column("name", sa.String(length=120), nullable=False, server_default="Legacy direct client"))
            batch_op.add_column(sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
            batch_op.add_column(sa.Column("created_by_user_id", sa.Integer(), nullable=True))
            batch_op.add_column(sa.Column("last_resolved_client_ip", sa.String(length=80), nullable=True))
            batch_op.add_column(sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
            batch_op.drop_constraint("ck_mcp_direct_auth_mode_fields", type_="check")
            batch_op.create_check_constraint("ck_mcp_direct_auth_mode_fields", NEW_MODE_FIELDS)
            batch_op.create_foreign_key("fk_mcp_direct_auth_created_by_user_id", "users", ["created_by_user_id"], ["id"], ondelete="SET NULL")
            batch_op.create_check_constraint("ck_mcp_direct_auth_name_length", "length(trim(name)) >= 1 AND length(name) <= 120")
        op.create_index("ix_mcp_direct_auth_enabled", "mcp_direct_auth", ["enabled"], unique=False)
        op.create_index("ix_mcp_direct_auth_revoked_at", "mcp_direct_auth", ["revoked_at"], unique=False)
        op.create_index("ix_mcp_direct_auth_created_by_user_id", "mcp_direct_auth", ["created_by_user_id"], unique=False)
        connection.execute(sa.text("UPDATE mcp_direct_auth SET enabled=CASE WHEN mode='disabled' THEN 0 ELSE 1 END, name=CASE WHEN trim(coalesce(name,''))='' THEN 'Legacy direct client' ELSE name END"))

    active = connection.execute(
        sa.text(
            "SELECT CASE WHEN EXISTS(SELECT 1 FROM mcp_direct_auth "
            "WHERE revoked_at IS NULL AND enabled=1 AND mode!='disabled') "
            "THEN 1 ELSE 0 END"
        )
    ).scalar_one()
    _insert_setting_if_missing(DIRECT_MASTER_KEY, "true" if active else "false")
    _insert_setting_if_missing(DIRECT_NO_AUTH_KEY, "false")
    _verify_sqlite_foreign_keys("upgrade")


def downgrade() -> None:
    connection = op.get_bind()
    records = connection.execute(
        sa.text(
            "SELECT id,mode,key_ciphertext,key_digest,key_prefix,custom_header_name,"
            "trusted_networks_json,rotated_at,last_used_at,created_at,updated_at "
            "FROM mcp_direct_auth WHERE revoked_at IS NULL AND enabled=1 "
            "AND mode!='disabled' ORDER BY id"
        )
    ).mappings().all()
    if len(records) > 1:
        raise RuntimeError(
            "Cannot downgrade 0015_mcp_direct_clients while more than one active "
            "named direct client exists. Revoke extra direct clients first."
        )
    if records and records[0]["id"] != 1:
        row = records[0]
        connection.execute(sa.text("DELETE FROM mcp_direct_auth"))
        connection.execute(
            sa.text(
                "INSERT INTO mcp_direct_auth "
                "(id,mode,key_ciphertext,key_digest,key_prefix,custom_header_name,"
                "trusted_networks_json,rotated_at,last_used_at,created_at,updated_at,"
                "name,enabled,created_by_user_id,last_resolved_client_ip,revoked_at) "
                "VALUES (1,:mode,:key_ciphertext,:key_digest,:key_prefix,:custom_header_name,"
                ":trusted_networks_json,:rotated_at,:last_used_at,:created_at,:updated_at,"
                "'Legacy direct client',1,NULL,NULL,NULL)"
            ),
            dict(row),
        )
    elif not records:
        connection.execute(sa.text("DELETE FROM mcp_direct_auth WHERE id != 1"))
        if connection.execute(sa.text("SELECT count(*) FROM mcp_direct_auth WHERE id=1")).scalar_one() == 0:
            connection.execute(
                sa.text(
                    "INSERT INTO mcp_direct_auth "
                    "(id,mode,key_ciphertext,key_digest,key_prefix,custom_header_name,"
                    "trusted_networks_json,rotated_at,last_used_at,created_at,updated_at,"
                    "name,enabled,created_by_user_id,last_resolved_client_ip,revoked_at) "
                    "VALUES (1,'disabled',NULL,NULL,NULL,NULL,NULL,NULL,NULL,"
                    "CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'Legacy direct client',0,NULL,NULL,NULL)"
                )
            )
    else:
        connection.execute(sa.text("DELETE FROM mcp_direct_auth WHERE id != 1"))

    connection.execute(
        sa.text("DELETE FROM app_settings WHERE key IN (:master,:noauth)"),
        {"master": DIRECT_MASTER_KEY, "noauth": DIRECT_NO_AUTH_KEY},
    )

    op.drop_index("ix_mcp_direct_auth_created_by_user_id", table_name="mcp_direct_auth")
    op.drop_index("ix_mcp_direct_auth_revoked_at", table_name="mcp_direct_auth")
    op.drop_index("ix_mcp_direct_auth_enabled", table_name="mcp_direct_auth")
    with op.batch_alter_table("mcp_direct_auth", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_mcp_direct_auth_name_length", type_="check")
        batch_op.drop_constraint("fk_mcp_direct_auth_created_by_user_id", type_="foreignkey")
        batch_op.drop_constraint("ck_mcp_direct_auth_mode_fields", type_="check")
        batch_op.create_check_constraint("ck_mcp_direct_auth_mode_fields", OLD_MODE_FIELDS)
        batch_op.drop_column("revoked_at")
        batch_op.drop_column("last_resolved_client_ip")
        batch_op.drop_column("created_by_user_id")
        batch_op.drop_column("enabled")
        batch_op.drop_column("name")
        batch_op.create_check_constraint("ck_mcp_direct_auth_singleton", "id = 1")
    _verify_sqlite_foreign_keys("downgrade")
