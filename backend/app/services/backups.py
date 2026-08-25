from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import tempfile
from typing import Any
import zipfile

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.models import AuditLog
from app.schemas.backups import (
    BackupApplicationManifest,
    BackupDatabaseManifest,
    BackupManifest,
    BackupRestorePolicyManifest,
    BackupSchemaManifest,
    BackupScopeManifest,
    LatestManualBackupStatus,
    ManualBackupStatusResponse,
)


# PARTPILOT:BACKUP_FORMAT_V2_CURRENT_SCHEMA:V597
BACKUP_FORMAT = "part-pilot-backup"
BACKUP_FORMAT_VERSION = 2
BACKUP_WRITER_VERSION = 2
HISTORICAL_STATUS_FORMAT_VERSIONS = (1, BACKUP_FORMAT_VERSION)
BACKUP_EXTENSION = ".ppbackup"
BACKUP_MEDIA_TYPE = "application/vnd.partpilot.backup+zip"
MANIFEST_ENTRY_NAME = "manifest.json"
DATABASE_ENTRY_NAME = "partpilot.db"
ARCHIVE_ENTRY_NAMES = (
    MANIFEST_ENTRY_NAME,
    DATABASE_ENTRY_NAME,
)
EXPECTED_ALEMBIC_REVISION = "0022_mcp_inventory_part_lifecycle"
EXPECTED_CRITICAL_SCHEMA_SHA256 = (
    "2b4bbbdebf042b980e018e209eda626983c8f85c467b9d74b33dffb9e0e278e0"
)
LEGACY_UNSUPPORTED_BACKUP_CONTRACTS = (
    (
        2,
        "0021_mcp_inventory_part_metadata_update",
        "2b4bbbdebf042b980e018e209eda626983c8f85c467b9d74b33dffb9e0e278e0",
    ),
    (
        2,
        "0020_mcp_inventory_part_create",
        "2b4bbbdebf042b980e018e209eda626983c8f85c467b9d74b33dffb9e0e278e0",
    ),
    (
        2,
        "0019_mcp_inventory_stock_write",
        "2b4bbbdebf042b980e018e209eda626983c8f85c467b9d74b33dffb9e0e278e0",
    ),
    (
        2,
        "0018_mcp_write_intents",
        "2b4bbbdebf042b980e018e209eda626983c8f85c467b9d74b33dffb9e0e278e0",
    ),
    (
        2,
        "0017_user_roles",
        "19f85d2d7cef281db58746bb1666feabd360de4987e05349191a4a7f0d9829af",
    ),
    (
        1,
        "0007_projects_contract",
        "c80247b636ff8476605926a15e14892aec8c3630b6f3873d29c2525e02f1f24d",
    ),
    (
        2,
        "0012_user_avatar_id",
        "b424bcf63d7de8ccb3d9742a1f2f25a58054d4a41fba274710296112d6b17abc",
    ),
    (
        2,
        "0013_user_avatar_image",
        "322ee84f5827a24d242a6a7a54a95aac103b68871f02ec27505ef2dc523c86c1",
    ),
    (
        2,
        "0014_api_keys",
        "555544ad46a8d24d2835e8beff05c6f59a937ecdb45bc9010925cf879b345617",
    ),
    (
        2,
        "0015_mcp_direct_clients",
        "4c4017e84da3725adc5c20060e0452ad37aded19493b1c9b2a46e7c714f7f339",
    ),
    (
        2,
        "0016_mcp_tool_permissions",
        "ee430d771826a549316a354a9c307198e12b9e473be28ced5a38f13ba3796d6d",
    ),
)
COMPATIBILITY_POLICY = "exact_revision"
MANIFEST_MAX_BYTES = 64 * 1024
DATABASE_MAX_BYTES = 1024 * 1024 * 1024
ARCHIVE_MAX_BYTES = 256 * 1024 * 1024
OPERATION_PREFIX = "partpilot-backup-"
OPERATION_MARKER = ".partpilot-backup-operation"
OPERATION_MARKER_CONTENT = "part-pilot-backup-operation-v2\n"
ALLOWED_COMPRESSION_TYPES = {
    zipfile.ZIP_STORED,
    zipfile.ZIP_DEFLATED,
}

