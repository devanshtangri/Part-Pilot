from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import stat
from typing import Any, BinaryIO
import zipfile

from app.schemas.restores import (
    RESTORE_TOKEN_PATTERN,
    RestoreStageState,
    RestoreValidationResponse,
)
from app.services.backups import (
    ARCHIVE_ENTRY_NAMES,
    ARCHIVE_MAX_BYTES,
    BACKUP_EXTENSION,
    DATABASE_ENTRY_NAME,
    DATABASE_MAX_BYTES,
    EXPECTED_ALEMBIC_REVISION,
    MANIFEST_ENTRY_NAME,
    BackupArtifactError,
    canonical_json_bytes,
    inspect_sqlite_snapshot,
    sha256_path,
    validate_backup_artifact,
)


RESTORE_STAGE_VERSION = 1
RESTORE_STAGE_TTL_SECONDS = 15 * 60
RESTORE_ROOT_NAME = ".partpilot-restore"
RESTORE_OPERATION_PREFIX = "validated-"
RESTORE_OPERATION_MARKER = (
    ".partpilot-restore-operation"
)
RESTORE_OPERATION_MARKER_CONTENT = (
    "part-pilot-restore-operation-v1\n"
)
RESTORE_ARCHIVE_FILENAME = "upload.ppbackup"
RESTORE_DATABASE_FILENAME = "candidate.db"
RESTORE_STATE_FILENAME = "state.json"
RESTORE_COMMIT_FILENAME = "commit.json"
RESTORE_RESULT_FILENAME = "result.json"
RESTORE_ROLLBACK_FILENAME = "rollback.db"
RESTORE_PREVIOUS_FILENAME = "previous.db"
RESTORE_FAILED_DATABASE_FILENAME = "failed.db"
RESTORE_BOOTSTRAP_EXTRA_FILES = frozenset(
    {
        RESTORE_COMMIT_FILENAME,
        RESTORE_RESULT_FILENAME,
        RESTORE_ROLLBACK_FILENAME,
        RESTORE_PREVIOUS_FILENAME,
        RESTORE_FAILED_DATABASE_FILENAME,
    }
)
RESTORE_TOKEN_BYTES = 32
RESTORE_TOKEN_RE = re.compile(
    RESTORE_TOKEN_PATTERN
)
RESTORE_CHUNK_BYTES = 1024 * 1024
RESTORE_MAX_COMPRESSION_RATIO = 200.0
RESTORE_RATIO_MIN_FILE_BYTES = 1024 * 1024


class RestoreValidationError(RuntimeError):
    pass


class RestoreUploadTooLargeError(
    RestoreValidationError
):
    pass


class RestoreStagingStateError(
    RestoreValidationError
):
    pass


@dataclass(frozen=True)
class StagedRestore:
    operation_directory: Path
    state: RestoreStageState

    def response(
        self,
    ) -> RestoreValidationResponse:
        return RestoreValidationResponse(
            status="ready_for_review",
            validation_token=self.token,
            original_filename=(
                self.state.original_filename
            ),
            backup_created_at_utc=(
                self.state.backup_created_at_utc
            ),
            validated_at_utc=(
                self.state.validated_at_utc
            ),
            expires_at_utc=(
                self.state.expires_at_utc
            ),
            format_version=(
                self.state.format_version
            ),
            alembic_revision=(
                self.state.alembic_revision
            ),
            archive_sha256=(
                self.state.archive_sha256
            ),
            archive_size_bytes=(
                self.state.archive_size_bytes
            ),
            database_sha256=(
                self.state.database_sha256
            ),
            database_size_bytes=(
                self.state.database_size_bytes
            ),
            user_count=self.state.user_count,
            active_user_count=(
                self.state.active_user_count
            ),
            sessions_present=(
                self.state.sessions_present
            ),
            warnings=self.state.warnings,
        )

    @property
    def token(self) -> str:
        prefix = RESTORE_OPERATION_PREFIX
        name = self.operation_directory.name
        if not name.startswith(prefix):
            raise RestoreStagingStateError(
                "Restore operation directory is invalid."
            )
        token = name[len(prefix):]
        _validate_token(token)
        return token


