"""RuleEngine 테스트 — cooldown 으로 중복 알림 억제 (현재 develop 동작 기준).

참고: 현재 엔진은 _last_fire 초기값이 0.0 이라, 첫 발화는 now_sec >= cooldown
이어야 가능하다(알려진 t=0 억제 동작). 아래 테스트는 now_sec 를 그에 맞춰 잡는다.
"""
from __future__ import annotations

from src.rules import RuleEngine, TrackHistory
from src.rules.base import Rule, TrackSnapshot
from src.types import Event


class AlwaysFireRule(Rule):
    name = "always"
    event_type = "always"

    def __init__(self):
        self.calls = 0

    def evaluate(self, history, sections, all_histories, camera_id):
        self.calls += 1
        return Event(
            event_type=self.event_type,
            gate_section_id="gate_01",
            camera_id=camera_id,
            confidence=0.9,
            track_id=history.track_id,
            timestamp=Event.now_iso(),
        )


def _history(track_id=1):
    h = TrackHistory(track_id=track_id)
    h.push(TrackSnapshot(frame_idx=0, timestamp_sec=0.0, bbox=(0, 0, 10, 20)))
    return {track_id: h}


def test_engine_fires_then_suppresses_within_cooldown():
    engine = RuleEngine([AlwaysFireRule()], cooldown_seconds={"always": 3.0})
    hist = _history()

    assert len(engine.evaluate(hist, {}, "camera_001", now_sec=5.0)) == 1   # 발화
    assert engine.evaluate(hist, {}, "camera_001", now_sec=6.0) == []       # 쿨다운 내 억제
    assert len(engine.evaluate(hist, {}, "camera_001", now_sec=9.0)) == 1   # 쿨다운 경과


def test_engine_skips_empty_history():
    rule = AlwaysFireRule()
    engine = RuleEngine([rule])
    empty = {1: TrackHistory(track_id=1)}  # 스냅샷 없음

    assert engine.evaluate(empty, {}, "camera_001", now_sec=5.0) == []
    assert rule.calls == 0  # 룰 호출조차 안 됨


def test_engine_cooldown_is_per_track():
    engine = RuleEngine([AlwaysFireRule()], cooldown_seconds={"always": 3.0})
    h1 = TrackHistory(track_id=1)
    h1.push(TrackSnapshot(frame_idx=0, timestamp_sec=0.0, bbox=(0, 0, 10, 20)))
    h2 = TrackHistory(track_id=2)
    h2.push(TrackSnapshot(frame_idx=0, timestamp_sec=0.0, bbox=(0, 0, 10, 20)))

    fired = engine.evaluate({1: h1, 2: h2}, {}, "camera_001", now_sec=5.0)
    assert {e.track_id for e in fired} == {1, 2}


def test_add_rule_registers_with_cooldown():
    engine = RuleEngine([])
    engine.add_rule(AlwaysFireRule(), cooldown_seconds=2.0)
    hist = _history()

    assert len(engine.evaluate(hist, {}, "camera_001", now_sec=5.0)) == 1
    assert engine.evaluate(hist, {}, "camera_001", now_sec=6.0) == []  # 2s 쿨다운 내
