"""Pose estimator interfaces for eligibility signals."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

from ..types import Track


@dataclass(frozen=True)
class PoseEstimate:
    track_id: int
    senior_score: float
    confidence: float
    keypoints: tuple[tuple[float, float, float], ...] = ()


class PoseEstimator(ABC):
    @abstractmethod
    def estimate(self, frame: np.ndarray, tracks: list[Track]) -> dict[int, PoseEstimate]:
        ...

    @abstractmethod
    def warmup(self) -> None:
        ...

    @property
    @abstractmethod
    def model_version(self) -> str:
        ...


class NullPoseEstimator(PoseEstimator):
    def estimate(self, frame: np.ndarray, tracks: list[Track]) -> dict[int, PoseEstimate]:
        return {}

    def warmup(self) -> None:
        return None

    @property
    def model_version(self) -> str:
        return "pose:none"