def restore_staging_root_for_database(
    database_path: Path,
) -> Path:
    return (
        database_path.expanduser().resolve().parent
        / RESTORE_ROOT_NAME
    )


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
        raise RestoreStagingStateError(
            "Restore staging timestamp is invalid."
        ) from exc


def _validate_token(token: str) -> None:
    if RESTORE_TOKEN_RE.fullmatch(token) is None:
        raise RestoreStagingStateError(
            "Restore validation token is invalid."
        )


def _token_sha256(token: str) -> str:
    return hashlib.sha256(
        token.encode("ascii")
    ).hexdigest()


def _normalize_original_filename(
    value: str,
) -> str:
    if (
        not value
        or len(value) > 255
        or value != Path(value).name
        or "/" in value
        or "\\" in value
        or not value.lower().endswith(
            BACKUP_EXTENSION
        )
    ):
        raise RestoreValidationError(
            "Restore upload filename must be a .ppbackup basename."
        )
    return value


def _ensure_directory_mode(
    path: Path,
    mode: int,
) -> None:
    if path.is_symlink():
        raise RestoreStagingStateError(
            "Restore staging path cannot be a symlink."
        )
    path.mkdir(
        parents=True,
        exist_ok=True,
        mode=mode,
    )
    if not path.is_dir():
        raise RestoreStagingStateError(
            "Restore staging path is not a directory."
        )
    os.chmod(path, mode)


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


def _create_operation(
    staging_root: Path,
) -> tuple[str, Path]:
    _ensure_directory_mode(
        staging_root,
        0o700,
    )
    for _attempt in range(8):
        token = secrets.token_urlsafe(
            RESTORE_TOKEN_BYTES
        )
        _validate_token(token)
        operation = (
            staging_root
            / f"{RESTORE_OPERATION_PREFIX}{token}"
        )
        try:
            operation.mkdir(
                mode=0o700,
            )
        except FileExistsError:
            continue
        try:
            os.chmod(operation, 0o700)
            marker = (
                operation
                / RESTORE_OPERATION_MARKER
            )
            marker.write_text(
                RESTORE_OPERATION_MARKER_CONTENT,
                encoding="utf-8",
            )
            os.chmod(marker, 0o600)
            _fsync_file(marker)
            _fsync_directory(operation)
            _fsync_directory(staging_root)
            return token, operation
        except Exception:
            shutil.rmtree(
                operation,
                ignore_errors=True,
            )
            raise
    raise RestoreStagingStateError(
        "Could not allocate a restore validation token."
    )


def _owned_operation(
    operation: Path,
    *,
    expected_root: Path,
) -> bool:
    operation = operation.resolve()
    root = expected_root.resolve()
    if (
        operation.parent != root
        or not operation.name.startswith(
            RESTORE_OPERATION_PREFIX
        )
        or operation.is_symlink()
        or not operation.is_dir()
    ):
        return False
    token = operation.name[
        len(RESTORE_OPERATION_PREFIX):
    ]
    if RESTORE_TOKEN_RE.fullmatch(token) is None:
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


def _remove_owned_operation(
    operation: Path,
    *,
    expected_root: Path,
) -> None:
    if not _owned_operation(
        operation,
        expected_root=expected_root,
    ):
        raise RestoreStagingStateError(
            "Refusing to remove an unowned restore directory."
        )
    shutil.rmtree(operation)
    if expected_root.is_dir():
        _fsync_directory(expected_root)


def _copy_upload(
    source: BinaryIO,
    destination: Path,
) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with destination.open("xb") as output:
        while True:
            chunk = source.read(
                RESTORE_CHUNK_BYTES
            )
            if not chunk:
                break
            total += len(chunk)
            if total > ARCHIVE_MAX_BYTES:
                raise RestoreUploadTooLargeError(
                    "Restore archive exceeds the 256 MiB limit."
                )
            digest.update(chunk)
            output.write(chunk)
        output.flush()
        os.fsync(output.fileno())
    os.chmod(destination, 0o600)
    if total < 1:
        raise RestoreValidationError(
            "Restore archive is empty."
        )
    return digest.hexdigest(), total


