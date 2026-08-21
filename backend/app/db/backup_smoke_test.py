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
    BACKUP_FORMAT_VERSION,
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
            "0017-user-roles.ppbackup"
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

        legacy_archive = root / "legacy-v1.ppbackup"
        legacy_manifest = manifest.model_dump(mode="json")
        legacy_manifest["format_version"] = 1
        legacy_manifest["application"]["backup_writer_version"] = 1
        rebuild_archive(
            artifact.archive_path,
            legacy_archive,
            manifest_override=canonical_json_bytes(legacy_manifest),
        )
        expect_rejected(
            legacy_archive,
            contains="backup format version 2",
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
        "version-2 online SQLite snapshots, validates canonical "
        "two-file archives, preserves all copied rows, remains "
        "consistent during concurrent writes, rejects malformed "
        "artifacts, and cleans only marker-owned directories"
    )




def check_backup_download_api() -> None:
    from unittest.mock import patch
    from uuid import uuid4

    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from app.api.routes import backups as backups_route
    from app.db.session import SessionLocal
    from app.main import app as fastapi_app
    from app.models import AuditLog
    from app.services.auth import create_session, create_user

    source_path = sqlite_path_from_database_url(
        get_settings().database_url
    )
    baseline = logical_snapshot(source_path)
    baseline_hash = logical_sha256(baseline)
    suffix = uuid4().hex[:12]
    username = f"smoke_backup_api_{suffix}"
    password = "backup-api-smoke-password"
    user_id: int | None = None
    token: str | None = None
    root = Path(
        tempfile.mkdtemp(
            prefix="partpilot-backup-api-smoke-"
        )
    )
    os.chmod(root, 0o700)

    def cleanup() -> None:
        if user_id is not None:
            with SessionLocal() as db:
                db.execute(
                    text(
                        "DELETE FROM audit_log "
                        "WHERE event_type='backup.generated' "
                        "AND actor_user_id=:user_id"
                    ),
                    {"user_id": user_id},
                )
                db.execute(
                    text(
                        "DELETE FROM sessions "
                        "WHERE user_id=:user_id"
                    ),
                    {"user_id": user_id},
                )
                db.execute(
                    text(
                        "DELETE FROM users WHERE id=:user_id"
                    ),
                    {"user_id": user_id},
                )
                db.commit()

    cleanup()
    client = TestClient(fastapi_app)

    try:
        paths = client.get(
            "/openapi.json"
        ).json().get("paths", {})
        if set(
            paths.get("/api/backups/download", {})
        ) != {"post"}:
            fail(
                "Backup download OpenAPI contract is incorrect: "
                f"{paths.get('/api/backups/download')}"
            )
        if set(
            paths.get("/api/backups/status", {})
        ) != {"get"}:
            fail(
                "Backup status OpenAPI contract is incorrect: "
                f"{paths.get('/api/backups/status')}"
            )
        if "post" not in paths.get(
            "/api/parts/{part_id}/restore",
            {},
        ):
            fail(
                "Inventory soft-delete restore route disappeared."
            )

        unauthenticated = client.post(
            "/api/backups/download"
        )
        if unauthenticated.status_code != 401:
            fail(
                "Backup download should require authentication: "
                f"{unauthenticated.status_code}"
            )
        unauthenticated_status = client.get(
            "/api/backups/status"
        )
        if unauthenticated_status.status_code != 401:
            fail(
                "Backup status should require authentication: "
                f"{unauthenticated_status.status_code}"
            )

        with SessionLocal() as db:
            user = create_user(
                db,
                username=username,
                password=password,
                display_name="Backup API Smoke",
                commit=False,
            )
            session_token = create_session(
                db,
                user=user,
                user_agent="backup-api-smoke",
                ip_address="127.0.0.1",
                commit=False,
            )
            legacy_status_filename = (
                "part-pilot-backup-20260801T000000Z-"
                "0007-projects-contract.ppbackup"
            )
            db.add(
                AuditLog(
                    event_type="backup.generated",
                    entity_type="backup",
                    entity_id=None,
                    actor_type="user",
                    actor_user_id=user.id,
                    summary="Generated manual Part Pilot backup",
                    before_json=None,
                    after_json={
                        "filename": legacy_status_filename,
                        "format": "part-pilot-backup",
                        "format_version": 1,
                        "alembic_revision": "0007_projects_contract",
                        "database_sha256": "0" * 64,
                        "archive_sha256": "1" * 64,
                    },
                    metadata_json={
                        "manual_download": True,
                        "archive_size_bytes": 123,
                        "database_size_bytes": 456,
                        "compatibility_policy": "exact_revision",
                        "media_type": "application/vnd.partpilot.backup+zip",
                    },
                )
            )
            db.commit()
            db.refresh(user)
            user_id = int(user.id)
            token = session_token.token

        headers = {
            "Authorization": f"Bearer {token}"
        }
        before_status = logical_snapshot(source_path)
        status_before_response = client.get(
            "/api/backups/status",
            headers=headers,
        )
        if status_before_response.status_code != 200:
            fail(
                "Authenticated backup status failed: "
                f"{status_before_response.status_code}: "
                f"{status_before_response.text}"
            )
        if (
            status_before_response.headers.get("cache-control")
            != "no-store, max-age=0"
            or status_before_response.headers.get("pragma") != "no-cache"
            or status_before_response.headers.get("x-content-type-options")
            != "nosniff"
        ):
            fail(
                "Backup status no-cache/security headers are incorrect."
            )
        status_before = status_before_response.json()
        if (
            status_before.get("mode") != "manual_download"
            or status_before.get("scheduled_backups_active") is not False
            or status_before.get("server_copy_retained") is not False
            or not isinstance(
                status_before.get("recorded_download_count"),
                int,
            )
            or status_before.get("recorded_download_count") < 0
        ):
            fail(
                "Backup status capability flags are incorrect: "
                f"{status_before}"
            )
        latest_before = status_before.get("latest_manual_backup")
        if (
            not isinstance(latest_before, dict)
            or latest_before.get("filename") != legacy_status_filename
            or latest_before.get("format_version") != 1
            or latest_before.get("alembic_revision")
            != "0007_projects_contract"
        ):
            fail(
                "Historical V1 backup status was not preserved: "
                f"{status_before}"
            )
        if logical_snapshot(source_path) != before_status:
            fail("Backup status read changed the copied database.")

        before_request = logical_snapshot(source_path)
        before_audits = len(
            before_request["audit_log"]
        )
        before_backups = len(
            before_request["backups"]
        )
        protected_tables = (
            "app_settings",
            "api_keys",
            "part_types",
            "part_type_fields",
            "manufacturers",
            "packages",
            "locations",
            "parts",
            "part_field_values",
            "aliases",
            "tags",
            "part_tags",
            "projects",
            "project_items",
            "reservations",
            "reservation_items",
            "stock_movements",
            "backups",
        )
        before_counts = {
            table: len(before_request[table])
            for table in protected_tables
        }

        with patch.object(
            backups_route,
            "BACKUP_OPERATION_PARENT",
            root,
        ):
            response = client.post(
                "/api/backups/download",
                headers=headers,
            )

        if response.status_code != 200:
            fail(
                "Authenticated backup download failed: "
                f"{response.status_code}: {response.text}"
            )
        if (
            response.headers.get("content-type")
            != "application/vnd.partpilot.backup+zip"
        ):
            fail(
                "Backup media type is incorrect: "
                f"{response.headers.get('content-type')}"
            )
        if (
            response.headers.get("cache-control")
            != "no-store, max-age=0"
            or response.headers.get("pragma") != "no-cache"
            or response.headers.get("x-content-type-options")
            != "nosniff"
        ):
            fail(
                "Backup no-cache/security headers are incorrect."
            )
        content_disposition = response.headers.get(
            "content-disposition",
            "",
        )
        if (
            "attachment" not in content_disposition.lower()
            or ".ppbackup" not in content_disposition
            or "part-pilot-backup-" not in content_disposition
        ):
            fail(
                "Backup Content-Disposition is incorrect: "
                f"{content_disposition}"
            )

        downloaded = root / "downloaded.ppbackup"
        downloaded.write_bytes(response.content)
        os.chmod(downloaded, 0o600)
        manifest = validate_backup_artifact(
            downloaded,
            validation_parent=root,
        )
        if (
            manifest.format != "part-pilot-backup"
            or manifest.format_version != BACKUP_FORMAT_VERSION
            or manifest.schema.alembic_revision
            != EXPECTED_ALEMBIC_REVISION
        ):
            fail(
                "Downloaded backup manifest is incorrect."
            )

        extracted = root / "downloaded.db"
        extract_database(downloaded, extracted)
        downloaded_snapshot = logical_snapshot(extracted)
        if downloaded_snapshot != before_request:
            fail(
                "Downloaded snapshot does not match the "
                "pre-audit database state."
            )

        after_success = logical_snapshot(source_path)
        if len(after_success["audit_log"]) != before_audits + 1:
            fail(
                "Successful backup did not append exactly one audit."
            )
        if len(after_success["backups"]) != before_backups:
            fail(
                "Manual download unexpectedly inserted a backups row."
            )
        after_counts = {
            table: len(after_success[table])
            for table in protected_tables
        }
        if after_counts != before_counts:
            fail(
                "Backup download changed protected table counts: "
                f"{before_counts} -> {after_counts}"
            )

        with SessionLocal() as db:
            audit = db.execute(
                text(
                    "SELECT actor_type, actor_user_id, summary, "
                    "after_json, metadata_json "
                    "FROM audit_log "
                    "WHERE event_type='backup.generated' "
                    "AND actor_user_id=:user_id "
                    "ORDER BY id DESC LIMIT 1"
                ),
                {"user_id": user_id},
            ).mappings().one()
        raw_after_json = audit["after_json"]
        after_json = (
            raw_after_json
            if isinstance(raw_after_json, dict)
            else json.loads(raw_after_json)
        )
        raw_metadata_json = audit["metadata_json"]
        metadata_json = (
            raw_metadata_json
            if isinstance(raw_metadata_json, dict)
            else json.loads(raw_metadata_json)
        )
        disposition_filename = (
            content_disposition.split(
                'filename="',
                1,
            )[1].split('"', 1)[0]
            if 'filename="' in content_disposition
            else ""
        )
        if (
            audit["actor_type"] != "user"
            or int(audit["actor_user_id"]) != user_id
            or audit["summary"]
            != "Generated manual Part Pilot backup"
            or after_json.get("filename")
            != disposition_filename
        ):
            fail(
                "Backup audit actor, summary, or filename is incorrect."
            )

        status_after_response = client.get(
            "/api/backups/status",
            headers=headers,
        )
        if status_after_response.status_code != 200:
            fail(
                "Post-download backup status failed: "
                f"{status_after_response.status_code}: "
                f"{status_after_response.text}"
            )
        status_after = status_after_response.json()
        latest = status_after.get("latest_manual_backup")
        if (
            status_after.get("recorded_download_count")
            != status_before["recorded_download_count"] + 1
            or not isinstance(latest, dict)
            or latest.get("filename") != disposition_filename
            or latest.get("archive_size_bytes") != len(response.content)
            or latest.get("database_size_bytes")
            != manifest.database.size_bytes
            or latest.get("format_version") != BACKUP_FORMAT_VERSION
            or latest.get("alembic_revision")
            != EXPECTED_ALEMBIC_REVISION
            or not isinstance(latest.get("generated_at_utc"), str)
            or not latest["generated_at_utc"].endswith("Z")
        ):
            fail(
                "Backup status did not reflect the new manual "
                f"download accurately: {status_after}"
            )
        if (
            after_json.get("format")
            != "part-pilot-backup"
            or after_json.get("format_version") != BACKUP_FORMAT_VERSION
            or after_json.get("alembic_revision")
            != EXPECTED_ALEMBIC_REVISION
            or after_json.get("database_sha256")
            != manifest.database.sha256
            or after_json.get("archive_sha256")
            != hashlib.sha256(response.content).hexdigest()
            or metadata_json.get("manual_download") is not True
            or metadata_json.get("media_type")
            != "application/vnd.partpilot.backup+zip"
        ):
            fail(
                "Backup audit metadata does not match the artifact."
            )

        with patch.object(
            backups_route,
            "BACKUP_OPERATION_PARENT",
            root,
        ):
            acquired = (
                backups_route.BACKUP_GENERATION_LOCK.acquire(
                    blocking=False
                )
            )
            if not acquired:
                fail("Could not acquire the backup smoke lock.")
            try:
                contention = client.post(
                    "/api/backups/download",
                    headers=headers,
                )
            finally:
                backups_route.BACKUP_GENERATION_LOCK.release()
        if contention.status_code != 409:
            fail(
                "Concurrent backup generation should return 409: "
                f"{contention.status_code}"
            )

        with (
            patch.object(
                backups_route,
                "BACKUP_OPERATION_PARENT",
                root,
            ),
            patch.object(
                backups_route,
                "create_backup_artifact",
                side_effect=BackupArtifactError(
                    "injected generation failure"
                ),
            ),
        ):
            generation_failure = client.post(
                "/api/backups/download",
                headers=headers,
            )
        if (
            generation_failure.status_code != 500
            or generation_failure.json().get("detail")
            != "Backup generation failed."
        ):
            fail(
                "Injected backup generation failure was not sanitized."
            )

        with (
            patch.object(
                backups_route,
                "BACKUP_OPERATION_PARENT",
                root,
            ),
            patch.object(
                backups_route,
                "record_backup_generated_audit",
                side_effect=RuntimeError(
                    "injected audit failure"
                ),
            ),
        ):
            audit_failure = client.post(
                "/api/backups/download",
                headers=headers,
            )
        if (
            audit_failure.status_code != 500
            or audit_failure.json().get("detail")
            != "Backup generation failed."
        ):
            fail(
                "Injected backup audit failure was not sanitized."
            )

        remaining_operations = [
            path
            for path in root.iterdir()
            if path.is_dir()
            and path.name.startswith(
                "partpilot-backup-"
            )
        ]
        if remaining_operations:
            fail(
                "Backup response/failure cleanup left operation "
                f"directories: {remaining_operations}"
            )

        final_fixture_state = logical_snapshot(source_path)
        if len(final_fixture_state["audit_log"]) != before_audits + 1:
            fail(
                "Rejected backup requests added unexpected audits."
            )
        if len(final_fixture_state["backups"]) != before_backups:
            fail(
                "Rejected backup requests changed backups rows."
            )

    finally:
        cleanup()
        shutil.rmtree(root, ignore_errors=True)

    final_state = logical_snapshot(source_path)
    if (
        final_state != baseline
        or logical_sha256(final_state) != baseline_hash
    ):
        fail(
            "Backup API smoke cleanup did not restore its "
            "copied-database baseline."
        )

    print(
        "[PASS] Protected backup download and status enforce "
        "authentication, expose truthful no-store manual-download "
        "metadata without implying scheduling or retained server copies, "
        "return a canonical .ppbackup file, record one actor-attributed "
        "post-snapshot audit without backups rows or inventory mutations, "
        "limit concurrent generation, sanitize failures, and clean "
        "operation-owned files"
    )

def main() -> None:
    check_backup_artifact_core()
    check_backup_download_api()


if __name__ == "__main__":
    main()
