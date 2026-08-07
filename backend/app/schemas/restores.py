from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


RESTORE_TOKEN_PATTERN = r"^[A-Za-z0-9_-]{43}$"


class RestoreContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
    )


# PARTPILOT:RESTORE_FORMAT_V2_SCHEMA:V597
class RestoreValidationResponse(RestoreContractModel):
    status: Literal["ready_for_review"]
    validation_token: str = Field(
        pattern=RESTORE_TOKEN_PATTERN
    )
    original_filename: str = Field(
        min_length=1,
        max_length=255,
    )
    backup_created_at_utc: str
    validated_at_utc: str
    expires_at_utc: str
    format_version: Literal[2]
    alembic_revision: Literal[
        "0013_user_avatar_image"
    ]
    archive_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    archive_size_bytes: int = Field(
        ge=1,
    )
    database_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    database_size_bytes: int = Field(
        ge=1,
    )
    user_count: int = Field(
        ge=1,
    )
    active_user_count: int = Field(
        ge=1,
    )
    sessions_present: bool
    warnings: tuple[str, ...]


class RestoreStageState(RestoreContractModel):
    state_version: Literal[1]
    status: Literal["validated"]
    token_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    actor_user_id: int = Field(
        ge=1,
    )
    actor_username: str = Field(
        min_length=1,
        max_length=80,
    )
    original_filename: str = Field(
        min_length=1,
        max_length=255,
    )
    archive_filename: Literal["upload.ppbackup"]
    candidate_database_filename: Literal[
        "candidate.db"
    ]
    backup_created_at_utc: str
    validated_at_utc: str
    expires_at_utc: str
    format_version: Literal[2]
    alembic_revision: Literal[
        "0013_user_avatar_image"
    ]
    critical_schema_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    archive_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    archive_size_bytes: int = Field(
        ge=1,
    )
    database_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    database_size_bytes: int = Field(
        ge=1,
    )
    user_count: int = Field(
        ge=1,
    )
    active_user_count: int = Field(
        ge=1,
    )
    sessions_present: bool
    warnings: tuple[str, ...]


class RestoreCommitJob(RestoreContractModel):
    job_version: Literal[1]
    status: Literal["pending"]
    validation_token: str = Field(
        pattern=RESTORE_TOKEN_PATTERN
    )
    token_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    actor_user_id: int = Field(
        ge=1,
    )
    actor_username: str = Field(
        min_length=1,
        max_length=80,
    )
    requested_at_utc: str
    expected_live_database_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    expected_live_database_size_bytes: int = Field(
        ge=1,
    )
    staged_archive_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    staged_database_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    result_filename: Literal["result.json"]


class RestoreBootstrapResult(RestoreContractModel):
    result_version: Literal[1]
    status: Literal["succeeded", "failed"]
    validation_token: str = Field(
        pattern=RESTORE_TOKEN_PATTERN
    )
    started_at_utc: str
    finished_at_utc: str
    event_type: Literal[
        "backup.restored",
        "backup.restore_failed",
    ]
    actor_type: Literal["user", "system"]
    actor_user_id: int | None = Field(
        default=None,
        ge=1,
    )
    live_database_sha256_before: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    live_database_sha256_after: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    restored_snapshot_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    rollback_snapshot_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    rollback_verified: bool
    sessions_invalidated: int = Field(
        ge=0,
    )
    audit_id: int | None = Field(
        default=None,
        ge=1,
    )
    error_code: str | None = Field(
        default=None,
        max_length=80,
    )


class RestoreCommitRequest(RestoreContractModel):
    confirmation: Literal["RESTORE"]


class RestoreCommitResponse(RestoreContractModel):
    status: Literal["restart_scheduled"]
    validation_token: str = Field(
        pattern=RESTORE_TOKEN_PATTERN
    )
    message: str = Field(
        min_length=1,
        max_length=240,
    )
    sessions_will_be_invalidated: Literal[True]
    reauthentication_required: Literal[True]
