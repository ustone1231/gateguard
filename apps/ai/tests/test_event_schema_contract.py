from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

from src.types import Event, Signals


REPO_ROOT = Path(__file__).resolve().parents[3]
EVENT_SCHEMA_PATH = REPO_ROOT / "packages/schema/events/event.schema.json"


def _event_schema() -> dict:
    return json.loads(EVENT_SCHEMA_PATH.read_text(encoding="utf-8"))


def test_ai_signals_fields_match_v022_event_schema():
    schema = _event_schema()
    schema_signal_fields = set(schema["properties"]["signals"]["properties"])
    ai_signal_fields = {field.name for field in fields(Signals)}

    assert ai_signal_fields == schema_signal_fields


def test_gate_passage_payload_uses_schema_declared_fields_only():
    schema = _event_schema()
    event = Event(
        event_type="gate_passage",
        gate_section_id="gate_01",
        camera_id="camera_001",
        confidence=0.91,
        track_id=7,
        timestamp=Event.now_iso(),
        reliability="high",
        severity="info",
        signals=Signals(
            face_age_estimate=32.5,
            gait_senior_score=0.12,
            senior_probability=0.11,
            child_probability=0.02,
            estimated_age_group="adult",
            age_group_confidence=0.78,
            perceived_gender="male",
            gender_confidence=0.83,
        ),
        raw_meta={"line_type": "entry"},
    )

    payload = event.to_payload()

    assert set(schema["required"]).issubset(payload)
    assert set(payload).issubset(schema["properties"])
    assert set(payload["signals"]).issubset(schema["properties"]["signals"]["properties"])
    assert "pose_senior_score" not in payload["signals"]
    assert "assistive_device_detected" not in payload["signals"]
