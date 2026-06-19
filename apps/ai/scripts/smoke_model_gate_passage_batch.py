"""Run model gate passage smoke tests from a sample manifest.

Usage:
    python scripts/smoke_model_gate_passage_batch.py \
      config/model_gate_passage_samples.example.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.smoke_model_gate_passage import run_smoke


def main() -> None:
    args = parse_args()
    manifest = load_manifest(Path(args.manifest))
    results = []
    failures = []
    for sample in manifest.get("samples", []):
        smoke_args = sample_to_args(sample, args)
        result = run_smoke(smoke_args)
        result["name"] = sample["name"]
        result["passed"] = (
            result["summary"]["model_signal_gate_passage_count"]
            >= smoke_args.min_signal_events
        )
        results.append(result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        if not result["passed"]:
            failures.append(result)

    summary = summarize_batch(results)
    print("batch_summary:", json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if failures:
        names = ", ".join(result["name"] for result in failures)
        raise SystemExit(f"model gate passage smoke failed for: {names}")
    validate_batch_thresholds(summary, args.min_samples, args.min_passed_samples)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", help="JSON manifest with a top-level samples array")
    parser.add_argument("--config", default="config/pipeline.json")
    parser.add_argument("--output-dir", default="runs/model_gate_passage_samples")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--torch-dtype", default="float32")
    parser.add_argument("--min-samples", type=int, default=1)
    parser.add_argument("--min-passed-samples", type=int, default=1)
    return parser.parse_args()


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples:
        raise SystemExit("manifest must contain a non-empty `samples` array")
    for sample in samples:
        if not sample.get("name"):
            raise SystemExit("each sample requires `name`")
        if not sample.get("video"):
            raise SystemExit(f"sample {sample['name']} requires `video`")
        if not sample.get("sections"):
            raise SystemExit(f"sample {sample['name']} requires `sections`")
    return manifest


def sample_to_args(sample: dict[str, Any], defaults: argparse.Namespace) -> SimpleNamespace:
    output_dir = Path(defaults.output_dir)
    output = sample.get("output") or output_dir / f"{sample['name']}.jsonl"
    return SimpleNamespace(
        video=sample["video"],
        config=sample.get("config", defaults.config),
        sections=sample["sections"],
        output=str(output),
        append=False,
        start_sec=float(sample.get("start_sec", 0.0)),
        max_frames=int(sample.get("max_frames", 120)),
        min_signal_events=int(sample.get("min_signal_events", 1)),
        device=sample.get("device", defaults.device),
        torch_dtype=sample.get("torch_dtype", defaults.torch_dtype),
        hf_mivolo_model_id=sample.get("hf_mivolo_model_id"),
        hf_mivolo_revision=sample.get("hf_mivolo_revision"),
    )


def summarize_batch(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "sample_count": len(results),
        "passed_count": sum(1 for result in results if result.get("passed")),
        "gate_passage_count": sum(
            result["summary"]["gate_passage_count"] for result in results
        ),
        "model_signal_gate_passage_count": sum(
            result["summary"]["model_signal_gate_passage_count"] for result in results
        ),
        "high_confidence_gender_gate_passage_count": sum(
            result["summary"]["high_confidence_gender_gate_passage_count"]
            for result in results
        ),
    }


def validate_batch_thresholds(
    summary: dict[str, Any],
    min_samples: int,
    min_passed_samples: int,
) -> None:
    if summary["sample_count"] < min_samples:
        raise SystemExit(
            "not enough samples for model gate passage smoke: "
            f"required={min_samples}, actual={summary['sample_count']}"
        )
    if summary["passed_count"] < min_passed_samples:
        raise SystemExit(
            "not enough passing samples for model gate passage smoke: "
            f"required={min_passed_samples}, actual={summary['passed_count']}"
        )


if __name__ == "__main__":
    main()
