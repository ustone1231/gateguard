"""Gate passage 룰.

백엔드 AFC 매칭 엔진의 핵심 입력이다. AI는 결제 여부를 확정하지 않고,
사람이 게이트 line을 통과했다는 사실을 `gate_passage`로 발행한다.
"""
from __future__ import annotations

from typing import Optional

from .base import Rule, TrackHistory, TrackSnapshot
from ..types import Event
from ..zone import GateSection


class GatePassageRule(Rule):
    name = "gate_passage"
    event_type = "gate_passage"

    def __init__(self, recent_window_frames: int = 3):
        self._recent_window = recent_window_frames
        self._emitted: set[tuple[int, int, str, str]] = set()

    def evaluate(
        self,
        history: TrackHistory,
        sections: dict[str, GateSection],
        all_histories: dict[int, TrackHistory],
        camera_id: str,
    ) -> Optional[Event]:
        recent = list(history.snapshots)[-self._recent_window:]
        for snap in reversed(recent):
            event = self._event_from_snapshot(history.track_id, snap, camera_id)
            if event is not None:
                return event
        return None

    def _event_from_snapshot(
        self,
        track_id: int,
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
            key = (track_id, snap.frame_idx, section_id, line_type)
            if key in self._emitted:
                continue
            self._emitted.add(key)
            return Event(
                event_type=self.event_type,
                gate_section_id=section_id,
                camera_id=camera_id,
                confidence=round(max(0.0, min(1.0, snap.confidence)), 3),
                track_id=track_id,
                timestamp=Event.now_iso(),
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
