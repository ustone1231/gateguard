"""TailgatingRule 테스트 (꼬리물기).

발화: 이 트랙이 최근 3프레임 안에 entry_line 통과 + 같은 섹션에서 다른 트랙이
max_gap_seconds 이내 entry_line 통과.
"""
from __future__ import annotations

from src.rules import TailgatingRule, TrackHistory
from src.rules.base import TrackSnapshot


def _entry_history(track_id, *, ts_frame, section="gate_01", fps=30.0):
    """마지막 스냅샷에서 section entry_line 통과한 히스토리."""
    history = TrackHistory(track_id=track_id)
    for f in range(ts_frame - 2, ts_frame + 1):
        crossed = section if f == ts_frame else None
        history.push(TrackSnapshot(
            frame_idx=f, timestamp_sec=f / fps, bbox=(0, 0, 10, 20),
            crossed_entry=crossed,
        ))
    return history


def test_tailgating_fires_for_close_following():
    # A: frame30(1.0s), B: frame15(0.5s) → gap 0.5s
    hist_a = _entry_history(1, ts_frame=30)
    hist_b = _entry_history(2, ts_frame=15)
    rule = TailgatingRule(max_gap_seconds=1.5)

    event = rule.evaluate(hist_a, {}, {1: hist_a, 2: hist_b}, "camera_001")
    assert event is not None
    assert event.event_type == "tailgating"
    assert event.track_id == 1
    assert event.raw_meta["other_track_id"] == 2
    assert abs(event.raw_meta["gap_seconds"] - 0.5) < 1e-6


def test_tailgating_silent_when_gap_too_large():
    hist_a = _entry_history(1, ts_frame=150)  # 5.0s
    hist_b = _entry_history(2, ts_frame=15)   # 0.5s → gap 4.5s
    rule = TailgatingRule(max_gap_seconds=1.5)
    assert rule.evaluate(hist_a, {}, {1: hist_a, 2: hist_b}, "camera_001") is None


def test_tailgating_silent_for_different_section():
    hist_a = _entry_history(1, ts_frame=30, section="gate_01")
    hist_b = _entry_history(2, ts_frame=25, section="gate_02")
    rule = TailgatingRule()
    assert rule.evaluate(hist_a, {}, {1: hist_a, 2: hist_b}, "camera_001") is None


def test_tailgating_silent_when_alone():
    hist_a = _entry_history(1, ts_frame=30)
    rule = TailgatingRule()
    assert rule.evaluate(hist_a, {}, {1: hist_a}, "camera_001") is None


def test_tailgating_currently_fires_for_both_tracks():
    """현재 동작 문서화: A↔B 근접 시 A 평가도 B 평가도 모두 발화 → 이벤트 2건.
    추후 중복 억제 검토 대상."""
    hist_a = _entry_history(1, ts_frame=30)
    hist_b = _entry_history(2, ts_frame=15)
    rule = TailgatingRule()
    histories = {1: hist_a, 2: hist_b}

    ev_a = rule.evaluate(hist_a, {}, histories, "camera_001")
    ev_b = rule.evaluate(hist_b, {}, histories, "camera_001")
    assert ev_a is not None and ev_b is not None
    assert ev_a.track_id == 1 and ev_b.track_id == 2
