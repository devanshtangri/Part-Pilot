from __future__ import annotations

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
