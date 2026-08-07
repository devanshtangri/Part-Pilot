from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BackupManifestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# PARTPILOT:BACKUP_FORMAT_V2_SCHEMA:V597
class BackupApplicationManifest(BackupManifestModel):
    name: Literal["Part Pilot"]
    backup_writer_version: Literal[2]


class BackupDatabaseManifest(BackupManifestModel):
    filename: Literal["partpilot.db"]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    sqlite_integrity_check: Literal["ok"]
    foreign_key_violations: Literal[0]


class BackupRestorePolicyManifest(BackupManifestModel):
    invalidate_all_sessions_after_restore: Literal[True]
    sessions_present_in_snapshot: bool


class BackupSchemaManifest(BackupManifestModel):
    alembic_revision: str = Field(min_length=1, max_length=128)
    compatibility_policy: Literal["exact_revision"]
    critical_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    database_dialect: Literal["sqlite"]


class BackupScopeManifest(BackupManifestModel):
    included: tuple[str, ...]
    excluded: tuple[str, ...]


class BackupManifest(BackupManifestModel):
    format: Literal["part-pilot-backup"]
    format_version: Literal[2]
    created_at_utc: str
    application: BackupApplicationManifest
    database: BackupDatabaseManifest
    restore_policy: BackupRestorePolicyManifest
    schema: BackupSchemaManifest
    scope: BackupScopeManifest

# PARTPILOT:MANUAL_BACKUP_STATUS_SCHEMA:V452
class LatestManualBackupStatus(BackupManifestModel):
    generated_at_utc: str
    filename: str = Field(min_length=1, max_length=255)
    archive_size_bytes: int = Field(ge=0)
    database_size_bytes: int = Field(ge=0)
    format_version: Literal[1, 2]
    alembic_revision: str = Field(min_length=1, max_length=128)


class ManualBackupStatusResponse(BackupManifestModel):
    mode: Literal["manual_download"]
    scheduled_backups_active: Literal[False]
    server_copy_retained: Literal[False]
    recorded_download_count: int = Field(ge=0)
    latest_manual_backup: LatestManualBackupStatus | None
