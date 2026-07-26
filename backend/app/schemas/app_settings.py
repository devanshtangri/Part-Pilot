from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SearchSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    show_out_of_stock_section: bool


class SearchSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    show_out_of_stock_section: bool
