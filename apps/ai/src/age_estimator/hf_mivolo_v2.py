"""HuggingFace MiVOLO v2 age/gender estimator."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..types import Track
from .base import AgeGenderEstimate, AgeGenderEstimator


@dataclass(frozen=True)
class HfMivoloV2Config:
    model_id: str = "iitolstykh/mivolo_v2"
    device: str = "cpu"
    torch_dtype: str = "float32"
    revision: str | None = None


class HfMivoloV2AgeGenderEstimator(AgeGenderEstimator):
    """Use the Apache-2.0 HuggingFace MiVOLO v2 model.

    This path avoids the original MiVOLO `.pth.tar` checkpoint requirement.
    It still uses `trust_remote_code=True`, so production deployments should
    pin `revision` after reviewing the downloaded model code.
    """

    def __init__(self, config: HfMivoloV2Config):
        try:
            import torch
            from transformers import AutoConfig, AutoImageProcessor, AutoModelForImageClassification
        except ImportError as exc:
            raise RuntimeError(
                "HuggingFace MiVOLO v2 requires transformers, accelerate, and torch. "
                "Install optional dependencies from the AI README."
            ) from exc

        self._torch = torch
        self._config = config
        self._device = torch.device(config.device)
        self._dtype = _torch_dtype(torch, config.torch_dtype)
        kwargs = {"trust_remote_code": True}
        if config.revision:
            kwargs["revision"] = config.revision

        try:
            self._hf_config = AutoConfig.from_pretrained(config.model_id, **kwargs)
            self._processor = AutoImageProcessor.from_pretrained(config.model_id, **kwargs)
            self._model = AutoModelForImageClassification.from_pretrained(
                config.model_id,
                torch_dtype=self._dtype,
                **kwargs,
            )
        except ModuleNotFoundError as exc:
            missing = exc.name or "unknown"
            if missing == "mivolo":
                raise RuntimeError(
                    "HuggingFace MiVOLO v2 remote code imports the `mivolo` package. "
                    "Install the optional MiVOLO runtime described in the AI README."
                ) from exc
            raise
        self._model.to(self._device)
        self._model.eval()

    def warmup(self) -> None:
        dummy = np.zeros((384, 384, 3), dtype=np.uint8)
        self._predict_batch([None], [dummy])

    def estimate(self, frame: np.ndarray, tracks: list[Track]) -> dict[int, AgeGenderEstimate]:
        if not tracks:
            return {}

        crops = [_crop(frame, track.bbox) for track in tracks]
        valid_pairs = [(track, crop) for track, crop in zip(tracks, crops) if crop is not None]
        if not valid_pairs:
            return {}

        valid_tracks = [track for track, _ in valid_pairs]
        body_crops = [crop for _, crop in valid_pairs]
        face_crops = [None for _ in body_crops]
        outputs = self._predict_batch(face_crops, body_crops)

        estimates: dict[int, AgeGenderEstimate] = {}
        id2label = self._hf_config.gender_id2label
        for idx, track in enumerate(valid_tracks):
            age = float(outputs.age_output[idx].item())
            gender_idx = int(outputs.gender_class_idx[idx].item())
            gender_prob = float(outputs.gender_probs[idx].item())
            estimates[track.track_id] = AgeGenderEstimate(
                track_id=track.track_id,
                age=round(age, 2),
                age_confidence=_age_confidence(age),
                perceived_gender=_normalize_gender(id2label[gender_idx]),
                gender_confidence=round(gender_prob, 3),
            )
        return estimates

    @property
    def model_version(self) -> str:
        revision = f"@{self._config.revision}" if self._config.revision else ""
        return f"hf-mivolo-v2:{self._config.model_id}{revision}"

    def _predict_batch(self, face_crops: list[np.ndarray | None], body_crops: list[np.ndarray]):
        faces_input = self._processor(images=face_crops)["pixel_values"]
        body_input = self._processor(images=body_crops)["pixel_values"]
        faces_input = faces_input.to(dtype=self._dtype, device=self._device)
        body_input = body_input.to(dtype=self._dtype, device=self._device)
        with self._torch.no_grad():
            return self._model(faces_input=faces_input, body_input=body_input)


def _torch_dtype(torch, name: str):
    if name == "float16":
        return torch.float16
    if name == "bfloat16":
        return torch.bfloat16
    return torch.float32


def _crop(frame: np.ndarray, bbox: tuple[float, float, float, float]) -> np.ndarray | None:
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = bbox
    x1_i = max(0, min(width - 1, int(x1)))
    y1_i = max(0, min(height - 1, int(y1)))
    x2_i = max(0, min(width, int(x2)))
    y2_i = max(0, min(height, int(y2)))
    if x2_i <= x1_i or y2_i <= y1_i:
        return None
    crop = frame[y1_i:y2_i, x1_i:x2_i]
    if crop.size == 0:
        return None
    return crop


def _normalize_gender(value: str) -> str:
    lowered = value.lower()
    if lowered.startswith("m"):
        return "male"
    if lowered.startswith("f") or lowered.startswith("w"):
        return "female"
    return "unknown"


def _age_confidence(age: float) -> float:
    # MiVOLO v2 does not expose calibrated age uncertainty. Keep this explicit
    # and conservative so backend thresholds do not treat age as legal truth.
    if age < 0 or age > 122:
        return 0.0
    return 0.7
