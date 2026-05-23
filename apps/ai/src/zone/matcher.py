"""SectionMatcher — track_id의 발 위치 → 어느 gate_section에 있는가."""
from __future__ import annotations

from typing import Optional

from .section import GateSection
from .geometry import foot_point, point_in_polygon
from ..types import Track


class SectionMatcher:
    def __init__(self, sections: dict[str, GateSection]):
        self._sections = sections

    def match(self, track: Track) -> Optional[str]:
        """track의 발 위치가 어느 section에 있는가. 없으면 None."""
        foot = foot_point(track.bbox)
        for sid, section in self._sections.items():
            if point_in_polygon(foot, section.polygon):
                return sid
        return None

    @property
    def sections(self) -> dict[str, GateSection]:
        return self._sections
