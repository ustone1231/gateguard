from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import EventCreate, FareTap
from app.services import store as store_module
from app.services.store import InMemoryStore
from tests.test_api import event_payload, fare_tap_payload


def test_gate_passage_waits_for_late_approved_tap(monkeypatch) -> None:
    current_time = {"value": datetime(2026, 6, 1, 12, 0, tzinfo=UTC)}
    monkeypatch.setattr(store_module, "now_utc", lambda: current_time["value"])
    store = InMemoryStore()

    _, _, event_derived = store.save_event(EventCreate.model_validate(event_payload()))
    assert event_derived == []
    assert store.list_events(event_type="confirmed_unpaid") == []

    current_time["value"] += timedelta(milliseconds=500)
    _, _, tap_derived = store.save_fare_tap(FareTap.model_validate(fare_tap_payload()))

    assert [event.event_type for event in tap_derived] == ["confirmed_misuse"]
    assert store.list_events(event_type="confirmed_unpaid") == []
    assert len(store.list_events(event_type="confirmed_misuse")) == 1


def test_unmatched_gate_passage_emits_confirmed_unpaid_after_buffer(monkeypatch) -> None:
    current_time = {"value": datetime(2026, 6, 1, 12, 0, tzinfo=UTC)}
    monkeypatch.setattr(store_module, "now_utc", lambda: current_time["value"])
    store = InMemoryStore()

    _, _, event_derived = store.save_event(EventCreate.model_validate(event_payload()))
    assert event_derived == []

    current_time["value"] += timedelta(milliseconds=999)
    assert store.flush_matching() == []

    current_time["value"] += timedelta(milliseconds=2)
    derived = store.flush_matching()

    assert [event.event_type for event in derived] == ["confirmed_unpaid"]
    unpaid = derived[0]
    assert unpaid.source_event_id == event_payload()["event_id"]
    assert unpaid.severity == "critical"
    assert unpaid.afc_match is None
    assert unpaid.raw_meta["unpaid_reason"] == "no_approved_fare_tap"

    assert store.flush_matching() == []


def test_denied_tap_without_approved_emits_confirmed_unpaid_after_buffer(monkeypatch) -> None:
    current_time = {"value": datetime(2026, 6, 1, 12, 0, tzinfo=UTC)}
    monkeypatch.setattr(store_module, "now_utc", lambda: current_time["value"])
    store = InMemoryStore()
    denied_tap = fare_tap_payload() | {"result": "denied"}

    store.save_fare_tap(FareTap.model_validate(denied_tap))
    store.save_event(EventCreate.model_validate(event_payload()))
    current_time["value"] += timedelta(milliseconds=1001)

    derived = store.flush_matching()

    assert [event.event_type for event in derived] == ["confirmed_unpaid"]
    unpaid = derived[0]
    assert unpaid.afc_match is None
    assert unpaid.raw_meta["unpaid_reason"] == "denied_without_approved"
    assert unpaid.raw_meta["denied_fare_tap_id"] == denied_tap["fare_tap_id"]


def test_denied_then_approved_uses_approved_tap_and_suppresses_unpaid(monkeypatch) -> None:
    current_time = {"value": datetime(2026, 6, 1, 12, 0, tzinfo=UTC)}
    monkeypatch.setattr(store_module, "now_utc", lambda: current_time["value"])
    store = InMemoryStore()
    denied_tap = fare_tap_payload() | {
        "fare_tap_id": "tap_denied_1",
        "result": "denied",
        "timestamp": "2026-05-28T03:42:10.900000+00:00",
    }

    store.save_fare_tap(FareTap.model_validate(denied_tap))
    store.save_fare_tap(FareTap.model_validate(fare_tap_payload()))
    store.save_event(EventCreate.model_validate(event_payload()))
    current_time["value"] += timedelta(milliseconds=1001)

    store.flush_matching()

    gate_passage = store.events[event_payload()["event_id"]]
    assert gate_passage.afc_match is not None
    assert gate_passage.afc_match.fare_tap_id == fare_tap_payload()["fare_tap_id"]
    assert store.list_events(event_type="confirmed_unpaid") == []
    assert len(store.list_events(event_type="confirmed_misuse")) == 1