def _preflight_compression(
    archive_path: Path,
) -> None:
    try:
        with zipfile.ZipFile(
            archive_path,
            mode="r",
        ) as archive:
            infos = archive.infolist()
            names = [
                info.filename
                for info in infos
            ]
            if (
                len(infos) != 2
                or len(set(names)) != 2
                or tuple(sorted(names))
                != tuple(
                    sorted(ARCHIVE_ENTRY_NAMES)
                )
            ):
                raise RestoreValidationError(
                    "Restore archive entry contract is invalid."
                )
            database_info = archive.getinfo(
                DATABASE_ENTRY_NAME
            )
            if (
                database_info.file_size
                > DATABASE_MAX_BYTES
            ):
                raise RestoreUploadTooLargeError(
                    "Restore database exceeds the 1 GiB limit."
                )
            if (
                database_info.file_size
                >= RESTORE_RATIO_MIN_FILE_BYTES
            ):
                compressed = max(
                    database_info.compress_size,
                    1,
                )
                ratio = (
                    database_info.file_size
                    / compressed
                )
                if (
                    ratio
                    > RESTORE_MAX_COMPRESSION_RATIO
                ):
                    raise RestoreValidationError(
                        "Restore archive compression ratio is suspicious."
                    )
    except zipfile.BadZipFile as exc:
        raise RestoreValidationError(
            "Restore archive is not a valid ZIP file."
        ) from exc


def _extract_database(
    archive_path: Path,
    destination: Path,
    *,
    expected_sha256: str,
    expected_size: int,
) -> None:
    digest = hashlib.sha256()
    total = 0
    try:
        with zipfile.ZipFile(
            archive_path,
            mode="r",
        ) as archive:
            with archive.open(
                DATABASE_ENTRY_NAME,
                mode="r",
            ) as source:
                with destination.open(
                    "xb"
                ) as output:
                    while True:
                        chunk = source.read(
                            RESTORE_CHUNK_BYTES
                        )
                        if not chunk:
                            break
                        total += len(chunk)
                        if (
                            total
                            > DATABASE_MAX_BYTES
                        ):
                            raise RestoreUploadTooLargeError(
                                "Restore database exceeds the 1 GiB limit."
                            )
                        digest.update(chunk)
                        output.write(chunk)
                    output.flush()
                    os.fsync(
                        output.fileno()
                    )
    except zipfile.BadZipFile as exc:
        raise RestoreValidationError(
            "Restore archive became unreadable."
        ) from exc
    os.chmod(destination, 0o600)
    if (
        total != expected_size
        or digest.hexdigest()
        != expected_sha256
    ):
        raise RestoreValidationError(
            "Restore database does not match its manifest."
        )


def _inspect_users(
    database_path: Path,
) -> tuple[int, int]:
    connection = sqlite3.connect(
        f"{database_path.resolve().as_uri()}?mode=ro&immutable=1",
        uri=True,
        timeout=30.0,
    )
    try:
        connection.execute(
            "PRAGMA query_only=ON"
        )
        user_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM users"
            ).fetchone()[0]
        )
        active_user_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM users "
                "WHERE is_active=1"
            ).fetchone()[0]
        )
        first_user = connection.execute(
            "SELECT id, role, is_active FROM users ORDER BY id ASC LIMIT 1"
        ).fetchone()
        owner_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM users WHERE role='owner'"
            ).fetchone()[0]
        )
    except sqlite3.Error as exc:
        raise RestoreValidationError(
            "Restore user records could not be inspected."
        ) from exc
    finally:
        connection.close()
    if user_count < 1:
        raise RestoreValidationError(
            "Restore database contains no users."
        )
    if active_user_count < 1:
        raise RestoreValidationError(
            "Restore database contains no active user."
        )
    if (
        first_user is None
        or str(first_user[1]) != "owner"
        or int(first_user[2]) != 1
        or owner_count != 1
    ):
        raise RestoreValidationError(
            "Restore database must contain exactly one active primary Owner as its first user."
        )
    return user_count, active_user_count


