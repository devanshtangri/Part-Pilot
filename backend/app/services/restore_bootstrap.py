from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
from typing import Any

from app.schemas.restores import (
    RestoreBootstrapResult,
    RestoreCommitJob,
)
from app.services.backups import (
    EXPECTED_ALEMBIC_REVISION,
    BackupArtifactError,
    canonical_json_bytes,
    inspect_sqlite_snapshot,
    sha256_path,
    validate_backup_artifact,
)
from app.services.restores import (
    RESTORE_ARCHIVE_FILENAME,
    RESTORE_BOOTSTRAP_EXTRA_FILES,
    RESTORE_COMMIT_FILENAME,
    RESTORE_DATABASE_FILENAME,
    RESTORE_FAILED_DATABASE_FILENAME,
    RESTORE_OPERATION_MARKER,
    RESTORE_OPERATION_MARKER_CONTENT,
    RESTORE_OPERATION_PREFIX,
    RESTORE_PREVIOUS_FILENAME,
    RESTORE_RESULT_FILENAME,
    RESTORE_ROLLBACK_FILENAME,
    RESTORE_STATE_FILENAME,
    RestoreStagingStateError,
    StagedRestore,
    load_staged_restore,
)


RESTORE_COMMIT_JOB_VERSION = 1
RESTORE_RESULT_VERSION = 1
RESTORE_JOB_MAX_AGE_SECONDS = 15 * 60
BOOTSTRAP_EVENT_SUCCESS = "backup.restored"
BOOTSTRAP_EVENT_FAILURE = "backup.restore_failed"


class RestoreBootstrapError(RuntimeError):
    pass


class RestoreBootstrapFatalError(
    RestoreBootstrapError
):
    pass


FaultInjector = Callable[[str], None]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(
        microsecond=0
    )


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _parse_utc(value: str) -> datetime:
    try:
        return datetime.strptime(
            value,
            "%Y-%m-%dT%H:%M:%SZ",
        ).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise RestoreBootstrapError(
            "Restore bootstrap timestamp is invalid."
        ) from exc


def _token_sha256(token: str) -> str:
    return hashlib.sha256(
        token.encode("ascii")
    ).hexdigest()


