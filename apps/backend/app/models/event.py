from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


EventType = Literal[
    "gate_passage",
    "jump",
    "crawling",
    "tailgating",
    "unpaid",
    "confirmed_unpaid",
    "confirmed_misuse",
]
Gender = Literal["male", "female", "unknown"]
AgeGroup = Literal["child", "youth", "adult", "senior", "unknown"]


class Signals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    face_age_estimate: float | None = Field(default=None, ge=0, le=120)
    pose_senior_score: float | None = Field(default=None, ge=0, le=1)
    gait_senior_score: float | None = Field(default=None, ge=0, le=1)
    assistive_device_detected: bool | None = None
    assistive_device_type: Literal["cane", "walker", "wheelchair"] | None = None
    senior_probability: float | None = Field(default=None, ge=0, le=1)
    child_probability: float | None = Field(default=None, ge=0, le=1)
    estimated_age_group: AgeGroup | None = None
    age_group_confidence: float | None = Field(default=None, ge=0, le=1)
    perceived_gender: Gender | None = None
    gender_confidence: float | None = Field(default=None, ge=0, le=1)


class AfcMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fare_tap_id: str = Field(pattern=r"^tap_[a-zA-Z0-9_-]+$")
    card_id_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    card_category: Literal["regular", "senior", "child", "disabled", "national_merit"]
    holder_gender: Gender = "unknown"
    tap_timestamp: datetime
    time_delta_ms: int | None = None


class EventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(pattern=r"^evt_[a-f0-9]{32}$")
    event_type: EventType
    gate_section_id: str
    camera_id: str
    confidence: float = Field(ge=0, le=1)
    track_id: int = Field(ge=1)
    timestamp: datetime
    source_event_id: str | None = Field(default=None, pattern=r"^evt_[a-f0-9]{32}$")
    clip_url: str | None = None
    signals: Signals | None = None
    reliability: Literal["low", "mid", "high"] | None = None
    severity: Literal["info", "warning", "critical"] | None = None
    afc_match: AfcMatch | None = None
    raw_meta: dict[str, Any] = Field(default_factory=dict)


class Event(EventCreate):
    stored_at: datetime
