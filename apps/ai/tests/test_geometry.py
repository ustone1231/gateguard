"""src/zone/geometry.py 순수 함수 단위 테스트.

테스트 대상:
- foot_point: bbox → 발 위치 추정
- point_in_polygon: 점이 polygon 내부인가
- segments_intersect: 두 선분 교차 여부
- line_crossing_direction: 선 통과 방향 (+1, -1, 0)
"""
from __future__ import annotations

import numpy as np
import pytest

from src.zone.geometry import (
    foot_point,
    line_crossing_direction,
    point_in_polygon,
    segments_intersect,
)


# ───────── foot_point ─────────

def test_foot_point_is_bottom_center_of_bbox():
    # bbox (x1=10, y1=20, x2=30, y2=80) → 발 = (중심 x=20, 바닥 y=80)
    bbox = (10.0, 20.0, 30.0, 80.0)
    assert foot_point(bbox) == (20.0, 80.0)


def test_foot_point_handles_square_bbox():
    bbox = (0.0, 0.0, 100.0, 100.0)
    assert foot_point(bbox) == (50.0, 100.0)


# ───────── point_in_polygon ─────────

@pytest.fixture
def unit_square():
    """[(0,0), (10,0), (10,10), (0,10)] 사각형."""
    return np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float32)


def test_point_inside_polygon_returns_true(unit_square):
    assert point_in_polygon((5.0, 5.0), unit_square) is True


def test_point_outside_polygon_returns_false(unit_square):
    assert point_in_polygon((20.0, 20.0), unit_square) is False
    assert point_in_polygon((-1.0, 5.0), unit_square) is False


def test_point_on_polygon_boundary_returns_true(unit_square):
    # OpenCV pointPolygonTest 는 경계 위(0) 도 >= 0 이라 True
    assert point_in_polygon((0.0, 5.0), unit_square) is True


# ───────── segments_intersect ─────────

def test_crossing_segments_intersect():
    # X 자 교차
    assert segments_intersect(((0, 0), (10, 10)), ((0, 10), (10, 0))) is True


def test_parallel_segments_do_not_intersect():
    assert segments_intersect(((0, 0), (10, 0)), ((0, 5), (10, 5))) is False


def test_non_overlapping_segments_do_not_intersect():
    assert segments_intersect(((0, 0), (1, 1)), ((10, 10), (11, 11))) is False


def test_t_junction_does_not_count_as_intersection():
    # 한 선분의 끝점이 다른 선분 위에 닿기만 함 (T 자)
    # 현재 구현은 strict crossing (양쪽 부호가 명확히 다를 때) 만 True
    assert segments_intersect(((0, 0), (10, 0)), ((5, 0), (5, 10))) is False


# ───────── line_crossing_direction ─────────
#
# 부호의 절대 의미 (왼/오, entry/exit) 는 호출자가 정의함.
# 따라서 단위 테스트는 다음 invariant 만 검증:
#   1. 가로지르면 0 이 아님
#   2. 같은 방향 통과는 같은 부호
#   3. 반대 방향 통과는 부호 반대
#   4. 가로지르지 않으면 0

def test_crossing_returns_nonzero():
    line = ((5, 0), (5, 10))
    assert line_crossing_direction((0, 5), (10, 5), line) != 0


def test_opposite_crossings_have_opposite_signs():
    line = ((5, 0), (5, 10))
    forward = line_crossing_direction((0, 5), (10, 5), line)
    backward = line_crossing_direction((10, 5), (0, 5), line)
    assert forward != 0
    assert backward != 0
    assert forward == -backward


def test_same_direction_crossings_have_same_sign():
    line = ((5, 0), (5, 10))
    pass1 = line_crossing_direction((0, 5), (10, 5), line)
    pass2 = line_crossing_direction((1, 3), (9, 7), line)  # 다른 점, 같은 통과 방향
    assert pass1 == pass2


def test_no_crossing_returns_zero():
    line = ((5, 0), (5, 10))
    # 점이 line 한쪽에서만 움직임
    assert line_crossing_direction((0, 5), (3, 5), line) == 0


def test_movement_along_line_returns_zero():
    line = ((5, 0), (5, 10))
    # 점이 line 옆으로만 평행 이동
    assert line_crossing_direction((0, 5), (0, 8), line) == 0
