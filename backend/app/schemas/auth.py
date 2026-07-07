from __future__ import annotations

from pydantic import BaseModel, Field


class SetupStatusResponse(BaseModel):
    setup_complete: bool


class SetupRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=256)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class AuthTokenResponse(BaseModel):
    token: str
    username: str


class CurrentUserResponse(BaseModel):
    id: int
    username: str
    is_active: bool


class LogoutResponse(BaseModel):
    ok: bool
