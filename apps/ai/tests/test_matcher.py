"""src/zone/matcher.py — SectionMatcher 단위 테스트."""
from __future__ import annotations

import numpy as np
import pytest

from src.types import Track
from src.zone.matcher import SectionMatcher
from src.zone.section import GateSection


def _make_section(sid: str, polygon: list[list[float]]) -> GateSection:
    """테스트용 GateSection 빠른 생성."""
    return GateSection(
        id=sid,
        section_no=1,
        name=sid,
        polygon=np.array(polygon, dtype=np.float32),
        entry_line=((0, 0), (1, 0)),
        exit_line=((0, 1), (1, 1)),
        active=True,
    )


def _make_track(track_id: int, bbox: tuple[float, float, float, float]) -> Track:
    return Track(track_id=track_id, bbox=bbox, confidence=0.9)


@pytest.fixture
def two_section_matcher():
    """가로로 나란히 있는 두 게이트."""
    sections = {
        "gate_01": _make_section("gate_01", [[0, 0], [10, 0], [10, 10], [0, 10]]),
        "gate_02": _make_section("gate_02", [[20, 0], [30, 0], [30, 10], [20, 10]]),
    }
    return SectionMatcher(sections)


def test_match_returns_section_id_when_foot_inside(two_section_matcher):
    # bbox 발 위치 = (5, 5) → gate_01 안
    track = _make_track(track_id=1, bbox=(4, 0, 6, 5))
    assert two_section_matcher.match(track) == "gate_01"


def test_match_returns_correct_section_when_track_in_second_polygon(two_section_matcher):
    # bbox 발 위치 = (25, 5) → gate_02 안
    track = _make_track(track_id=2, bbox=(24, 0, 26, 5))
    assert two_section_matcher.match(track) == "gate_02"


def test_match_returns_none_when_foot_outside_all_sections(two_section_matcher):
    # bbox 발 위치 = (15, 5) → 두 게이트 사이의 빈 공간
    track = _make_track(track_id=3, bbox=(14, 0, 16, 5))
    assert two_section_matcher.match(track) is None


def test_match_returns_none_for_far_away_track(two_section_matcher):
    # 영상 밖
    track = _make_track(track_id=4, bbox=(1000, 1000, 1010, 1100))
    assert two_section_matcher.match(track) is None


def test_match_uses_foot_not_bbox_center():
    """발 위치(=bbox 하단 중심)로 판정함을 명시.

    bbox 중심은 polygon 밖이지만 발은 안인 케이스로 검증.
    """
    # polygon 은 y=8~12 사이 가로 띠
    matcher = SectionMatcher(
        {"gate_01": _make_section("gate_01", [[0, 8], [20, 8], [20, 12], [0, 12]])}
    )
    # bbox: y=0~10. 중심은 y=5 (polygon 밖), 발은 y=10 (polygon 안)
    track = _make_track(track_id=1, bbox=(8, 0, 12, 10))
    assert matcher.match(track) == "gate_01"


def test_sections_property_returns_underlying_dict(two_section_matcher):
    assert set(two_section_matcher.sections.keys()) == {"gate_01", "gate_02"}
