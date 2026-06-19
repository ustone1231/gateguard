from __future__ import annotations

import json
from pathlib import Path

from app.models.event import AfcMatch, EventCreate, Signals


REPO_ROOT = Path(__file__).resolve().parents[3]
EVENT_SCHEMA_PATH = REPO_ROOT / "packages/schema/events/event.schema.json"


def _event_schema() -> dict:
    return json.loads(EVENT_SCHEMA_PATH.read_text(encoding="utf-8"))


def test_backend_event_model_fields_match_v022_event_schema():
    schema = _event_schema()

    assert set(EventCreate.model_fields).issubset(schema["properties"])
    assert set(schema["required"]).issubset(EventCreate.model_fields)


def test_backend_signals_fields_match_v022_event_schema():
    schema = _event_schema()

    assert set(Signals.model_fields) == set(schema["properties"]["signals"]["properties"])


def test_backend_afc_match_fields_match_v022_event_schema():
    schema = _event_schema()

    assert set(AfcMatch.model_fields) == set(schema["properties"]["afc_match"]["properties"])
    assert set(schema["properties"]["afc_match"]["required"]).issubset(AfcMatch.model_fields)


def test_backend_accepts_representative_ai_model_gate_passage_payload():
    payload = {
        "event_type": "gate_passage",
        "gate_section_id": "gate_01",
        "camera_id": "camera_001",
        "confidence": 0.689,
        "track_id": 3,
        "timestamp": "2026-06-19T02:42:48.634122+00:00",
        "event_id": "evt_36fc5509cfc7423c9e6d8d81fa7b71b6",
        "signals": {
            "face_age_estimate": 43.64,
            "gait_senior_score": 0.15,
            "senior_probability": 0.08,
            "child_probability": 0.05,
            "estimated_age_group": "adult",
            "age_group_confidence": 0.7,
            "perceived_gender": "male",
            "gender_confidence": 0.997,
        },
        "reliability": "high",
        "severity": "info",
        "raw_meta": {
            "line_type": "entry",
            "line_crossing_direction": -1,
            "line_crossing_timestamp_sec": 12.969,
            "frame_idx": 447,
        },
    }

    event = EventCreate.model_validate(payload)

    assert event.event_type == "gate_passage"
    assert event.signals is not None
    assert event.signals.perceived_gender == "male"
    assert event.signals.gender_confidence == 0.997


def test_backend_accepts_representative_ai_behavior_event_without_signals():
    payload = {
        "event_type": "tailgating",
        "gate_section_id": "gate_01",
        "camera_id": "camera_001",
        "confidence": 0.627,
        "track_id": 3,
        "timestamp": "2026-06-19T02:42:48.634211+00:00",
        "event_id": "evt_b74cde078bad422b885f6053d2abd065",
        "raw_meta": {"other_track_id": 1, "gap_seconds": 1.364},
    }

    event = EventCreate.model_validate(payload)

    assert event.event_type == "tailgating"
    assert event.signals is None
