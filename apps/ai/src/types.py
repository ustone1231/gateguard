"""공통 데이터 타입.

packages/schema/events/event.schema.json v0.2.2 와 1:1 매칭.
백엔드 POST /api/v1/events 요청 본문이 Event 인스턴스를 그대로 직렬화한 형태.

발행자 책임:
  - AI 트랙: gate_passage, jump, crawling, tailgating, unpaid (=우회/역방향)
  - 백엔드: confirmed_unpaid, confirmed_misuse (AI event + AFC fare_tap 매칭 후)
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Literal, Optional


BBox = tuple[float, float, float, float]  # (x1, y1, x2, y2)
Point = tuple[float, float]
Line = tuple[Point, Point]


Reliability = Literal["low", "mid", "high"]
Severity = Literal["info", "warning", "critical"]
CardCategory = Literal["regular", "senior", "child", "disabled", "national_merit"]
AssistiveDeviceType = Literal["cane", "walker", "wheelchair"]
Gender = Literal["male", "female", "unknown"]
AgeGroup = Literal["child", "youth", "adult", "senior", "unknown"]


@dataclass
class Detection:
    """Detector 출력 1개. 한 프레임 내 사람 1명."""
    bbox: BBox
    confidence: float
    class_id: int = 0  # 0 = person


@dataclass
class Track:
    """Tracker 출력 1개. 시간에 걸친 동일 인물."""
    track_id: int
    bbox: BBox
    confidence: float


@dataclass
class Signals:
    """v0.2.0 신규. 다중 신호 분석 결과.

    AI 의 gate_passage event 에 자격 일치 검증용 보조 신호를 첨부.
    백엔드가 fare_tap 매칭 후 misuse 판정 시 활용.
    """
    face_age_estimate: Optional[float] = None
    pose_senior_score: Optional[float] = None
    gait_senior_score: Optional[float] = None
    assistive_device_detected: Optional[bool] = None
    assistive_device_type: Optional[AssistiveDeviceType] = None  # v0.2.1 신규
    senior_probability: Optional[float] = None
    child_probability: Optional[float] = None
    estimated_age_group: Optional[AgeGroup] = None
    age_group_confidence: Optional[float] = None
    perceived_gender: Optional[Gender] = None
    gender_confidence: Optional[float] = None


@dataclass
class AfcMatch:
    """v0.2.0 신규. 백엔드 매칭 엔진이 채우는 fare_tap 매칭 결과.

    AI 는 발행 시 None 으로 둠. 백엔드가 ±1초 윈도로 매칭 후 업데이트.
    """
    fare_tap_id: str
    card_id_hash: str
    card_category: CardCategory
    tap_timestamp: str
    holder_gender: Gender = "unknown"
    time_delta_ms: Optional[int] = None


@dataclass
class Event:
    """백엔드 POST /api/v1/events 페이로드와 동일 (schema v0.2.2).

    v0.2.2: 우대 자격 일치 검증용 signals 확장(child/gender)과 afc_match.holder_gender 추가.
    """
    event_type: str            # gate_passage | jump | crawling | tailgating | unpaid | confirmed_unpaid | confirmed_misuse
    gate_section_id: str       # gate_01 등
    camera_id: str
    confidence: float
    track_id: int
    timestamp: str             # ISO-8601 UTC timezone-aware
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex}")
    source_event_id: Optional[str] = None  # v0.2.1 신규. 백엔드 confirmed_* 가 참조하는 원본 event_id
    clip_url: Optional[str] = None
    signals: Optional[Signals] = None
    reliability: Optional[Reliability] = None
    severity: Optional[Severity] = None
    afc_match: Optional[AfcMatch] = None
    raw_meta: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def to_payload(self) -> dict[str, Any]:
        """백엔드로 보낼 JSON 페이로드. None 은 빼고 보냄.

        중첩 dataclass (signals, afc_match) 도 내부 None 필드 제거.
        """
        d = asdict(self)
        d = {k: v for k, v in d.items() if v is not None}
        if "signals" in d and isinstance(d["signals"], dict):
            d["signals"] = {k: v for k, v in d["signals"].items() if v is not None}
            if not d["signals"]:
                del d["signals"]
        if "afc_match" in d and isinstance(d["afc_match"], dict):
            d["afc_match"] = {k: v for k, v in d["afc_match"].items() if v is not None}
        return d
