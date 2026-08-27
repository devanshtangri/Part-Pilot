from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import tempfile
from unittest.mock import patch
from uuid import uuid4
import zipfile

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.api.routes import restores as restores_route
from app.core.config import get_settings
from app.core.upload_limits import (
    RestoreUploadLimitMiddleware,
)
from app.db.session import SessionLocal
from app.main import app as fastapi_app
from app.models import User
from app.services.auth import (
    create_session,
    create_user,
)
from app.services.authorization import ROLE_ADMINISTRATOR, ROLE_OWNER
from app.schemas.restores import (
    RestoreStageState,
    RestoreValidationResponse,
)
from app.services.backups import (
    BACKUP_FORMAT_VERSION,
    BACKUP_MEDIA_TYPE,
    EXPECTED_ALEMBIC_REVISION,
    DATABASE_ENTRY_NAME,
    canonical_json_bytes,
    MANIFEST_ENTRY_NAME,
    create_backup_artifact,
    remove_backup_operation_directory,
    sqlite_path_from_database_url,
    validate_backup_artifact,
)
from app.services.restores import (
    RESTORE_ARCHIVE_FILENAME,
    RESTORE_COMMIT_FILENAME,
    RESTORE_DATABASE_FILENAME,
    RESTORE_OPERATION_MARKER,
    RESTORE_PREVIOUS_FILENAME,
    RESTORE_RESULT_FILENAME,
    RESTORE_ROLLBACK_FILENAME,
    RESTORE_STATE_FILENAME,
    RestoreStagingStateError,
    load_staged_restore,
    remove_staged_restore,
    stage_restore_archive,
    sweep_expired_restore_staging,
)


class RestoreValidationSmokeFailure(
    RuntimeError
):
    pass


def fail(message: str) -> None:
    raise RestoreValidationSmokeFailure(
        message
    )


def logical_snapshot(
    path: Path,
) -> dict[str, list[dict[str, object]]]:
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


def expect_status(
    response,
    expected: int,
    label: str,
) -> None:
    if response.status_code != expected:
        fail(
            f"{label} returned "
            f"{response.status_code}: {response.text}"
        )


async def content_length_limit_probe() -> None:
    sent: list[dict[str, object]] = []
    inner_called = False

    async def receive():
        return {
            "type": "http.request",
            "body": b"",
            "more_body": False,
        }

    async def send(message):
        sent.append(message)

    async def inner_app(
        scope,
        inner_receive,
        inner_send,
    ):
        nonlocal inner_called
        inner_called = True
        await inner_send(
            {
                "type": "http.response.start",
                "status": 204,
                "headers": [],
            }
        )
        await inner_send(
            {
                "type": "http.response.body",
                "body": b"",
            }
        )

    middleware = RestoreUploadLimitMiddleware(
        inner_app,
        max_body_bytes=10,
    )
    await middleware(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/restores/validate",
            "headers": [
                (
                    b"content-length",
                    b"11",
                ),
            ],
        },
        receive,
        send,
    )
    starts = [
        message
        for message in sent
        if message.get("type")
        == "http.response.start"
    ]
    if (
        inner_called
        or len(starts) != 1
        or starts[0].get("status") != 413
    ):
        fail(
            f"Content-Length upload limit failed: {sent}"
        )


async def chunked_limit_probe() -> None:
    messages = [
        {
            "type": "http.request",
            "body": b"123456",
            "more_body": True,
        },
        {
            "type": "http.request",
            "body": b"789012",
            "more_body": False,
        },
    ]
    sent: list[dict[str, object]] = []

    async def receive():
        if messages:
            return messages.pop(0)
        return {
            "type": "http.disconnect",
        }

    async def send(message):
        sent.append(message)

    async def drain_app(
        scope,
        inner_receive,
        inner_send,
    ):
        while True:
            message = await inner_receive()
            if (
                message.get("type")
                != "http.request"
                or not message.get(
                    "more_body",
                    False,
                )
            ):
                break
        await inner_send(
            {
                "type": "http.response.start",
                "status": 204,
                "headers": [],
            }
        )
        await inner_send(
            {
                "type": "http.response.body",
                "body": b"",
            }
        )

    middleware = RestoreUploadLimitMiddleware(
        drain_app,
        max_body_bytes=10,
    )
    await middleware(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/restores/validate",
            "headers": [],
        },
        receive,
        send,
    )
    starts = [
        message
        for message in sent
        if message.get("type")
        == "http.response.start"
    ]
    if (
        len(starts) != 1
        or starts[0].get("status") != 413
    ):
        fail(
            f"Chunked upload limit failed: {sent}"
        )


