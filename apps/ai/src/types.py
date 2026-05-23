"""공통 데이터 타입.

md 문서의 이벤트 페이로드 스키마와 1:1 매칭.
백엔드 POST /api/events 요청 본문이 Event 인스턴스를 그대로 직렬화한 형태.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


BBox = tuple[float, float, float, float]  # (x1, y1, x2, y2)
Point = tuple[float, float]
Line = tuple[Point, Point]


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
class Event:
    """백엔드 POST /api/events 페이로드와 동일.

    md 명세 필드:
      event_type, gate_section_id, camera_id, confidence,
      clip_url, track_id, timestamp, raw_meta
    """
    event_type: str            # jump | crawling | tailgating | unpaid
    gate_section_id: str       # gate_01 등
    camera_id: str
    confidence: float
    track_id: int
    timestamp: str             # ISO8601
    clip_url: Optional[str] = None
    raw_meta: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def to_payload(self) -> dict[str, Any]:
        """백엔드로 보낼 JSON 페이로드. None은 빼고 보냄."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}
