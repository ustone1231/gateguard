"""Smoke test model-backed signals on real gate passage events.

This script runs the normal config-based pipeline with `age_estimator` enabled,
then verifies that at least one emitted `gate_passage` event contains model
signals used by the backend misuse matcher.

Usage:
    python scripts/smoke_model_gate_passage.py \
      ../../videos/gateguard_test_video.mov \
      --sections config/gate_sections.local.json \
      --start-sec 11.5 \
      --max-frames 90
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline import build_from_config

REQUIRED_SIGNAL_FIELDS = (
    "face_age_estimate",
    "estimated_age_group",
    "perceived_gender",
    "gender_confidence",
)
HIGH_CONFIDENCE_GENDER_THRESHOLD = 0.80


def main() -> None:
    args = parse_args()
    result = run_smoke(args)
    print("stats:", json.dumps(result["stats"], ensure_ascii=False, sort_keys=True))
    print("summary:", json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))
    if result["summary"]["model_signal_gate_passage_count"] < args.min_signal_events:
        raise SystemExit(
            "model-backed gate_passage signals not found: "
            f"required={args.min_signal_events}, "
            f"actual={result['summary']['model_signal_gate_passage_count']}"
        )


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    video_path = Path(args.video)
    sections_path = Path(args.sections)
    if not video_path.exists():
        raise SystemExit(f"video not found: {video_path}")
    if not sections_path.exists():
        raise SystemExit(f"sections config not found: {sections_path}")

    output_path = Path(args.output)
    if output_path.exists() and not args.append:
        output_path.unlink()

    temp_config = write_smoke_config(args, output_path)
    pipeline = build_from_config(temp_config, sections_path)
    stats = pipeline.run(
        str(video_path),
        max_frames=args.max_frames,
        start_sec=args.start_sec,
        output_video=None,
    )
    events = read_jsonl(output_path)
    summary = validate_gate_passage_signals(events)
    return {"stats": stats, "summary": summary, "output": str(output_path)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", help="Video path to run through the pipeline")
    parser.add_argument("--config", default="config/pipeline.json")
    parser.add_argument("--sections", default="config/gate_sections.local.json")
    parser.add_argument("--output", default="runs/model_gate_passage_smoke.jsonl")
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--start-sec", type=float, default=0.0)
    parser.add_argument("--max-frames", type=int, default=120)
    parser.add_argument("--min-signal-events", type=int, default=1)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--torch-dtype", default="float32")
    parser.add_argument("--hf-mivolo-model-id", default=None)
    parser.add_argument("--hf-mivolo-revision", default=None)
    return parser.parse_args()


def write_smoke_config(args: argparse.Namespace, output_path: Path) -> Path:
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    age_cfg = cfg.setdefault("age_estimator", {})
    age_cfg["enabled"] = True
    age_cfg["type"] = "hf_mivolo_v2"
    age_cfg["device"] = args.device
    age_cfg["torch_dtype"] = args.torch_dtype
    if args.hf_mivolo_model_id:
        age_cfg["model_id"] = args.hf_mivolo_model_id
    if args.hf_mivolo_revision:
        age_cfg["revision"] = args.hf_mivolo_revision

    cfg.setdefault("pose_estimator", {})["enabled"] = False
    cfg.setdefault("pipeline", {})["save_annotated_video"] = False
    publisher_cfg = cfg.setdefault("publisher", {})
    publisher_cfg["type"] = "file"
    publisher_cfg["file_path"] = str(output_path)

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
        json.dump(cfg, tmp)
        return Path(tmp.name)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def validate_gate_passage_signals(events: list[dict[str, Any]]) -> dict[str, Any]:
    gate_passages = [event for event in events if event.get("event_type") == "gate_passage"]
    model_signal_events = []
    high_confidence_gender_events = []
    for event in gate_passages:
        signals = event.get("signals") or {}
        if all(signals.get(field) is not None for field in REQUIRED_SIGNAL_FIELDS):
            model_signal_events.append(event)
        gender = signals.get("perceived_gender")
        gender_confidence = signals.get("gender_confidence")
        if (
            gender in {"male", "female"}
            and isinstance(gender_confidence, (int, float))
            and gender_confidence >= HIGH_CONFIDENCE_GENDER_THRESHOLD
        ):
            high_confidence_gender_events.append(event)

    return {
        "event_count": len(events),
        "gate_passage_count": len(gate_passages),
        "model_signal_gate_passage_count": len(model_signal_events),
        "high_confidence_gender_gate_passage_count": len(high_confidence_gender_events),
        "high_confidence_gender_threshold": HIGH_CONFIDENCE_GENDER_THRESHOLD,
        "required_signal_fields": list(REQUIRED_SIGNAL_FIELDS),
    }


if __name__ == "__main__":
    main()
