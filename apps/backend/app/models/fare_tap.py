from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.event import Gender


class FareTap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fare_tap_id: str = Field(pattern=r"^tap_[a-zA-Z0-9_-]+$")
    event_type: Literal["fare_tap"]
    gate_section_id: str
    card_id_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    card_category: Literal["regular", "senior", "child", "disabled", "national_merit"]
    holder_gender: Gender = "unknown"
    timestamp: datetime
    result: Literal["approved", "denied", "error"]
    raw_meta: dict[str, Any] = Field(default_factory=dict)
    stored_at: datetime | None = None
