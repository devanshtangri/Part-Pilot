from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile
import threading
import time
import zipfile

from app.core.config import get_settings
from app.services.backups import (
    ARCHIVE_ENTRY_NAMES,
    DATABASE_ENTRY_NAME,
    EXPECTED_ALEMBIC_REVISION,
    EXPECTED_CRITICAL_SCHEMA_SHA256,
    MANIFEST_ENTRY_NAME,
    BackupArtifactError,
    canonical_json_bytes,
    create_backup_artifact,
    remove_backup_operation_directory,
    sqlite_path_from_database_url,
    validate_backup_artifact,
)


class BackupSmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise BackupSmokeFailure(message)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def logical_snapshot(path: Path) -> dict[str, list[dict[str, object]]]:
    connection = sqlite3.connect(path)
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
        return {
            table: [
                dict(row)
                for row in connection.execute(
                    f'SELECT * FROM "{table}" ORDER BY 1'
                ).fetchall()
            ]
            for table in tables
        }
    finally:
        connection.close()


def logical_sha256(
    snapshot: dict[str, list[dict[str, object]]],
) -> str:
    payload = json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def extract_database(
    archive_path: Path,
    destination: Path,
) -> None:
    with zipfile.ZipFile(archive_path, mode="r") as archive:
        with archive.open(
            DATABASE_ENTRY_NAME,
            mode="r",
        ) as source:
            with destination.open("xb") as output:
                shutil.copyfileobj(
                    source,
                    output,
                    length=1024 * 1024,
                )
    os.chmod(destination, 0o600)


def copy_sqlite_database(
    source: Path,
    destination: Path,
) -> None:
    source_connection = sqlite3.connect(source)
    destination_connection = sqlite3.connect(destination)
    try:
        source_connection.backup(destination_connection)
    finally:
        destination_connection.close()
        source_connection.close()
    os.chmod(destination, 0o600)


def rebuild_archive(
    source_archive: Path,
    destination_archive: Path,
    *,
    manifest_override: bytes | None = None,
    extra_entry: str | None = None,
) -> None:
    with zipfile.ZipFile(source_archive, mode="r") as source:
        with zipfile.ZipFile(
            destination_archive,
            mode="x",
            compression=zipfile.ZIP_DEFLATED,
        ) as destination:
            for info in source.infolist():
                payload = source.read(info.filename)
                if (
                    info.filename == MANIFEST_ENTRY_NAME
                    and manifest_override is not None
                ):
                    payload = manifest_override
                destination.writestr(info, payload)
            if extra_entry is not None:
                destination.writestr(
                    extra_entry,
                    b"unexpected\n",
                )


def expect_rejected(
    archive_path: Path,
    *,
    contains: str,
    validation_parent: Path,
) -> None:
    try:
        validate_backup_artifact(
            archive_path,
            validation_parent=validation_parent,
        )
    except BackupArtifactError as exc:
        if contains not in str(exc):
            fail(
                "Backup rejection used unexpected error: "
                f"{exc}"
            )
    else:
        fail(
            f"Invalid backup was accepted: {archive_path.name}"
        )


def concurrent_writer(
    database_path: Path,
    started: threading.Event,
    stop: threading.Event,
) -> None:
    connection = sqlite3.connect(
        database_path,
        timeout=30.0,
    )
    try:
        sequence = 0
        while not stop.is_set():
            sequence += 1
            connection.execute(
                "INSERT INTO audit_log "
                "(created_at, event_type, actor_type, summary, "
                "metadata_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    datetime.now(timezone.utc).isoformat(),
                    "backup.smoke_concurrent",
                    "system",
                    f"Concurrent backup smoke row {sequence}",
                    json.dumps(
                        {"sequence": sequence},
                        sort_keys=True,
                    ),
                ),
            )
            connection.commit()
            started.set()
            time.sleep(0.002)
    finally:
        connection.close()


