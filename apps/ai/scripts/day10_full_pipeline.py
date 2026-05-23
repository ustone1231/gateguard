"""Day 10 — config 기반 전체 파이프라인.

config/pipeline.json의 publisher.type을 "file" → "http"로 바꾸면
백엔드 POST /api/events 로 연동됨. 코드 변경 0.

Usage:
    python scripts/day10_full_pipeline.py path/to/test.mp4
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline import build_from_config


def main(video_path: str) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    pipeline = build_from_config(
        pipeline_config_path="config/pipeline.json",
        sections_config_path="config/gate_sections.json",
    )
    stats = pipeline.run(
        source=video_path,
        output_video="runs/day10_output.mp4",
    )
    print("stats:", stats)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/day10_full_pipeline.py <video_path>")
        sys.exit(1)
    main(sys.argv[1])
