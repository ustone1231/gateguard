"""JumpRule 테스트.

발화 조건 (둘 다 충족 + 섹션 내부):
  S1. bbox 상단(y1)이 위로 빠르게 이동  (top_speed_up >= top_speed_threshold)
  S2. bbox 높이 변동 큼               (height_std >= height_std_threshold)
"""
from __future__ import annotations

from src.rules import JumpRule, TrackHistory
from src.rules.base import TrackSnapshot


def _history(bboxes, *, track_id=7, section_id="gate_01", fps=30.0):
    history = TrackHistory(track_id=track_id)
    for i, bbox in enumerate(bboxes):
        history.push(TrackSnapshot(
            frame_idx=i, timestamp_sec=i / fps, bbox=bbox, section_id=section_id,
        ))
    return history


def _rising_bboxes(n=10, *, y_top_start=300.0, y_top_step=20.0, y_bottom=400.0):
    """y1(상단)이 매 프레임 위로, y2(하단) 고정 → 속도↑ + 높이변동↑."""
    return [(100.0, y_top_start - y_top_step * i, 160.0, y_bottom) for i in range(n)]


def _fire(rule, hist, track_id=7):
    """JumpRule 은 내부 디바운스로 min_consecutive_frames 연속 만족해야 발화.
    같은 히스토리로 그만큼 평가해 실제 발행 Event 를 얻는다."""
    event = None
    for _ in range(3):
        event = rule.evaluate(hist, {}, {track_id: hist}, "camera_001")
    return event


def test_jump_fires_on_fast_rise_and_height_variation():
    rule = JumpRule()
    hist = _history(_rising_bboxes())
    event = _fire(rule, hist)

    assert event is not None
    assert event.event_type == "jump"
    assert event.gate_section_id == "gate_01"
    assert event.track_id == 7
    assert 0.4 <= event.confidence <= 1.0
    assert event.raw_meta["top_speed_up_px_per_frame"] > 15.0
    assert event.raw_meta["height_std_px"] > 30.0
    assert event.raw_meta["frames_evaluated"] == 10


def test_jump_silent_when_history_too_short():
    rule = JumpRule(min_history_frames=10)
    hist = _history(_rising_bboxes(n=5))
    assert rule.evaluate(hist, {}, {7: hist}, "camera_001") is None


def test_jump_silent_when_no_section():
    rule = JumpRule()
    hist = _history(_rising_bboxes(), section_id=None)
    assert rule.evaluate(hist, {}, {7: hist}, "camera_001") is None


def test_jump_silent_on_slow_movement():
    rule = JumpRule()
    bboxes = [(100.0, 300.0 - 2.0 * i, 160.0, 400.0 + 10.0 * i) for i in range(10)]
    hist = _history(bboxes)
    assert rule.evaluate(hist, {}, {7: hist}, "camera_001") is None


def test_jump_requires_both_signals_not_just_speed():
    """상단이 빠르게 올라가도 높이가 일정하면(걷기) 발화 안 함 → 두 신호 AND."""
    rule = JumpRule()
    bboxes = [(100.0, 300.0 - 20.0 * i, 160.0, 500.0 - 20.0 * i) for i in range(10)]
    hist = _history(bboxes)
    assert rule.evaluate(hist, {}, {7: hist}, "camera_001") is None
