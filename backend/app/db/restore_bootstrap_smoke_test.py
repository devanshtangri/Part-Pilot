from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile

from app.core.config import get_settings
from app.schemas.restores import (
    RestoreBootstrapResult,
)
from app.services.backups import (
    create_backup_artifact,
    remove_backup_operation_directory,
    sqlite_path_from_database_url,
)
from app.services.restore_bootstrap import (
    BOOTSTRAP_EVENT_FAILURE,
    BOOTSTRAP_EVENT_SUCCESS,
    prepare_restore_commit_job,
    process_pending_restore,
)
from app.services.restores import (
    RESTORE_RESULT_FILENAME,
    stage_restore_archive,
)


class RestoreBootstrapSmokeFailure(
    RuntimeError
):
    pass


def fail(message: str) -> None:
    raise RestoreBootstrapSmokeFailure(
        message
    )


def copy_database(
    source: Path,
    destination: Path,
) -> None:
    source_connection = sqlite3.connect(
        source
    )
    destination_connection = sqlite3.connect(
        destination
    )
    try:
        source_connection.backup(
            destination_connection
        )
    finally:
        destination_connection.close()
        source_connection.close()
    os.chmod(destination, 0o600)


def setting_value(
    database_path: Path,
    key: str,
):
    connection = sqlite3.connect(
        database_path
    )
    try:
        raw = connection.execute(
            "SELECT value_json FROM app_settings "
            "WHERE key=?",
            (key,),
        ).fetchone()[0]
        return json.loads(raw)
    finally:
        connection.close()


def counts(
    database_path: Path,
) -> dict[str, int]:
    connection = sqlite3.connect(
        database_path
    )
    try:
        return {
            table: int(
                connection.execute(
                    f'SELECT COUNT(*) FROM "{table}"'
                ).fetchone()[0]
            )
            for table in (
                "users",
                "sessions",
                "parts",
                "projects",
                "reservations",
                "stock_movements",
                "audit_log",
            )
        }
    finally:
        connection.close()


def first_active_user(
    database_path: Path,
) -> tuple[int, str]:
    connection = sqlite3.connect(
        database_path
    )
    try:
        row = connection.execute(
            "SELECT id, username FROM users "
            "WHERE is_active=1 ORDER BY id LIMIT 1"
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        fail(
            "Copied database has no active user."
        )
    return int(row[0]), str(row[1])


def change_display_name(
    database_path: Path,
    value: str,
) -> None:
    connection = sqlite3.connect(
        database_path
    )
    try:
        connection.execute(
            "UPDATE app_settings "
            "SET value_json=? "
            "WHERE key='app.display_name'",
            (
                json.dumps(value),
            ),
        )
        connection.commit()
    finally:
        connection.close()


def load_result(
    operation: Path,
) -> RestoreBootstrapResult:
    payload = json.loads(
        (
            operation
            / RESTORE_RESULT_FILENAME
        ).read_text(
            encoding="utf-8"
        )
    )
    return RestoreBootstrapResult.model_validate(
        payload
    )


def check_noop(
    root: Path,
    source_database: Path,
) -> None:
    live = root / "noop.db"
    copy_database(
        source_database,
        live,
    )
    before = live.read_bytes()
    result = process_pending_restore(
        live_database_path=live,
        staging_root=(
            root / "missing-staging"
        ),
        now=datetime(
            2026,
            8,
            2,
            1,
            5,
            tzinfo=timezone.utc,
        ),
    )
    if result is not None or live.read_bytes() != before:
        fail(
            "No-op bootstrap changed a database."
        )


def stage_candidate(
    *,
    source_database: Path,
    live_database: Path,
    artifact_root: Path,
    staging_root: Path,
    actor_user_id: int,
    actor_username: str,
    display_name: str,
    now: datetime,
):
    candidate = (
        artifact_root
        / (
            display_name.lower().replace(
                " ",
                "-",
            )
            + ".db"
        )
    )
    copy_database(
        source_database,
        candidate,
    )
    change_display_name(
        candidate,
        display_name,
    )
    artifact = create_backup_artifact(
        candidate,
        artifact_root,
        created_at_utc=now,
    )
    try:
        with artifact.archive_path.open(
            "rb"
        ) as source:
            staged = stage_restore_archive(
                source,
                original_filename=(
                    artifact.filename
                ),
                actor_user_id=(
                    actor_user_id
                ),
                actor_username=(
                    actor_username
                ),
                staging_root=staging_root,
                now=now,
            )
        prepare_restore_commit_job(
            staged.token,
            actor_user_id=(
                actor_user_id
            ),
            actor_username=(
                actor_username
            ),
            live_database_path=(
                live_database
            ),
            staging_root=staging_root,
            now=now,
        )
        return staged
    finally:
        remove_backup_operation_directory(
            artifact.operation_directory,
            expected_parent=artifact_root,
        )
        candidate.unlink(
            missing_ok=True
        )


def check_success(
    root: Path,
    source_database: Path,
) -> None:
    case = root / "success"
    case.mkdir(mode=0o700)
    live = case / "partpilot.db"
    artifact_root = case / "artifacts"
    artifact_root.mkdir(mode=0o700)
    staging_root = case / ".partpilot-restore"
    copy_database(
        source_database,
        live,
    )
    actor_user_id, actor_username = (
        first_active_user(live)
    )
    before_counts = counts(live)
    before_display_name = setting_value(
        live,
        "app.display_name",
    )
    now = datetime(
        2026,
        8,
        2,
        1,
        6,
        tzinfo=timezone.utc,
    )
    staged = stage_candidate(
        source_database=source_database,
        live_database=live,
        artifact_root=artifact_root,
        staging_root=staging_root,
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        display_name="Restored Bootstrap Smoke",
        now=now,
    )
    result = process_pending_restore(
        live_database_path=live,
        staging_root=staging_root,
        now=now,
    )
    if (
        result is None
        or result.status != "succeeded"
        or result.event_type
        != BOOTSTRAP_EVENT_SUCCESS
        or not result.rollback_verified
        or result.sessions_invalidated
        != before_counts["sessions"]
    ):
        fail(
            f"Successful bootstrap result is incorrect: {result}"
        )
    if (
        setting_value(
            live,
            "app.display_name",
        )
        != "Restored Bootstrap Smoke"
        or setting_value(
            live,
            "app.display_name",
        )
        == before_display_name
    ):
        fail(
            "Successful bootstrap did not install the candidate."
        )
    after_counts = counts(live)
    if (
        after_counts["sessions"] != 0
        or after_counts["audit_log"]
        != before_counts["audit_log"] + 1
    ):
        fail(
            "Successful bootstrap did not invalidate sessions "
            "and append exactly one audit."
        )
    connection = sqlite3.connect(
        live
    )
    try:
        audit = connection.execute(
            "SELECT event_type, actor_type, actor_user_id "
            "FROM audit_log WHERE id=?",
            (result.audit_id,),
        ).fetchone()
        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]
        foreign_keys = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
    finally:
        connection.close()
    if (
        audit
        != (
            BOOTSTRAP_EVENT_SUCCESS,
            "user",
            actor_user_id,
        )
        or integrity != "ok"
        or foreign_keys
    ):
        fail(
            "Successful bootstrap audit or SQLite verification failed."
        )
    loaded_result = load_result(
        staged.operation_directory
    )
    if loaded_result != result:
        fail(
            "Persisted successful result differs from runtime result."
        )


