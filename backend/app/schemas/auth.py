from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

USERNAME_PATTERN = r"^[a-z0-9._]+$"
CURRENCY_PATTERN = r"^[A-Z]{3}$"
TIMEZONE_PATTERN = r"^[A-Za-z0-9._+-]+(?:/[A-Za-z0-9._+-]+)*$"
UserRole = Literal["owner", "administrator", "operator", "viewer"]
AssignableUserRole = Literal["administrator", "operator", "viewer"]

BuiltInAvatarId = Literal[
    "initials", "chip", "circuit", "terminal", "storage", "rocket"
]


class SetupStatusResponse(BaseModel):
    setup_complete: bool
    account_exists: bool
    default_currency: str | None = None
    timezone: str | None = None


class SetupPreferencesRequest(BaseModel):
    default_currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=CURRENCY_PATTERN,
    )
    timezone: str = Field(
        min_length=1,
        max_length=100,
        pattern=TIMEZONE_PATTERN,
    )

    @field_validator("default_currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("timezone", mode="before")
    @classmethod
    def normalize_timezone(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class SetupRequest(SetupPreferencesRequest):
    display_name: str = Field(min_length=1, max_length=160)
    username: str = Field(
        min_length=1,
        max_length=80,
        pattern=USERNAME_PATTERN,
    )
    password: str = Field(min_length=8, max_length=256)


class LoginRequest(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=80,
        pattern=USERNAME_PATTERN,
    )
    password: str = Field(min_length=1, max_length=256)


class AuthTokenResponse(BaseModel):
    token: str
    username: str
    display_name: str
    role: UserRole


class CurrentUserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    avatar_id: BuiltInAvatarId
    has_custom_avatar: bool
    avatar_image_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    role: UserRole
    is_active: bool


class ProfileUpdateRequest(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=80,
        pattern=USERNAME_PATTERN,
    )
    display_name: str = Field(min_length=1, max_length=160)
    avatar_id: BuiltInAvatarId

    @field_validator("username", mode="before")
    @classmethod
    def normalize_profile_username(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_profile_display_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


# PARTPILOT:CUSTOM_AVATAR_SCHEMA:V598
class ProfileResponse(CurrentUserResponse):
    available_avatar_ids: list[BuiltInAvatarId]


class LogoutResponse(BaseModel):
    ok: bool

class DebugResetRequest(BaseModel):
    confirmation: str = Field(min_length=1, max_length=80)


class DebugResetResponse(BaseModel):
    ok: bool
    recreated_part_types: int
    recreated_template_fields: int
    recreated_settings: int

# PARTPILOT:PASSWORD_SESSION_ADMIN_SCHEMA:V584
class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class PasswordChangeResponse(BaseModel):
    ok: bool
    revoked_other_sessions: int


class SessionResponse(BaseModel):
    id: int
    is_current: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    user_agent: str | None
    ip_address: str | None


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]


class SessionRevokeResponse(BaseModel):
    ok: bool
    revoked: bool


class OtherSessionsRevokeResponse(BaseModel):
    ok: bool
    revoked_sessions: int


# PARTPILOT:USER_ROLE_ADMIN_SCHEMA:V732
class ManagedUserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    role: UserRole
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ManagedUserListResponse(BaseModel):
    users: list[ManagedUserResponse]
    total: int


class ManagedUserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80, pattern=USERNAME_PATTERN)
    display_name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=8, max_length=256)
    role: AssignableUserRole

    @field_validator("username", mode="before")
    @classmethod
    def normalize_managed_username(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_managed_display_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ManagedUserAccessUpdateRequest(BaseModel):
    role: AssignableUserRole | None = None
    is_active: bool | None = None

    @field_validator("is_active")
    @classmethod
    def preserve_boolean(cls, value: bool | None) -> bool | None:
        return value


class ManagedUserPasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=256)


class ManagedUserDeleteRequest(BaseModel):
    confirmation_username: str = Field(min_length=1, max_length=80)

    @field_validator("confirmation_username", mode="before")
    @classmethod
    def normalize_confirmation_username(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class ManagedUserActionResponse(BaseModel):
    ok: bool
    revoked_sessions: int = 0
