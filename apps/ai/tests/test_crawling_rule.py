"""CrawlingRule 테스트.

발화 조건:
  - baseline 높이(앞 baseline_window 프레임 평균) 대비 최근 평균 높이가
    height_ratio_threshold 이하 + 섹션 내부
"""
from __future__ import annotations

from src.rules import CrawlingRule, TrackHistory
from src.rules.base import TrackSnapshot


def _history(bboxes, *, track_id=5, section_id="gate_01", fps=30.0):
    history = TrackHistory(track_id=track_id)
    for i, bbox in enumerate(bboxes):
        history.push(TrackSnapshot(
            frame_idx=i, timestamp_sec=i / fps, bbox=bbox, section_id=section_id,
        ))
    return history


def _tall_then_short(tall_n=30, tall_h=200.0, short_n=10, short_h=80.0):
    """앞 tall_n 프레임 서있음(tall_h), 뒤 short_n 프레임 기어감(short_h)."""
    bboxes = [(100.0, 0.0, 160.0, tall_h) for _ in range(tall_n)]
    bboxes += [(100.0, 120.0, 160.0, 120.0 + short_h) for _ in range(short_n)]
    return bboxes


def _fire(rule, hist, track_id=5):
    """CrawlingRule 은 내부 디바운스로 연속 만족해야 발행."""
    event = None
    for _ in range(3):
        event = rule.evaluate(hist, {}, {track_id: hist}, "camera_001")
    return event


def test_crawling_fires_when_height_drops():
    rule = CrawlingRule()
    hist = _history(_tall_then_short())  # baseline 200 → recent 80, ratio 0.4
    event = _fire(rule, hist)

    assert event is not None
    assert event.event_type == "crawling"
    assert event.gate_section_id == "gate_01"
    assert event.track_id == 5
    assert event.raw_meta["height_ratio"] <= 0.55
    assert event.raw_meta["baseline_height_px"] > event.raw_meta["recent_avg_height_px"]


def test_crawling_silent_when_history_too_short():
    rule = CrawlingRule()
    hist = _history([(100.0, 0.0, 160.0, 200.0)] * 10)
    assert rule.evaluate(hist, {}, {5: hist}, "camera_001") is None


def test_crawling_silent_for_standing_person():
    rule = CrawlingRule()
    hist = _history([(100.0, 0.0, 160.0, 200.0)] * 40)
    assert rule.evaluate(hist, {}, {5: hist}, "camera_001") is None


def test_crawling_silent_when_no_section():
    rule = CrawlingRule()
    hist = _history(_tall_then_short(), section_id=None)
    assert rule.evaluate(hist, {}, {5: hist}, "camera_001") is None


def test_crawling_confidence_clamped():
    rule = CrawlingRule()
    hist = _history(_tall_then_short(short_h=20.0))  # 극단적으로 낮은 자세
    event = _fire(rule, hist)
    assert event is not None
    assert 0.5 <= event.confidence <= 0.95
