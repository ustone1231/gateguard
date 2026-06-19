from __future__ import annotations

import numpy as np
import pytest

from src.age_estimator import MivoloAgeGenderEstimator, MivoloConfig, NullAgeGenderEstimator
from src.pose_estimator import NullPoseEstimator
from src.rules import TrackHistory
from src.rules.base import TrackSnapshot
from src.eligibility_signals import EligibilitySignalEstimator
from src.types import Track


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