def check_rollback(
    root: Path,
    source_database: Path,
) -> None:
    case = root / "rollback"
    case.mkdir(mode=0o700)
    live = case / "partpilot.db"
    artifact_root = case / "artifacts"
    artifact_root.mkdir(mode=0o700)
    staging_root = case / ".partpilot-restore"
    copy_database(
        source_database,
        live,
    )
    actor_user_id, actor_username = (
        first_active_user(live)
    )
    before_counts = counts(live)
    before_display_name = setting_value(
        live,
        "app.display_name",
    )
    now = datetime(
        2026,
        8,
        2,
        1,
        7,
        tzinfo=timezone.utc,
    )
    staged = stage_candidate(
        source_database=source_database,
        live_database=live,
        artifact_root=artifact_root,
        staging_root=staging_root,
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        display_name="Rollback Candidate Smoke",
        now=now,
    )

    def inject(phase: str) -> None:
        if phase == "after_replace":
            raise RuntimeError(
                "injected post-replacement failure"
            )

    result = process_pending_restore(
        live_database_path=live,
        staging_root=staging_root,
        now=now,
        fault_injector=inject,
    )
    if (
        result is None
        or result.status != "failed"
        or result.event_type
        != BOOTSTRAP_EVENT_FAILURE
        or not result.rollback_verified
        or not result.error_code
    ):
        fail(
            f"Rollback bootstrap result is incorrect: {result}"
        )
    if setting_value(
        live,
        "app.display_name",
    ) != before_display_name:
        fail(
            "Rollback did not restore the original database."
        )
    after_counts = counts(live)
    expected_counts = dict(
        before_counts
    )
    expected_counts["audit_log"] += 1
    if after_counts != expected_counts:
        fail(
            "Rollback changed data beyond one failure audit: "
            f"{before_counts} -> {after_counts}"
        )
    connection = sqlite3.connect(
        live
    )
    try:
        audit = connection.execute(
            "SELECT event_type, actor_type, actor_user_id "
            "FROM audit_log WHERE id=?",
            (result.audit_id,),
        ).fetchone()
        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]
        foreign_keys = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
    finally:
        connection.close()
    if (
        audit
        != (
            BOOTSTRAP_EVENT_FAILURE,
            "user",
            actor_user_id,
        )
        or integrity != "ok"
        or foreign_keys
    ):
        fail(
            "Rollback failure audit or SQLite verification failed."
        )
    loaded_result = load_result(
        staged.operation_directory
    )
    if loaded_result != result:
        fail(
            "Persisted rollback result differs from runtime result."
        )


def main() -> None:
    source_database = (
        sqlite_path_from_database_url(
            get_settings().database_url
        )
    )
    root = Path(
        tempfile.mkdtemp(
            prefix="partpilot-restore-bootstrap-smoke-"
        )
    )
    os.chmod(root, 0o700)
    try:
        check_noop(
            root,
            source_database,
        )
        check_success(
            root,
            source_database,
        )
        check_rollback(
            root,
            source_database,
        )
    finally:
        shutil.rmtree(
            root,
            ignore_errors=True,
        )

    print(
        "[PASS] Pre-Uvicorn restore bootstrap is a no-op "
        "without a job, revalidates and atomically installs "
        "a staged database, preserves file ownership/mode, "
        "creates and validates an online rollback snapshot, "
        "invalidates restored sessions, records actor-aware "
        "success, and exactly rolls back an injected "
        "post-replacement failure before recording one "
        "failure audit, all on copied databases"
    )


if __name__ == "__main__":
    main()
