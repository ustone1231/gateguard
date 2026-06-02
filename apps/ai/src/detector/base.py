"""Detector 추상 인터페이스.

md 명세:
    Detector.detect(frame) -> [bbox, class, conf]

모델 교체(YOLO → RT-DETR → MediaPipe 등)는 이 인터페이스만 구현하면 됨.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from ..types import Detection


class Detector(ABC):
    """프레임 1장 → 사람 detection 리스트."""

    @abstractmethod
    def detect(self, frame: np.ndarray) -> list[Detection]:
        ...

    @abstractmethod
    def warmup(self) -> None:
        """첫 추론 전 워밍업. GPU JIT 컴파일 등."""
        ...

    @property
    @abstractmethod
    def model_version(self) -> str:
        """이 detection을 만든 모델 식별자. model_versions 테이블과 매칭."""
        ...
