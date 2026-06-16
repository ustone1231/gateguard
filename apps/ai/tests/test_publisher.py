"""EventPublisher 테스트 — FilePublisher / HttpPublisher.

HttpPublisher 는 실제 네트워크 대신 세션을 가짜로 갈아끼워 검증한다.
event_id 는 Event 가 자동 생성 (evt_+hex, Issue #14 규칙).
"""
from __future__ import annotations

import json

import requests

from src.publisher import FilePublisher, HttpPublisher
from src.types import Event


def _event(track_id=1):
    return Event(
        event_type="jump",
        gate_section_id="gate_01",
        camera_id="camera_001",
        confidence=0.87,
        track_id=track_id,
        timestamp="2026-05-23T03:42:11.123456+00:00",
    )


# --------------------------------------------------------------------------
# FilePublisher
# --------------------------------------------------------------------------
def test_file_publisher_writes_jsonl(tmp_path):
    path = tmp_path / "events.jsonl"
    pub = FilePublisher(path)
    try:
        assert pub.publish(_event(1)) is True
        assert pub.publish(_event(2)) is True
    finally:
        pub.close()

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["event_type"] == "jump"
    assert first["track_id"] == 1
    assert first["event_id"].startswith("evt_")   # Issue #14 형식
    assert "clip_url" not in first                 # None 은 페이로드에서 제외


def test_file_publisher_creates_parent_dir(tmp_path):
    path = tmp_path / "nested" / "dir" / "events.jsonl"
    pub = FilePublisher(path)
    pub.close()
    assert path.parent.is_dir()


# --------------------------------------------------------------------------
# HttpPublisher (세션 모킹)
# --------------------------------------------------------------------------
class _FakeResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


class _FakeSession:
    """requests.Session 대역. post 호출 기록 + 정해진 결과 반환."""

    def __init__(self, *, status_code=200, raise_exc=None):
        self._status_code = status_code
        self._raise_exc = raise_exc
        self.calls = []
        self.closed = False

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        if self._raise_exc is not None:
            raise self._raise_exc
        return _FakeResponse(self._status_code)

    def close(self):
        self.closed = True


def test_http_publisher_success(tmp_path):
    pub = HttpPublisher(
        endpoint="http://backend:8000/api/v1/events",
        token="secret-token",
        fallback_path=tmp_path / "failed.jsonl",
    )
    fake = _FakeSession(status_code=201)
    pub._session = fake

    assert pub.publish(_event()) is True
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["url"] == "http://backend:8000/api/v1/events"
    assert call["json"]["event_type"] == "jump"
    assert call["headers"]["Authorization"] == "Bearer secret-token"
    assert not (tmp_path / "failed.jsonl").exists()


def test_http_publisher_rejection_writes_fallback(tmp_path):
    fallback = tmp_path / "failed.jsonl"
    pub = HttpPublisher(endpoint="http://backend/api/v1/events", fallback_path=fallback)
    pub._session = _FakeSession(status_code=400)

    assert pub.publish(_event(7)) is False
    assert fallback.exists()
    saved = json.loads(fallback.read_text(encoding="utf-8").strip())
    assert saved["track_id"] == 7


def test_http_publisher_network_error_writes_fallback(tmp_path):
    fallback = tmp_path / "failed.jsonl"
    pub = HttpPublisher(endpoint="http://backend/api/v1/events", fallback_path=fallback)
    pub._session = _FakeSession(raise_exc=requests.ConnectionError("backend down"))

    assert pub.publish(_event(3)) is False
    saved = json.loads(fallback.read_text(encoding="utf-8").strip())
    assert saved["track_id"] == 3


def test_http_publisher_no_token_has_no_auth_header(tmp_path):
    pub = HttpPublisher(endpoint="http://backend/api/v1/events", fallback_path=tmp_path / "f.jsonl")
    fake = _FakeSession(status_code=200)
    pub._session = fake

    pub.publish(_event())
    assert "Authorization" not in fake.calls[0]["headers"]
