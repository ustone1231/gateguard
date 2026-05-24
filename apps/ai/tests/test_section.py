"""src/zone/section.py — GateSection 데이터 모델 + JSON 로더 테스트."""
from __future__ import annotations

import json

import numpy as np
import pytest

from src.zone.section import GateSection, load_sections


# ───────── GateSection.from_dict ─────────

@pytest.fixture
def valid_section_dict():
    return {
        "id": "gate_01",
        "section_no": 1,
        "name": "1번 개찰구",
        "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]],
        "entry_line": [[0, 5], [10, 5]],
        "exit_line": [[0, 8], [10, 8]],
        "active": True,
    }


def test_from_dict_populates_basic_fields(valid_section_dict):
    sec = GateSection.from_dict(valid_section_dict, camera_id="cam_01")
    assert sec.id == "gate_01"
    assert sec.section_no == 1
    assert sec.name == "1번 개찰구"
    assert sec.camera_id == "cam_01"
    assert sec.active is True


def test_from_dict_polygon_is_float32_ndarray(valid_section_dict):
    """rules 모듈이 polygon 의 dtype 에 의존하므로 회귀 방지용."""
    sec = GateSection.from_dict(valid_section_dict)
    assert isinstance(sec.polygon, np.ndarray)
    assert sec.polygon.dtype == np.float32
    assert sec.polygon.shape == (4, 2)


def test_from_dict_lines_are_tuples_of_tuples(valid_section_dict):
    sec = GateSection.from_dict(valid_section_dict)
    assert sec.entry_line == ((0, 5), (10, 5))
    assert sec.exit_line == ((0, 8), (10, 8))


def test_from_dict_defaults_name_to_id_when_missing(valid_section_dict):
    valid_section_dict.pop("name")
    sec = GateSection.from_dict(valid_section_dict)
    assert sec.name == "gate_01"


def test_from_dict_defaults_active_to_true_when_missing(valid_section_dict):
    valid_section_dict.pop("active")
    sec = GateSection.from_dict(valid_section_dict)
    assert sec.active is True


# ───────── load_sections ─────────

def test_load_sections_returns_camera_id_and_section_map(tmp_path):
    config = {
        "camera_id": "cam_007",
        "sections": [
            {
                "id": "gate_01", "section_no": 1, "name": "g1",
                "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]],
                "entry_line": [[0, 5], [10, 5]],
                "exit_line": [[0, 8], [10, 8]],
                "active": True,
            },
            {
                "id": "gate_02", "section_no": 2, "name": "g2",
                "polygon": [[20, 0], [30, 0], [30, 10], [20, 10]],
                "entry_line": [[20, 5], [30, 5]],
                "exit_line": [[20, 8], [30, 8]],
                "active": True,
            },
        ],
    }
    path = tmp_path / "gate_sections.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    camera_id, sections = load_sections(path)
    assert camera_id == "cam_007"
    assert set(sections.keys()) == {"gate_01", "gate_02"}
    assert sections["gate_01"].camera_id == "cam_007"


def test_load_sections_excludes_inactive_sections(tmp_path):
    config = {
        "camera_id": "cam_001",
        "sections": [
            {
                "id": "gate_01", "section_no": 1, "name": "g1",
                "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]],
                "entry_line": [[0, 5], [10, 5]],
                "exit_line": [[0, 8], [10, 8]],
                "active": True,
            },
            {
                "id": "gate_dead", "section_no": 99, "name": "비활성",
                "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]],
                "entry_line": [[0, 0], [1, 0]],
                "exit_line": [[0, 1], [1, 1]],
                "active": False,
            },
        ],
    }
    path = tmp_path / "gate_sections.json"
    path.write_text(json.dumps(config), encoding="utf-8")

    _, sections = load_sections(path)
    assert "gate_01" in sections
    assert "gate_dead" not in sections
