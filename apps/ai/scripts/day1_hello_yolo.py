"""Day 1 — YOLO Hello World.

영상 1개에 YOLO 돌려서 사람 bbox 그린 결과 영상 생성.

Usage:
    python scripts/day1_hello_yolo.py path/to/test.mp4
"""
from __future__ import annotations

import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (스크립트 직접 실행용)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
from src.detector import YoloDetector


def main(video_path: str) -> None:
    detector = YoloDetector(weights="yolo11n.pt", conf_threshold=0.4)
    detector.warmup()

    cap = cv2.VideoCapture(video_path)
    assert cap.isOpened(), f"open failed: {video_path}"
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    out_path = Path("runs/day1_output.mp4")
    out_path.parent.mkdir(exist_ok=True)
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        dets = detector.detect(frame)
        for d in dets:
            x1, y1, x2, y2 = map(int, d.bbox)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"person {d.confidence:.2f}",
                        (x1, max(y1 - 8, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        writer.write(frame)
        frame_idx += 1

    cap.release()
    writer.release()
    print(f"done. {frame_idx} frames → {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/day1_hello_yolo.py <video_path>")
        sys.exit(1)
    main(sys.argv[1])
