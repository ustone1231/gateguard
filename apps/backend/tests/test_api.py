from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.runtime import store


client = TestClient(app)
AI_HEADERS = {"Authorization": f"Bearer {settings.ai_service_token}"}
AFC_HEADERS = {"Authorization": f"Bearer {settings.afc_service_token}"}
OP_HEADERS = {"Authorization": f"Bearer {settings.jwt_secret}"}


def setup_function() -> None:
    store.reset()


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_event_ingest_and_dedupe() -> None:
    payload = event_payload()
    created = client.post("/api/v1/events", json=payload, headers=AI_HEADERS)
    assert created.status_code == 201
    assert created.json()["event_id"] == payload["event_id"]

    duplicate = client.post("/api/v1/events", json=payload, headers=AI_HEADERS)
    assert duplicate.status_code == 201
    assert duplicate.json()["deduped"] is True

    listed = client.get("/api/v1/events", headers=OP_HEADERS)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_fare_tap_matching_creates_review_queue_for_misuse() -> None:
    event = event_payload()
    client.post("/api/v1/events", json=event, headers=AI_HEADERS)

    tap = fare_tap_payload()
    created = client.post("/api/v1/fare-taps", json=tap, headers=AFC_HEADERS)
    assert created.status_code == 201
    assert len(created.json()["derived_event_ids"]) == 1

    listed = client.get("/api/v1/events?event_type=confirmed_misuse", headers=OP_HEADERS)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    queue = client.get("/api/v1/review-queue", headers=OP_HEADERS)
    assert queue.status_code == 200
    assert len(queue.json()["data"]) == 1


def test_auth_required_for_ingest() -> None:
    response = client.post("/api/v1/events", json=event_payload())
    assert response.status_code == 401


def event_payload() -> dict:
    return {
        "event_id": "evt_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "event_type": "gate_passage",
        "gate_section_id": "gate_01",
        "camera_id": "camera_001",
        "confidence": 0.91,
        "track_id": 7,
        "timestamp": "2026-05-28T03:42:11.000000+00:00",
        "signals": {
            "face_age_estimate": 24,
            "pose_senior_score": 0.05,
            "gait_senior_score": 0.08,
            "assistive_device_detected": False,
            "assistive_device_type": None,
            "senior_probability": 0.12,
        },
        "reliability": "high",
        "severity": "info",
        "raw_meta": {},
    }


def fare_tap_payload() -> dict:
    return {
        "fare_tap_id": "tap_demo_1",
        "event_type": "fare_tap",
        "gate_section_id": "gate_01",
        "card_id_hash": "sha256:" + "a" * 64,
        "card_category": "senior",
        "timestamp": "2026-05-28T03:42:11.500000+00:00",
        "result": "approved",
        "raw_meta": {"fare_amount": 0, "card_type": "Senior_Pass"},
    }
