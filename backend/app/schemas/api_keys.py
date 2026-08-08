from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# PARTPILOT:REST_API_KEY_SCHEMA:V615
ApiKeyScope = Literal[
    "inventory:read",
    "inventory:write",
    "catalogues:read",
    "catalogues:write",
    "projects:read",
    "projects:write",
    "reservations:read",
    "reservations:write",
    "history:read",
]
ApiKeyStatus = Literal["active", "expired", "revoked"]


class ApiKeyCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    scopes: list[ApiKeyScope] = Field(min_length=1, max_length=9)
    expires_at: datetime | None = None


class ApiKeyUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    scopes: list[ApiKeyScope] = Field(min_length=1, max_length=9)
    expires_at: datetime | None = None


class ApiKeySummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int = Field(ge=1)
    name: str
    masked_key: str
    scopes: list[ApiKeyScope]
    status: ApiKeyStatus
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None
    rotated_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiKeyListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keys: list[ApiKeySummaryResponse]
    total: int = Field(ge=0)
    available_scopes: list[ApiKeyScope]


class ApiKeySecretResponse(ApiKeySummaryResponse):
    key: str = Field(min_length=32, max_length=160, repr=False)
