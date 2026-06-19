from __future__ import annotations

from pathlib import Path

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
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["uptime_sec"], int)
    assert body["schema_version"] == "0.2.2"


def test_event_ingest_and_dedupe() -> None:
    payload = event_payload()
    created = client.post("/api/v1/events", json=payload, headers=AI_HEADERS)
    assert created.status_code == 201
    assert created.json()["event_id"] == payload["event_id"]

    duplicate = client.post("/api/v1/events", json=payload, headers=AI_HEADERS)
    assert duplicate.status_code == 200
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


def test_gender_mismatch_requires_high_confidence() -> None:
    event = event_payload() | {
        "event_id": "evt_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        "signals": {
            "perceived_gender": "male",
            "gender_confidence": 0.79,
        },
    }
    tap = fare_tap_payload() | {
        "fare_tap_id": "tap_gender_low_confidence",
        "card_category": "regular",
        "holder_gender": "female",
        "timestamp": "2026-05-28T03:42:11.400000+00:00",
    }

    client.post("/api/v1/events", json=event, headers=AI_HEADERS)
    client.post("/api/v1/fare-taps", json=tap, headers=AFC_HEADERS)
    assert client.get("/api/v1/events?event_type=confirmed_misuse", headers=OP_HEADERS).json()["total"] == 0

    high_confidence_event = event | {
        "event_id": "evt_ffffffffffffffffffffffffffffffff",
        "track_id": 8,
        "timestamp": "2026-05-28T03:42:15.000000+00:00",
        "signals": {
            "perceived_gender": "male",
            "gender_confidence": 0.83,
        },
    }
    high_confidence_tap = tap | {
        "fare_tap_id": "tap_gender_high_confidence",
        "timestamp": "2026-05-28T03:42:15.300000+00:00",
    }

    created = client.post("/api/v1/events", json=high_confidence_event, headers=AI_HEADERS)
    matched = client.post("/api/v1/fare-taps", json=high_confidence_tap, headers=AFC_HEADERS)

    assert created.status_code == 201
    assert matched.status_code == 201
    assert len(matched.json()["derived_event_ids"]) == 1
    assert client.get("/api/v1/events?event_type=confirmed_misuse", headers=OP_HEADERS).json()["total"] == 1


def test_child_card_mismatch_uses_child_probability() -> None:
    event = event_payload() | {
        "event_id": "evt_11111111111111111111111111111111",
        "signals": {
            "child_probability": 0.12,
            "estimated_age_group": "adult",
            "age_group_confidence": 0.88,
        },
    }
    tap = fare_tap_payload() | {
        "fare_tap_id": "tap_child_mismatch",
        "card_category": "child",
        "holder_gender": "unknown",
    }

    client.post("/api/v1/events", json=event, headers=AI_HEADERS)
    matched = client.post("/api/v1/fare-taps", json=tap, headers=AFC_HEADERS)

    assert matched.status_code == 201
    assert len(matched.json()["derived_event_ids"]) == 1


def test_websocket_receives_realtime_event() -> None:
    with client.websocket_connect(f"/ws/v1/events?token={settings.jwt_secret}") as websocket:
        heartbeat = websocket.receive_json()
        assert heartbeat["type"] == "heartbeat"

        payload = event_payload() | {
            "event_id": "evt_cccccccccccccccccccccccccccccccc",
            "track_id": 9,
        }
        created = client.post("/api/v1/events", json=payload, headers=AI_HEADERS)
        assert created.status_code == 201

        message = websocket.receive_json()
        assert message["type"] == "event_new"
        assert message["data"]["event_id"] == payload["event_id"]


def test_video_clip_endpoint_redirects_to_signed_download() -> None:
    payload = event_payload() | {
        "event_id": "evt_dddddddddddddddddddddddddddddddd",
        "track_id": 10,
    }
    clip_dir = Path(settings.video_clip_dir)
    clip_dir.mkdir(parents=True, exist_ok=True)
    clip_path = clip_dir / f"{payload['event_id']}.mp4"
    clip_path.write_bytes(b"demo clip")

    created = client.post("/api/v1/events", json=payload, headers=AI_HEADERS)
    assert created.status_code == 201

    redirect = client.get(
        f"/api/v1/events/{payload['event_id']}/video-clip",
        headers=OP_HEADERS,
        follow_redirects=False,
    )
    assert redirect.status_code == 302
    assert redirect.headers["location"].startswith(f"/api/v1/video-clips/{payload['event_id']}")

    downloaded = client.get(redirect.headers["location"])
    assert downloaded.status_code == 200
    assert downloaded.content == b"demo clip"

    clip_path.unlink(missing_ok=True)


