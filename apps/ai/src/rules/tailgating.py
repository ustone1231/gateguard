"""Tailgating 룰 (꼬리물기).

md 명세:
    "동일 section에 2개 track_id가 N초 이내 연속 entry_line 통과"

판정 절차:
  1. 이 트랙이 방금 entry_line을 통과했는가
  2. 같은 section에서 다른 track_id가 N초 이내에 entry_line 통과했는가
  3. 그렇다면 tailgating
"""
from __future__ import annotations

from typing import Optional

from .base import Rule, TrackHistory
from ..types import Event
from ..zone import GateSection


class TailgatingRule(Rule):
    name = "tailgating"
    event_type = "tailgating"

    def __init__(self, max_gap_seconds: float = 1.5):
        self._max_gap = max_gap_seconds

    def evaluate(
        self,
        history: TrackHistory,
        sections: dict[str, GateSection],
        all_histories: dict[int, TrackHistory],
        camera_id: str,
    ) -> Optional[Event]:
        # 이 트랙이 방금 (최근 3프레임 안에) entry_line 통과?
        recent = list(history.snapshots)[-3:]
        my_entry: Optional[tuple[str, float]] = None
        for s in recent:
            if s.crossed_entry:
                my_entry = (s.crossed_entry, s.timestamp_sec)
        if my_entry is None:
            return None

        section_id, my_ts = my_entry

        # 같은 section에서 다른 track이 [my_ts - max_gap, my_ts] 사이에 entry 통과?
        for other_tid, other_hist in all_histories.items():
            if other_tid == history.track_id:
                continue
            for snap in other_hist.snapshots:
                if snap.crossed_entry != section_id:
                    continue
                gap = abs(my_ts - snap.timestamp_sec)
                if 0 < gap <= self._max_gap:
                    conf = 0.6 + 0.3 * (1.0 - gap / self._max_gap)
                    return Event(
                        event_type=self.event_type,
                        gate_section_id=section_id,
                        camera_id=camera_id,
                        confidence=round(conf, 3),
                        track_id=history.track_id,
                        timestamp=Event.now_iso(),
                        raw_meta={
                            "other_track_id": other_tid,
                            "gap_seconds": round(gap, 3),
                        },
                    )
        return None
