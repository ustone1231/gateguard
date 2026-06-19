from __future__ import annotations

import numpy as np
import pytest

from src.age_estimator import (
    HfMivoloV2Config,
    MivoloAgeGenderEstimator,
    MivoloConfig,
    NullAgeGenderEstimator,
)
from src.age_estimator.hf_mivolo_v2 import _age_confidence, _crop, _normalize_gender
from src.pose_estimator import NullPoseEstimator
from src.rules import TrackHistory
from src.rules.base import TrackSnapshot
from src.eligibility_signals import EligibilitySignalEstimator
from src.types import Track
from scripts.smoke_model_gate_passage import validate_gate_passage_signals


def test_null_model_estimators_are_noops():
    frame = np.zeros((32, 32, 3), dtype=np.uint8)
    tracks = [Track(track_id=1, bbox=(1, 1, 10, 20), confidence=0.9)]

    assert NullPoseEstimator().estimate(frame, tracks) == {}
    assert NullAgeGenderEstimator().estimate(frame, tracks) == {}


def test_mivolo_missing_weights_fails_loudly(tmp_path):
    with pytest.raises((FileNotFoundError, RuntimeError)):
        MivoloAgeGenderEstimator(
            MivoloConfig(
                detector_weights=str(tmp_path / "missing_detector.pt"),
                checkpoint=str(tmp_path / "missing_checkpoint.pth.tar"),
            )
        )


def test_hf_mivolo_v2_config_defaults_to_public_model():
    config = HfMivoloV2Config()

    assert config.model_id == "iitolstykh/mivolo_v2"
    assert config.device == "cpu"
    assert config.torch_dtype == "float32"


def test_hf_mivolo_helpers_crop_and_normalize_gender():
    frame = np.zeros((20, 30, 3), dtype=np.uint8)

    crop = _crop(frame, (-5, 2, 10, 18))

    assert crop is not None
    assert crop.shape == (16, 10, 3)
    assert _crop(frame, (10, 10, 10, 15)) is None
    assert _normalize_gender("male") == "male"
    assert _normalize_gender("female") == "female"
    assert _normalize_gender("other") == "unknown"
    assert _age_confidence(42) == 0.7
    assert _age_confidence(130) == 0.0


def test_eligibility_signals_prefer_model_hints_over_heuristics():
    history = TrackHistory(track_id=3)
    history.push(
        TrackSnapshot(
            frame_idx=1,
            timestamp_sec=0.0,
            bbox=(10, 10, 40, 170),
            face_age_estimate=72,
            pose_senior_score=0.8,
            perceived_gender="female",
            gender_confidence=0.91,
            age_group_confidence=0.82,
        )
    )

    signals = EligibilitySignalEstimator().estimate(history, history.snapshots[-1])

    assert signals is not None
    assert signals.face_age_estimate == 72
    assert signals.pose_senior_score == 0.8
    assert signals.senior_probability is not None
    assert signals.senior_probability > 0.65
    assert signals.estimated_age_group == "senior"
    assert signals.perceived_gender == "female"
    assert signals.gender_confidence == 0.91


def test_model_gate_passage_smoke_validator_requires_model_signals():
    events = [
        {
            "event_type": "gate_passage",
            "signals": {
                "face_age_estimate": 32.5,
                "estimated_age_group": "adult",
                "perceived_gender": "male",
                "gender_confidence": 0.91,
            },
        },
        {"event_type": "gate_passage", "signals": {"estimated_age_group": "adult"}},
        {"event_type": "tailgating"},
    ]

    summary = validate_gate_passage_signals(events)

    assert summary["event_count"] == 3
    assert summary["gate_passage_count"] == 2
    assert summary["model_signal_gate_passage_count"] == 1
    assert summary["high_confidence_gender_gate_passage_count"] == 1
    assert summary["high_confidence_gender_threshold"] == 0.8
