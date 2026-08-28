from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

from app.core.config import get_settings


# PARTPILOT:CONTAINER_DATABASE_BOOTSTRAP:V812
class StartupDatabaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class DatabaseState:
    is_fresh: bool
    revision: str | None


def _sqlite_path(database_url: str) -> Path:
    try:
        url = make_url(database_url)
    except Exception as exc:
        raise StartupDatabaseError("Database URL could not be parsed.") from exc
    if url.get_backend_name() != "sqlite":
        raise StartupDatabaseError(
            "Automatic container database bootstrap currently supports SQLite only."
        )
    database = url.database
    if not database or database == ":memory:":
        raise StartupDatabaseError(
            "Automatic container database bootstrap requires a file-backed SQLite database."
        )
    return Path(database).expanduser().resolve()


def _user_tables(path: Path) -> set[str]:
    if not path.exists() or path.stat().st_size == 0:
        return set()
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise StartupDatabaseError("SQLite database could not be opened.") from exc
    try:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
    finally:
        connection.close()


def _read_revisions(path: Path) -> tuple[str, ...]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return tuple(
            str(row[0])
            for row in connection.execute(
                "SELECT version_num FROM alembic_version ORDER BY version_num"
            ).fetchall()
        )
    finally:
        connection.close()


def inspect_database(path: Path) -> DatabaseState:
    tables = _user_tables(path)
    if not tables:
        return DatabaseState(is_fresh=True, revision=None)
    if "alembic_version" not in tables:
        raise StartupDatabaseError(
            "Existing SQLite database contains application tables but is not "
            "Alembic-managed; refusing to guess or stamp its schema."
        )
    revisions = _read_revisions(path)
    if not revisions:
        if tables == {"alembic_version"}:
            return DatabaseState(is_fresh=True, revision=None)
        raise StartupDatabaseError(
            "Existing SQLite database has application tables but no Alembic revision; "
            "refusing an unsafe automatic migration."
        )
    if len(revisions) != 1:
        raise StartupDatabaseError(
            "Part Pilot expects exactly one Alembic revision in the SQLite database."
        )
    return DatabaseState(is_fresh=False, revision=revisions[0])


def _alembic_config(database_url: str) -> tuple[Config, str]:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    if len(heads) != 1:
        raise StartupDatabaseError(
            f"Part Pilot expects one Alembic head, found {len(heads)}."
        )
    return config, str(heads[0])


def _setting_exists(path: Path, key: str) -> bool:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        row = connection.execute(
            "SELECT 1 FROM app_settings WHERE key=? LIMIT 1", (key,)
        ).fetchone()
        return row is not None
    finally:
        connection.close()


def _verify_initialized_seed(path: Path) -> None:
    from app.db.seed import BUILTIN_PART_TYPES, DEFAULT_APP_SETTINGS

    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        quick = connection.execute("PRAGMA quick_check").fetchone()
        if quick != ("ok",):
            raise StartupDatabaseError("Fresh database failed SQLite quick_check.")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise StartupDatabaseError("Fresh database has foreign-key violations.")
        keys = {
            str(row[0])
            for row in connection.execute("SELECT key FROM app_settings").fetchall()
        }
        missing = set(DEFAULT_APP_SETTINGS) - keys
        if missing:
            raise StartupDatabaseError(
                f"Fresh database is missing required default settings: {sorted(missing)}"
            )
        builtin_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM part_types WHERE is_builtin=1"
            ).fetchone()[0]
        )
        if builtin_count < len(BUILTIN_PART_TYPES):
            raise StartupDatabaseError(
                "Fresh database did not receive the complete built-in part-type catalogue."
            )
        raw_policy = connection.execute(
            "SELECT value_json FROM app_settings WHERE key='mcp.tool_permissions'"
        ).fetchone()
        if raw_policy is None:
            raise StartupDatabaseError("Fresh database is missing MCP tool permissions.")
        policy = raw_policy[0]
        if isinstance(policy, str):
            policy = json.loads(policy)
        expected = DEFAULT_APP_SETTINGS["mcp.tool_permissions"]["value_json"]
        if not isinstance(policy, dict) or set(policy) != set(expected):
            raise StartupDatabaseError(
                "Fresh database MCP tool-permission catalogue is incomplete."
            )
        if any(type(value) is not bool for value in policy.values()):
            raise StartupDatabaseError(
                "Fresh database MCP tool-permission values are not booleans."
            )
    finally:
        connection.close()


def bootstrap_database() -> None:
    settings = get_settings()
    database_path = _sqlite_path(settings.database_url)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    before = inspect_database(database_path)
    if before.is_fresh:
        print("Part Pilot database bootstrap: fresh database detected", flush=True)
    else:
        print(
            "Part Pilot database bootstrap: existing Alembic database at "
            f"{before.revision}",
            flush=True,
        )

    config, expected_head = _alembic_config(settings.database_url)
    try:
        command.upgrade(config, "head")
    except Exception as exc:
        raise StartupDatabaseError(
            f"Alembic upgrade to {expected_head} failed."
        ) from exc

    after = inspect_database(database_path)
    if after.is_fresh or after.revision != expected_head:
        raise StartupDatabaseError(
            f"Database did not reach Alembic head {expected_head}."
        )
    print(
        f"Part Pilot database bootstrap: Alembic head {expected_head}",
        flush=True,
    )

    needs_seed = before.is_fresh or not _setting_exists(
        database_path, "setup.completed"
    )
    if needs_seed:
        if before.is_fresh:
            print(
                "Part Pilot database bootstrap: initializing fresh defaults",
                flush=True,
            )
        else:
            print(
                "Part Pilot database bootstrap: initialization marker missing; "
                "resuming idempotent seed",
                flush=True,
            )
        from app.db.seed import (
            seed_builtin_part_types,
            seed_builtin_template_fields,
            seed_default_app_settings,
        )
        from app.db.session import SessionLocal, dispose_database_engine

        db = SessionLocal()
        try:
            created_types = seed_builtin_part_types(db)
            created_fields = seed_builtin_template_fields(db)
            created_settings = seed_default_app_settings(db)
        finally:
            db.close()
            dispose_database_engine()
        _verify_initialized_seed(database_path)
        if not _setting_exists(database_path, "setup.completed"):
            raise StartupDatabaseError(
                "Fresh database initialization did not create setup.completed."
            )
        print(
            "Part Pilot database bootstrap: seed complete "
            f"(types={created_types}, fields={created_fields}, settings={created_settings})",
            flush=True,
        )
    else:
        print(
            "Part Pilot database bootstrap: seed skipped; initialization marker exists",
            flush=True,
        )


def main() -> int:
    try:
        bootstrap_database()
    except StartupDatabaseError as exc:
        print(f"Part Pilot database bootstrap fatal: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