REQUIRED_TABLES = (
    "alembic_version",
    "aliases",
    "api_keys",
    "app_settings",
    "audit_log",
    "backups",
    "locations",
    "manufacturers",
    "mcp_direct_auth",
    "mcp_oauth_authorization_codes",
    "mcp_oauth_clients",
    "mcp_oauth_consents",
    "mcp_oauth_tokens",
    "mcp_write_intents",
    "packages",
    "part_field_values",
    "part_tags",
    "part_type_fields",
    "part_types",
    "parts",
    "project_items",
    "projects",
    "reservation_items",
    "reservations",
    "sessions",
    "stock_movements",
    "tags",
    "users",
)
CRITICAL_SETTING_KEYS = (
    "app.display_name",
    "appearance.theme",
    "currency.default",
    "setup.completed",
    "timezone.default",
)
VALID_APPEARANCE_THEMES = {
    "dark",
    "light",
    "system",
}
INCLUDED_SCOPE = (
    "users",
    "catalogues",
    "parts",
    "projects",
    "reservations",
    "stock_movements",
    "audit_log",
    "app_settings",
    "sessions",
    "api_keys",
    "mcp_direct_auth",
    "mcp_oauth",
    "mcp_write_intents",
)
EXCLUDED_SCOPE = (
    "container_image",
    "logs",
    "temporary_files",
)


class BackupArtifactError(RuntimeError):
    pass


@dataclass(frozen=True)
class SnapshotInspection:
    alembic_revision: str
    critical_schema_sha256: str
    sessions_present: bool
    database_sha256: str
    database_size_bytes: int


@dataclass(frozen=True)
class BackupArtifact:
    operation_directory: Path
    archive_path: Path
    filename: str
    manifest: BackupManifest
    archive_sha256: str
    archive_size_bytes: int
    database_sha256: str
    database_size_bytes: int