def test_stats_and_loss_estimate_include_period_by_hour_and_incidents() -> None:
    event = event_payload()
    client.post("/api/v1/events", json=event, headers=AI_HEADERS)
    client.post("/api/v1/fare-taps", json=fare_tap_payload(), headers=AFC_HEADERS)

    stats = client.get(
        "/api/v1/stats",
        headers=OP_HEADERS,
        params={
            "from": "2026-05-28T00:00:00+00:00",
            "to": "2026-05-29T00:00:00+00:00",
            "period": "day",
        },
    )
    assert stats.status_code == 200
    body = stats.json()
    assert body["period"] == "day"
    assert body["by_type"]["gate_passage"] == 1
    assert len(body["by_hour"]) == 24
    assert body["by_hour"][3] >= 1

    loss = client.get(
        "/api/v1/loss-estimate",
        headers=OP_HEADERS,
        params={
            "from": "2026-05-28T00:00:00+00:00",
            "to": "2026-06-30T00:00:00+00:00",
            "unit_loss_krw": 1500,
        },
    )
    assert loss.status_code == 200
    assert loss.json()["total_incidents"] == 1
    assert loss.json()["estimated_loss_krw"] == 1500


def test_auth_required_for_ingest() -> None:
    response = client.post("/api/v1/events", json=event_payload())
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "unauthorized"
    assert body["error"]["request_id"].startswith("req_")


def test_auth_login_success() -> None:
    response = client.post("/api/v1/auth/login", json={"username": "op", "password": "pass"})
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_auth_refresh_success() -> None:
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": settings.jwt_secret})
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] == settings.jwt_secret
    assert "expires_in" in body


def test_auth_refresh_invalid() -> None:
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "wrong-token"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID"


def test_auth_logout_success() -> None:
    response = client.post("/api/v1/auth/logout", headers=OP_HEADERS)
    assert response.status_code == 204


def test_auth_logout_no_header() -> None:
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_auth_logout_invalid_token() -> None:
    response = client.post("/api/v1/auth/logout", headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID"


def test_events_time_filter() -> None:
    payload = event_payload()
    client.post("/api/v1/events", json=payload, headers=AI_HEADERS)

    in_range = client.get(
        "/api/v1/events",
        headers=OP_HEADERS,
        params={"from": "2026-05-28T00:00:00+00:00", "to": "2026-05-29T00:00:00+00:00"},
    )
    assert in_range.status_code == 200
    assert in_range.json()["total"] == 1

    out_of_range = client.get(
        "/api/v1/events",
        headers=OP_HEADERS,
        params={"from": "2026-06-01T00:00:00+00:00", "to": "2026-06-02T00:00:00+00:00"},
    )
    assert out_of_range.status_code == 200
    assert out_of_range.json()["total"] == 0


def test_events_cursor_pagination() -> None:
    for i in range(1, 4):
        client.post(
            "/api/v1/events",
            json={
                "event_id": f"evt_bb{'0' * 28}{i:02d}",
                "event_type": "jump",
                "gate_section_id": "gate_01",
                "camera_id": "camera_001",
                "confidence": 0.9,
                "track_id": i,
                "timestamp": f"2026-05-28T0{i}:00:00.000000+00:00",
                "severity": "critical",
                "raw_meta": {},
            },
            headers=AI_HEADERS,
        )

    page1 = client.get("/api/v1/events", headers=OP_HEADERS, params={"limit": 2})
    assert page1.status_code == 200
    body1 = page1.json()
    assert len(body1["data"]) == 2
    assert body1["total"] == 3
    assert body1["next_cursor"] is not None

    page2 = client.get(
        "/api/v1/events", headers=OP_HEADERS, params={"limit": 2, "cursor": body1["next_cursor"]}
    )
    assert page2.status_code == 200
    body2 = page2.json()
    assert len(body2["data"]) == 1
    assert body2["total"] == 3
    assert body2["next_cursor"] is None

    all_ids = [e["event_id"] for e in body1["data"]] + [e["event_id"] for e in body2["data"]]
    assert len(set(all_ids)) == 3


def test_wildcard_cors_disables_credentials() -> None:
    response = client.options(
        "/api/v1/events",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in response.headers


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
        "holder_gender": "female",
        "timestamp": "2026-05-28T03:42:11.500000+00:00",
        "result": "approved",
        "raw_meta": {"fare_amount": 0, "card_type": "Senior_Pass"},
    }
