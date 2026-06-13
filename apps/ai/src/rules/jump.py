"""Jump 룰.

md 명세:
    "bbox 상단이 섹션 상단선을 빠르게 횡단 + 높이 변화 비정상"

판정 신호:
  S1. bbox 상단(y1)이 최근 N프레임 동안 빠르게 위로 이동
  S2. bbox 높이(y2-y1)의 변동이 큼 (정상 보행 대비)
  S3. 섹션 내부에서 발생

confidence = 신호 가중 합. 임계치 통과 시 발화.
"""
from __future__ import annotations

import statistics
from typing import Optional

from .base import Rule, SustainedEventDebouncer, TrackHistory
from ..types import Event
from ..zone import GateSection


class JumpRule(Rule):
    name = "jump"
    event_type = "jump"

    def __init__(
        self,
        top_speed_threshold: float = 15.0,    # px / frame (위로 이동)
        height_std_threshold: float = 30.0,   # px
        min_history_frames: int = 10,
        min_consecutive_frames: int = 3,      # 이만큼 연속 만족해야 1회 발화
        reset_after_misses: int = 3,          # 이만큼 끊겨야 다음 점프를 새 이벤트로
    ):
        self._top_speed_th = top_speed_threshold
        self._height_std_th = height_std_threshold
        self._min_history = min_history_frames
        # 동일 점프가 수십 프레임 연속 발화하는 것을 1건으로 묶음 (P0)
        self._debounce = SustainedEventDebouncer(
            min_consecutive_frames=min_consecutive_frames,
            reset_after_misses=reset_after_misses,
        )

    def evaluate(
        self,
        history: TrackHistory,
        sections: dict[str, GateSection],
        all_histories: dict[int, TrackHistory],
        camera_id: str,
    ) -> Optional[Event]:
        candidate = self._detect(history, camera_id)
        return self._debounce.feed(history.track_id, candidate)

    def _detect(self, history: TrackHistory, camera_id: str) -> Optional[Event]:
        snaps = list(history.snapshots)
        if len(snaps) < self._min_history:
            return None

        recent = snaps[-self._min_history:]

        # 최근 프레임 중 섹션 안에 있던 적이 있는가
        section_ids_in_history = [s.section_id for s in recent if s.section_id]
        if not section_ids_in_history:
            return None
        section_id = max(set(section_ids_in_history), key=section_ids_in_history.count)

        # S1. bbox 상단(y1)의 이동 속도 (위로 = y 감소)
        y_tops = [s.bbox[1] for s in recent]
        top_speed_up = (y_tops[0] - y_tops[-1]) / len(recent)  # 양수면 위로

        # S2. bbox 높이 변동
        heights = [s.bbox[3] - s.bbox[1] for s in recent]
        height_std = statistics.pstdev(heights) if len(heights) > 1 else 0.0

        if top_speed_up < self._top_speed_th or height_std < self._height_std_th:
            return None

        # confidence: 신호 두 개의 정규화 가중 합
        c_speed = min(1.0, top_speed_up / (self._top_speed_th * 2))
        c_height = min(1.0, height_std / (self._height_std_th * 2))
        conf = 0.4 + 0.3 * c_speed + 0.3 * c_height

        return Event(
            event_type=self.event_type,
            gate_section_id=section_id,
            camera_id=camera_id,
            confidence=round(conf, 3),
            track_id=history.track_id,
            timestamp=Event.now_iso(),
            raw_meta={
                "top_speed_up_px_per_frame": round(top_speed_up, 2),
                "height_std_px": round(height_std, 2),
                "frames_evaluated": len(recent),
            },
        )
