"""Day 2 — Detector + Tracker.

YOLO로 사람 잡고 ByteTrack으로 track_id 부여. 같은 사람에게 같은 ID가 유지됨.

Usage:
    python scripts/day2_tracking.py path/to/test.mp4
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
from src.detector import YoloDetector
from src.tracker import ByteTrackTracker


_COLORS = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
    (255, 0, 255), (0, 255, 255), (128, 0, 128), (255, 128, 0),
]


def main(video_path: str) -> None:
    detector = YoloDetector(weights="yolo11n.pt")
    tracker = ByteTrackTracker()
    detector.warmup()
    tracker.reset()

    cap = cv2.VideoCapture(video_path)
    assert cap.isOpened(), f"open failed: {video_path}"
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    out_path = Path("runs/day2_output.mp4")
    out_path.parent.mkdir(exist_ok=True)
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        dets = detector.detect(frame)
        tracks = tracker.update(dets, frame_idx)
        for tr in tracks:
            x1, y1, x2, y2 = map(int, tr.bbox)
            color = _COLORS[tr.track_id % len(_COLORS)]
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"id:{tr.track_id}",
                        (x1, max(y1 - 8, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        writer.write(frame)
        frame_idx += 1

    cap.release()
    writer.release()
    print(f"done. {frame_idx} frames → {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/day2_tracking.py <video_path>")
        sys.exit(1)
    main(sys.argv[1])