def check_backup_artifact_core() -> None:
    source_path = sqlite_path_from_database_url(
        get_settings().database_url
    )
    if not source_path.is_file():
        fail(
            f"Copied smoke database is missing: {source_path}"
        )

    root = Path(
        tempfile.mkdtemp(
            prefix="partpilot-backup-smoke-"
        )
    )
    os.chmod(root, 0o700)
    operation_directory: Path | None = None
    concurrent_operation: Path | None = None

    try:
        source_file_hash = sha256_path(source_path)
        source_logical = logical_snapshot(source_path)
        source_logical_hash = logical_sha256(
            source_logical
        )
        fixed_time = datetime(
            2026,
            8,
            2,
            0,
            0,
            0,
            tzinfo=timezone.utc,
        )

        artifact = create_backup_artifact(
            source_path,
            root,
            created_at_utc=fixed_time,
        )
        operation_directory = (
            artifact.operation_directory
        )

        expected_filename = (
            "part-pilot-backup-20260802T000000Z-"
            "0007-projects-contract.ppbackup"
        )
        if artifact.filename != expected_filename:
            fail(
                "Backup filename is not deterministic: "
                f"{artifact.filename}"
            )
        if artifact.archive_path.name != expected_filename:
            fail("Backup archive path and filename differ.")
        if (
            stat.S_IMODE(
                operation_directory.stat().st_mode
            )
            != 0o700
        ):
            fail("Backup operation directory is not mode 0700.")
        for path in (
            artifact.archive_path,
            operation_directory / DATABASE_ENTRY_NAME,
            operation_directory / MANIFEST_ENTRY_NAME,
        ):
            if stat.S_IMODE(path.stat().st_mode) != 0o600:
                fail(
                    f"Backup artifact file is not mode 0600: {path.name}"
                )

        manifest = validate_backup_artifact(
            artifact.archive_path,
            validation_parent=root,
        )
        if manifest != artifact.manifest:
            fail("Validated manifest differs from generated manifest.")
        if (
            manifest.schema.alembic_revision
            != EXPECTED_ALEMBIC_REVISION
            or manifest.schema.critical_schema_sha256
            != EXPECTED_CRITICAL_SCHEMA_SHA256
        ):
            fail("Backup schema contract is incorrect.")
        if (
            artifact.archive_sha256
            != sha256_path(artifact.archive_path)
            or artifact.archive_size_bytes
            != artifact.archive_path.stat().st_size
        ):
            fail("Backup archive metadata is incorrect.")

        with zipfile.ZipFile(
            artifact.archive_path,
            mode="r",
        ) as archive:
            infos = archive.infolist()
            names = tuple(info.filename for info in infos)
            if names != ARCHIVE_ENTRY_NAMES:
                fail(
                    f"Backup archive entry order changed: {names}"
                )
            manifest_bytes = archive.read(
                MANIFEST_ENTRY_NAME
            )
            expected_manifest_bytes = canonical_json_bytes(
                manifest.model_dump(mode="json")
            )
            if manifest_bytes != expected_manifest_bytes:
                fail("Backup manifest is not canonical JSON.")
            if not manifest_bytes.endswith(b"\n"):
                fail("Backup manifest lacks a trailing newline.")

        extracted = root / "extracted.db"
        extract_database(
            artifact.archive_path,
            extracted,
        )
        if logical_snapshot(extracted) != source_logical:
            fail(
                "Online backup did not preserve every logical row."
            )
        if (
            sha256_path(source_path) != source_file_hash
            or logical_sha256(
                logical_snapshot(source_path)
            )
            != source_logical_hash
        ):
            fail(
                "Backup generation changed its source database."
            )

        extra_archive = root / "extra.ppbackup"
        rebuild_archive(
            artifact.archive_path,
            extra_archive,
            extra_entry="../unexpected.txt",
        )
        expect_rejected(
            extra_archive,
            contains="exactly two entries",
            validation_parent=root,
        )

        mismatch_archive = root / "hash-mismatch.ppbackup"
        raw_manifest = manifest.model_dump(mode="json")
        raw_manifest["database"]["sha256"] = "0" * 64
        rebuild_archive(
            artifact.archive_path,
            mismatch_archive,
            manifest_override=canonical_json_bytes(
                raw_manifest
            ),
        )
        expect_rejected(
            mismatch_archive,
            contains="SHA-256",
            validation_parent=root,
        )

        concurrent_source = (
            root / "concurrent-source.db"
        )
        copy_sqlite_database(
            source_path,
            concurrent_source,
        )
        initial_audits = len(
            logical_snapshot(concurrent_source)[
                "audit_log"
            ]
        )
        started = threading.Event()
        stop = threading.Event()
        thread = threading.Thread(
            target=concurrent_writer,
            args=(
                concurrent_source,
                started,
                stop,
            ),
            daemon=True,
        )
        thread.start()
        if not started.wait(timeout=10.0):
            fail("Concurrent writer did not start.")

        try:
            concurrent_artifact = create_backup_artifact(
                concurrent_source,
                root,
                created_at_utc=fixed_time.replace(
                    second=1
                ),
            )
            concurrent_operation = (
                concurrent_artifact.operation_directory
            )
        finally:
            stop.set()
            thread.join(timeout=10.0)
        if thread.is_alive():
            fail("Concurrent writer did not stop.")

        concurrent_extracted = (
            root / "concurrent-extracted.db"
        )
        extract_database(
            concurrent_artifact.archive_path,
            concurrent_extracted,
        )
        artifact_audits = len(
            logical_snapshot(concurrent_extracted)[
                "audit_log"
            ]
        )
        final_audits = len(
            logical_snapshot(concurrent_source)[
                "audit_log"
            ]
        )
        if not (
            initial_audits
            < artifact_audits
            <= final_audits
        ):
            fail(
                "Online snapshot was not a consistent point "
                "during concurrent writes: "
                f"initial={initial_audits}, "
                f"artifact={artifact_audits}, "
                f"final={final_audits}"
            )
        validate_backup_artifact(
            concurrent_artifact.archive_path,
            validation_parent=root,
        )

        remove_backup_operation_directory(
            concurrent_operation,
            expected_parent=root,
        )
        concurrent_operation = None
        remove_backup_operation_directory(
            operation_directory,
            expected_parent=root,
        )
        operation_directory = None

        foreign_directory = root / "not-owned"
        foreign_directory.mkdir()
        try:
            remove_backup_operation_directory(
                foreign_directory,
                expected_parent=root,
            )
        except BackupArtifactError:
            pass
        else:
            fail(
                "Cleanup accepted an unowned directory."
            )

    finally:
        if concurrent_operation is not None:
            shutil.rmtree(
                concurrent_operation,
                ignore_errors=True,
            )
        if operation_directory is not None:
            shutil.rmtree(
                operation_directory,
                ignore_errors=True,
            )
        shutil.rmtree(root, ignore_errors=True)

    print(
        "[PASS] Backup artifact core creates deterministic "
        "version-1 online SQLite snapshots, validates canonical "
        "two-file archives, preserves all copied rows, remains "
        "consistent during concurrent writes, rejects malformed "
        "artifacts, and cleans only marker-owned directories"
    )


def main() -> None:
    check_backup_artifact_core()


if __name__ == "__main__":
    main()
