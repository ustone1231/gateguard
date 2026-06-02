"""GateSection — md의 gate_sections DB 테이블과 1:1 매칭.

스키마:
    id, section_no, name, polygon, entry_line, exit_line, active
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..types import Line


@dataclass
class GateSection:
    id: str
    section_no: int
    name: str
    polygon: np.ndarray             # shape (N, 2), float32
    entry_line: Line
    exit_line: Line
    active: bool = True
    camera_id: str = ""

    @classmethod
    def from_dict(cls, d: dict, camera_id: str = "") -> "GateSection":
        return cls(
            id=d["id"],
            section_no=int(d["section_no"]),
            name=d.get("name", d["id"]),
            polygon=np.array(d["polygon"], dtype=np.float32),
            entry_line=(tuple(d["entry_line"][0]), tuple(d["entry_line"][1])),
            exit_line=(tuple(d["exit_line"][0]), tuple(d["exit_line"][1])),
            active=d.get("active", True),
            camera_id=camera_id,
        )


def load_sections(config_path: str | Path) -> tuple[str, dict[str, GateSection]]:
    """config/gate_sections.json → (camera_id, {section_id: GateSection}).

    파일 형식은 Zone Editor가 백엔드에 POST할 형식과 동일.
    """
    data = json.loads(Path(config_path).read_text(encoding="utf-8"))
    camera_id = data["camera_id"]
    sections = {
        s["id"]: GateSection.from_dict(s, camera_id=camera_id)
        for s in data["sections"]
        if s.get("active", True)
    }
    return camera_id, sections