def _load_json_exact(
    payload: bytes,
) -> dict[str, Any]:
    def reject_duplicates(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise RestoreStagingStateError(
                    "Restore staging state contains duplicate keys."
                )
            result[key] = value
        return result

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
        )
    except RestoreStagingStateError:
        raise
    except Exception as exc:
        raise RestoreStagingStateError(
            "Restore staging state is invalid JSON."
        ) from exc
    if not isinstance(value, dict):
        raise RestoreStagingStateError(
            "Restore staging state must be an object."
        )
    return value


def _write_state(
    operation: Path,
    state: RestoreStageState,
) -> None:
    state_path = (
        operation
        / RESTORE_STATE_FILENAME
    )
    temporary = state_path.with_suffix(
        ".tmp"
    )
    payload = canonical_json_bytes(
        state.model_dump(mode="json")
    )
    with temporary.open("xb") as output:
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())
    os.chmod(temporary, 0o600)
    os.replace(
        temporary,
        state_path,
    )
    os.chmod(state_path, 0o600)
    _fsync_file(state_path)
    _fsync_directory(operation)


def _read_state(
    operation: Path,
) -> RestoreStageState:
    state_path = (
        operation
        / RESTORE_STATE_FILENAME
    )
    try:
        payload = state_path.read_bytes()
    except OSError as exc:
        raise RestoreStagingStateError(
            "Restore staging state is missing."
        ) from exc
    raw = _load_json_exact(payload)
    warnings = raw.get("warnings")
    if isinstance(warnings, list):
        raw["warnings"] = tuple(warnings)
    try:
        state = RestoreStageState.model_validate(
            raw
        )
    except RestoreStagingStateError:
        raise
    except Exception as exc:
        raise RestoreStagingStateError(
            "Restore staging state does not match version 1."
        ) from exc
    canonical = canonical_json_bytes(
        state.model_dump(mode="json")
    )
    if payload != canonical:
        raise RestoreStagingStateError(
            "Restore staging state is not canonical."
        )
    return state


