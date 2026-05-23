"""Day 8-9 — 4종 룰 모두 활성화.

Usage:
    python scripts/day8_all_rules.py path/to/test.mp4
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.detector import YoloDetector
from src.tracker import ByteTrackTracker
from src.publisher import FilePublisher
from src.rules import (
    RuleEngine, JumpRule, CrawlingRule, TailgatingRule, UnpaidRule,
)
from src.zone import SectionMatcher, load_sections
from src.pipeline import Pipeline, Visualizer


def main(video_path: str) -> None:
    camera_id, sections = load_sections("config/gate_sections.json")
    pipeline = Pipeline(
        detector=YoloDetector(weights="yolo11n.pt"),
        tracker=ByteTrackTracker(),
        matcher=SectionMatcher(sections),
        rule_engine=RuleEngine(
            rules=[JumpRule(), CrawlingRule(), TailgatingRule(), UnpaidRule()],
            cooldown_seconds={
                "jump": 3.0,
                "crawling": 3.0,
                "tailgating": 3.0,
                "unpaid": 5.0,
            },
        ),
        publisher=FilePublisher("runs/events_day8.jsonl"),
        camera_id=camera_id,
        visualizer=Visualizer(),
    )
    stats = pipeline.run(
        source=video_path,
        output_video="runs/day8_output.mp4",
    )
    print("stats:", stats)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/day8_all_rules.py <video_path>")
        sys.exit(1)
    main(sys.argv[1])
