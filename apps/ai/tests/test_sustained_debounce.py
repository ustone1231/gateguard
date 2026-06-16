"""P0: 동일 트랙 다중 발화 완화 회귀 테스트.

- SustainedEventDebouncer: 지속성/단일발행/평활화/재무장/끊김 허용
- JumpRule 통합: 지속 점프 → 이벤트 1건
- 비회귀: gate_passage(순간 이벤트)는 디바운스 영향 없이 크로싱마다 발행
- RuleEngine: now_sec=0.0(첫 프레임)에서도 발화 (t=0 억제 버그 수정)
"""
from __future__ import annotations

from typing import Optional

from src.rules import GatePassageRule, JumpRule, RuleEngine, TrackHistory
from src.rules.base import Rule, SustainedEventDebouncer, TrackSnapshot
from src.types import Event


def _ev(conf=0.9, track_id=1):
    return Event(
        event_type="jump", gate_section_id="gate_01", camera_id="camera_001",
        confidence=conf, track_id=track_id, timestamp=Event.now_iso(),
    )


# --------------------------------------------------------------------------
# SustainedEventDebouncer 단위
# --------------------------------------------------------------------------
def test_debouncer_requires_min_consecutive():
    d = SustainedEventDebouncer(min_consecutive_frames=3)
    assert d.feed(1, _ev()) is None     # hits=1
    assert d.feed(1, _ev()) is None     # hits=2
    assert d.feed(1, _ev()) is not None  # hits=3 → 발행


def test_debouncer_fires_once_per_run():
    d = SustainedEventDebouncer(min_consecutive_frames=3)
    emitted = [d.feed(1, _ev()) for _ in range(40)]
    assert sum(e is not None for e in emitted) == 1


def test_debouncer_smooths_confidence():
    d = SustainedEventDebouncer(min_consecutive_frames=3)
    d.feed(1, _ev(0.6))
    d.feed(1, _ev(0.8))
    ev = d.feed(1, _ev(1.0))            # 평균 (0.6+0.8+1.0)/3 = 0.8
    assert ev is not None
    assert ev.confidence == 0.8
    assert ev.raw_meta["smoothed_confidence"] == 0.8
    assert ev.raw_meta["consecutive_frames"] == 3


def test_debouncer_rearms_after_reset():
    d = SustainedEventDebouncer(min_consecutive_frames=3, reset_after_misses=3)
    out = []
    out += [d.feed(1, _ev()) for _ in range(3)]   # 1st 발행
    out += [d.feed(1, None) for _ in range(4)]     # >3 미충족 → run 종료
    out += [d.feed(1, _ev()) for _ in range(3)]    # 2nd 발행
    assert sum(e is not None for e in out) == 2


def test_debouncer_tolerates_brief_dropout():
    d = SustainedEventDebouncer(min_consecutive_frames=3, reset_after_misses=3)
    out = []
    out += [d.feed(1, _ev()) for _ in range(3)]   # 발행
    out.append(d.feed(1, None))                    # 1프레임 끊김 (<=3)
    out += [d.feed(1, _ev()) for _ in range(3)]    # 같은 run → 억제
    assert sum(e is not None for e in out) == 1


def test_debouncer_is_per_track():
    d = SustainedEventDebouncer(min_consecutive_frames=3)
    out = []
    for _ in range(3):
        out.append(d.feed(1, _ev(track_id=1)))
        out.append(d.feed(2, _ev(track_id=2)))
    fired = [e for e in out if e is not None]
    assert {e.track_id for e in fired} == {1, 2}


# --------------------------------------------------------------------------
# JumpRule 통합 — 지속 점프 1건
# --------------------------------------------------------------------------
def test_jump_rule_sustained_motion_fires_once():
    rule = JumpRule()
    hist = TrackHistory(track_id=1)
    events = []
    for i in range(30):  # y1 계속 상승 → 점프 조건 지속
        hist.push(TrackSnapshot(
            frame_idx=i, timestamp_sec=i / 30,
            bbox=(100.0, 300.0 - 20.0 * i, 160.0, 400.0),
            section_id="gate_01",
        ))
        ev = rule.evaluate(hist, {}, {1: hist}, "camera_001")
        if ev is not None:
            events.append(ev)
    assert len(events) == 1
    assert events[0].raw_meta["consecutive_frames"] >= 3
    assert "smoothed_confidence" in events[0].raw_meta


# --------------------------------------------------------------------------
# 비회귀: gate_passage 는 디바운스 영향 없음 (크로싱마다 발행)
# --------------------------------------------------------------------------
def test_gate_passage_still_emits_per_crossing_through_engine():
    engine = RuleEngine([GatePassageRule()], cooldown_seconds={"gate_passage": 0.0})
    hist = TrackHistory(track_id=1)
    fired = []
    for i in range(15):
        crossing = "gate_01" if i in (0, 5, 10) else None  # 3회 통과
        hist.push(TrackSnapshot(
            frame_idx=i, timestamp_sec=i / 30, bbox=(0, 0, 10, 20),
            crossed_entry=crossing, crossed_entry_direction=1,
        ))
        fired += engine.evaluate({1: hist}, {}, "camera_001", now_sec=i / 30)
    gate_events = [e for e in fired if e.event_type == "gate_passage"]
    assert len(gate_events) == 3   # 디바운스로 뭉개지지 않음


# --------------------------------------------------------------------------
# RuleEngine t=0 억제 버그 수정
# --------------------------------------------------------------------------
class _FireOnce(Rule):
    name = event_type = "always"

    def __init__(self):
        self._done = False

    def evaluate(self, history, sections, all_histories, camera_id) -> Optional[Event]:
        if self._done:
            return None
        self._done = True
        return _ev(track_id=history.track_id)


def test_engine_fires_at_t0():
    """이전: _last_fire=defaultdict(0.0) 라 now_sec=0.0 에서 cooldown 이
    첫 발화를 막았음. 수정 후 첫 프레임에서도 발화 가능."""
    engine = RuleEngine([_FireOnce()], cooldown_seconds={"always": 3.0})
    hist = TrackHistory(track_id=1)
    hist.push(TrackSnapshot(frame_idx=0, timestamp_sec=0.0, bbox=(0, 0, 10, 20)))
    fired = engine.evaluate({1: hist}, {}, "camera_001", now_sec=0.0)
    assert len(fired) == 1
