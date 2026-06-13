"""UnpaidRule 테스트 (무단진입/우회).

MVP 판정: exit_line 은 통과했는데 같은 섹션 entry_line 은 (그 이전에)
통과한 적 없음 → 우회/금지방향.
(주의: AI unpaid 는 '의심', 결제 없음 확정은 backend confirmed_unpaid — Issue #14)
"""
from __future__ import annotations

from src.rules import TrackHistory, UnpaidRule
from src.rules.base import TrackSnapshot


def _history(snaps_spec, *, track_id=9, fps=30.0):
    """snaps_spec: (frame, crossed_entry, crossed_exit) 튜플 리스트."""
    history = TrackHistory(track_id=track_id)
    for frame, c_entry, c_exit in snaps_spec:
        history.push(TrackSnapshot(
            frame_idx=frame, timestamp_sec=frame / fps, bbox=(0, 0, 10, 20),
            crossed_entry=c_entry, crossed_exit=c_exit,
        ))
    return history


def test_unpaid_fires_on_exit_without_entry():
    hist = _history([(0, None, None), (1, None, None), (2, None, "gate_01")])
    rule = UnpaidRule()

    event = rule.evaluate(hist, {}, {9: hist}, "camera_001")
    assert event is not None
    assert event.event_type == "unpaid"
    assert event.track_id == 9
    assert event.confidence == 0.75
    assert "exit" in event.raw_meta["reason"].lower()


def test_unpaid_silent_on_normal_entry_then_exit():
    hist = _history([(0, "gate_01", None), (1, None, None), (2, None, "gate_01")])
    rule = UnpaidRule()
    assert rule.evaluate(hist, {}, {9: hist}, "camera_001") is None


def test_unpaid_silent_when_no_exit():
    hist = _history([(f, "gate_01", None) for f in range(3)])
    rule = UnpaidRule()
    assert rule.evaluate(hist, {}, {9: hist}, "camera_001") is None


def test_unpaid_fires_when_entry_only_after_exit():
    """entry 가 exit 이후면 '정상 진입'으로 안 침 (passed_entry 는 ts<=exit_ts 만 인정)."""
    hist = _history([(0, None, "gate_01"), (1, "gate_01", None), (2, None, None)])
    rule = UnpaidRule()
    event = rule.evaluate(hist, {}, {9: hist}, "camera_001")
    assert event is not None
    assert event.event_type == "unpaid"
