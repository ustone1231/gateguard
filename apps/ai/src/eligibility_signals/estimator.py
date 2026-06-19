"""MVP eligibility signal estimator.

This module produces the v0.2.2 `Event.signals` payload expected by the
backend matching engine. It is intentionally conservative: without face/pose
models it only emits weak age-group hints from track motion and bbox scale,
and leaves gender as `unknown`.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..rules.base import TrackHistory, TrackSnapshot
from ..types import Signals


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


@dataclass(frozen=True)
class EligibilitySignalConfig:
    enabled: bool = True
    slow_speed_px_per_sec: float = 80.0
    fast_speed_px_per_sec: float = 220.0
    child_bbox_height_px: float = 90.0
    adult_bbox_height_px: float = 150.0
    min_age_group_confidence: float = 0.35


class EligibilitySignalEstimator:
    """Estimate weak eligibility signals from already available track history.

    The real roadmap adds MiVOLO, pose, gait, and assistive-device models. This
    MVP estimator keeps the integration contract alive without pretending that
    gender or legal age can be inferred from CCTV alone.
    """

    def __init__(self, config: EligibilitySignalConfig | None = None):
        self._config = config or EligibilitySignalConfig()

    def estimate(self, history: TrackHistory, snapshot: TrackSnapshot) -> Signals | None:
        if not self._config.enabled:
            return None

        gait_score = self._gait_senior_score(history)
        child_probability = self._child_probability(snapshot)
        senior_probability = self._senior_probability(gait_score, child_probability)
        estimated_age_group, confidence = self._age_group(senior_probability, child_probability)

        return Signals(
            gait_senior_score=round(gait_score, 3),
            senior_probability=round(senior_probability, 3),
            child_probability=round(child_probability, 3),
            estimated_age_group=estimated_age_group,
            age_group_confidence=round(confidence, 3),
            perceived_gender="unknown",
        )

    def _gait_senior_score(self, history: TrackHistory) -> float:
        snaps = list(history.snapshots)[-10:]
        if len(snaps) < 2:
            return 0.5

        first = snaps[0]
        last = snaps[-1]
        dt = max(1e-6, last.timestamp_sec - first.timestamp_sec)
        dx = _center_x(last) - _center_x(first)
        dy = _center_y(last) - _center_y(first)
        speed = ((dx * dx + dy * dy) ** 0.5) / dt

        cfg = self._config
        if speed <= cfg.slow_speed_px_per_sec:
            return 0.8
        if speed >= cfg.fast_speed_px_per_sec:
            return 0.15
        ratio = (speed - cfg.slow_speed_px_per_sec) / (cfg.fast_speed_px_per_sec - cfg.slow_speed_px_per_sec)
        return _clamp(0.8 - ratio * 0.65)

    def _child_probability(self, snapshot: TrackSnapshot) -> float:
        height = max(0.0, snapshot.bbox[3] - snapshot.bbox[1])
        cfg = self._config
        if height <= cfg.child_bbox_height_px:
            return 0.75
        if height >= cfg.adult_bbox_height_px:
            return 0.05
        ratio = (height - cfg.child_bbox_height_px) / (cfg.adult_bbox_height_px - cfg.child_bbox_height_px)
        return _clamp(0.75 - ratio * 0.70)

    @staticmethod
    def _senior_probability(gait_score: float, child_probability: float) -> float:
        # In the MVP, gait is the only senior proxy. Child-like scale reduces
        # senior probability so backend child/senior mismatch checks do not fight.
        return _clamp(gait_score * (1.0 - child_probability * 0.75))

    def _age_group(self, senior_probability: float, child_probability: float) -> tuple[str, float]:
        if child_probability >= 0.55:
            return "child", child_probability
        if senior_probability >= 0.65:
            return "senior", senior_probability

        adult_confidence = max(1.0 - senior_probability, 1.0 - child_probability) * 0.6
        if adult_confidence >= self._config.min_age_group_confidence:
            return "adult", _clamp(adult_confidence)
        return "unknown", 0.0


def _center_x(snapshot: TrackSnapshot) -> float:
    return (snapshot.bbox[0] + snapshot.bbox[2]) / 2.0


def _center_y(snapshot: TrackSnapshot) -> float:
    return (snapshot.bbox[1] + snapshot.bbox[3]) / 2.0
