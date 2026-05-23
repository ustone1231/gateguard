"""ByteTrack 기반 Tracker.

ultralytics 내장 트래커를 쓰지 않고 supervision의 ByteTrack을 직접 호출.
이유: Detector와 결합도를 낮춰서, YOLO가 아닌 다른 detector도 그대로 추적 가능.
"""
from __future__ import annotations

import numpy as np

from .base import Tracker
from ..types import Detection, Track


class ByteTrackTracker(Tracker):
    def __init__(
        self,
        track_activation_threshold: float = 0.25,
        lost_track_buffer: int = 30,
        minimum_matching_threshold: float = 0.8,
        frame_rate: int = 30,
    ):
        import supervision as sv

        self._sv = sv
        self._frame_rate = frame_rate
        self._tracker = sv.ByteTrack(
            track_activation_threshold=track_activation_threshold,
            lost_track_buffer=lost_track_buffer,
            minimum_matching_threshold=minimum_matching_threshold,
            frame_rate=frame_rate,
        )

    def reset(self) -> None:
        self._tracker.reset()

    def update(self, detections: list[Detection], frame_idx: int) -> list[Track]:
        if not detections:
            return []

        xyxy = np.array([d.bbox for d in detections], dtype=float)
        conf = np.array([d.confidence for d in detections], dtype=float)
        cls = np.array([d.class_id for d in detections], dtype=int)

        sv_det = self._sv.Detections(xyxy=xyxy, confidence=conf, class_id=cls)
        tracked = self._tracker.update_with_detections(sv_det)

        out: list[Track] = []
        if tracked.tracker_id is None:
            return out
        for box, tid, c in zip(tracked.xyxy, tracked.tracker_id, tracked.confidence):
            x1, y1, x2, y2 = box.tolist()
            out.append(Track(track_id=int(tid), bbox=(x1, y1, x2, y2), confidence=float(c)))
        return out
