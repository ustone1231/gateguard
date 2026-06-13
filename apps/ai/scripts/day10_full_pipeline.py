"""Day 10 — config 기반 전체 파이프라인.

config/pipeline.json의 publisher.type을 "file" → "http"로 바꾸면
백엔드 POST /api/events 로 연동됨. 코드 변경 0.

Usage:
    python scripts/day10_full_pipeline.py path/to/test.mp4
    python scripts/day10_full_pipeline.py path/to/test.mp4 --sections config/gate_sections.local.json
    python scripts/day10_full_pipeline.py path/to/test.mp4 --start-sec 12
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline import build_from_config


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    pipeline = build_from_config(
        pipeline_config_path=args.config,
        sections_config_path=args.sections,
    )
    stats = pipeline.run(
        source=args.video,
        output_video=args.output,
        start_sec=args.start_sec,
    )
    print("stats:", stats)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", help="Video path")
    parser.add_argument("--config", default="config/pipeline.json")
    parser.add_argument("--sections", default="config/gate_sections.json")
    parser.add_argument("--output", default="runs/day10_output.mp4")
    parser.add_argument("--start-sec", type=float, default=0.0)
    return parser.parse_args()


if __name__ == "__main__":
    main()
