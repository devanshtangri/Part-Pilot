from __future__ import annotations

from pydantic import BaseModel, Field


# PARTPILOT:LIVE_SYNC_STATE_SCHEMA:V687
class LiveSyncStateResponse(BaseModel):
    generation: str
    sequence: int = Field(ge=0)
    revisions: dict[str, int]
