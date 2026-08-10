from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator


class SearchSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    show_out_of_stock_section: bool


class SearchSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    show_out_of_stock_section: bool


# PARTPILOT:RESERVATION_SETTINGS_SCHEMA:V361
ReservationExpiryMode = Literal["none", "default"]
ReservationDefaultDays = Annotated[StrictInt, Field(ge=1, le=3650)]


class ReservationSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expiry_mode: ReservationExpiryMode
    default_days: ReservationDefaultDays | None


class ReservationSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expiry_mode: ReservationExpiryMode
    default_days: ReservationDefaultDays | None = None

    @model_validator(mode="after")
    def validate_expiry_default(self) -> "ReservationSettingsUpdateRequest":
        if self.expiry_mode == "default" and self.default_days is None:
            raise ValueError(
                "default_days is required when expiry_mode is default"
            )
        if self.expiry_mode == "none":
            self.default_days = None
        return self


# PARTPILOT:APPEARANCE_SETTINGS_SCHEMA:V411
AppearanceTheme = Literal["dark", "light", "system"]


class AppearanceSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: AppearanceTheme
    light_theme_available: bool


class AppearanceSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: AppearanceTheme


# PARTPILOT:TARGETED_PREFERENCE_RESET_SCHEMA:V673
ReversiblePreferenceResetTarget = Literal["appearance", "inventory", "reservations"]

class ReversiblePreferenceResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: ReversiblePreferenceResetTarget

class ReversiblePreferenceResetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: ReversiblePreferenceResetTarget
    appearance: AppearanceSettingsResponse | None = None
    inventory: SearchSettingsResponse | None = None
    reservations: ReservationSettingsResponse | None = None


# PARTPILOT:MCP_SETTINGS_SCHEMA:V473
class McpSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    read_tools_enabled: bool
    write_tools_enabled: bool
    direct_clients_enabled: bool
    direct_no_auth_enabled: bool
    direct_no_auth_last_client_ip: str | None = None


class McpSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    read_tools_enabled: bool
    write_tools_enabled: bool
    direct_clients_enabled: bool
    direct_no_auth_enabled: bool
    direct_no_auth_confirmation: str | None = Field(default=None, max_length=80)


# PARTPILOT:MCP_TOOL_PERMISSION_ADMIN_SCHEMA:V650
McpToolCapability = Literal["read"]


class McpToolPermissionItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=160)
    capability: McpToolCapability
    enabled: bool


class McpToolPermissionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tools: list[McpToolPermissionItemResponse]


class McpToolPermissionsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    permissions: dict[str, StrictBool]


class McpClientToolPermissionItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=160)
    capability: McpToolCapability
    global_enabled: bool
    denied: bool
    effective_enabled: bool


class McpClientToolPermissionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    denied_tools: list[str]
    tools: list[McpClientToolPermissionItemResponse]


class McpClientToolPermissionsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    denied_tools: list[str] = Field(default_factory=list, max_length=6)


# PARTPILOT:MCP_OAUTH_CLIENT_ADMIN_SCHEMA:V540
McpOAuthClientConnectionStatus = Literal["connected"]
McpOAuthClientType = Literal["public", "confidential"]
McpOAuthTokenEndpointAuthMethod = Literal[
    "none",
    "client_secret_post",
    "client_secret_basic",
]


class McpOAuthClientSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    database_id: int = Field(ge=1)
    client_id: str = Field(min_length=1, max_length=255)
    client_name: str = Field(min_length=1, max_length=200)
    status: McpOAuthClientConnectionStatus
    client_type: McpOAuthClientType
    token_endpoint_auth_method: McpOAuthTokenEndpointAuthMethod
    redirect_origins: list[str]
    scopes: list[str]
    created_at: datetime
    connected_at: datetime
    last_used_at: datetime | None
    active_token_count: int = Field(ge=1)
    token_family_count: int = Field(ge=1)
    total_token_count: int = Field(ge=1)
    authorization_code_count: int = Field(ge=0)
    active_consent_count: int = Field(ge=1)
    denied_tools: list[str]
    tool_permissions: list[McpClientToolPermissionItemResponse]


class McpOAuthClientsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clients: list[McpOAuthClientSummaryResponse]
    total: int = Field(ge=0)


# PARTPILOT:MCP_OAUTH_MANAGEABLE_SCHEMA:V559
McpOAuthManageableClientStatus = Literal["registered", "connected", "revoked"]

class McpOAuthManageableClientSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    database_id: int = Field(ge=1)
    client_id: str = Field(min_length=1, max_length=255)
    client_name: str = Field(min_length=1, max_length=200)
    status: McpOAuthManageableClientStatus
    client_type: McpOAuthClientType
    token_endpoint_auth_method: McpOAuthTokenEndpointAuthMethod
    redirect_origins: list[str]
    scopes: list[str]
    created_at: datetime
    connected_at: datetime | None
    last_used_at: datetime | None
    active_token_count: int = Field(ge=0)
    token_family_count: int = Field(ge=0)
    total_token_count: int = Field(ge=0)
    authorization_code_count: int = Field(ge=0)
    active_consent_count: int = Field(ge=0)
    registered_by_current_user: bool
    denied_tools: list[str]
    tool_permissions: list[McpClientToolPermissionItemResponse]

class McpOAuthManageableClientsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clients: list[McpOAuthManageableClientSummaryResponse]
    total: int = Field(ge=0)


# PARTPILOT:MCP_OAUTH_MANUAL_REGISTRATION_SCHEMA:V555
class McpOAuthClientRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_name: str = Field(min_length=1, max_length=200)
    redirect_uris: list[str] = Field(min_length=1, max_length=20)
    client_type: McpOAuthClientType
    token_endpoint_auth_method: McpOAuthTokenEndpointAuthMethod

class McpOAuthClientRegistrationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    database_id: int = Field(ge=1)
    client_id: str = Field(min_length=1, max_length=160)
    client_name: str = Field(min_length=1, max_length=200)
    redirect_uris: list[str] = Field(min_length=1, max_length=20)
    client_type: McpOAuthClientType
    token_endpoint_auth_method: McpOAuthTokenEndpointAuthMethod
    created_at: datetime
    client_secret: str | None = Field(default=None, repr=False)


# PARTPILOT:MCP_DIRECT_AUTH_API_SCHEMA:V503
McpDirectAuthMode = Literal["disabled", "bearer_key", "custom_header", "trusted_network"]

class McpDirectAuthStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: McpDirectAuthMode
    configured: bool
    masked_key: str | None
    custom_header_name: str | None
    trusted_networks: list[str]
    rotated_at: datetime | None
    last_used_at: datetime | None


class McpDirectAuthCustomHeaderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    header_name: str = Field(
        default="x-partpilot-mcp-key",
        min_length=1,
        max_length=120,
    )


class McpDirectAuthTrustedNetworkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    networks: list[str] = Field(min_length=1, max_length=64)


class McpDirectAuthKeyResponse(McpDirectAuthStatusResponse):
    key: str


# PARTPILOT:MCP_NAMED_DIRECT_CLIENTS_SCHEMA:V627
McpDirectClientMode = Literal["bearer_key", "custom_header", "trusted_network"]


class McpDirectClientSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=120)
    enabled: bool
    mode: McpDirectClientMode
    masked_key: str | None
    custom_header_name: str | None
    trusted_networks: list[str]
    rotated_at: datetime | None
    last_used_at: datetime | None
    last_resolved_client_ip: str | None
    created_at: datetime
    updated_at: datetime
    denied_tools: list[str]
    tool_permissions: list[McpClientToolPermissionItemResponse]


class McpDirectClientsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clients: list[McpDirectClientSummaryResponse]
    total: int = Field(ge=0)


class McpDirectClientCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    mode: McpDirectClientMode
    header_name: str | None = Field(default=None, max_length=120)
    networks: list[str] = Field(default_factory=list, max_length=64)


class McpDirectClientUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None


class McpDirectClientRotateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    header_name: str | None = Field(default=None, max_length=120)


class McpDirectClientCreateResponse(McpDirectClientSummaryResponse):
    key: str | None = None


class McpDirectClientKeyResponse(McpDirectClientSummaryResponse):
    key: str
