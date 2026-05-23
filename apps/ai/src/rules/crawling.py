"""Crawling 룰.

md 명세:
    "bbox 높이가 평균 대비 임계치 이하 + 섹션 하단 따라 이동"

판정 신호:
  S1. bbox 높이가 정상 평균의 일정 비율 이하로 유지 (N프레임)
  S2. 섹션 내부 + 발이 섹션 하단 영역에 위치

주의: 카메라 각도에 따라 임계치 보정 필요. 임계치는 config로 노출.
"""
from __future__ import annotations

from typing import Optional

from .base import Rule, TrackHistory
from ..types import Event
from ..zone import GateSection


class CrawlingRule(Rule):
    name = "crawling"
    event_type = "crawling"

    def __init__(
        self,
        height_ratio_threshold: float = 0.55,   # 정상 높이 대비 비율
        min_frames_crawling: int = 8,
        baseline_window: int = 30,              # 이 트랙의 정상 높이 baseline
    ):
        self._height_ratio_th = height_ratio_threshold
        self._min_frames = min_frames_crawling
        self._baseline_window = baseline_window

    def evaluate(
        self,
        history: TrackHistory,
        sections: dict[str, GateSection],
        all_histories: dict[int, TrackHistory],
        camera_id: str,
    ) -> Optional[Event]:
        snaps = list(history.snapshots)
        if len(snaps) < max(self._min_frames, 15):
            return None

        # baseline: 트랙의 첫 baseline_window 프레임 평균 (정상 자세로 가정)
        baseline_snaps = snaps[: self._baseline_window]
        baseline_heights = [s.bbox[3] - s.bbox[1] for s in baseline_snaps]
        if not baseline_heights:
            return None
        baseline = sum(baseline_heights) / len(baseline_heights)
        if baseline <= 0:
            return None

        # 최근 N프레임이 baseline의 일정 비율 이하인가
        recent = snaps[-self._min_frames:]
        recent_heights = [s.bbox[3] - s.bbox[1] for s in recent]
        avg_recent = sum(recent_heights) / len(recent_heights)
        ratio = avg_recent / baseline

        if ratio > self._height_ratio_th:
            return None

        # 섹션 안에서 진행 중인가
        section_ids = [s.section_id for s in recent if s.section_id]
        if not section_ids:
            return None
        section_id = max(set(section_ids), key=section_ids.count)

        # confidence: 비율이 낮을수록 (자세가 낮을수록) 높음
        conf = 0.5 + 0.4 * (1.0 - ratio / self._height_ratio_th)
        conf = max(0.5, min(0.95, conf))

        return Event(
            event_type=self.event_type,
            gate_section_id=section_id,
            camera_id=camera_id,
            confidence=round(conf, 3),
            track_id=history.track_id,
            timestamp=Event.now_iso(),
            raw_meta={
                "height_ratio": round(ratio, 3),
                "baseline_height_px": round(baseline, 1),
                "recent_avg_height_px": round(avg_recent, 1),
            },
        )
