"""Rule 추상 + TrackHistory + RuleEngine.

확장 지점 (Option B 학습 트랙):
    Rule을 그대로 두고, RuleEngine.add_rule()로 학습된 모델 기반 rule을
    하나 더 끼우면 됨. 다른 코드 변경 X.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional

from ..types import BBox, Event
from ..zone import GateSection


@dataclass
class TrackSnapshot:
    frame_idx: int
    timestamp_sec: float
    bbox: BBox
    section_id: Optional[str] = None
    crossed_entry: Optional[str] = None   # 어느 section의 entry line을 가로질렀나
    crossed_exit: Optional[str] = None


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


class RuleEngine:
    """모든 Rule을 묶어서 매 프레임 평가 + cooldown 관리.

    md의 'N프레임 지속 + cooldown 로직 (중복 알림 방지)' 구현.
    """

    def __init__(self, rules: list[Rule], cooldown_seconds: dict[str, float] | None = None):
        self._rules = rules
        self._cooldown = cooldown_seconds or {}
        # (track_id, event_type) -> last fire timestamp_sec
        self._last_fire: dict[tuple[int, str], float] = defaultdict(float)

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
                if now_sec - self._last_fire[key] < cd:
                    continue
                event = rule.evaluate(hist, sections, track_histories, camera_id)
                if event is not None:
                    self._last_fire[key] = now_sec
                    fired.append(event)
        return fired
