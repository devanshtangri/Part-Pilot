from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.routes import restores as restores_route
from app.core.config import get_settings
from app.core.lifecycle import (
    application_lifecycle,
)
from app.db.session import (
    SessionLocal,
    dispose_database_engine,
)
from app.main import app as fastapi_app
from app.services.auth import (
    create_session,
)
from app.services.backups import (
    BACKUP_MEDIA_TYPE,
    create_backup_artifact,
    remove_backup_operation_directory,
    sqlite_path_from_database_url,
)
from app.services.restore_bootstrap import (
    BOOTSTRAP_EVENT_SUCCESS,
    process_pending_restore,
)
from app.services.restores import (
    RESTORE_COMMIT_FILENAME,
    RESTORE_RESULT_FILENAME,
)


class RestoreCommitSmokeFailure(
    RuntimeError
):
    pass


def fail(message: str) -> None:
    raise RestoreCommitSmokeFailure(
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


def display_name(
    database_path: Path,
) -> str:
    connection = sqlite3.connect(
        database_path
    )
    try:
        raw = connection.execute(
            "SELECT value_json FROM app_settings "
            "WHERE key='app.display_name'"
        ).fetchone()[0]
        return str(json.loads(raw))
    finally:
        connection.close()


def set_display_name(
    database_path: Path,
    value: str,
) -> None:
    connection = sqlite3.connect(
        database_path
    )
    try:
        connection.execute(
            "UPDATE app_settings SET value_json=? "
            "WHERE key='app.display_name'",
            (json.dumps(value),),
        )
        connection.commit()
    finally:
        connection.close()


def table_count(
    database_path: Path,
    table: str,
) -> int:
    connection = sqlite3.connect(
        database_path
    )
    try:
        return int(
            connection.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]
        )
    finally:
        connection.close()


