from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


# PARTPILOT:MCP_OAUTH_HTTP_SCHEMAS:V467
class DynamicClientRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    redirect_uris: list[str] = Field(min_length=1, max_length=20)
    client_name: str = Field(default="MCP Client", min_length=1, max_length=200)
    client_uri: str | None = Field(default=None, max_length=2048)
    grant_types: list[str] = Field(
        default_factory=lambda: ["authorization_code", "refresh_token"],
        min_length=1,
        max_length=4,
    )
    response_types: list[str] = Field(
        default_factory=lambda: ["code"],
        min_length=1,
        max_length=4,
    )
    token_endpoint_auth_method: str = Field(default="none", max_length=40)
    application_type: str | None = Field(default=None, max_length=20)
    software_id: str | None = Field(default=None, max_length=200)
    software_version: str | None = Field(default=None, max_length=100)

    @field_validator("client_name", mode="before")
    @classmethod
    def normalize_client_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class DynamicClientRegistrationResponse(BaseModel):
    client_id: str
    client_secret: str | None = None
    client_id_issued_at: int
    client_secret_expires_at: int | None = None
    redirect_uris: list[str]
    client_name: str
    client_uri: str | None = None
    grant_types: list[str]
    response_types: list[str]
    token_endpoint_auth_method: str
    application_type: str | None = None
    software_id: str | None = None
    software_version: str | None = None


class OAuthTokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    scope: str
    refresh_token: str | None = None
