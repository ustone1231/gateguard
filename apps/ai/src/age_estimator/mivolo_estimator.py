"""Optional MiVOLO age/gender estimator wrapper."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from ..types import BBox, Track
from .base import AgeGenderEstimate, AgeGenderEstimator


@dataclass(frozen=True)
class MivoloConfig:
    detector_weights: str = "models/yolov8x_person_face.pt"
    checkpoint: str = "models/mivolo_imbd.pth.tar"
    device: str = "cpu"
    with_persons: bool = True
    disable_faces: bool = False
    iou_match_threshold: float = 0.30


class MivoloAgeGenderEstimator(AgeGenderEstimator):
    """Run MiVOLO and map detected persons/faces to existing track IDs.

    The `mivolo` package and weights are intentionally optional. Construction
    fails loudly with a useful message if they are missing, instead of silently
    pretending model-backed signals exist.
    """

    def __init__(self, config: MivoloConfig):
        try:
            from mivolo.predictor import Predictor
        except ImportError as exc:
            raise RuntimeError(
                "MiVOLO is not installed. Install optional model dependencies with "
                "`pip install git+https://github.com/WildChlamydia/MiVOLO.git@main`."
            ) from exc

        _require_file(config.detector_weights, "MiVOLO detector weights")
        _require_file(config.checkpoint, "MiVOLO checkpoint")

        self._config = config
        self._predictor = Predictor(
            SimpleNamespace(
                detector_weights=config.detector_weights,
                checkpoint=config.checkpoint,
                device=config.device,
                with_persons=config.with_persons,
                disable_faces=config.disable_faces,
                draw=False,
            ),
            verbose=False,
        )

    def warmup(self) -> None:
        dummy = np.zeros((640, 640, 3), dtype=np.uint8)
        self._predictor.recognize(dummy)

    def estimate(self, frame: np.ndarray, tracks: list[Track]) -> dict[int, AgeGenderEstimate]:
        if not tracks:
            return {}
        detected, _ = self._predictor.recognize(frame)
        candidates = _extract_candidates(detected)
        estimates: dict[int, AgeGenderEstimate] = {}
        for track in tracks:
            candidate = _best_candidate(track.bbox, candidates)
            if candidate is None:
                continue
            bbox, age, gender, gender_confidence = candidate
            if _iou(track.bbox, bbox) < self._config.iou_match_threshold:
                continue
            estimates[track.track_id] = AgeGenderEstimate(
                track_id=track.track_id,
                age=age,
                age_confidence=0.75 if age is not None else None,
                perceived_gender=_normalize_gender(gender),
                gender_confidence=gender_confidence,
            )
        return estimates

    @property
    def model_version(self) -> str:
        return f"mivolo:{Path(self._config.checkpoint).name}"


def _require_file(path: str, label: str) -> None:
    if not Path(path).exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def _extract_candidates(detected: Any) -> list[tuple[BBox, float | None, str | None, float | None]]:
    rows = []
    if hasattr(detected, "get_results_for_tracking"):
        persons, faces = detected.get_results_for_tracking()
        rows.extend(_rows_from_tracking_results(persons))
        rows.extend(_rows_from_tracking_results(faces))
    return rows


def _rows_from_tracking_results(results: dict[Any, Any]) -> list[tuple[BBox, float | None, str | None, float | None]]:
    rows = []
    for _, value in results.items():
        if not isinstance(value, (tuple, list)) or len(value) < 2:
            continue
        age, gender = value[0], value[1]
        bbox = value[2] if len(value) > 2 else None
        if bbox is None or len(bbox) != 4:
            continue
        rows.append((tuple(float(x) for x in bbox), _to_float(age), str(gender), None))
    return rows


def _best_candidate(
    track_box: BBox,
    candidates: list[tuple[BBox, float | None, str | None, float | None]],
) -> tuple[BBox, float | None, str | None, float | None] | None:
    if not candidates:
        return None
    return max(candidates, key=lambda row: _iou(track_box, row[0]))


def _iou(a: BBox, b: BBox) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    return 0.0 if union <= 0 else intersection / union


def _normalize_gender(value: str | None) -> str:
    if value is None:
        return "unknown"
    lowered = value.lower()
    if lowered.startswith("m"):
        return "male"
    if lowered.startswith("f") or lowered.startswith("w"):
        return "female"
    return "unknown"


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