def _fsync_file(path: Path) -> None:
    descriptor = os.open(
        path,
        os.O_RDONLY,
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(
        path,
        os.O_RDONLY | os.O_DIRECTORY,
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _load_json_exact(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise RestoreBootstrapError(
            f"Restore bootstrap file is missing: {path.name}"
        ) from exc

    def reject_duplicates(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise RestoreBootstrapError(
                    "Restore bootstrap JSON contains duplicate keys."
                )
            result[key] = value
        return result

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
        )
    except RestoreBootstrapError:
        raise
    except Exception as exc:
        raise RestoreBootstrapError(
            "Restore bootstrap JSON is invalid."
        ) from exc
    if not isinstance(value, dict):
        raise RestoreBootstrapError(
            "Restore bootstrap JSON must be an object."
        )
    return value


def _write_model(
    path: Path,
    model,
) -> None:
    temporary = path.with_name(
        path.name + ".tmp"
    )
    temporary.unlink(missing_ok=True)
    payload = canonical_json_bytes(
        model.model_dump(mode="json")
    )
    with temporary.open("xb") as output:
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
    os.chmod(path, 0o600)
    _fsync_file(path)
    _fsync_directory(path.parent)


def _load_job(
    path: Path,
) -> RestoreCommitJob:
    raw = _load_json_exact(path)
    try:
        job = RestoreCommitJob.model_validate(
            raw
        )
    except Exception as exc:
        raise RestoreBootstrapError(
            "Restore commit job does not match version 1."
        ) from exc
    if path.read_bytes() != canonical_json_bytes(
        job.model_dump(mode="json")
    ):
        raise RestoreBootstrapError(
            "Restore commit job is not canonical JSON."
        )
    return job


def _operation_is_owned(
    operation: Path,
    *,
    staging_root: Path,
) -> bool:
    try:
        operation_resolved = operation.resolve()
        root_resolved = staging_root.resolve()
    except OSError:
        return False
    if (
        operation_resolved.parent != root_resolved
        or operation.is_symlink()
        or not operation.is_dir()
        or not operation.name.startswith(
            RESTORE_OPERATION_PREFIX
        )
    ):
        return False
    marker = (
        operation
        / RESTORE_OPERATION_MARKER
    )
    try:
        return marker.read_text(
            encoding="utf-8"
        ) == RESTORE_OPERATION_MARKER_CONTENT
    except OSError:
        return False


def discover_pending_restore_job(
    staging_root: Path,
) -> tuple[Path, RestoreCommitJob] | None:
    root = staging_root.expanduser().resolve()
    if not root.exists():
        return None
    if (
        root.is_symlink()
        or not root.is_dir()
        or stat.S_IMODE(root.stat().st_mode)
        != 0o700
    ):
        raise RestoreBootstrapFatalError(
            "Restore staging root is unsafe."
        )

    pending: list[
        tuple[Path, RestoreCommitJob]
    ] = []
    for operation in sorted(root.iterdir()):
        if not _operation_is_owned(
            operation,
            staging_root=root,
        ):
            continue
        job_path = (
            operation
            / RESTORE_COMMIT_FILENAME
        )
        result_path = (
            operation
            / RESTORE_RESULT_FILENAME
        )
        if (
            job_path.is_file()
            and not result_path.exists()
        ):
            pending.append(
                (
                    operation,
                    _load_job(job_path),
                )
            )
    if not pending:
        return None
    if len(pending) != 1:
        raise RestoreBootstrapFatalError(
            "Multiple pending restore jobs require manual recovery."
        )
    return pending[0]


def sqlite_logical_sha256(
    database_path: Path,
) -> str:
    digest = hashlib.sha256()
    connection = sqlite3.connect(
        f"{database_path.resolve().as_uri()}?mode=ro",
        uri=True,
        timeout=30.0,
    )
    connection.row_factory = sqlite3.Row
    try:
        tables = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            ).fetchall()
        ]
        for table in tables:
            digest.update(
                canonical_json_bytes(
                    {"table": table}
                )
            )
            quoted = table.replace(
                '"',
                '""',
            )
            for row in connection.execute(
                f'SELECT * FROM "{quoted}" ORDER BY rowid'
            ):
                digest.update(
                    canonical_json_bytes(
                        list(row)
                    )
                )
    finally:
        connection.close()
    return digest.hexdigest()


def _sqlite_online_backup(
    source: Path,
    destination: Path,
) -> None:
    if destination.exists():
        raise RestoreBootstrapError(
            "Rollback snapshot path already exists."
        )
    source_connection = sqlite3.connect(
        source,
        timeout=30.0,
    )
    destination_connection = sqlite3.connect(
        destination,
        timeout=30.0,
    )
    try:
        source_connection.backup(
            destination_connection,
            pages=128,
            sleep=0.005,
        )
        destination_connection.commit()
    except sqlite3.Error as exc:
        raise RestoreBootstrapError(
            "Rollback snapshot creation failed."
        ) from exc
    finally:
        destination_connection.close()
        source_connection.close()
    os.chmod(destination, 0o600)
    _fsync_file(destination)


def _inspect_actor(
    connection: sqlite3.Connection,
    *,
    actor_user_id: int,
    actor_username: str,
) -> tuple[str, int | None]:
    row = connection.execute(
        "SELECT id, username, is_active "
        "FROM users WHERE id=?",
        (actor_user_id,),
    ).fetchone()
    if (
        row is not None
        and int(row[0]) == actor_user_id
        and str(row[1]) == actor_username
        and bool(row[2])
    ):
        return "user", actor_user_id
    return "system", None


def _append_audit(
    database_path: Path,
    *,
    event_type: str,
    actor_user_id: int,
    actor_username: str,
    summary: str,
    after_json: dict[str, Any],
    metadata_json: dict[str, Any],
    invalidate_sessions: bool,
    created_at: datetime,
) -> tuple[
    str,
    int | None,
    int,
    int,
]:
    connection = sqlite3.connect(
        database_path,
        timeout=30.0,
    )
    try:
        connection.execute(
            "PRAGMA foreign_keys=ON"
        )
        connection.execute(
            "BEGIN IMMEDIATE"
        )
        actor_type, matched_user_id = (
            _inspect_actor(
                connection,
                actor_user_id=actor_user_id,
                actor_username=actor_username,
            )
        )
        sessions_invalidated = 0
        if invalidate_sessions:
            sessions_invalidated = int(
                connection.execute(
                    "SELECT COUNT(*) FROM sessions"
                ).fetchone()[0]
            )
            connection.execute(
                "DELETE FROM sessions"
            )
        cursor = connection.execute(
            "INSERT INTO audit_log "
            "(created_at, event_type, entity_type, "
            "entity_id, actor_type, actor_user_id, "
            "summary, before_json, after_json, "
            "metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                created_at.isoformat(),
                event_type,
                "backup",
                None,
                actor_type,
                matched_user_id,
                summary,
                None,
                json.dumps(
                    after_json,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                json.dumps(
                    metadata_json,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        )
        audit_id = int(cursor.lastrowid)
        connection.commit()
        return (
            actor_type,
            matched_user_id,
            sessions_invalidated,
            audit_id,
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _validate_job_and_stage(
    operation: Path,
    job: RestoreCommitJob,
    *,
    live_database_path: Path,
    staging_root: Path,
    now: datetime,
) -> StagedRestore:
    token = operation.name[
        len(RESTORE_OPERATION_PREFIX):
    ]
    if (
        job.validation_token != token
        or job.token_sha256
        != _token_sha256(token)
    ):
        raise RestoreBootstrapError(
            "Restore commit token does not match its directory."
        )
    requested_at = _parse_utc(
        job.requested_at_utc
    )
    if (
        requested_at > now + timedelta(seconds=5)
        or now - requested_at
        > timedelta(
            seconds=RESTORE_JOB_MAX_AGE_SECONDS
        )
    ):
        raise RestoreBootstrapError(
            "Restore commit job is stale."
        )
    if (
        not live_database_path.is_file()
        or sha256_path(live_database_path)
        != job.expected_live_database_sha256
        or live_database_path.stat().st_size
        != job.expected_live_database_size_bytes
    ):
        raise RestoreBootstrapError(
            "Live database changed after restore confirmation."
        )

    staged = load_staged_restore(
        token,
        actor_user_id=job.actor_user_id,
        actor_username=job.actor_username,
        staging_root=staging_root,
        now=now,
        require_unexpired=False,
        allowed_extra_files=frozenset(
            {
                RESTORE_COMMIT_FILENAME,
            }
        ),
    )
    state_expiry = _parse_utc(
        staged.state.expires_at_utc
    )
    if requested_at > state_expiry:
        raise RestoreBootstrapError(
            "Restore was confirmed after validation expiry."
        )
    if (
        staged.state.archive_sha256
        != job.staged_archive_sha256
        or staged.state.database_sha256
        != job.staged_database_sha256
    ):
        raise RestoreBootstrapError(
            "Restore commit hashes do not match staging state."
        )

    archive_path = (
        operation
        / RESTORE_ARCHIVE_FILENAME
    )
    candidate_path = (
        operation
        / RESTORE_DATABASE_FILENAME
    )
    try:
        manifest = validate_backup_artifact(
            archive_path,
            validation_parent=operation,
            expected_revision=(
                EXPECTED_ALEMBIC_REVISION
            ),
        )
        inspection = inspect_sqlite_snapshot(
            candidate_path,
            expected_revision=(
                EXPECTED_ALEMBIC_REVISION
            ),
        )
    except BackupArtifactError as exc:
        raise RestoreBootstrapError(
            "Restore staging revalidation failed."
        ) from exc
    if (
        manifest.database.sha256
        != job.staged_database_sha256
        or inspection.database_sha256
        != job.staged_database_sha256
    ):
        raise RestoreBootstrapError(
            "Restore candidate hash changed."
        )
    return staged


def prepare_restore_commit_job(
    validation_token: str,
    *,
    actor_user_id: int,
    actor_username: str,
    live_database_path: Path,
    staging_root: Path,
    now: datetime | None = None,
) -> RestoreCommitJob:
    current = (
        now.astimezone(timezone.utc).replace(
            microsecond=0
        )
        if now is not None
        else _utc_now()
    )
    staged = load_staged_restore(
        validation_token,
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        staging_root=staging_root,
        now=current,
    )
    operation = staged.operation_directory
    job_path = (
        operation
        / RESTORE_COMMIT_FILENAME
    )
    result_path = (
        operation
        / RESTORE_RESULT_FILENAME
    )
    if (
        job_path.exists()
        or result_path.exists()
    ):
        raise RestoreBootstrapError(
            "Restore staging already has a commit or result."
        )
    live_path = (
        live_database_path.expanduser().resolve()
    )
    inspect_sqlite_snapshot(
        live_path,
        expected_revision=(
            EXPECTED_ALEMBIC_REVISION
        ),
    )
    job = RestoreCommitJob(
        job_version=(
            RESTORE_COMMIT_JOB_VERSION
        ),
        status="pending",
        validation_token=validation_token,
        token_sha256=_token_sha256(
            validation_token
        ),
        actor_user_id=actor_user_id,
        actor_username=(
            actor_username.strip()
        ),
        requested_at_utc=(
            _utc_text(current)
        ),
        expected_live_database_sha256=(
            sha256_path(live_path)
        ),
        expected_live_database_size_bytes=(
            live_path.stat().st_size
        ),
        staged_archive_sha256=(
            staged.state.archive_sha256
        ),
        staged_database_sha256=(
            staged.state.database_sha256
        ),
        result_filename=(
            RESTORE_RESULT_FILENAME
        ),
    )
    _write_model(
        job_path,
        job,
    )
    return job


def _write_result(
    operation: Path,
    result: RestoreBootstrapResult,
) -> None:
    _write_model(
        operation
        / RESTORE_RESULT_FILENAME,
        result,
    )


def process_pending_restore(
    *,
    live_database_path: Path,
    staging_root: Path,
    now: datetime | None = None,
    fault_injector: FaultInjector | None = None,
) -> RestoreBootstrapResult | None:
    current = (
        now.astimezone(timezone.utc).replace(
            microsecond=0
        )
        if now is not None
        else _utc_now()
    )
    discovered = discover_pending_restore_job(
        staging_root
    )
    if discovered is None:
        return None

    operation, job = discovered
    started = current
    before_hash = sha256_path(
        live_database_path
    )
    before_logical = sqlite_logical_sha256(
        live_database_path
    )
    rollback_path = (
        operation
        / RESTORE_ROLLBACK_FILENAME
    )
    previous_path = (
        operation
        / RESTORE_PREVIOUS_FILENAME
    )
    failed_path = (
        operation
        / RESTORE_FAILED_DATABASE_FILENAME
    )
    replacement_started = False
    rollback_snapshot_hash: str | None = None

    def inject(phase: str) -> None:
        if fault_injector is not None:
            fault_injector(phase)

    try:
        staged = _validate_job_and_stage(
            operation,
            job,
            live_database_path=(
                live_database_path
            ),
            staging_root=staging_root,
            now=current,
        )
        candidate_path = (
            staged.operation_directory
            / RESTORE_DATABASE_FILENAME
        )
        live_stat = live_database_path.stat()

        _sqlite_online_backup(
            live_database_path,
            rollback_path,
        )
        os.chmod(
            rollback_path,
            stat.S_IMODE(
                live_stat.st_mode
            ),
        )
        try:
            os.chown(
                rollback_path,
                live_stat.st_uid,
                live_stat.st_gid,
            )
        except PermissionError as exc:
            raise RestoreBootstrapError(
                "Rollback ownership could not be preserved."
            ) from exc
        rollback_inspection = (
            inspect_sqlite_snapshot(
                rollback_path,
                expected_revision=(
                    EXPECTED_ALEMBIC_REVISION
                ),
            )
        )
        rollback_snapshot_hash = (
            rollback_inspection.database_sha256
        )
        if (
            sqlite_logical_sha256(
                rollback_path
            )
            != before_logical
        ):
            raise RestoreBootstrapError(
                "Rollback snapshot logical hash changed."
            )

        os.chmod(
            candidate_path,
            stat.S_IMODE(
                live_stat.st_mode
            ),
        )
        try:
            os.chown(
                candidate_path,
                live_stat.st_uid,
                live_stat.st_gid,
            )
        except PermissionError as exc:
            raise RestoreBootstrapError(
                "Candidate ownership could not be preserved."
            ) from exc
        _fsync_file(candidate_path)
        _fsync_directory(operation)
        _fsync_directory(
            live_database_path.parent
        )
        inject("before_replace")

        os.replace(
            live_database_path,
            previous_path,
        )
        replacement_started = True
        _fsync_directory(
            live_database_path.parent
        )
        os.replace(
            candidate_path,
            live_database_path,
        )
        _fsync_file(
            live_database_path
        )
        _fsync_directory(
            live_database_path.parent
        )
        inject("after_replace")

        restored_snapshot_hash = sha256_path(
            live_database_path
        )
        (
            actor_type,
            matched_actor_id,
            sessions_invalidated,
            audit_id,
        ) = _append_audit(
            live_database_path,
            event_type=BOOTSTRAP_EVENT_SUCCESS,
            actor_user_id=job.actor_user_id,
            actor_username=job.actor_username,
            summary=(
                "Restored Part Pilot backup"
            ),
            after_json={
                "format_version": (
                    staged.state.format_version
                ),
                "alembic_revision": (
                    staged.state.alembic_revision
                ),
                "database_sha256": (
                    staged.state.database_sha256
                ),
                "backup_created_at_utc": (
                    staged.state.backup_created_at_utc
                ),
            },
            metadata_json={
                "requester_username": (
                    job.actor_username
                ),
                "archive_sha256": (
                    staged.state.archive_sha256
                ),
                "sessions_invalidated": True,
                "restore_bootstrap_version": 1,
            },
            invalidate_sessions=True,
            created_at=current,
        )
        inject("after_finalize")

        inspect_sqlite_snapshot(
            live_database_path,
            expected_revision=(
                EXPECTED_ALEMBIC_REVISION
            ),
        )
        verification = sqlite3.connect(
            live_database_path
        )
        try:
            sessions_remaining = int(
                verification.execute(
                    "SELECT COUNT(*) FROM sessions"
                ).fetchone()[0]
            )
            audit_exists = int(
                verification.execute(
                    "SELECT COUNT(*) FROM audit_log "
                    "WHERE id=? AND event_type=?",
                    (
                        audit_id,
                        BOOTSTRAP_EVENT_SUCCESS,
                    ),
                ).fetchone()[0]
            )
        finally:
            verification.close()
        if (
            sessions_remaining != 0
            or audit_exists != 1
        ):
            raise RestoreBootstrapError(
                "Restored database final verification failed."
            )

        result = RestoreBootstrapResult(
            result_version=(
                RESTORE_RESULT_VERSION
            ),
            status="succeeded",
            validation_token=(
                job.validation_token
            ),
            started_at_utc=(
                _utc_text(started)
            ),
            finished_at_utc=(
                _utc_text(current)
            ),
            event_type=(
                BOOTSTRAP_EVENT_SUCCESS
            ),
            actor_type=actor_type,
            actor_user_id=matched_actor_id,
            live_database_sha256_before=(
                before_hash
            ),
            live_database_sha256_after=(
                sha256_path(
                    live_database_path
                )
            ),
            restored_snapshot_sha256=(
                restored_snapshot_hash
            ),
            rollback_snapshot_sha256=(
                rollback_snapshot_hash
            ),
            rollback_verified=True,
            sessions_invalidated=(
                sessions_invalidated
            ),
            audit_id=audit_id,
            error_code=None,
        )
        _write_result(
            operation,
            result,
        )
        return result

    except Exception as exc:
        error_code = type(exc).__name__[:80]
        rollback_verified = False
        try:
            if replacement_started:
                if live_database_path.exists():
                    failed_path.unlink(
                        missing_ok=True
                    )
                    os.replace(
                        live_database_path,
                        failed_path,
                    )
                if not previous_path.is_file():
                    raise RestoreBootstrapFatalError(
                        "Exact previous database is missing."
                    )
                os.replace(
                    previous_path,
                    live_database_path,
                )
                _fsync_file(
                    live_database_path
                )
                _fsync_directory(
                    live_database_path.parent
                )

            if (
                sha256_path(
                    live_database_path
                )
                != before_hash
                or sqlite_logical_sha256(
                    live_database_path
                )
                != before_logical
            ):
                raise RestoreBootstrapFatalError(
                    "Original database rollback verification failed."
                )
            inspect_sqlite_snapshot(
                live_database_path,
                expected_revision=(
                    EXPECTED_ALEMBIC_REVISION
                ),
            )
            rollback_verified = True
            (
                actor_type,
                matched_actor_id,
                _sessions_invalidated,
                audit_id,
            ) = _append_audit(
                live_database_path,
                event_type=(
                    BOOTSTRAP_EVENT_FAILURE
                ),
                actor_user_id=(
                    job.actor_user_id
                ),
                actor_username=(
                    job.actor_username
                ),
                summary=(
                    "Part Pilot restore failed and "
                    "the original database was recovered"
                ),
                after_json={
                    "rollback_verified": True,
                    "error_code": error_code,
                },
                metadata_json={
                    "requester_username": (
                        job.actor_username
                    ),
                    "restore_bootstrap_version": 1,
                },
                invalidate_sessions=False,
                created_at=current,
            )
            result = RestoreBootstrapResult(
                result_version=(
                    RESTORE_RESULT_VERSION
                ),
                status="failed",
                validation_token=(
                    job.validation_token
                ),
                started_at_utc=(
                    _utc_text(started)
                ),
                finished_at_utc=(
                    _utc_text(current)
                ),
                event_type=(
                    BOOTSTRAP_EVENT_FAILURE
                ),
                actor_type=actor_type,
                actor_user_id=(
                    matched_actor_id
                ),
                live_database_sha256_before=(
                    before_hash
                ),
                live_database_sha256_after=(
                    sha256_path(
                        live_database_path
                    )
                ),
                restored_snapshot_sha256=None,
                rollback_snapshot_sha256=(
                    rollback_snapshot_hash
                ),
                rollback_verified=True,
                sessions_invalidated=0,
                audit_id=audit_id,
                error_code=error_code,
            )
            _write_result(
                operation,
                result,
            )
            return result
        except Exception as rollback_exc:
            raise RestoreBootstrapFatalError(
                "Restore failed and rollback could not be "
                f"verified: {rollback_exc}"
            ) from rollback_exc


def cancel_restore_commit_job(
    validation_token: str,
    *,
    actor_user_id: int,
    actor_username: str,
    staging_root: Path,
) -> None:
    staged = load_staged_restore(
        validation_token,
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        staging_root=staging_root,
        require_unexpired=False,
        allowed_extra_files=frozenset(
            {
                RESTORE_COMMIT_FILENAME,
            }
        ),
    )
    operation = staged.operation_directory
    job_path = (
        operation
        / RESTORE_COMMIT_FILENAME
    )
    result_path = (
        operation
        / RESTORE_RESULT_FILENAME
    )
    if result_path.exists():
        raise RestoreBootstrapError(
            "Restore result already exists."
        )
    if not job_path.is_file():
        raise RestoreBootstrapError(
            "Restore commit job is missing."
        )
    job = _load_job(job_path)
    if (
        job.validation_token
        != validation_token
        or job.actor_user_id
        != actor_user_id
        or job.actor_username
        != actor_username.strip()
    ):
        raise RestoreBootstrapError(
            "Restore commit job ownership changed."
        )
    job_path.unlink()
    _fsync_directory(operation)
