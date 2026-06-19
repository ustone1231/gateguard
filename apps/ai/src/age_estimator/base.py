"""Age/gender estimator interfaces for eligibility signals."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

from ..types import Track


@dataclass(frozen=True)
class AgeGenderEstimate:
    track_id: int
    age: float | None = None
    age_confidence: float | None = None
    perceived_gender: str = "unknown"
    gender_confidence: float | None = None


class AgeGenderEstimator(ABC):
    @abstractmethod
    def estimate(self, frame: np.ndarray, tracks: list[Track]) -> dict[int, AgeGenderEstimate]:
        ...

    @abstractmethod
    def warmup(self) -> None:
        ...

    @property
    @abstractmethod
    def model_version(self) -> str:
        ...


class NullAgeGenderEstimator(AgeGenderEstimator):
    def estimate(self, frame: np.ndarray, tracks: list[Track]) -> dict[int, AgeGenderEstimate]:
        return {}

    def warmup(self) -> None:
        return None

    @property
    def model_version(self) -> str:
        return "age-gender:none"
