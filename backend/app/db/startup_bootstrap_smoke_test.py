from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path


# PARTPILOT:CONTAINER_DATABASE_BOOTSTRAP_SMOKE:V812
REVISION = "0022_mcp_inventory_part_lifecycle"
BACKEND_ROOT = Path(__file__).resolve().parents[2]


def run(args: list[str], env: dict[str, str], *, expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=BACKEND_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != expect:
        raise RuntimeError(
            f"Command returned {result.returncode}, expected {expect}: {args}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def env_for(path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PARTPILOT_DATABASE_URL"] = f"sqlite:///{path}"
    env["PARTPILOT_INSTANCE_SECRET_FILE"] = str(path.parent / ".instance-secret")
    return env


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def revision(path: Path) -> str:
    with connect(path) as connection:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        if row is None:
            raise RuntimeError("Alembic revision row missing")
        return str(row[0])


def policy(path: Path) -> dict[str, bool]:
    with connect(path) as connection:
        row = connection.execute(
            "SELECT value_json FROM app_settings WHERE key='mcp.tool_permissions'"
        ).fetchone()
        if row is None:
            raise RuntimeError("MCP tool policy missing")
        raw = row[0]
        if isinstance(raw, str):
            raw = json.loads(raw)
        if not isinstance(raw, dict):
            raise RuntimeError("MCP tool policy is not an object")
        return dict(raw)


def assert_integrity(path: Path) -> None:
    with connect(path) as connection:
        if connection.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise RuntimeError("SQLite quick_check failed")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("SQLite foreign_key_check failed")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="partpilot-startup-bootstrap-") as raw:
        root = Path(raw)
        database = root / "fresh.db"
        env = env_for(database)

        first = run([sys.executable, "-m", "app.db.startup_bootstrap"], env)
        if "fresh database detected" not in first.stdout or "seed complete" not in first.stdout:
            raise RuntimeError("Fresh bootstrap did not report migration + seed initialization")
        if revision(database) != REVISION:
            raise RuntimeError("Fresh bootstrap did not reach Alembic head")
        with connect(database) as connection:
            builtin = connection.execute(
                "SELECT COUNT(*) FROM part_types WHERE is_builtin=1"
            ).fetchone()[0]
            fields = connection.execute(
                "SELECT COUNT(*) FROM part_type_fields f "
                "JOIN part_types t ON t.id=f.part_type_id WHERE t.is_builtin=1"
            ).fetchone()[0]
            users = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            setup = connection.execute(
                "SELECT value_json FROM app_settings WHERE key='setup.completed'"
            ).fetchone()
            manufacturers = connection.execute("SELECT COUNT(*) FROM manufacturers").fetchone()[0]
            packages = connection.execute("SELECT COUNT(*) FROM packages").fetchone()[0]
        if builtin != 34 or fields != 153 or users != 0:
            raise RuntimeError(
                f"Unexpected fresh seed counts: builtin={builtin} fields={fields} users={users}"
            )
        if setup is None or json.loads(setup[0]) is not False:
            raise RuntimeError("Fresh setup.completed default is not false")
        if manufacturers < 1 or packages < 1:
            raise RuntimeError("Migration-seeded catalogues are missing")
        if len(policy(database)) != 14 or any(
            type(value) is not bool for value in policy(database).values()
        ):
            raise RuntimeError("Fresh MCP tool policy is not the fourteen-tool boolean shape")
        assert_integrity(database)

        # Simulate an interrupted seed after schema migration. Absence of the
        # setup marker must resume the idempotent seed and restore the missing
        # built-in field rather than leaving a permanently partial fresh install.
        with connect(database) as connection:
            connection.execute("DELETE FROM app_settings WHERE key='setup.completed'")
            connection.execute(
                "DELETE FROM part_type_fields WHERE field_key='temperature_coefficient' "
                "AND part_type_id=(SELECT id FROM part_types WHERE name='Resistor' AND is_builtin=1)"
            )
            connection.commit()
        resumed = run([sys.executable, "-m", "app.db.startup_bootstrap"], env)
        if "initialization marker missing" not in resumed.stdout or "seed complete" not in resumed.stdout:
            raise RuntimeError("Interrupted seed was not resumed")
        with connect(database) as connection:
            if connection.execute(
                "SELECT COUNT(*) FROM app_settings WHERE key='setup.completed'"
            ).fetchone()[0] != 1:
                raise RuntimeError("Resumed seed did not restore setup.completed")
            if connection.execute(
                "SELECT COUNT(*) FROM part_type_fields WHERE field_key='temperature_coefficient' "
                "AND part_type_id=(SELECT id FROM part_types WHERE name='Resistor' AND is_builtin=1)"
            ).fetchone()[0] != 1:
                raise RuntimeError("Resumed seed did not restore missing built-in field")

        # Once initialized, deliberately remove another built-in field and change
        # a preference. Normal restart must migrate only and never reseed these
        # user-customizable values.
        with connect(database) as connection:
            connection.execute(
                "DELETE FROM part_type_fields WHERE field_key='power_rating' "
                "AND part_type_id=(SELECT id FROM part_types WHERE name='Resistor' AND is_builtin=1)"
            )
            connection.execute(
                "UPDATE app_settings SET value_json='false' "
                "WHERE key='search.show_out_of_stock_section'"
            )
            connection.commit()
        second = run([sys.executable, "-m", "app.db.startup_bootstrap"], env)
        if "seed skipped; initialization marker exists" not in second.stdout:
            raise RuntimeError("Initialized database was unexpectedly reseeded")
        with connect(database) as connection:
            if connection.execute(
                "SELECT COUNT(*) FROM part_type_fields WHERE field_key='power_rating' "
                "AND part_type_id=(SELECT id FROM part_types WHERE name='Resistor' AND is_builtin=1)"
            ).fetchone()[0] != 0:
                raise RuntimeError("Normal restart recreated a deliberately removed template field")
            raw = connection.execute(
                "SELECT value_json FROM app_settings WHERE key='search.show_out_of_stock_section'"
            ).fetchone()[0]
            if json.loads(raw) is not False:
                raise RuntimeError("Normal restart overwrote a user preference")

        # An older Alembic-managed database must upgrade automatically without
        # crossing back into seed mode.
        run(["alembic", "downgrade", "0021_mcp_inventory_part_metadata_update"], env)
        if revision(database) != "0021_mcp_inventory_part_metadata_update":
            raise RuntimeError("Downgrade fixture did not reach 0021")
        upgraded = run([sys.executable, "-m", "app.db.startup_bootstrap"], env)
        if revision(database) != REVISION:
            raise RuntimeError("Managed older database did not upgrade to head")
        if "seed skipped; initialization marker exists" not in upgraded.stdout:
            raise RuntimeError("Managed upgrade unexpectedly reseeded data")
        with connect(database) as connection:
            if connection.execute(
                "SELECT COUNT(*) FROM part_type_fields WHERE field_key='power_rating' "
                "AND part_type_id=(SELECT id FROM part_types WHERE name='Resistor' AND is_builtin=1)"
            ).fetchone()[0] != 0:
                raise RuntimeError("Managed upgrade recreated a customized template field")
        if len(policy(database)) != 14:
            raise RuntimeError("Managed upgrade did not restore fourteen-tool policy shape")
        assert_integrity(database)

        # A non-empty unversioned database is ambiguous and must be rejected.
        malformed = root / "unversioned.db"
        with connect(malformed) as connection:
            connection.execute("CREATE TABLE legacy_probe (id INTEGER PRIMARY KEY, note TEXT)")
            connection.execute("INSERT INTO legacy_probe(note) VALUES ('preserve-me')")
            connection.commit()
        bad = run(
            [sys.executable, "-m", "app.db.startup_bootstrap"],
            env_for(malformed),
            expect=1,
        )
        if "not Alembic-managed" not in bad.stderr:
            raise RuntimeError("Unversioned database refusal was not explicit")
        with connect(malformed) as connection:
            if connection.execute("SELECT note FROM legacy_probe").fetchone() != ("preserve-me",):
                raise RuntimeError("Unversioned refusal changed the database")

        print("Startup bootstrap smoke PASS")


if __name__ == "__main__":
    main()
