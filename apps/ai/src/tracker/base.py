"""Tracker 추상 인터페이스.

md 명세:
    Tracker.update(detections) -> [track_id, bbox]
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import Detection, Track


class Tracker(ABC):
    @abstractmethod
    def update(self, detections: list[Detection], frame_idx: int) -> list[Track]:
        ...

    @abstractmethod
    def reset(self) -> None:
        """새 영상 시작 시 호출."""
        ...
