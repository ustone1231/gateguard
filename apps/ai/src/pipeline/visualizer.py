"""시각화 — 디버깅/시연용.

운영 시엔 안 써도 됨. visualizer=None으로 두면 OpenCV 호출 0.
"""
from __future__ import annotations

import cv2
import numpy as np

from ..types import Event, Track
from ..zone import GateSection


_COLORS = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
    (255, 0, 255), (0, 255, 255), (128, 0, 128), (255, 128, 0),
]


class Visualizer:
    def __init__(self, draw_sections: bool = True, draw_lines: bool = True):
        self._draw_sections = draw_sections
        self._draw_lines = draw_lines

    def draw(
        self,
        frame: np.ndarray,
        tracks: list[Track],
        sections: dict[str, GateSection],
        recent_events: list[tuple[int, Event]],
        frame_idx: int,
    ) -> np.ndarray:
        out = frame.copy()

        # 1. 섹션 polygon + 라인
        if self._draw_sections:
            for sid, section in sections.items():
                pts = section.polygon.astype(np.int32).reshape(-1, 1, 2)
                cv2.polylines(out, [pts], isClosed=True, color=(0, 200, 200), thickness=2)
                cx, cy = section.polygon.mean(axis=0).astype(int)
                cv2.putText(out, sid, (cx - 30, cy),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 200), 2)

        if self._draw_lines:
            for section in sections.values():
                (x1, y1), (x2, y2) = section.entry_line
                cv2.line(out, (int(x1), int(y1)), (int(x2), int(y2)),
                         (0, 255, 0), 2)
                (x1, y1), (x2, y2) = section.exit_line
                cv2.line(out, (int(x1), int(y1)), (int(x2), int(y2)),
                         (0, 0, 255), 2)

        # 2. 트랙 bbox + track_id
        for tr in tracks:
            x1, y1, x2, y2 = map(int, tr.bbox)
            color = _COLORS[tr.track_id % len(_COLORS)]
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            label = f"id:{tr.track_id} {tr.confidence:.2f}"
            cv2.putText(out, label, (x1, max(y1 - 8, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            # 발 위치 점
            foot_x = (x1 + x2) // 2
            cv2.circle(out, (foot_x, y2), 4, color, -1)

        # 3. 최근 이벤트 오버레이 (우측 상단)
        y_off = 30
        for fi, ev in recent_events[-5:]:
            age = frame_idx - fi
            alpha = max(0, 255 - age * 4)
            text = f"[{ev.event_type}] {ev.gate_section_id} t={ev.track_id} c={ev.confidence:.2f}"
            cv2.putText(out, text, (out.shape[1] - 460, y_off),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, alpha), 2)
            y_off += 24

        return out
