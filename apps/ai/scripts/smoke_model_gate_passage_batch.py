"""Run model gate passage smoke tests from a sample manifest.

Usage:
    python scripts/smoke_model_gate_passage_batch.py \
      config/model_gate_passage_samples.example.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.smoke_model_gate_passage import run_smoke

SAMPLE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def main() -> None:
    args = parse_args()
    manifest = load_manifest(
        Path(args.manifest),
        min_samples=args.min_samples,
        min_passed_samples=args.min_passed_samples,
        check_paths=True,
    )
    if args.preflight_only:
        print(
            "preflight:",
            json.dumps(
                {"sample_count": len(manifest["samples"]), "passed": True},
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        return

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
    validate_batch_thresholds(
        summary,
        args.min_samples,
        args.min_passed_samples,
        max_line_jitter_candidates=args.max_line_jitter_candidates,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", help="JSON manifest with a top-level samples array")
    parser.add_argument("--config", default="config/pipeline.json")
    parser.add_argument("--output-dir", default="runs/model_gate_passage_samples")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--torch-dtype", default="float32")
    parser.add_argument("--min-samples", type=int, default=1)
    parser.add_argument("--min-passed-samples", type=int, default=1)
    parser.add_argument(
        "--max-line-jitter-candidates",
        type=int,
        default=0,
        help=(
            "Maximum allowed duplicate same-track/section/line gate_passage "
            "candidates across the batch."
        ),
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Validate the manifest and referenced files without loading models.",
    )
    return parser.parse_args()


def load_manifest(
    path: Path,
    min_samples: int = 1,
    min_passed_samples: int = 1,
    check_paths: bool = False,
) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples:
        raise SystemExit("manifest must contain a non-empty `samples` array")
    validate_manifest_samples(
        samples,
        min_samples=min_samples,
        min_passed_samples=min_passed_samples,
        check_paths=check_paths,
    )
    return manifest


def validate_manifest_samples(
    samples: list[dict[str, Any]],
    min_samples: int = 1,
    min_passed_samples: int = 1,
    check_paths: bool = False,
) -> None:
    if min_samples < 1:
        raise SystemExit("min_samples must be >= 1")
    if min_passed_samples < 1:
        raise SystemExit("min_passed_samples must be >= 1")
    if len(samples) < min_samples:
        raise SystemExit(
            "not enough samples for model gate passage smoke: "
            f"required={min_samples}, actual={len(samples)}"
        )
    if len(samples) < min_passed_samples:
        raise SystemExit(
            "not enough samples to satisfy passing threshold: "
            f"required={min_passed_samples}, actual={len(samples)}"
        )

    seen_names = set()
    seen_videos = set()
    for sample in samples:
        name = sample.get("name")
        if not name:
            raise SystemExit("each sample requires `name`")
        if not isinstance(name, str) or not SAMPLE_NAME_PATTERN.fullmatch(name):
            raise SystemExit(
                "sample name must use only letters, numbers, dots, underscores, "
                f"or hyphens: {name}"
            )
        if name in seen_names:
            raise SystemExit(f"duplicate sample name: {name}")
        seen_names.add(name)

        video = sample.get("video")
        sections = sample.get("sections")
        if not video:
            raise SystemExit(f"sample {name} requires `video`")
        if not sections:
            raise SystemExit(f"sample {name} requires `sections`")
        video_key = Path(video).expanduser()
        if check_paths:
            video_key = video_key.resolve()
        else:
            video_key = Path(str(video_key))
        if video_key in seen_videos:
            raise SystemExit(f"duplicate sample video: {video}")
        seen_videos.add(video_key)

        if _float_field(sample, "start_sec", 0.0) < 0:
            raise SystemExit(f"sample {name} requires start_sec >= 0")
        if _int_field(sample, "max_frames", 120) < 1:
            raise SystemExit(f"sample {name} requires max_frames >= 1")
        if _int_field(sample, "min_signal_events", 1) < 1:
            raise SystemExit(f"sample {name} requires min_signal_events >= 1")

        if check_paths:
            if not Path(video).exists():
                raise SystemExit(f"sample {name} video not found: {video}")
            if not Path(sections).exists():
                raise SystemExit(f"sample {name} sections config not found: {sections}")
            config = sample.get("config")
            if config and not Path(config).exists():
                raise SystemExit(f"sample {name} pipeline config not found: {config}")


def _float_field(sample: dict[str, Any], field: str, default: float) -> float:
    try:
        return float(sample.get(field, default))
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"sample {sample['name']} requires numeric {field}") from exc


def _int_field(sample: dict[str, Any], field: str, default: int) -> int:
    try:
        return int(sample.get(field, default))
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"sample {sample['name']} requires integer {field}") from exc


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
        "line_jitter_candidate_gate_passage_count": sum(
            result["summary"]["line_jitter_candidate_gate_passage_count"]
            for result in results
        ),
    }


def validate_batch_thresholds(
    summary: dict[str, Any],
    min_samples: int,
    min_passed_samples: int,
    max_line_jitter_candidates: int = 0,
) -> None:
    if max_line_jitter_candidates < 0:
        raise SystemExit("max_line_jitter_candidates must be >= 0")
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
    line_jitter_candidates = summary["line_jitter_candidate_gate_passage_count"]
    if line_jitter_candidates > max_line_jitter_candidates:
        raise SystemExit(
            "too many line jitter gate_passage candidates: "
            f"allowed={max_line_jitter_candidates}, actual={line_jitter_candidates}"
        )


if __name__ == "__main__":
    main()
