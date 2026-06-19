"""Gate passage 룰.

백엔드 AFC 매칭 엔진의 핵심 입력이다. AI는 결제 여부를 확정하지 않고,
사람이 게이트 line을 통과했다는 사실을 `gate_passage`로 발행한다.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .base import Rule, TrackHistory, TrackSnapshot
from ..types import Event
from ..zone import GateSection

if TYPE_CHECKING:
    from ..eligibility_signals import EligibilitySignalEstimator


class GatePassageRule(Rule):
    name = "gate_passage"
    event_type = "gate_passage"

    def __init__(
        self,
        recent_window_frames: int = 3,
        min_same_line_gap_frames: int = 3,
        eligibility_estimator: "EligibilitySignalEstimator | None" = None,
    ):
        self._recent_window = recent_window_frames
        self._emitted: set[tuple[int, int, str, str]] = set()
        self._min_same_line_gap_frames = max(0, min_same_line_gap_frames)
        self._last_emitted_line: dict[tuple[int, str, str], int] = {}
        self._eligibility_estimator = eligibility_estimator

    def evaluate(
        self,
        history: TrackHistory,
        sections: dict[str, GateSection],
        all_histories: dict[int, TrackHistory],
        camera_id: str,
    ) -> Optional[Event]:
        recent = list(history.snapshots)[-self._recent_window:]
        for snap in reversed(recent):
            event = self._event_from_snapshot(history, snap, camera_id)
            if event is not None:
                return event
        return None

    def _event_from_snapshot(
        self,
        history: TrackHistory,
        snap: TrackSnapshot,
        camera_id: str,
    ) -> Optional[Event]:
        crossings = []
        if snap.crossed_entry:
            crossings.append((
                "entry",
                snap.crossed_entry,
                snap.crossed_entry_direction,
            ))
        if snap.crossed_exit:
            crossings.append((
                "exit",
                snap.crossed_exit,
                snap.crossed_exit_direction,
            ))

        for line_type, section_id, direction in crossings:
            key = (history.track_id, snap.frame_idx, section_id, line_type)
            if key in self._emitted:
                continue
            line_key = (history.track_id, section_id, line_type)
            last_frame = self._last_emitted_line.get(line_key)
            if (
                last_frame is not None
                and snap.frame_idx - last_frame <= self._min_same_line_gap_frames
            ):
                continue
            self._emitted.add(key)
            self._last_emitted_line[line_key] = snap.frame_idx
            signals = (
                self._eligibility_estimator.estimate(history, snap)
                if self._eligibility_estimator is not None
                else None
            )
            return Event(
                event_type=self.event_type,
                gate_section_id=section_id,
                camera_id=camera_id,
                confidence=round(max(0.0, min(1.0, snap.confidence)), 3),
                track_id=history.track_id,
                timestamp=Event.now_iso(),
                signals=signals,
                reliability="high",
                severity="info",
                raw_meta={
                    "line_type": line_type,
                    "line_crossing_direction": direction,
                    "line_crossing_timestamp_sec": round(snap.timestamp_sec, 3),
                    "frame_idx": snap.frame_idx,
                },
            )
        return None
