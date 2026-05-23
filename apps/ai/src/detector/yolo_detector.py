"""YOLO11 기반 Detector 구현.

다른 모델로 바꾸려면 이 클래스만 갈아끼우면 됨.
"""
from __future__ import annotations

import numpy as np

from .base import Detector
from ..types import Detection


class YoloDetector(Detector):
    def __init__(
        self,
        weights: str = "yolo11n.pt",
        device: str = "auto",
        conf_threshold: float = 0.4,
        iou_threshold: float = 0.5,
        classes: list[int] | None = None,
    ):
        from ultralytics import YOLO

        self._weights = weights
        self._device = device if device != "auto" else None
        self._conf = conf_threshold
        self._iou = iou_threshold
        self._classes = classes or [0]
        self._model = YOLO(weights)

    def warmup(self) -> None:
        dummy = np.zeros((640, 640, 3), dtype=np.uint8)
        _ = self._model.predict(
            dummy, conf=self._conf, iou=self._iou,
            classes=self._classes, verbose=False,
        )

    def detect(self, frame: np.ndarray) -> list[Detection]:
        results = self._model.predict(
            frame,
            conf=self._conf,
            iou=self._iou,
            classes=self._classes,
            verbose=False,
            device=self._device,
        )
        detections: list[Detection] = []
        if not results:
            return detections

        r = results[0]
        if r.boxes is None or len(r.boxes) == 0:
            return detections

        xyxy = r.boxes.xyxy.cpu().numpy()
        confs = r.boxes.conf.cpu().numpy()
        cls = r.boxes.cls.cpu().numpy().astype(int)
        for box, c, k in zip(xyxy, confs, cls):
            x1, y1, x2, y2 = box.tolist()
            detections.append(
                Detection(bbox=(x1, y1, x2, y2), confidence=float(c), class_id=int(k))
            )
        return detections

    @property
    def model_version(self) -> str:
        return f"yolo:{self._weights}"