def stage_restore_archive(
    source: BinaryIO,
    *,
    original_filename: str,
    actor_user_id: int,
    actor_username: str,
    staging_root: Path,
    now: datetime | None = None,
    ttl_seconds: int = (
        RESTORE_STAGE_TTL_SECONDS
    ),
) -> StagedRestore:
    if actor_user_id < 1:
        raise RestoreValidationError(
            "Restore validation actor is invalid."
        )
    normalized_username = (
        actor_username.strip()
    )
    if not normalized_username:
        raise RestoreValidationError(
            "Restore validation actor username is invalid."
        )
    if ttl_seconds < 1:
        raise RestoreValidationError(
            "Restore validation TTL must be positive."
        )
    filename = _normalize_original_filename(
        original_filename
    )
    current = (
        now.astimezone(timezone.utc).replace(
            microsecond=0
        )
        if now is not None
        else _utc_now()
    )
    expires = current + timedelta(
        seconds=ttl_seconds
    )

    token, operation = _create_operation(
        staging_root
    )
    try:
        archive_path = (
            operation
            / RESTORE_ARCHIVE_FILENAME
        )
        archive_sha256, archive_size = (
            _copy_upload(
                source,
                archive_path,
            )
        )
        _preflight_compression(
            archive_path
        )
        try:
            manifest = validate_backup_artifact(
                archive_path,
                validation_parent=operation,
                expected_revision=(
                    EXPECTED_ALEMBIC_REVISION
                ),
            )
        except BackupArtifactError as exc:
            raise RestoreValidationError(
                "Restore archive is not a valid Part Pilot backup."
            ) from exc

        candidate_path = (
            operation
            / RESTORE_DATABASE_FILENAME
        )
        _extract_database(
            archive_path,
            candidate_path,
            expected_sha256=(
                manifest.database.sha256
            ),
            expected_size=(
                manifest.database.size_bytes
            ),
        )
        inspection = inspect_sqlite_snapshot(
            candidate_path,
            expected_revision=(
                EXPECTED_ALEMBIC_REVISION
            ),
        )
        user_count, active_user_count = (
            _inspect_users(candidate_path)
        )
        if (
            inspection.database_sha256
            != manifest.database.sha256
            or inspection.database_size_bytes
            != manifest.database.size_bytes
            or inspection.critical_schema_sha256
            != manifest.schema.critical_schema_sha256
        ):
            raise RestoreValidationError(
                "Restore database metadata changed during staging."
            )

        warnings = (
            (
                "All sessions will be invalidated "
                "after a successful restore.",
            )
            if inspection.sessions_present
            else ()
        )
        state = RestoreStageState(
            state_version=RESTORE_STAGE_VERSION,
            status="validated",
            token_sha256=_token_sha256(
                token
            ),
            actor_user_id=actor_user_id,
            actor_username=(
                normalized_username
            ),
            original_filename=filename,
            archive_filename=(
                RESTORE_ARCHIVE_FILENAME
            ),
            candidate_database_filename=(
                RESTORE_DATABASE_FILENAME
            ),
            backup_created_at_utc=(
                manifest.created_at_utc
            ),
            validated_at_utc=(
                _utc_text(current)
            ),
            expires_at_utc=(
                _utc_text(expires)
            ),
            format_version=(
                manifest.format_version
            ),
            alembic_revision=(
                manifest.schema.alembic_revision
            ),
            critical_schema_sha256=(
                manifest.schema.critical_schema_sha256
            ),
            archive_sha256=archive_sha256,
            archive_size_bytes=(
                archive_size
            ),
            database_sha256=(
                inspection.database_sha256
            ),
            database_size_bytes=(
                inspection.database_size_bytes
            ),
            user_count=user_count,
            active_user_count=(
                active_user_count
            ),
            sessions_present=(
                inspection.sessions_present
            ),
            warnings=warnings,
        )
        _write_state(
            operation,
            state,
        )
        _fsync_file(archive_path)
        _fsync_file(candidate_path)
        _fsync_directory(operation)
        _fsync_directory(
            staging_root
        )
        return StagedRestore(
            operation_directory=operation,
            state=state,
        )
    except Exception:
        if _owned_operation(
            operation,
            expected_root=staging_root,
        ):
            _remove_owned_operation(
                operation,
                expected_root=staging_root,
            )
        raise