def sqlite_path_from_database_url(database_url: str) -> Path:
    try:
        url = make_url(database_url)
    except Exception as exc:
        raise BackupArtifactError(
            "Database URL could not be parsed."
        ) from exc

    if url.get_backend_name() != "sqlite":
        raise BackupArtifactError(
            "Backup artifact generation currently supports SQLite only."
        )
    database = url.database
    if not database or database == ":memory:":
        raise BackupArtifactError(
            "A file-backed SQLite database is required."
        )
    return Path(database).expanduser().resolve()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BackupArtifactError(
                f"Manifest contains duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def _load_manifest_bytes(payload: bytes) -> BackupManifest:
    if len(payload) > MANIFEST_MAX_BYTES:
        raise BackupArtifactError(
            "Manifest exceeds the 64 KiB limit."
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BackupArtifactError(
            "Manifest is not valid UTF-8."
        ) from exc

    try:
        raw = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except BackupArtifactError:
        raise
    except Exception as exc:
        raise BackupArtifactError(
            "Manifest is not valid JSON."
        ) from exc

    try:
        manifest = BackupManifest.model_validate(raw)
    except Exception as exc:
        raise BackupArtifactError(
            "Manifest does not match backup format version 2."
        ) from exc

    canonical = canonical_json_bytes(
        manifest.model_dump(mode="json")
    )
    if payload != canonical:
        raise BackupArtifactError(
            "Manifest is not canonical JSON."
        )
    _validate_manifest_semantics(manifest)
    return manifest


def _validate_manifest_semantics(
    manifest: BackupManifest,
) -> None:
    try:
        created_at = datetime.strptime(
            manifest.created_at_utc,
            "%Y-%m-%dT%H:%M:%SZ",
        ).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise BackupArtifactError(
            "Manifest created_at_utc must use second-precision UTC Z format."
        ) from exc
    if created_at.year < 1980:
        raise BackupArtifactError(
            "Manifest timestamp is earlier than ZIP format support."
        )
    if tuple(manifest.scope.included) != INCLUDED_SCOPE:
        raise BackupArtifactError(
            "Manifest included scope does not match format version 2."
        )
    if tuple(manifest.scope.excluded) != EXCLUDED_SCOPE:
        raise BackupArtifactError(
            "Manifest excluded scope does not match format version 2."
        )
    if (
        manifest.schema.alembic_revision
        != EXPECTED_ALEMBIC_REVISION
    ):
        raise BackupArtifactError(
            "Manifest Alembic revision is not supported."
        )
    if (
        manifest.schema.critical_schema_sha256
        != EXPECTED_CRITICAL_SCHEMA_SHA256
    ):
        raise BackupArtifactError(
            "Manifest critical schema fingerprint is not supported."
        )


def _read_only_connection(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise BackupArtifactError(
            f"SQLite database does not exist: {path}"
        )
    try:
        connection = sqlite3.connect(
            f"{path.resolve().as_uri()}?mode=ro",
            uri=True,
            timeout=30.0,
        )
    except sqlite3.Error as exc:
        raise BackupArtifactError(
            f"Could not open SQLite database read-only: {path}"
        ) from exc
    connection.row_factory = sqlite3.Row
    return connection


def _normalize_schema_sql(value: str) -> str:
    return " ".join(value.split())


def _critical_schema_sha256(
    connection: sqlite3.Connection,
) -> str:
    rows = connection.execute(
        "SELECT type, name, tbl_name, sql "
        "FROM sqlite_master "
        "WHERE sql IS NOT NULL "
        "AND name NOT LIKE 'sqlite_%' "
        "ORDER BY type, name, tbl_name"
    ).fetchall()
    objects = [
        {
            "type": str(row["type"]),
            "name": str(row["name"]),
            "table": str(row["tbl_name"]),
            "sql": _normalize_schema_sql(str(row["sql"])),
        }
        for row in rows
    ]
    return hashlib.sha256(
        canonical_json_bytes(objects)
    ).hexdigest()


def _decode_setting_value(raw: Any) -> Any:
    if isinstance(raw, (str, bytes, bytearray)):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BackupArtifactError(
                "Critical application setting contains invalid JSON."
            ) from exc
    return raw


def _validate_critical_settings(
    connection: sqlite3.Connection,
) -> None:
    placeholders = ",".join(
        "?" for _ in CRITICAL_SETTING_KEYS
    )
    rows = connection.execute(
        "SELECT key, value_json "
        "FROM app_settings "
        f"WHERE key IN ({placeholders}) "
        "ORDER BY key",
        CRITICAL_SETTING_KEYS,
    ).fetchall()
    values = {
        str(row["key"]): _decode_setting_value(
            row["value_json"]
        )
        for row in rows
    }
    if tuple(sorted(values)) != CRITICAL_SETTING_KEYS:
        missing = sorted(
            set(CRITICAL_SETTING_KEYS) - set(values)
        )
        raise BackupArtifactError(
            "Snapshot is missing critical application settings: "
            + ", ".join(missing)
        )
    if values["setup.completed"] is not True:
        raise BackupArtifactError(
            "Snapshot setup is not complete."
        )
    display_name = values["app.display_name"]
    if not isinstance(display_name, str) or not display_name.strip():
        raise BackupArtifactError(
            "Snapshot application display name is invalid."
        )
    appearance = values["appearance.theme"]
    if appearance not in VALID_APPEARANCE_THEMES:
        raise BackupArtifactError(
            "Snapshot appearance theme is invalid."
        )
    currency = values["currency.default"]
    if (
        not isinstance(currency, str)
        or re.fullmatch(r"[A-Z]{3}", currency) is None
    ):
        raise BackupArtifactError(
            "Snapshot default currency is invalid."
        )
    timezone_name = values["timezone.default"]
    if (
        not isinstance(timezone_name, str)
        or not timezone_name.strip()
    ):
        raise BackupArtifactError(
            "Snapshot default timezone is invalid."
        )


def inspect_sqlite_snapshot(
    path: Path,
    *,
    expected_revision: str = EXPECTED_ALEMBIC_REVISION,
) -> SnapshotInspection:
    connection = _read_only_connection(path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        foreign_keys = int(
            connection.execute(
                "PRAGMA foreign_keys"
            ).fetchone()[0]
        )
        if foreign_keys != 1:
            raise BackupArtifactError(
                "SQLite foreign-key enforcement could not be enabled."
            )
        connection.execute("PRAGMA query_only=ON")

        integrity_rows = [
            str(row[0])
            for row in connection.execute(
                "PRAGMA integrity_check"
            ).fetchall()
        ]
        if integrity_rows != ["ok"]:
            raise BackupArtifactError(
                "SQLite integrity check failed: "
                + ", ".join(integrity_rows[:5])
            )

        foreign_key_rows = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
        if foreign_key_rows:
            raise BackupArtifactError(
                "SQLite foreign-key check found violations."
            )

        tables = tuple(
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            ).fetchall()
        )
        if tables != REQUIRED_TABLES:
            missing = sorted(set(REQUIRED_TABLES) - set(tables))
            extra = sorted(set(tables) - set(REQUIRED_TABLES))
            raise BackupArtifactError(
                "Snapshot table contract changed. "
                f"missing={missing}, extra={extra}"
            )

        revision_rows = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchall()
        if len(revision_rows) != 1:
            raise BackupArtifactError(
                "Snapshot must contain exactly one Alembic revision."
            )
        revision = str(revision_rows[0][0])
        if revision != expected_revision:
            raise BackupArtifactError(
                "Snapshot Alembic revision is incompatible: "
                f"{revision}"
            )

        _validate_critical_settings(connection)
        schema_sha256 = _critical_schema_sha256(connection)
        if (
            expected_revision == EXPECTED_ALEMBIC_REVISION
            and schema_sha256
            != EXPECTED_CRITICAL_SCHEMA_SHA256
        ):
            raise BackupArtifactError(
                "Snapshot critical schema fingerprint changed."
            )

        session_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM sessions"
            ).fetchone()[0]
        )
    finally:
        connection.close()

    size_bytes = path.stat().st_size
    if size_bytes > DATABASE_MAX_BYTES:
        raise BackupArtifactError(
            "Snapshot exceeds the 1 GiB extracted database limit."
        )
    return SnapshotInspection(
        alembic_revision=revision,
        critical_schema_sha256=schema_sha256,
        sessions_present=session_count > 0,
        database_sha256=sha256_path(path),
        database_size_bytes=size_bytes,
    )


def _online_sqlite_backup(
    source_path: Path,
    destination_path: Path,
) -> None:
    if destination_path.exists():
        raise BackupArtifactError(
            "Backup snapshot destination already exists."
        )
    source = _read_only_connection(source_path)
    destination = sqlite3.connect(
        destination_path,
        timeout=30.0,
    )
    try:
        source.backup(
            destination,
            pages=128,
            sleep=0.005,
        )
        destination.commit()
    except sqlite3.Error as exc:
        raise BackupArtifactError(
            "SQLite online backup failed."
        ) from exc
    finally:
        destination.close()
        source.close()
    os.chmod(destination_path, 0o600)


def _normalize_created_at(
    created_at_utc: datetime | None,
) -> datetime:
    value = (
        created_at_utc
        if created_at_utc is not None
        else datetime.now(timezone.utc)
    )
    if value.tzinfo is None:
        raise BackupArtifactError(
            "Backup timestamp must be timezone-aware."
        )
    value = value.astimezone(timezone.utc).replace(
        microsecond=0
    )
    if value.year < 1980:
        raise BackupArtifactError(
            "Backup timestamp is earlier than ZIP format support."
        )
    return value


def _revision_slug(revision: str) -> str:
    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        revision.lower(),
    ).strip("-")
    if not slug:
        raise BackupArtifactError(
            "Alembic revision cannot form a backup filename."
        )
    return slug


