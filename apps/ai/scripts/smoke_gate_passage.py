"""Gate passage smoke test without a video/backend.

Synthetic TrackHistory를 만들어 GatePassageRule이 entry/exit crossing을
`gate_passage` 이벤트로 발행하고 JSONL 파일에 저장하는지 확인한다.

Usage:
    python scripts/smoke_gate_passage.py
    python scripts/smoke_gate_passage.py --output runs/gate_passage_smoke.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.publisher import FilePublisher
from src.rules import GatePassageRule, TrackHistory
from src.rules.base import TrackSnapshot


def main() -> None:
    args = parse_args()
    output = Path(args.output)
    if output.exists() and not args.append:
        output.unlink()

    publisher = FilePublisher(output)
    try:
        events = run_smoke(publisher)
    finally:
        publisher.close()

    print(f"wrote {len(events)} gate_passage events -> {output}")
    for event in events:
        print(json.dumps(event.to_payload(), ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="runs/gate_passage_smoke.jsonl",
        help="JSONL output path. Existing file is replaced unless --append is set.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to output instead of replacing it.",
    )
    return parser.parse_args()


def run_smoke(publisher: FilePublisher):
    rule = GatePassageRule(recent_window_frames=5)
    history = TrackHistory(track_id=7)
    events = []

    for snapshot in synthetic_crossing_snapshots():
        history.push(snapshot)
        while True:
            event = rule.evaluate(history, {}, {history.track_id: history}, "camera_001")
            if event is None:
                break
            publisher.publish(event)
            events.append(event)

    return events


def synthetic_crossing_snapshots() -> list[TrackSnapshot]:
    return [
        TrackSnapshot(
            frame_idx=0,
            timestamp_sec=0.0,
            bbox=(100, 100, 160, 260),
            confidence=0.91,
            section_id="gate_01",
        ),
        TrackSnapshot(
            frame_idx=12,
            timestamp_sec=0.4,
            bbox=(105, 130, 165, 290),
            confidence=0.92,
            section_id="gate_01",
            crossed_entry="gate_01",
            crossed_entry_direction=1,
        ),
        TrackSnapshot(
            frame_idx=30,
            timestamp_sec=1.0,
            bbox=(110, 170, 170, 330),
            confidence=0.9,
            section_id="gate_01",
        ),
        TrackSnapshot(
            frame_idx=45,
            timestamp_sec=1.5,
            bbox=(115, 210, 175, 370),
            confidence=0.89,
            section_id="gate_01",
            crossed_exit="gate_01",
            crossed_exit_direction=1,
        ),
    ]


if __name__ == "__main__":
    main()
