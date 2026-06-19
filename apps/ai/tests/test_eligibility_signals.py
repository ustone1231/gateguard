from __future__ import annotations

from src.eligibility_signals import EligibilitySignalConfig, EligibilitySignalEstimator
from src.rules import TrackHistory
from src.rules.base import TrackSnapshot


def test_eligibility_signals_can_import_before_rules_package():
    assert EligibilitySignalEstimator is not None


def _history(*snapshots: TrackSnapshot) -> TrackHistory:
    history = TrackHistory(track_id=3)
    for snapshot in snapshots:
        history.push(snapshot)
    return history


def test_estimator_emits_v022_signal_fields_without_gender_claim():
    estimator = EligibilitySignalEstimator()
    history = _history(
        TrackSnapshot(frame_idx=1, timestamp_sec=0.0, bbox=(10, 10, 40, 170)),
        TrackSnapshot(frame_idx=8, timestamp_sec=0.8, bbox=(40, 10, 70, 170)),
    )

    signals = estimator.estimate(history, history.snapshots[-1])

    assert signals is not None
    assert signals.senior_probability is not None
    assert signals.child_probability is not None
    assert signals.estimated_age_group in {"adult", "senior", "child", "unknown"}
    assert signals.age_group_confidence is not None
    assert signals.perceived_gender == "unknown"
    assert signals.gender_confidence is None


def test_estimator_can_be_disabled():
    estimator = EligibilitySignalEstimator(EligibilitySignalConfig(enabled=False))
    snapshot = TrackSnapshot(frame_idx=1, timestamp_sec=0.0, bbox=(10, 10, 40, 80))
    history = _history(snapshot)

    assert estimator.estimate(history, snapshot) is None


def test_fast_adult_sized_track_gets_low_senior_and_child_probability():
    estimator = EligibilitySignalEstimator(
        EligibilitySignalConfig(
            slow_speed_px_per_sec=50.0,
            fast_speed_px_per_sec=150.0,
            child_bbox_height_px=80.0,
            adult_bbox_height_px=140.0,
        )
    )
    history = _history(
        TrackSnapshot(frame_idx=1, timestamp_sec=0.0, bbox=(10, 10, 40, 170)),
        TrackSnapshot(frame_idx=12, timestamp_sec=1.0, bbox=(220, 10, 250, 170)),
    )

    signals = estimator.estimate(history, history.snapshots[-1])

    assert signals is not None
    assert signals.senior_probability is not None
    assert signals.senior_probability < 0.20
    assert signals.child_probability is not None
    assert signals.child_probability < 0.20
    assert signals.estimated_age_group == "adult"