def backup_filename(
    created_at_utc: datetime,
    revision: str,
) -> str:
    return (
        "part-pilot-backup-"
        + created_at_utc.strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + _revision_slug(revision)
        + BACKUP_EXTENSION
    )


def _zip_info(
    name: str,
    created_at_utc: datetime,
) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(
        filename=name,
        date_time=(
            created_at_utc.year,
            created_at_utc.month,
            created_at_utc.day,
            created_at_utc.hour,
            created_at_utc.minute,
            created_at_utc.second,
        ),
    )
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (
        (stat.S_IFREG | 0o600) << 16
    )
    return info


def _write_archive(
    archive_path: Path,
    *,
    manifest_bytes: bytes,
    database_path: Path,
    created_at_utc: datetime,
) -> None:
    with zipfile.ZipFile(
        archive_path,
        mode="x",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        allowZip64=True,
    ) as archive:
        archive.writestr(
            _zip_info(
                MANIFEST_ENTRY_NAME,
                created_at_utc,
            ),
            manifest_bytes,
        )
        with archive.open(
            _zip_info(
                DATABASE_ENTRY_NAME,
                created_at_utc,
            ),
            mode="w",
            force_zip64=True,
        ) as destination:
            with database_path.open("rb") as source:
                shutil.copyfileobj(
                    source,
                    destination,
                    length=1024 * 1024,
                )
    os.chmod(archive_path, 0o600)


