from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3

from app.core.config import get_settings
from app.db.base import Base
import app.models  # noqa: F401 - register ORM models


# PARTPILOT:MCP_OAUTH_SCHEMA_SMOKE:V465
EXPECTED_HEAD = "0021_mcp_inventory_part_metadata_update"
TABLES = (
    "mcp_oauth_clients",
    "mcp_oauth_authorization_codes",
    "mcp_oauth_tokens",
    "mcp_oauth_consents",
)


class SmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeFailure(message)


def sqlite_path() -> Path:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"MCP OAuth smoke requires SQLite, got {url!r}")
    return Path(url[len(prefix):]).resolve()


@contextmanager
def connection():
    db = sqlite3.connect(sqlite_path(), timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
    finally:
        db.close()


def table_sql(db: sqlite3.Connection, table: str) -> str:
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    if row is None or not row[0]:
        fail(f"Missing OAuth table: {table}")
    return str(row[0])


def index_names(db: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in db.execute(f'PRAGMA index_list("{table}")')}


def foreign_keys(db: sqlite3.Connection, table: str) -> set[tuple[str, str, str, str]]:
    return {
        (str(row[2]), str(row[3]), str(row[4]), str(row[6]).upper())
        for row in db.execute(f'PRAGMA foreign_key_list("{table}")')
    }


def check_schema() -> None:
    with connection() as db:
        head = db.execute("SELECT version_num FROM alembic_version").fetchone()
        if head is None or str(head[0]) != EXPECTED_HEAD:
            fail(f"Expected Alembic {EXPECTED_HEAD}, got {head}")
        if str(db.execute("PRAGMA integrity_check").fetchone()[0]).lower() != "ok":
            fail("SQLite integrity_check failed")
        violations = list(db.execute("PRAGMA foreign_key_check"))
        if violations:
            fail(f"OAuth schema foreign-key violations: {violations[:20]}")

        expected_columns = {
            "mcp_oauth_clients": {
                "id", "client_id", "client_secret_hash", "client_name",
                "client_uri", "redirect_uris_json", "grant_types_json",
                "response_types_json", "token_endpoint_auth_method",
                "metadata_json", "denied_tools_json", "registered_by_user_id", "created_at", "updated_at", "revoked_at",
            },
            "mcp_oauth_authorization_codes": {
                "id", "code_hash", "client_id", "user_id", "redirect_uri",
                "scopes_json", "code_challenge", "code_challenge_method",
                "resource_uri", "expires_at", "consumed_at", "created_at",
            },
            "mcp_oauth_tokens": {
                "id", "access_token_hash", "refresh_token_hash",
                "token_family_id", "client_id", "user_id", "scopes_json",
                "resource_uri", "access_expires_at", "refresh_expires_at",
                "last_used_at", "revoked_at", "replaced_by_token_id",
                "replay_detected_at", "created_at", "updated_at",
            },
            "mcp_oauth_consents": {
                "id", "user_id", "client_id", "approved_scopes_json",
                "created_at", "updated_at", "revoked_at",
            },
        }
        for table, expected in expected_columns.items():
            actual = {str(row[1]) for row in db.execute(f'PRAGMA table_info("{table}")')}
            if actual != expected:
                fail(f"Unexpected {table} columns: {sorted(actual)}")

        required_sql = {
            "mcp_oauth_clients": (
                "ck_mcp_oauth_clients_auth_method",
                "uq_mcp_oauth_clients_client_id",
                "uq_mcp_oauth_clients_secret_hash",
            ),
            "mcp_oauth_authorization_codes": (
                "ck_mcp_oauth_codes_pkce_method",
                "uq_mcp_oauth_codes_code_hash",
            ),
            "mcp_oauth_tokens": (
                "ck_mcp_oauth_tokens_refresh_pair",
                "uq_mcp_oauth_tokens_access_hash",
                "uq_mcp_oauth_tokens_refresh_hash",
            ),
            "mcp_oauth_consents": (
                "uq_mcp_oauth_consents_user_client",
            ),
        }
        for table, markers in required_sql.items():
            sql = table_sql(db, table)
            for marker in markers:
                if marker not in sql:
                    fail(f"{table} is missing {marker}")

        expected_indexes = {
            "mcp_oauth_clients": {
                "ix_mcp_oauth_clients_client_id",
                "ix_mcp_oauth_clients_revoked_at",
                "ix_mcp_oauth_clients_registered_by_user_id",
            },
            "mcp_oauth_authorization_codes": {
                "ix_mcp_oauth_codes_client_id",
                "ix_mcp_oauth_codes_user_id",
                "ix_mcp_oauth_codes_expires_at",
                "ix_mcp_oauth_codes_consumed_at",
            },
            "mcp_oauth_tokens": {
                "ix_mcp_oauth_tokens_client_id",
                "ix_mcp_oauth_tokens_user_id",
                "ix_mcp_oauth_tokens_family_id",
                "ix_mcp_oauth_tokens_access_expires",
                "ix_mcp_oauth_tokens_refresh_expires",
                "ix_mcp_oauth_tokens_revoked_at",
            },
            "mcp_oauth_consents": {
                "ix_mcp_oauth_consents_user_id",
                "ix_mcp_oauth_consents_client_id",
                "ix_mcp_oauth_consents_revoked_at",
            },
        }
        for table, expected in expected_indexes.items():
            actual = index_names(db, table)
            if not expected.issubset(actual):
                fail(f"{table} indexes are incomplete: {sorted(actual)}")

        expected_fks = {
            "mcp_oauth_clients": {
                ("users", "registered_by_user_id", "id", "SET NULL"),
            },
            "mcp_oauth_authorization_codes": {
                ("mcp_oauth_clients", "client_id", "id", "CASCADE"),
                ("users", "user_id", "id", "CASCADE"),
            },
            "mcp_oauth_tokens": {
                ("mcp_oauth_clients", "client_id", "id", "CASCADE"),
                ("users", "user_id", "id", "CASCADE"),
                ("mcp_oauth_tokens", "replaced_by_token_id", "id", "SET NULL"),
            },
            "mcp_oauth_consents": {
                ("mcp_oauth_clients", "client_id", "id", "CASCADE"),
                ("users", "user_id", "id", "CASCADE"),
            },
        }
        for table, expected in expected_fks.items():
            actual = foreign_keys(db, table)
            if actual != expected:
                fail(f"Unexpected {table} foreign keys: {sorted(actual)}")

        metadata_tables = Base.metadata.tables
        for table in TABLES:
            if table not in metadata_tables:
                fail(f"ORM metadata is missing {table}")
            db_columns = {str(row[1]) for row in db.execute(f'PRAGMA table_info("{table}")')}
            model_columns = set(metadata_tables[table].columns.keys())
            if db_columns != model_columns:
                fail(
                    f"ORM/database column mismatch for {table}: "
                    f"database={sorted(db_columns)} model={sorted(model_columns)}"
                )


def expect_integrity_error(db: sqlite3.Connection, sql: str, params: tuple[object, ...]) -> None:
    db.execute("SAVEPOINT expected_failure")
    try:
        db.execute(sql, params)
    except sqlite3.IntegrityError:
        db.execute("ROLLBACK TO expected_failure")
        db.execute("RELEASE expected_failure")
    else:
        db.execute("ROLLBACK TO expected_failure")
        db.execute("RELEASE expected_failure")
        fail("OAuth schema accepted an invalid fixture")


def check_constraints_and_cascades() -> None:
    with connection() as db:
        user = db.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
        if user is None:
            fail("OAuth schema smoke requires one existing user")
        user_id = int(user[0])
        before = {
            table: int(db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            for table in TABLES
        }
        db.execute("BEGIN")
        try:
            cursor = db.execute(
                "INSERT INTO mcp_oauth_clients "
                "(client_id,client_name,redirect_uris_json,grant_types_json,"
                "response_types_json,token_endpoint_auth_method) "
                "VALUES (?,?,?,?,?,?)",
                (
                    "pp-smoke-client",
                    "Part Pilot OAuth Smoke",
                    json.dumps(["https://example.invalid/callback"]),
                    json.dumps(["authorization_code", "refresh_token"]),
                    json.dumps(["code"]),
                    "none",
                ),
            )
            client_pk = int(cursor.lastrowid)
            db.execute(
                "INSERT INTO mcp_oauth_consents "
                "(user_id,client_id,approved_scopes_json) VALUES (?,?,?)",
                (user_id, client_pk, json.dumps(["mcp:read"])),
            )
            db.execute(
                "INSERT INTO mcp_oauth_authorization_codes "
                "(code_hash,client_id,user_id,redirect_uri,scopes_json,"
                "code_challenge,code_challenge_method,resource_uri,expires_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    "code-hash-smoke",
                    client_pk,
                    user_id,
                    "https://example.invalid/callback",
                    json.dumps(["mcp:read"]),
                    "A" * 43,
                    "S256",
                    "https://example.invalid/mcp",
                    "2099-01-01T00:00:00+00:00",
                ),
            )
            db.execute(
                "INSERT INTO mcp_oauth_tokens "
                "(access_token_hash,refresh_token_hash,token_family_id,client_id,"
                "user_id,scopes_json,resource_uri,access_expires_at,refresh_expires_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    "access-hash-smoke",
                    "refresh-hash-smoke",
                    "family-smoke",
                    client_pk,
                    user_id,
                    json.dumps(["mcp:read"]),
                    "https://example.invalid/mcp",
                    "2099-01-01T00:00:00+00:00",
                    "2099-02-01T00:00:00+00:00",
                ),
            )

            expect_integrity_error(
                db,
                "INSERT INTO mcp_oauth_clients "
                "(client_id,client_name,redirect_uris_json,grant_types_json,"
                "response_types_json,token_endpoint_auth_method) "
                "VALUES (?,?,?,?,?,?)",
                (
                    "bad-auth-method",
                    "Bad",
                    "[]",
                    "[]",
                    "[]",
                    "private_key_jwt",
                ),
            )
            expect_integrity_error(
                db,
                "INSERT INTO mcp_oauth_authorization_codes "
                "(code_hash,client_id,user_id,redirect_uri,scopes_json,"
                "code_challenge,code_challenge_method,resource_uri,expires_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    "bad-code-hash",
                    client_pk,
                    user_id,
                    "https://example.invalid/callback",
                    "[]",
                    "challenge",
                    "plain",
                    "https://example.invalid/mcp",
                    "2099-01-01T00:00:00+00:00",
                ),
            )
            expect_integrity_error(
                db,
                "INSERT INTO mcp_oauth_tokens "
                "(access_token_hash,refresh_token_hash,token_family_id,client_id,"
                "user_id,scopes_json,resource_uri,access_expires_at,refresh_expires_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    "bad-access-hash",
                    "unpaired-refresh",
                    "bad-family",
                    client_pk,
                    user_id,
                    "[]",
                    "https://example.invalid/mcp",
                    "2099-01-01T00:00:00+00:00",
                    None,
                ),
            )
            expect_integrity_error(
                db,
                "INSERT INTO mcp_oauth_consents "
                "(user_id,client_id,approved_scopes_json) VALUES (?,?,?)",
                (user_id, client_pk, "[]"),
            )

            db.execute("DELETE FROM mcp_oauth_clients WHERE id=?", (client_pk,))
            for table in TABLES:
                remaining = int(db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
                if remaining != before[table]:
                    fail(f"Client cascade did not restore {table} to baseline")
        finally:
            db.rollback()

        after = {
            table: int(db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            for table in TABLES
        }
        if after != before:
            fail(f"OAuth fixture rollback changed table counts: {before} -> {after}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema-only", action="store_true")
    args = parser.parse_args()
    check_schema()
    if not args.schema_only:
        check_constraints_and_cascades()
    print(
        "[PASS] MCP OAuth persistence schema, ORM metadata, constraints, "
        "indexes, foreign keys and isolated fixtures are aligned"
    )


if __name__ == "__main__":
    main()
