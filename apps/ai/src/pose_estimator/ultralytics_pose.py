"""Ultralytics YOLO pose wrapper.

The wrapper maps pose detections back to existing ByteTrack IDs by bbox IoU so
the rest of the pipeline can keep using one track identity source.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ..types import BBox, Track
from .base import PoseEstimate, PoseEstimator


class UltralyticsPoseEstimator(PoseEstimator):
    def __init__(
        self,
        weights: str = "models/yolo11n-pose.pt",
        device: str = "auto",
        conf_threshold: float = 0.35,
        iou_match_threshold: float = 0.30,
    ):
        from ultralytics import YOLO

        self._weights = weights
        self._device = device if device != "auto" else None
        self._conf = conf_threshold
        self._iou_match = iou_match_threshold
        self._model = YOLO(weights)

    def warmup(self) -> None:
        dummy = np.zeros((640, 640, 3), dtype=np.uint8)
        _ = self._model.predict(dummy, conf=self._conf, verbose=False, device=self._device)

    def estimate(self, frame: np.ndarray, tracks: list[Track]) -> dict[int, PoseEstimate]:
        if not tracks:
            return {}
        results = self._model.predict(frame, conf=self._conf, verbose=False, device=self._device)
        if not results:
            return {}

        result = results[0]
        if result.boxes is None or result.keypoints is None:
            return {}

        boxes = result.boxes.xyxy.cpu().numpy()
        keypoints = result.keypoints.data.cpu().numpy()
        estimates: dict[int, PoseEstimate] = {}

        for track in tracks:
            best_idx = _best_iou_index(track.bbox, boxes)
            if best_idx is None:
                continue
            if _iou(track.bbox, tuple(boxes[best_idx].tolist())) < self._iou_match:
                continue

            kp = tuple(tuple(float(v) for v in point) for point in keypoints[best_idx].tolist())
            confidence = _mean_keypoint_confidence(kp)
            estimates[track.track_id] = PoseEstimate(
                track_id=track.track_id,
                senior_score=_pose_senior_score(kp),
                confidence=confidence,
                keypoints=kp,
            )
        return estimates

    @property
    def model_version(self) -> str:
        return f"ultralytics-pose:{Path(self._weights).name}"


def _best_iou_index(track_box: BBox, boxes: np.ndarray) -> int | None:
    if len(boxes) == 0:
        return None
    scores = [_iou(track_box, tuple(box.tolist())) for box in boxes]
    return int(np.argmax(scores))


def _iou(a: BBox, b: BBox) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    intersection = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    return 0.0 if union <= 0 else intersection / union


def _mean_keypoint_confidence(keypoints: tuple[tuple[float, float, float], ...]) -> float:
    confs = [point[2] for point in keypoints if len(point) >= 3 and point[2] > 0]
    return round(float(sum(confs) / len(confs)), 3) if confs else 0.0


def _pose_senior_score(keypoints: tuple[tuple[float, float, float], ...]) -> float:
    # COCO order: shoulders 5/6, hips 11/12. A larger forward/vertical torso
    # compression proxy nudges senior likelihood up, but stays conservative.
    if len(keypoints) < 13:
        return 0.5
    left_shoulder, right_shoulder = keypoints[5], keypoints[6]
    left_hip, right_hip = keypoints[11], keypoints[12]
    required = [left_shoulder, right_shoulder, left_hip, right_hip]
    if any(len(p) < 3 or p[2] < 0.25 for p in required):
        return 0.5

    shoulder_y = (left_shoulder[1] + right_shoulder[1]) / 2.0
    hip_y = (left_hip[1] + right_hip[1]) / 2.0
    torso_height = max(1.0, abs(hip_y - shoulder_y))
    shoulder_span = abs(right_shoulder[0] - left_shoulder[0])
    compression = shoulder_span / torso_height
    return round(max(0.1, min(0.9, 0.25 + compression * 0.35)), 3)
