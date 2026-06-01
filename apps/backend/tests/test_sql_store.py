from __future__ import annotations

from alembic import command
from alembic.config import Config
from app.models import EventCreate, FareTap
from app.services.sql_store import SqlStore
from tests.test_api import event_payload, fare_tap_payload


def test_sql_store_persists_events_and_matching(tmp_path) -> None:
    store = SqlStore(f"sqlite:///{tmp_path / 'gateguard.db'}")

    event, deduped, derived = store.save_event(EventCreate.model_validate(event_payload()))
    assert deduped is False
    assert event.event_id == event_payload()["event_id"]
    assert derived == []

    tap, tap_deduped, derived = store.save_fare_tap(FareTap.model_validate(fare_tap_payload()))
    assert tap_deduped is False
    assert tap.fare_tap_id == fare_tap_payload()["fare_tap_id"]
    assert [event.event_type for event in derived] == ["confirmed_misuse"]

    persisted = store.list_events(event_type="confirmed_misuse")
    assert len(persisted) == 1

    review_items = store.list_review_queue()
    assert len(review_items) == 1
    assert review_items[0]["event_id"] == persisted[0].event_id
    assert review_items[0]["status"] == "pending"

    reviewed = store.save_review_feedback(
        review_items[0]["queue_id"],
        "confirmed",
        "operator verified",
    )
    assert reviewed["status"] == "confirmed"
    assert reviewed["feedback"] == "operator verified"
    assert store.list_review_queue() == []
    assert store.list_review_queue(status_filter="all")[0]["status"] == "confirmed"

    other_event_payload = event_payload() | {
        "event_id": "evt_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "track_id": 8,
    }
    _, _, second_derived = store.save_event(EventCreate.model_validate(other_event_payload))
    assert second_derived == []
    assert len(store.list_events(event_type="confirmed_misuse")) == 1


def test_alembic_upgrade_creates_tables(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "migrated.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    config = Config("alembic.ini")
    command.upgrade(config, "head")

    store = SqlStore(f"sqlite:///{db_path}")
    event, _, _ = store.save_event(EventCreate.model_validate(event_payload()))
    assert event.event_id == event_payload()["event_id"]
