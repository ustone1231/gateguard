"""Day 3-4 — Section + point-in-polygon.

config/gate_sections.json의 polygon을 그리고, track의 발 위치가 어느
section에 있는지 콘솔 + 영상에 표시.

Usage:
    python scripts/day3_sections.py path/to/test.mp4
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np
from src.detector import YoloDetector
from src.tracker import ByteTrackTracker
from src.zone import SectionMatcher, load_sections
from src.zone.geometry import foot_point


def main(video_path: str) -> None:
    detector = YoloDetector(weights="yolo11n.pt")
    tracker = ByteTrackTracker()
    camera_id, sections = load_sections("config/gate_sections.json")
    matcher = SectionMatcher(sections)
    detector.warmup()

    cap = cv2.VideoCapture(video_path)
    assert cap.isOpened()
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    out_path = Path("runs/day3_output.mp4")
    out_path.parent.mkdir(exist_ok=True)
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    frame_idx = 0
    last_print: dict[int, str] = {}
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        # 섹션 그리기
        for sid, sec in sections.items():
            pts = sec.polygon.astype(np.int32).reshape(-1, 1, 2)
            cv2.polylines(frame, [pts], True, (0, 200, 200), 2)
            cx, cy = sec.polygon.mean(axis=0).astype(int)
            cv2.putText(frame, sid, (cx - 30, cy),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 200), 2)

        dets = detector.detect(frame)
        tracks = tracker.update(dets, frame_idx)
        for tr in tracks:
            sid = matcher.match(tr)
            x1, y1, x2, y2 = map(int, tr.bbox)
            color = (0, 255, 0) if sid else (200, 200, 200)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            foot = foot_point(tr.bbox)
            cv2.circle(frame, (int(foot[0]), int(foot[1])), 5, color, -1)
            label = f"id:{tr.track_id} {sid or '-'}"
            cv2.putText(frame, label, (x1, max(y1 - 8, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            # 콘솔: 섹션 진입/이탈 시점만 출력
            cur = sid or "-"
            if last_print.get(tr.track_id) != cur:
                print(f"frame {frame_idx}: track {tr.track_id} → {cur}")
                last_print[tr.track_id] = cur

        writer.write(frame)
        frame_idx += 1

    cap.release()
    writer.release()
    print(f"done. {frame_idx} frames → {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/day3_sections.py <video_path>")
        sys.exit(1)
    main(sys.argv[1])