def check_restore_commit_api() -> None:
    database_path = (
        sqlite_path_from_database_url(
            get_settings().database_url
        )
    )
    root = Path(
        tempfile.mkdtemp(
            dir=database_path.parent,
            prefix="partpilot-restore-commit-smoke-",
        )
    )
    os.chmod(root, 0o700)
    if (
        root.stat().st_dev
        != database_path.stat().st_dev
    ):
        fail(
            "Restore commit smoke workspace is not on the "
            "same filesystem as the copied live database: "
            f"workspace st_dev={root.stat().st_dev}, "
            f"database st_dev={database_path.stat().st_dev}"
        )
    candidate = root / "candidate-source.db"
    artifact_root = root / "artifacts"
    artifact_root.mkdir(mode=0o700)
    staging_root = root / ".partpilot-restore"
    artifact_operation: Path | None = None
    original_display_name = display_name(
        database_path
    )
    restored_display_name = (
        "Restore Commit Smoke"
    )

    try:
        actor_user_id, actor_username = (
            first_active_user(
                database_path
            )
        )
        with SessionLocal() as db:
            from app.models import User
            user = db.get(
                User,
                actor_user_id,
            )
            if user is None:
                fail(
                    "Active smoke user disappeared."
                )
            session = create_session(
                db,
                user=user,
                user_agent=(
                    "restore-commit-smoke"
                ),
                ip_address="127.0.0.1",
                commit=True,
            )
            token = session.token

        copy_database(
            database_path,
            candidate,
        )
        set_display_name(
            candidate,
            restored_display_name,
        )
        artifact = create_backup_artifact(
            candidate,
            artifact_root,
            created_at_utc=datetime.now(
                timezone.utc
            ).replace(
                microsecond=0
            ),
        )
        artifact_operation = (
            artifact.operation_directory
        )
        artifact_bytes = (
            artifact.archive_path.read_bytes()
        )
        headers = {
            "Authorization": f"Bearer {token}"
        }

        with (
            patch.object(
                restores_route,
                "RESTORE_STAGING_ROOT",
                staging_root,
            ),
            patch.object(
                restores_route,
                "RESTORE_LIVE_DATABASE_PATH",
                database_path,
            ),
        ):
            with TestClient(
                fastapi_app
            ) as client:
                paths = client.get(
                    "/openapi.json"
                ).json().get("paths", {})
                commit_path = (
                    "/api/restores/"
                    "{validation_token}/commit"
                )
                if set(
                    paths.get(
                        commit_path,
                        {},
                    )
                ) != {"post"}:
                    fail(
                        "Restore commit OpenAPI contract is incorrect."
                    )

                validation = client.post(
                    "/api/restores/validate",
                    headers=headers,
                    files={
                        "backup": (
                            artifact.filename,
                            artifact_bytes,
                            BACKUP_MEDIA_TYPE,
                        ),
                    },
                )
                if validation.status_code != 200:
                    fail(
                        "Restore validation failed before commit: "
                        f"{validation.status_code} "
                        f"{validation.text}"
                    )
                validation_token = (
                    validation.json()[
                        "validation_token"
                    ]
                )
                commit_url = (
                    "/api/restores/"
                    f"{validation_token}/commit"
                )

                unauthenticated = client.post(
                    commit_url,
                    json={
                        "confirmation": "RESTORE",
                    },
                )
                if unauthenticated.status_code != 401:
                    fail(
                        "Restore commit should require authentication."
                    )

                wrong_confirmation = client.post(
                    commit_url,
                    headers=headers,
                    json={
                        "confirmation": "restore",
                    },
                )
                if wrong_confirmation.status_code != 422:
                    fail(
                        "Restore commit accepted an incorrect confirmation."
                    )

                with patch.dict(
                    os.environ,
                    {
                        "PARTPILOT_RESTORE_SUPERVISOR_CONTRACT": "",
                    },
                ):
                    unavailable = client.post(
                        commit_url,
                        headers=headers,
                        json={
                            "confirmation": "RESTORE",
                        },
                    )
                if unavailable.status_code != 503:
                    fail(
                        "Restore commit ignored the supervisor contract."
                    )

                with patch.object(
                    application_lifecycle,
                    "wait_for_drain",
                    return_value=False,
                ):
                    drain_failure = client.post(
                        commit_url,
                        headers=headers,
                        json={
                            "confirmation": "RESTORE",
                        },
                    )
                if (
                    drain_failure.status_code != 409
                    or application_lifecycle.snapshot().phase
                    != "ready"
                ):
                    fail(
                        "Restore drain failure did not recover readiness."
                    )
                operation = (
                    staging_root
                    / (
                        "validated-"
                        + validation_token
                    )
                )
                if (
                    operation
                    / RESTORE_COMMIT_FILENAME
                ).exists():
                    fail(
                        "Drain failure left a pending restore job."
                    )

                termination_calls: list[
                    tuple[str, int, str, Path]
                ] = []

                def fake_terminate(
                    received_token: str,
                    received_user_id: int,
                    received_username: str,
                    received_root: Path,
                ) -> None:
                    termination_calls.append(
                        (
                            received_token,
                            received_user_id,
                            received_username,
                            received_root,
                        )
                    )
                    dispose_database_engine()
                    application_lifecycle.leave_maintenance()

                with patch.object(
                    restores_route,
                    "terminate_process_for_restore",
                    side_effect=fake_terminate,
                ):
                    committed = client.post(
                        commit_url,
                        headers=headers,
                        json={
                            "confirmation": "RESTORE",
                        },
                    )
                if (
                    committed.status_code != 202
                    or committed.json().get(
                        "status"
                    )
                    != "restart_scheduled"
                    or committed.json().get(
                        "sessions_will_be_invalidated"
                    )
                    is not True
                    or committed.json().get(
                        "reauthentication_required"
                    )
                    is not True
                    or committed.headers.get(
                        "cache-control"
                    )
                    != "no-store, max-age=0"
                    or committed.headers.get(
                        "retry-after"
                    )
                    != "5"
                ):
                    fail(
                        "Restore commit response is incorrect: "
                        f"{committed.status_code} "
                        f"{committed.text}"
                    )
                if termination_calls != [
                    (
                        validation_token,
                        actor_user_id,
                        actor_username,
                        staging_root,
                    )
                ]:
                    fail(
                        "Restore commit did not schedule exactly one "
                        "process termination."
                    )
                if application_lifecycle.snapshot().phase != "ready":
                    fail(
                        "Fake termination did not restore test readiness."
                    )
                if not (
                    operation
                    / RESTORE_COMMIT_FILENAME
                ).is_file():
                    fail(
                        "Restore commit job was not persisted."
                    )

            dispose_database_engine()
            result = process_pending_restore(
                live_database_path=(
                    database_path
                ),
                staging_root=staging_root,
                now=datetime.now(
                    timezone.utc
                ).replace(
                    microsecond=0
                ),
            )
            if (
                result is None
                or result.status != "succeeded"
                or result.event_type
                != BOOTSTRAP_EVENT_SUCCESS
                or not result.rollback_verified
            ):
                fail(
                    f"Scheduled restore bootstrap failed: {result}"
                )
            if (
                display_name(
                    database_path
                )
                != restored_display_name
            ):
                fail(
                    "Scheduled restore did not install the candidate."
                )
            if table_count(
                database_path,
                "sessions",
            ) != 0:
                fail(
                    "Scheduled restore did not invalidate sessions."
                )
            if not (
                operation
                / RESTORE_RESULT_FILENAME
            ).is_file():
                fail(
                    "Scheduled restore did not persist a result."
                )
            if process_pending_restore(
                live_database_path=(
                    database_path
                ),
                staging_root=staging_root,
                now=datetime.now(
                    timezone.utc
                ).replace(
                    microsecond=0
                ),
            ) is not None:
                fail(
                    "Completed restore was processed twice."
                )

    finally:
        dispose_database_engine()
        if artifact_operation is not None:
            try:
                remove_backup_operation_directory(
                    artifact_operation,
                    expected_parent=artifact_root,
                )
            except Exception:
                shutil.rmtree(
                    artifact_operation,
                    ignore_errors=True,
                )
        shutil.rmtree(
            root,
            ignore_errors=True,
        )

    if (
        original_display_name
        == restored_display_name
    ):
        fail(
            "Restore commit smoke lacked a distinct candidate marker."
        )

    print(
        "[PASS] Protected restore commit requires exact "
        "confirmation and supervisor support, enters maintenance, "
        "drains all other requests, leaves no job on drain failure, "
        "fsyncs one user-bound pending job, returns a no-store 202 "
        "before scheduling one process termination, and the "
        "pre-Uvicorn processor then performs same-filesystem "
        "atomic replacement, installs the copied candidate, "
        "invalidates all sessions, records success, persists a "
        "result, and refuses duplicate processing"
    )


def main() -> None:
    check_restore_commit_api()


if __name__ == "__main__":
    main()
