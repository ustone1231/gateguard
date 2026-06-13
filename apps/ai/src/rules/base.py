"""Rule 추상 + TrackHistory + RuleEngine.

확장 지점 (Option B 학습 트랙):
    Rule을 그대로 두고, RuleEngine.add_rule()로 학습된 모델 기반 rule을
    하나 더 끼우면 됨. 다른 코드 변경 X.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from ..types import BBox, Event
from ..zone import GateSection


@dataclass
class TrackSnapshot:
    frame_idx: int
    timestamp_sec: float
    bbox: BBox
    confidence: float = 1.0
    section_id: Optional[str] = None
    crossed_entry: Optional[str] = None   # 어느 section의 entry line을 가로질렀나
    crossed_exit: Optional[str] = None
    crossed_entry_direction: Optional[int] = None
    crossed_exit_direction: Optional[int] = None


@dataclass
class TrackHistory:
    """track_id별 최근 N프레임의 상태 보관.

    룰들은 이걸 보고 판정. Rule이 직접 frame을 보지 않는 게 핵심.
    """
    track_id: int
    max_len: int = 90  # 약 3초 @ 30fps
    snapshots: deque[TrackSnapshot] = field(default_factory=deque)
    last_section_id: Optional[str] = None

    def push(self, snap: TrackSnapshot) -> None:
        self.snapshots.append(snap)
        if len(self.snapshots) > self.max_len:
            self.snapshots.popleft()
        if snap.section_id is not None:
            self.last_section_id = snap.section_id


class Rule(ABC):
    """행동 룰 1개.

    evaluate()는 매 프레임 호출됨. 이벤트가 확정되면 Event 반환, 아니면 None.
    cooldown은 RuleEngine이 관리.
    """

    name: str = "base"
    event_type: str = "unknown"

    @abstractmethod
    def evaluate(
        self,
        history: TrackHistory,
        sections: dict[str, GateSection],
        all_histories: dict[int, TrackHistory],
        camera_id: str,
    ) -> Optional[Event]:
        ...


@dataclass
class _EpisodeState:
    """SustainedEventDebouncer 의 트랙별 진행 상태."""
    hits: int = 0           # 이 run 에서 조건을 만족한 프레임 수
    misses: int = 0         # 마지막 hit 이후 연속 미충족 프레임 수
    conf_sum: float = 0.0    # confidence 합 (평활화용)
    emitted: bool = False    # 이 run 에서 이미 발행했는가


class SustainedEventDebouncer:
    """지속 행동 룰(jump/crawling) 전용 트랙별 발화 디바운스 + confidence 평활화.

    같은 사람의 한 번의 행동(점프/기어가기)이 수십 프레임 연속으로 룰을
    발화시키는 것을 이벤트 1건으로 묶는다 (P0: 동일 트랙 다중 발화 완화).

    주의: gate_passage 같은 '순간 이벤트'(line crossing)에는 쓰지 않는다 —
    그건 룰 자체가 crossing 단위로 1회 발행하므로 디바운스하면 오히려 누락된다.

    규칙:
      - 조건이 min_consecutive_frames 연속 만족해야 1회 발행 (지속성 → 1프레임 오탐 억제).
      - 한 번의 run 당 1회만. reset_after_misses 초과로 조건이 끊겼다 재발생해야 새 이벤트.
      - 발행 confidence = run 동안 프레임별 confidence 의 평균 (단일 프레임 노이즈 제거).
    """

    def __init__(self, min_consecutive_frames: int = 3, reset_after_misses: int = 3):
        self._min_consecutive = max(1, min_consecutive_frames)
        self._reset_after_misses = max(0, reset_after_misses)
        self._states: dict[int, _EpisodeState] = {}

    def feed(self, track_id: int, candidate: Optional[Event]) -> Optional[Event]:
        """매 프레임 호출. 룰이 만든 raw Event(또는 None)를 받아
        실제 발행할 Event(평활화 적용) 또는 None 을 돌려준다."""
        st = self._states.get(track_id)

        if candidate is None:                     # 조건 미충족 → run 종료 판단
            if st is not None:
                st.misses += 1
                if st.misses > self._reset_after_misses:
                    del self._states[track_id]    # run 종료 → 다음 발생은 새 이벤트
            return None

        if st is None:
            st = _EpisodeState()
            self._states[track_id] = st
        st.misses = 0
        st.hits += 1
        st.conf_sum += candidate.confidence

        if st.emitted or st.hits < self._min_consecutive:
            return None                           # 이미 발행했거나 지속성 미확정

        smoothed = round(st.conf_sum / st.hits, 3)
        candidate.confidence = smoothed
        candidate.raw_meta = {
            **candidate.raw_meta,
            "consecutive_frames": st.hits,
            "smoothed_confidence": smoothed,
        }
        st.emitted = True
        return candidate


class RuleEngine:
    """모든 Rule을 묶어서 매 프레임 평가 + cooldown 관리.

    md의 'N프레임 지속 + cooldown 로직 (중복 알림 방지)' 구현.

    참고: 지속 run 단위 중복 제거는 각 룰(jump/crawling)이
    SustainedEventDebouncer 로 자체 처리한다. 여기 cooldown 은 서로 다른
    run/이벤트 사이의 2차 시간 가드다.
    """

    def __init__(self, rules: list[Rule], cooldown_seconds: dict[str, float] | None = None):
        self._rules = rules
        self._cooldown = cooldown_seconds or {}
        # (track_id, event_type) -> last fire timestamp_sec. 발화한 적 있을 때만 존재.
        # (defaultdict 가 아니라 plain dict: 첫 발화를 cooldown 이 막지 않도록 — t=0 버그 수정)
        self._last_fire: dict[tuple[int, str], float] = {}

    def add_rule(self, rule: Rule, cooldown_seconds: float = 3.0) -> None:
        """확장 지점: 학습된 모델 기반 rule 추가용."""
        self._rules.append(rule)
        self._cooldown[rule.event_type] = cooldown_seconds

    def evaluate(
        self,
        track_histories: dict[int, TrackHistory],
        sections: dict[str, GateSection],
        camera_id: str,
        now_sec: float,
    ) -> list[Event]:
        fired: list[Event] = []
        for tid, hist in track_histories.items():
            if not hist.snapshots:
                continue
            for rule in self._rules:
                key = (tid, rule.event_type)
                cd = self._cooldown.get(rule.event_type, 3.0)
                last = self._last_fire.get(key)
                if last is not None and now_sec - last < cd:
                    continue
                event = rule.evaluate(hist, sections, track_histories, camera_id)
                if event is not None:
                    self._last_fire[key] = now_sec
                    fired.append(event)
        return fired
