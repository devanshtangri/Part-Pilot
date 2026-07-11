from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

USERNAME_PATTERN = r"^[a-z0-9._]+$"
CURRENCY_PATTERN = r"^[A-Z]{3}$"
TIMEZONE_PATTERN = r"^[A-Za-z0-9._+-]+(?:/[A-Za-z0-9._+-]+)*$"


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


class CurrentUserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    is_active: bool


class LogoutResponse(BaseModel):
    ok: bool

class DebugResetRequest(BaseModel):
    confirmation: str = Field(min_length=1, max_length=80)


class DebugResetResponse(BaseModel):
    ok: bool
    recreated_part_types: int
    recreated_template_fields: int
    recreated_settings: int

