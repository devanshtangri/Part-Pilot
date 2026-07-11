from __future__ import annotations

from pydantic import BaseModel, Field

USERNAME_PATTERN = r"^[a-z0-9._]+$"


class SetupStatusResponse(BaseModel):
    setup_complete: bool


class SetupRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=160)
    username: str = Field(min_length=1, max_length=80, pattern=USERNAME_PATTERN)
    password: str = Field(min_length=8, max_length=256)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80, pattern=USERNAME_PATTERN)
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
