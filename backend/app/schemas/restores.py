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
    format_version: Literal[1]
    alembic_revision: Literal[
        "0007_projects_contract"
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
    format_version: Literal[1]
    alembic_revision: Literal[
        "0007_projects_contract"
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
