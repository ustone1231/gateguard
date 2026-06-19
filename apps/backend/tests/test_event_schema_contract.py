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
