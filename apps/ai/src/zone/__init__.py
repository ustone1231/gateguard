from .section import GateSection, load_sections
from .geometry import (
    foot_point,
    point_in_polygon,
    segments_intersect,
    line_crossing_direction,
)
from .matcher import SectionMatcher

__all__ = [
    "GateSection", "load_sections",
    "foot_point", "point_in_polygon",
    "segments_intersect", "line_crossing_direction",
    "SectionMatcher",
]
