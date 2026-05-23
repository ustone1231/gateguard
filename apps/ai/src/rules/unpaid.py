"""Unpaid 룰 (무단진입/우회).

md 명세:
    "정상 결제 신호 없이 통과. MVP는 우회/금지방향으로 대체"

MVP 판정 (결제 센서 미연동):
  - 사람이 섹션을 통과했는데 entry_line은 안 지났음 → 우회 의심
    또는 entry_line을 역방향으로 통과 → 금지방향
  - 즉, exit_line은 지났는데 entry_line은 안 지났음 = unpaid

실제 운영 시엔 게이트 센서/결제 데이터 연동 필요. 그건 백엔드 확장으로.
"""
from __future__ import annotations

from typing import Optional

from .base import Rule, TrackHistory
from ..types import Event
from ..zone import GateSection


class UnpaidRule(Rule):
    name = "unpaid"
    event_type = "unpaid"

    def evaluate(
        self,
        history: TrackHistory,
        sections: dict[str, GateSection],
        all_histories: dict[int, TrackHistory],
        camera_id: str,
    ) -> Optional[Event]:
        snaps = list(history.snapshots)

        # 이 트랙이 최근에 exit_line을 통과했는가
        recent = snaps[-5:]
        exit_event = None
        for s in recent:
            if s.crossed_exit:
                exit_event = (s.crossed_exit, s.timestamp_sec)
        if exit_event is None:
            return None

        section_id, exit_ts = exit_event

        # 같은 section의 entry_line을 통과한 적이 있는가 (이전 history 전체)
        passed_entry = any(
            s.crossed_entry == section_id and s.timestamp_sec <= exit_ts
            for s in snaps
        )
        if passed_entry:
            # 정상: entry 후 exit → unpaid 아님
            return None

        # entry 안 지나고 exit 지남 = 우회/금지방향
        return Event(
            event_type=self.event_type,
            gate_section_id=section_id,
            camera_id=camera_id,
            confidence=0.75,
            track_id=history.track_id,
            timestamp=Event.now_iso(),
            raw_meta={
                "reason": "exited without entry crossing",
                "exit_timestamp_sec": round(exit_ts, 3),
            },
        )
