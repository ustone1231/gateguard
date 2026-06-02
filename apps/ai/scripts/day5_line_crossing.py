"""Day 5 — Line crossing 감지.

entry_line / exit_line을 가로지른 track을 콘솔 + 영상에 표시.

Usage:
    python scripts/day5_line_crossing.py path/to/test.mp4
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np
from src.detector import YoloDetector
from src.tracker import ByteTrackTracker
from src.zone import load_sections
from src.zone.geometry import foot_point, line_crossing_direction


def main(video_path: str) -> None:
    detector = YoloDetector(weights="yolo11n.pt")
    tracker = ByteTrackTracker()
    camera_id, sections = load_sections("config/gate_sections.json")
    detector.warmup()

    cap = cv2.VideoCapture(video_path)
    assert cap.isOpened()
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    out_path = Path("runs/day5_output.mp4")
    out_path.parent.mkdir(exist_ok=True)
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    prev_foot: dict[int, tuple[float, float]] = {}
    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        # 섹션 + 라인 그리기
        for sid, sec in sections.items():
            pts = sec.polygon.astype(np.int32).reshape(-1, 1, 2)
            cv2.polylines(frame, [pts], True, (0, 200, 200), 1)
            (x1, y1), (x2, y2) = sec.entry_line
            cv2.line(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            (x1, y1), (x2, y2) = sec.exit_line
            cv2.line(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)

        dets = detector.detect(frame)
        tracks = tracker.update(dets, frame_idx)
        for tr in tracks:
            x1, y1, x2, y2 = map(int, tr.bbox)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 2)
            foot = foot_point(tr.bbox)
            prev = prev_foot.get(tr.track_id)
            prev_foot[tr.track_id] = foot

            if prev is None:
                continue
            for sid, sec in sections.items():
                d_in = line_crossing_direction(prev, foot, sec.entry_line)
                d_out = line_crossing_direction(prev, foot, sec.exit_line)
                if d_in != 0:
                    print(f"frame {frame_idx}: track {tr.track_id} crossed ENTRY of {sid} dir={d_in:+d}")
                    cv2.putText(frame, f"ENTRY {sid}", (x1, y1 - 25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                if d_out != 0:
                    print(f"frame {frame_idx}: track {tr.track_id} crossed EXIT of {sid} dir={d_out:+d}")
                    cv2.putText(frame, f"EXIT {sid}", (x1, y1 - 45),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        writer.write(frame)
        frame_idx += 1

    cap.release()
    writer.release()
    print(f"done. {frame_idx} frames → {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/day5_line_crossing.py <video_path>")
        sys.exit(1)
    main(sys.argv[1])