def load_staged_restore(
    validation_token: str,
    *,
    actor_user_id: int,
    actor_username: str,
    staging_root: Path,
    now: datetime | None = None,
    require_unexpired: bool = True,
    allowed_extra_files: frozenset[str] = frozenset(),
) -> StagedRestore:
    _validate_token(
        validation_token
    )
    operation = (
        staging_root.expanduser().resolve()
        / (
            RESTORE_OPERATION_PREFIX
            + validation_token
        )
    )
    if not _owned_operation(
        operation,
        expected_root=staging_root,
    ):
        raise RestoreStagingStateError(
            "Restore validation token was not found."
        )
    state = _read_state(operation)
    if not secrets.compare_digest(
        state.token_sha256,
        _token_sha256(
            validation_token
        ),
    ):
        raise RestoreStagingStateError(
            "Restore validation token does not match its state."
        )
    if (
        state.actor_user_id
        != actor_user_id
        or state.actor_username
        != actor_username.strip()
    ):
        raise RestoreStagingStateError(
            "Restore validation token belongs to another user."
        )
    current = (
        now.astimezone(timezone.utc).replace(
            microsecond=0
        )
        if now is not None
        else _utc_now()
    )
    if (
        require_unexpired
        and _parse_utc(
            state.expires_at_utc
        ) <= current
    ):
        raise RestoreStagingStateError(
            "Restore validation token has expired."
        )
    if not allowed_extra_files.issubset(
        RESTORE_BOOTSTRAP_EXTRA_FILES
    ):
        raise RestoreStagingStateError(
            "Restore staging extra-file allowlist is invalid."
        )

    expected_files = {
        RESTORE_OPERATION_MARKER,
        RESTORE_ARCHIVE_FILENAME,
        RESTORE_DATABASE_FILENAME,
        RESTORE_STATE_FILENAME,
        *allowed_extra_files,
    }
    actual_files = {
        child.name
        for child in operation.iterdir()
    }
    if actual_files != expected_files:
        raise RestoreStagingStateError(
            "Restore staging file allowlist changed."
        )
    if stat.S_IMODE(
        operation.stat().st_mode
    ) != 0o700:
        raise RestoreStagingStateError(
            "Restore operation permissions changed."
        )
    for name in expected_files:
        path = operation / name
        if (
            path.is_symlink()
            or not path.is_file()
            or stat.S_IMODE(
                path.stat().st_mode
            ) != 0o600
        ):
            raise RestoreStagingStateError(
                "Restore staging file permissions changed."
            )
    archive_path = (
        operation
        / RESTORE_ARCHIVE_FILENAME
    )
    candidate_path = (
        operation
        / RESTORE_DATABASE_FILENAME
    )
    if (
        sha256_path(archive_path)
        != state.archive_sha256
        or archive_path.stat().st_size
        != state.archive_size_bytes
        or sha256_path(candidate_path)
        != state.database_sha256
        or candidate_path.stat().st_size
        != state.database_size_bytes
    ):
        raise RestoreStagingStateError(
            "Restore staging hashes changed."
        )
    return StagedRestore(
        operation_directory=operation,
        state=state,
    )


def remove_staged_restore(
    validation_token: str,
    *,
    staging_root: Path,
) -> None:
    _validate_token(
        validation_token
    )
    operation = (
        staging_root.expanduser().resolve()
        / (
            RESTORE_OPERATION_PREFIX
            + validation_token
        )
    )
    _remove_owned_operation(
        operation,
        expected_root=staging_root,
    )



# PARTPILOT:RESTORE_STAGING_RETENTION:V451
def sweep_expired_restore_staging(
    staging_root: Path,
    *,
    now: datetime | None = None,
) -> int:
    root = staging_root.expanduser().resolve()
    if not root.exists():
        return 0
    if root.is_symlink() or not root.is_dir():
        raise RestoreStagingStateError(
            "Restore staging root is invalid."
        )
    if stat.S_IMODE(
        root.stat().st_mode
    ) != 0o700:
        raise RestoreStagingStateError(
            "Restore staging root permissions changed."
        )

    current = (
        now.astimezone(timezone.utc).replace(
            microsecond=0
        )
        if now is not None
        else _utc_now()
    )
    validation_only_files = {
        RESTORE_OPERATION_MARKER,
        RESTORE_ARCHIVE_FILENAME,
        RESTORE_DATABASE_FILENAME,
        RESTORE_STATE_FILENAME,
    }
    removed = 0

    for operation in sorted(
        root.iterdir()
    ):
        if not _owned_operation(
            operation,
            expected_root=root,
        ):
            continue

        try:
            children = list(
                operation.iterdir()
            )
        except OSError:
            continue
        if {
            child.name
            for child in children
        } != validation_only_files:
            continue
        if any(
            child.is_symlink()
            or not child.is_file()
            or stat.S_IMODE(
                child.stat().st_mode
            ) != 0o600
            for child in children
        ):
            continue

        try:
            state = _read_state(
                operation
            )
            expires = _parse_utc(
                state.expires_at_utc
            )
        except RestoreStagingStateError:
            continue
        if expires > current:
            continue

        _remove_owned_operation(
            operation,
            expected_root=root,
        )
        removed += 1

    return removed
