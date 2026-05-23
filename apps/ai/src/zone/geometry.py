"""기하학 유틸리티 — 룰/매칭 모듈이 공통 사용.

순수 함수만. 외부 상태 0.
"""
from __future__ import annotations

import cv2
import numpy as np

from ..types import BBox, Line, Point


def foot_point(bbox: BBox) -> Point:
    """사람의 발 위치 추정 = bbox 하단 중심.

    md의 'bbox 하단 중심 (카메라 각도 고려)' 명세.
    """
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, y2)


def point_in_polygon(point: Point, polygon: np.ndarray) -> bool:
    """OpenCV의 pointPolygonTest 사용. 내부 +, 경계 0, 외부 -."""
    return cv2.pointPolygonTest(polygon.astype(np.float32), point, False) >= 0


def segments_intersect(seg_a: Line, seg_b: Line) -> bool:
    """두 선분이 교차하는지. 외적 부호 변화 검사."""
    (x1, y1), (x2, y2) = seg_a
    (x3, y3), (x4, y4) = seg_b

    def cross(ox, oy, ax, ay, bx, by):
        return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)

    d1 = cross(x3, y3, x4, y4, x1, y1)
    d2 = cross(x3, y3, x4, y4, x2, y2)
    d3 = cross(x1, y1, x2, y2, x3, y3)
    d4 = cross(x1, y1, x2, y2, x4, y4)

    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    return False


def line_crossing_direction(prev: Point, curr: Point, line: Line) -> int:
    """이전→현재 이동이 선을 가로질렀다면 방향 부호 반환.

    return 0: 가로지르지 않음
    return +1: line의 '왼쪽→오른쪽' 통과
    return -1: line의 '오른쪽→왼쪽' 통과
    (왼/오 정의는 line의 시작→끝 벡터 기준)
    """
    if not segments_intersect((prev, curr), line):
        return 0
    (x1, y1), (x2, y2) = line
    # line 시작점 기준 prev의 부호
    sign_prev = (x2 - x1) * (prev[1] - y1) - (y2 - y1) * (prev[0] - x1)
    return 1 if sign_prev < 0 else -1
