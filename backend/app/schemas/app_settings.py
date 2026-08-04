from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator


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


# PARTPILOT:MCP_SETTINGS_SCHEMA:V473
class McpSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    read_tools_enabled: bool
    write_tools_enabled: bool


class McpSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    read_tools_enabled: bool
    write_tools_enabled: bool


# PARTPILOT:MCP_DIRECT_AUTH_API_SCHEMA:V485
McpDirectAuthMode = Literal["disabled", "bearer_key", "custom_header", "trusted_network"]

class McpDirectAuthStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: McpDirectAuthMode
    configured: bool
    masked_key: str | None
    rotated_at: datetime | None
    last_used_at: datetime | None

class McpDirectAuthKeyResponse(McpDirectAuthStatusResponse):
    key: str
