from __future__ import annotations

from src.rules import GatePassageRule, TrackHistory
from src.rules.base import TrackSnapshot


def _history_with_snapshot(snapshot: TrackSnapshot) -> TrackHistory:
    history = TrackHistory(track_id=7)
    history.push(snapshot)
    return history


def test_entry_line_crossing_emits_gate_passage_event():
    rule = GatePassageRule()
    history = _history_with_snapshot(
        TrackSnapshot(
            frame_idx=12,
            timestamp_sec=0.4,
            bbox=(10, 10, 30, 80),
            confidence=0.87,
            crossed_entry="gate_01",
            crossed_entry_direction=1,
        )
    )

    event = rule.evaluate(history, {}, {7: history}, "camera_001")

    assert event is not None
    assert event.event_type == "gate_passage"
    assert event.gate_section_id == "gate_01"
    assert event.camera_id == "camera_001"
    assert event.track_id == 7
    assert event.confidence == 0.87
    assert event.reliability == "high"
    assert event.severity == "info"
    assert event.raw_meta["line_type"] == "entry"
    assert event.raw_meta["line_crossing_direction"] == 1


def test_exit_line_crossing_emits_gate_passage_event():
    rule = GatePassageRule()
    history = _history_with_snapshot(
        TrackSnapshot(
            frame_idx=18,
            timestamp_sec=0.6,
            bbox=(10, 10, 30, 80),
            confidence=0.92,
            crossed_exit="gate_02",
            crossed_exit_direction=-1,
        )
    )

    event = rule.evaluate(history, {}, {7: history}, "camera_001")

    assert event is not None
    assert event.event_type == "gate_passage"
    assert event.gate_section_id == "gate_02"
    assert event.raw_meta["line_type"] == "exit"
    assert event.raw_meta["line_crossing_direction"] == -1


def test_same_crossing_frame_is_not_emitted_twice():
    rule = GatePassageRule()
    history = _history_with_snapshot(
        TrackSnapshot(
            frame_idx=21,
            timestamp_sec=0.7,
            bbox=(10, 10, 30, 80),
            crossed_entry="gate_01",
        )
    )

    first = rule.evaluate(history, {}, {7: history}, "camera_001")
    second = rule.evaluate(history, {}, {7: history}, "camera_001")

    assert first is not None
    assert second is None


def test_entry_and_exit_crossings_can_both_emit_for_same_track():
    rule = GatePassageRule(recent_window_frames=5)
    history = TrackHistory(track_id=7)
    history.push(
        TrackSnapshot(
            frame_idx=30,
            timestamp_sec=1.0,
            bbox=(10, 10, 30, 80),
            crossed_entry="gate_01",
            crossed_entry_direction=1,
        )
    )
    history.push(
        TrackSnapshot(
            frame_idx=45,
            timestamp_sec=1.5,
            bbox=(10, 10, 30, 80),
            crossed_exit="gate_01",
            crossed_exit_direction=1,
        )
    )

    first = rule.evaluate(history, {}, {7: history}, "camera_001")
    second = rule.evaluate(history, {}, {7: history}, "camera_001")

    assert first is not None
    assert first.raw_meta["line_type"] == "exit"
    assert second is not None
    assert second.raw_meta["line_type"] == "entry"