def _validate_zip_entry(
    info: zipfile.ZipInfo,
) -> None:
    if info.filename not in ARCHIVE_ENTRY_NAMES:
        raise BackupArtifactError(
            f"Unexpected archive entry: {info.filename}"
        )
    if info.is_dir() or info.filename.endswith("/"):
        raise BackupArtifactError(
            "Backup archive entries must be regular files."
        )
    if info.flag_bits & 0x1:
        raise BackupArtifactError(
            "Encrypted backup archive entries are not supported."
        )
    if info.compress_type not in ALLOWED_COMPRESSION_TYPES:
        raise BackupArtifactError(
            "Backup archive uses an unsupported compression method."
        )
    mode = (info.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(mode)
    if file_type not in (0, stat.S_IFREG):
        raise BackupArtifactError(
            "Backup archive contains a non-regular entry."
        )


def validate_backup_artifact(
    archive_path: Path,
    *,
    validation_parent: Path | None = None,
    expected_revision: str = EXPECTED_ALEMBIC_REVISION,
) -> BackupManifest:
    if not archive_path.is_file():
        raise BackupArtifactError(
            "Backup archive does not exist."
        )
    if archive_path.stat().st_size > ARCHIVE_MAX_BYTES:
        raise BackupArtifactError(
            "Backup archive exceeds the 256 MiB limit."
        )

    validation_directory: Path | None = None
    try:
        with zipfile.ZipFile(archive_path, mode="r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(infos) != 2:
                raise BackupArtifactError(
                    "Backup archive must contain exactly two entries."
                )
            if len(set(names)) != len(names):
                raise BackupArtifactError(
                    "Backup archive contains duplicate entries."
                )
            if tuple(sorted(names)) != tuple(
                sorted(ARCHIVE_ENTRY_NAMES)
            ):
                raise BackupArtifactError(
                    "Backup archive entry allowlist does not match."
                )
            for info in infos:
                _validate_zip_entry(info)

            manifest_info = archive.getinfo(
                MANIFEST_ENTRY_NAME
            )
            database_info = archive.getinfo(
                DATABASE_ENTRY_NAME
            )
            if manifest_info.file_size > MANIFEST_MAX_BYTES:
                raise BackupArtifactError(
                    "Manifest exceeds the 64 KiB limit."
                )
            if database_info.file_size > DATABASE_MAX_BYTES:
                raise BackupArtifactError(
                    "Database exceeds the 1 GiB extracted limit."
                )

            manifest_bytes = archive.read(
                MANIFEST_ENTRY_NAME
            )
            manifest = _load_manifest_bytes(
                manifest_bytes
            )
            if (
                manifest.schema.alembic_revision
                != expected_revision
            ):
                raise BackupArtifactError(
                    "Backup archive Alembic revision is incompatible."
                )

            parent = (
                validation_parent.resolve()
                if validation_parent is not None
                else archive_path.parent.resolve()
            )
            parent.mkdir(parents=True, exist_ok=True)
            validation_directory = Path(
                tempfile.mkdtemp(
                    prefix="partpilot-backup-validation-",
                    dir=parent,
                )
            )
            os.chmod(validation_directory, 0o700)
            database_path = (
                validation_directory
                / DATABASE_ENTRY_NAME
            )

            digest = hashlib.sha256()
            extracted_size = 0
            with archive.open(
                DATABASE_ENTRY_NAME,
                mode="r",
            ) as source:
                with database_path.open("xb") as destination:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        extracted_size += len(chunk)
                        if extracted_size > DATABASE_MAX_BYTES:
                            raise BackupArtifactError(
                                "Extracted database exceeds the 1 GiB limit."
                            )
                        digest.update(chunk)
                        destination.write(chunk)
            os.chmod(database_path, 0o600)

        database_sha256 = digest.hexdigest()
        if (
            extracted_size
            != manifest.database.size_bytes
            or extracted_size != database_info.file_size
        ):
            raise BackupArtifactError(
                "Backup database size does not match the manifest."
            )
        if database_sha256 != manifest.database.sha256:
            raise BackupArtifactError(
                "Backup database SHA-256 does not match the manifest."
            )

        inspection = inspect_sqlite_snapshot(
            database_path,
            expected_revision=expected_revision,
        )
        if (
            inspection.database_sha256
            != manifest.database.sha256
            or inspection.database_size_bytes
            != manifest.database.size_bytes
            or inspection.critical_schema_sha256
            != manifest.schema.critical_schema_sha256
            or inspection.sessions_present
            != manifest.restore_policy.sessions_present_in_snapshot
        ):
            raise BackupArtifactError(
                "Backup manifest metadata does not match the snapshot."
            )
        return manifest

    except zipfile.BadZipFile as exc:
        raise BackupArtifactError(
            "Backup archive is not a valid ZIP file."
        ) from exc
    finally:
        if validation_directory is not None:
            shutil.rmtree(
                validation_directory,
                ignore_errors=True,
            )


def create_backup_artifact(
    source_database_path: Path,
    operation_parent: Path,
    *,
    created_at_utc: datetime | None = None,
    expected_revision: str = EXPECTED_ALEMBIC_REVISION,
) -> BackupArtifact:
    source_database_path = (
        source_database_path.expanduser().resolve()
    )
    operation_parent = operation_parent.expanduser().resolve()
    operation_parent.mkdir(
        parents=True,
        exist_ok=True,
        mode=0o700,
    )
    timestamp = _normalize_created_at(created_at_utc)

    operation_directory = Path(
        tempfile.mkdtemp(
            prefix=OPERATION_PREFIX,
            dir=operation_parent,
        )
    )
    os.chmod(operation_directory, 0o700)
    marker_path = operation_directory / OPERATION_MARKER
    marker_path.write_text(
        OPERATION_MARKER_CONTENT,
        encoding="utf-8",
    )
    os.chmod(marker_path, 0o600)

    try:
        snapshot_path = (
            operation_directory
            / DATABASE_ENTRY_NAME
        )
        _online_sqlite_backup(
            source_database_path,
            snapshot_path,
        )
        inspection = inspect_sqlite_snapshot(
            snapshot_path,
            expected_revision=expected_revision,
        )

        manifest = BackupManifest(
            format=BACKUP_FORMAT,
            format_version=BACKUP_FORMAT_VERSION,
            created_at_utc=timestamp.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            application=BackupApplicationManifest(
                name="Part Pilot",
                backup_writer_version=(
                    BACKUP_WRITER_VERSION
                ),
            ),
            database=BackupDatabaseManifest(
                filename=DATABASE_ENTRY_NAME,
                sha256=inspection.database_sha256,
                size_bytes=(
                    inspection.database_size_bytes
                ),
                sqlite_integrity_check="ok",
                foreign_key_violations=0,
            ),
            restore_policy=(
                BackupRestorePolicyManifest(
                    invalidate_all_sessions_after_restore=True,
                    sessions_present_in_snapshot=(
                        inspection.sessions_present
                    ),
                )
            ),
            schema=BackupSchemaManifest(
                alembic_revision=(
                    inspection.alembic_revision
                ),
                compatibility_policy=(
                    COMPATIBILITY_POLICY
                ),
                critical_schema_sha256=(
                    inspection.critical_schema_sha256
                ),
                database_dialect="sqlite",
            ),
            scope=BackupScopeManifest(
                included=INCLUDED_SCOPE,
                excluded=EXCLUDED_SCOPE,
            ),
        )
        manifest_bytes = canonical_json_bytes(
            manifest.model_dump(mode="json")
        )
        manifest_path = (
            operation_directory
            / MANIFEST_ENTRY_NAME
        )
        manifest_path.write_bytes(manifest_bytes)
        os.chmod(manifest_path, 0o600)

        filename = backup_filename(
            timestamp,
            inspection.alembic_revision,
        )
        archive_path = operation_directory / filename
        _write_archive(
            archive_path,
            manifest_bytes=manifest_bytes,
            database_path=snapshot_path,
            created_at_utc=timestamp,
        )

        validated_manifest = validate_backup_artifact(
            archive_path,
            validation_parent=operation_parent,
            expected_revision=expected_revision,
        )
        if validated_manifest != manifest:
            raise BackupArtifactError(
                "Generated backup manifest changed during validation."
            )

        archive_size = archive_path.stat().st_size
        if archive_size > ARCHIVE_MAX_BYTES:
            raise BackupArtifactError(
                "Generated archive exceeds the 256 MiB limit."
            )
        return BackupArtifact(
            operation_directory=operation_directory,
            archive_path=archive_path,
            filename=filename,
            manifest=manifest,
            archive_sha256=sha256_path(archive_path),
            archive_size_bytes=archive_size,
            database_sha256=inspection.database_sha256,
            database_size_bytes=(
                inspection.database_size_bytes
            ),
        )

    except Exception:
        shutil.rmtree(
            operation_directory,
            ignore_errors=True,
        )
        raise



def _backup_audit_json_object(
    value: Any,
) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _manual_backup_status_from_audit(
    audit: AuditLog,
) -> LatestManualBackupStatus | None:
    after = _backup_audit_json_object(audit.after_json)
    metadata = _backup_audit_json_object(audit.metadata_json)
    if metadata.get("manual_download") is not True:
        return None

    filename = after.get("filename")
    archive_size = metadata.get("archive_size_bytes")
    database_size = metadata.get("database_size_bytes")
    format_version = after.get("format_version")
    alembic_revision = after.get("alembic_revision")
    created_at = audit.created_at

    if (
        not isinstance(filename, str)
        or not filename
        or len(filename) > 255
        or filename != Path(filename).name
        or not filename.lower().endswith(BACKUP_EXTENSION)
        or isinstance(archive_size, bool)
        or not isinstance(archive_size, int)
        or archive_size < 0
        or isinstance(database_size, bool)
        or not isinstance(database_size, int)
        or database_size < 0
        or format_version not in HISTORICAL_STATUS_FORMAT_VERSIONS
        or not isinstance(alembic_revision, str)
        or not 1 <= len(alembic_revision) <= 128
        or not isinstance(created_at, datetime)
    ):
        return None

    normalized = (
        created_at.replace(tzinfo=timezone.utc)
        if created_at.tzinfo is None
        else created_at.astimezone(timezone.utc)
    )
    return LatestManualBackupStatus(
        generated_at_utc=normalized.strftime("%Y-%m-%dT%H:%M:%SZ"),
        filename=filename,
        archive_size_bytes=archive_size,
        database_size_bytes=database_size,
        format_version=format_version,
        alembic_revision=alembic_revision,
    )


# PARTPILOT:MANUAL_BACKUP_STATUS_SERVICE:V452
def get_manual_backup_status(
    db: Session,
) -> ManualBackupStatusResponse:
    audits = db.scalars(
        select(AuditLog)
        .where(AuditLog.event_type == "backup.generated")
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    ).all()

    valid_entries: list[LatestManualBackupStatus] = []
    for audit in audits:
        entry = _manual_backup_status_from_audit(audit)
        if entry is not None:
            valid_entries.append(entry)

    return ManualBackupStatusResponse(
        mode="manual_download",
        scheduled_backups_active=False,
        server_copy_retained=False,
        recorded_download_count=len(valid_entries),
        latest_manual_backup=valid_entries[0] if valid_entries else None,
    )


def record_backup_generated_audit(
    db: Session,
    artifact: BackupArtifact,
    *,
    actor_user_id: int,
    commit: bool = True,
) -> int:
    if actor_user_id < 1:
        raise BackupArtifactError(
            "Backup audit actor must be a positive user ID."
        )

    audit = AuditLog(
        event_type="backup.generated",
        entity_type="backup",
        entity_id=None,
        actor_type="user",
        actor_user_id=actor_user_id,
        summary="Generated manual Part Pilot backup",
        before_json=None,
        after_json={
            "filename": artifact.filename,
            "format": artifact.manifest.format,
            "format_version": artifact.manifest.format_version,
            "alembic_revision": (
                artifact.manifest.schema.alembic_revision
            ),
            "database_sha256": artifact.database_sha256,
            "archive_sha256": artifact.archive_sha256,
        },
        metadata_json={
            "manual_download": True,
            "archive_size_bytes": artifact.archive_size_bytes,
            "database_size_bytes": artifact.database_size_bytes,
            "compatibility_policy": (
                artifact.manifest.schema.compatibility_policy
            ),
            "media_type": BACKUP_MEDIA_TYPE,
        },
    )
    try:
        db.add(audit)
        db.flush()
        audit_id = int(audit.id)
        if commit:
            db.commit()
        return audit_id
    except Exception:
        if commit:
            db.rollback()
        raise


def remove_backup_operation_directory(
    operation_directory: Path,
    *,
    expected_parent: Path | None = None,
) -> None:
    operation_directory = (
        operation_directory.expanduser().resolve()
    )
    if (
        not operation_directory.name.startswith(
            OPERATION_PREFIX
        )
        or not operation_directory.is_dir()
    ):
        raise BackupArtifactError(
            "Refusing to remove an unowned backup directory."
        )
    if expected_parent is not None:
        expected = expected_parent.expanduser().resolve()
        if operation_directory.parent != expected:
            raise BackupArtifactError(
                "Backup operation directory is outside its expected parent."
            )
    marker_path = operation_directory / OPERATION_MARKER
    try:
        marker_content = marker_path.read_text(
            encoding="utf-8"
        )
    except OSError as exc:
        raise BackupArtifactError(
            "Backup operation marker is missing."
        ) from exc
    if marker_content != OPERATION_MARKER_CONTENT:
        raise BackupArtifactError(
            "Backup operation marker is invalid."
        )
    shutil.rmtree(operation_directory)