def build_compression_bomb(
    path: Path,
) -> None:
    with zipfile.ZipFile(
        path,
        mode="x",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        archive.writestr(
            MANIFEST_ENTRY_NAME,
            b"{}\n",
        )
        archive.writestr(
            DATABASE_ENTRY_NAME,
            b"\0" * (2 * 1024 * 1024),
        )


def check_restore_validation_api() -> None:
    response_revision = (
        RestoreValidationResponse.model_json_schema()
        ["properties"]["alembic_revision"].get("const")
    )
    stage_revision = (
        RestoreStageState.model_json_schema()
        ["properties"]["alembic_revision"].get("const")
    )
    if (
        response_revision != EXPECTED_ALEMBIC_REVISION
        or stage_revision != EXPECTED_ALEMBIC_REVISION
    ):
        fail(
            "Restore schema revision contract drifted: "
            f"response={response_revision!r}, stage={stage_revision!r}, "
            f"expected={EXPECTED_ALEMBIC_REVISION!r}"
        )

    database_path = (
        sqlite_path_from_database_url(
            get_settings().database_url
        )
    )
    baseline = logical_snapshot(
        database_path
    )
    root = Path(
        tempfile.mkdtemp(
            prefix="partpilot-restore-validation-smoke-"
        )
    )
    os.chmod(root, 0o700)
    artifact_root = root / "artifacts"
    artifact_root.mkdir(mode=0o700)
    staging_root = root / "staging"
    suffix = uuid4().hex[:12]
    username = ""
    user_id: int | None = None
    fixture_user_id: int | None = None
    artifact_operation: Path | None = None

    def cleanup_fixture() -> None:
        with SessionLocal() as db:
            if user_id is not None:
                db.execute(
                    text(
                        "DELETE FROM sessions "
                        "WHERE user_id=:user_id "
                        "AND user_agent='restore-validation-smoke'"
                    ),
                    {"user_id": user_id},
                )
            if fixture_user_id is not None:
                db.execute(
                    text(
                        "DELETE FROM users WHERE id=:user_id"
                    ),
                    {"user_id": fixture_user_id},
                )
            db.commit()

    client = TestClient(
        fastapi_app
    )
    try:
        openapi_document = client.get(
            "/openapi.json"
        ).json()
        paths = openapi_document.get("paths", {})
        restore_schema_revision = (
            openapi_document.get("components", {})
            .get("schemas", {})
            .get("RestoreValidationResponse", {})
            .get("properties", {})
            .get("alembic_revision", {})
            .get("const")
        )
        if restore_schema_revision != EXPECTED_ALEMBIC_REVISION:
            fail(
                "Restore validation OpenAPI revision contract is stale: "
                f"{restore_schema_revision!r}"
            )
        if set(
            paths.get(
                "/api/restores/validate",
                {},
            )
        ) != {"post"}:
            fail(
                "Restore validation OpenAPI contract is incorrect."
            )
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
        unexpected_restore_paths = [
            path
            for path in paths
            if path.startswith(
                "/api/restores/"
            )
            and path
            not in {
                "/api/restores/validate",
                commit_path,
            }
        ]
        if unexpected_restore_paths:
            fail(
                "Unexpected restore controls were exposed: "
                f"{unexpected_restore_paths}"
            )

        unauthenticated = client.post(
            "/api/restores/validate",
            files={
                "backup": (
                    "empty.ppbackup",
                    b"x",
                    BACKUP_MEDIA_TYPE,
                ),
            },
        )
        expect_status(
            unauthenticated,
            401,
            "Unauthenticated restore validation",
        )

        with SessionLocal() as db:
            primary_owner = db.execute(
                select(User).order_by(User.id.asc()).limit(1)
            ).scalar_one_or_none()
            if (
                primary_owner is None
                or primary_owner.role != ROLE_OWNER
                or not primary_owner.is_active
            ):
                fail("Restore smoke requires an active primary Owner as the first user")
            fixture_user = create_user(
                db,
                username=f"smoke_restore_validate_{suffix}",
                password="restore-validation-smoke-password",
                display_name="Restore Validation Smoke",
                role=ROLE_ADMINISTRATOR,
                commit=False,
            )
            db.flush()
            session = create_session(
                db,
                user=primary_owner,
                user_agent="restore-validation-smoke",
                ip_address="127.0.0.1",
                commit=False,
            )
            db.commit()
            user_id = int(primary_owner.id)
            username = primary_owner.username
            fixture_user_id = int(fixture_user.id)
            token = session.token

        headers = {
            "Authorization": f"Bearer {token}"
        }
        before_validation = logical_snapshot(
            database_path
        )
        artifact = create_backup_artifact(
            database_path,
            artifact_root,
            created_at_utc=datetime(
                2026,
                8,
                2,
                0,
                45,
                tzinfo=timezone.utc,
            ),
        )
        artifact_operation = (
            artifact.operation_directory
        )
        artifact_bytes = (
            artifact.archive_path.read_bytes()
        )

        with patch.object(
            restores_route,
            "RESTORE_STAGING_ROOT",
            staging_root,
        ):
            response = client.post(
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
        expect_status(
            response,
            200,
            "Valid restore validation",
        )
        payload = response.json()
        if (
            payload.get("status")
            != "ready_for_review"
            or payload.get("format_version") != BACKUP_FORMAT_VERSION
            or payload.get("alembic_revision")
            != EXPECTED_ALEMBIC_REVISION
            or payload.get("active_user_count", 0)
            < 1
            or not payload.get(
                "validation_token"
            )
            or "operation_directory"
            in payload
            or "archive_path" in payload
        ):
            fail(
                f"Restore validation metadata is invalid: {payload}"
            )

        validation_token = str(
            payload["validation_token"]
        )
        staged = load_staged_restore(
            validation_token,
            actor_user_id=user_id,
            actor_username=username,
            staging_root=staging_root,
        )
        expected_files = {
            RESTORE_OPERATION_MARKER,
            RESTORE_ARCHIVE_FILENAME,
            RESTORE_DATABASE_FILENAME,
            RESTORE_STATE_FILENAME,
        }
        actual_files = {
            path.name
            for path in (
                staged.operation_directory
            ).iterdir()
        }
        if actual_files != expected_files:
            fail(
                f"Restore staging allowlist changed: {actual_files}"
            )
        if stat.S_IMODE(
            staged.operation_directory.stat().st_mode
        ) != 0o700:
            fail(
                "Restore operation directory is not mode 0700."
            )
        for name in expected_files:
            path = (
                staged.operation_directory
                / name
            )
            if stat.S_IMODE(
                path.stat().st_mode
            ) != 0o600:
                fail(
                    f"Restore staged file is not mode 0600: {name}"
                )

        candidate = (
            staged.operation_directory
            / RESTORE_DATABASE_FILENAME
        )
        if (
            logical_snapshot(candidate)
            != before_validation
        ):
            fail(
                "Staged restore candidate differs from the "
                "pre-validation database."
            )
        if (
            logical_snapshot(database_path)
            != before_validation
        ):
            fail(
                "Restore validation changed its source database."
            )

        try:
            load_staged_restore(
                validation_token,
                actor_user_id=user_id + 1,
                actor_username=username,
                staging_root=staging_root,
            )
        except RestoreStagingStateError:
            pass
        else:
            fail(
                "Restore token was not bound to its requesting user."
            )

        remove_staged_restore(
            validation_token,
            staging_root=staging_root,
        )
        if staged.operation_directory.exists():
            fail(
                "Restore staging cleanup did not remove the operation."
            )

        with patch.object(
            restores_route,
            "RESTORE_STAGING_ROOT",
            staging_root,
        ):
            invalid = client.post(
                "/api/restores/validate",
                headers=headers,
                files={
                    "backup": (
                        "invalid.ppbackup",
                        b"not-a-zip",
                        BACKUP_MEDIA_TYPE,
                    ),
                },
            )
        expect_status(
            invalid,
            422,
            "Invalid restore archive",
        )

        with patch.object(
            restores_route,
            "RESTORE_STAGING_ROOT",
            staging_root,
        ):
            wrong_extension = client.post(
                "/api/restores/validate",
                headers=headers,
                files={
                    "backup": (
                        "invalid.zip",
                        artifact_bytes,
                        BACKUP_MEDIA_TYPE,
                    ),
                },
            )
        expect_status(
            wrong_extension,
            422,
            "Wrong restore extension",
        )

        bomb_path = root / "bomb.ppbackup"
        build_compression_bomb(
            bomb_path
        )
        with patch.object(
            restores_route,
            "RESTORE_STAGING_ROOT",
            staging_root,
        ):
            bomb = client.post(
                "/api/restores/validate",
                headers=headers,
                files={
                    "backup": (
                        "bomb.ppbackup",
                        bomb_path.read_bytes(),
                        BACKUP_MEDIA_TYPE,
                    ),
                },
            )
        expect_status(
            bomb,
            422,
            "Suspicious compression ratio",
        )

        inactive_database = (
            root / "inactive.db"
        )
        copy_database(
            database_path,
            inactive_database,
        )
        connection = sqlite3.connect(
            inactive_database
        )
        try:
            connection.execute(
                "UPDATE users SET is_active=0"
            )
            connection.commit()
        finally:
            connection.close()
        inactive_artifact = (
            create_backup_artifact(
                inactive_database,
                artifact_root,
                created_at_utc=datetime(
                    2026,
                    8,
                    2,
                    0,
                    46,
                    tzinfo=timezone.utc,
                ),
            )
        )
        try:
            with patch.object(
                restores_route,
                "RESTORE_STAGING_ROOT",
                staging_root,
            ):
                inactive = client.post(
                    "/api/restores/validate",
                    headers=headers,
                    files={
                        "backup": (
                            inactive_artifact.filename,
                            inactive_artifact.archive_path.read_bytes(),
                            BACKUP_MEDIA_TYPE,
                        ),
                    },
                )
            expect_status(
                inactive,
                422,
                "No-active-user restore",
            )
        finally:
            remove_backup_operation_directory(
                inactive_artifact.operation_directory,
                expected_parent=artifact_root,
            )

        multiple_owner_database = root / "multiple-owner.db"
        copy_database(database_path, multiple_owner_database)
        connection = sqlite3.connect(multiple_owner_database)
        try:
            connection.execute(
                "UPDATE users SET role='owner' WHERE id=:user_id",
                {"user_id": fixture_user_id},
            )
            connection.commit()
        finally:
            connection.close()
        multiple_owner_artifact = create_backup_artifact(
            multiple_owner_database,
            artifact_root,
            created_at_utc=datetime(
                2026, 8, 2, 0, 46, 30, tzinfo=timezone.utc
            ),
        )
        try:
            with patch.object(
                restores_route,
                "RESTORE_STAGING_ROOT",
                staging_root,
            ):
                multiple_owner = client.post(
                    "/api/restores/validate",
                    headers=headers,
                    files={
                        "backup": (
                            multiple_owner_artifact.filename,
                            multiple_owner_artifact.archive_path.read_bytes(),
                            BACKUP_MEDIA_TYPE,
                        ),
                    },
                )
            expect_status(
                multiple_owner,
                422,
                "Multiple-Owner restore",
            )
        finally:
            remove_backup_operation_directory(
                multiple_owner_artifact.operation_directory,
                expected_parent=artifact_root,
            )

        asyncio.run(
            content_length_limit_probe()
        )
        asyncio.run(
            chunked_limit_probe()
        )

        fixed = datetime(
            2026,
            8,
            2,
            0,
            47,
            tzinfo=timezone.utc,
        )

        def stage_for_sweep(
            *,
            ttl_seconds: int,
        ):
            with artifact.archive_path.open(
                "rb"
            ) as source:
                return stage_restore_archive(
                    source,
                    original_filename=(
                        artifact.filename
                    ),
                    actor_user_id=user_id,
                    actor_username=username,
                    staging_root=staging_root,
                    now=fixed,
                    ttl_seconds=ttl_seconds,
                )

        expiring = stage_for_sweep(ttl_seconds=1)
        fresh = stage_for_sweep(ttl_seconds=60)
        pending = stage_for_sweep(ttl_seconds=1)
        pending_commit = pending.operation_directory / RESTORE_COMMIT_FILENAME
        pending_commit.write_text("{}", encoding="utf-8")
        os.chmod(pending_commit, 0o600)

        completed = stage_for_sweep(ttl_seconds=1)
        (completed.operation_directory / RESTORE_DATABASE_FILENAME).unlink()
        for filename in (RESTORE_COMMIT_FILENAME, RESTORE_RESULT_FILENAME):
            path = completed.operation_directory / filename
            path.write_text("{}", encoding="utf-8")
            os.chmod(path, 0o600)
        for filename in (RESTORE_PREVIOUS_FILENAME, RESTORE_ROLLBACK_FILENAME):
            path = completed.operation_directory / filename
            shutil.copy2(database_path, path)
            os.chmod(path, stat.S_IMODE(database_path.stat().st_mode))

        unknown_extra = stage_for_sweep(ttl_seconds=1)
        unknown_path = unknown_extra.operation_directory / "unknown-evidence.txt"
        unknown_path.write_text("preserve", encoding="utf-8")
        os.chmod(unknown_path, 0o600)

        legacy_v1 = stage_for_sweep(ttl_seconds=1)
        legacy_state_path = legacy_v1.operation_directory / RESTORE_STATE_FILENAME
        legacy_state = json.loads(legacy_state_path.read_text(encoding="utf-8"))
        legacy_state["format_version"] = 1
        legacy_state_path.write_bytes(canonical_json_bytes(legacy_state))
        os.chmod(legacy_state_path, 0o600)

        removed = sweep_expired_restore_staging(
            staging_root,
            now=fixed + timedelta(seconds=2),
        )
        if (
            removed != 1
            or expiring.operation_directory.exists()
            or not fresh.operation_directory.exists()
            or not pending.operation_directory.exists()
            or not completed.operation_directory.exists()
            or not unknown_extra.operation_directory.exists()
            or not legacy_v1.operation_directory.exists()
        ):
            fail(
                "Restore staging sweep did not remove only the "
                "expired validation-only operation."
            )

        for preserved in (fresh, pending, completed, unknown_extra, legacy_v1):
            remove_staged_restore(
                preserved.token,
                staging_root=staging_root,
            )

        if staging_root.exists():
            remaining = list(
                staging_root.iterdir()
            )
            if remaining:
                fail(
                    "Rejected restore validation left staged files: "
                    f"{remaining}"
                )

        if (
            logical_snapshot(database_path)
            != before_validation
        ):
            fail(
                "Restore validation tests changed the copied database."
            )

    finally:
        cleanup_fixture()
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

    final_state = logical_snapshot(
        database_path
    )
    if final_state != baseline:
        fail(
            "Restore validation fixture cleanup did not "
            "return the copied database to baseline."
        )

    print(
        "[PASS] Protected restore validation enforces "
        "authentication and ASGI/body limits, accepts only "
        "strict V2 .ppbackup artifacts, rejects malformed, "
        "compressed-bomb and no-active-user inputs, stages "
        "mode-0600 files under opaque user-bound expiring "
        "tokens, exposes sanitized review metadata, sweeps "
        "only expired validation-only operations while preserving "
        "fresh, pending, completed, legacy-version and unknown evidence, and leaves "
        "the source database unchanged without replacing the source "
        "database during validation"
    )


def main() -> None:
    check_restore_validation_api()


if __name__ == "__main__":
    main()
