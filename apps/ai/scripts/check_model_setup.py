"""Check optional model-backed AI components.

This script is intentionally explicit: missing model files fail the relevant
check instead of falling back to heuristic signals.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.age_estimator import (
    HfMivoloV2AgeGenderEstimator,
    HfMivoloV2Config,
    MivoloAgeGenderEstimator,
    MivoloConfig,
)
from src.pose_estimator import UltralyticsPoseEstimator


def main() -> None:
    args = parse_args()
    if args.pose:
        pose = UltralyticsPoseEstimator(weights=args.pose_weights, device=args.device)
        pose.warmup()
        print(f"pose OK: {pose.model_version}")

    if args.mivolo:
        estimator = MivoloAgeGenderEstimator(
            MivoloConfig(
                detector_weights=args.mivolo_detector_weights,
                checkpoint=args.mivolo_checkpoint,
                device=args.device,
            )
        )
        estimator.warmup()
        print(f"mivolo OK: {estimator.model_version}")

    if args.hf_mivolo_v2:
        estimator = HfMivoloV2AgeGenderEstimator(
            HfMivoloV2Config(
                model_id=args.hf_mivolo_model_id,
                device=args.device,
                torch_dtype=args.torch_dtype,
                revision=args.hf_mivolo_revision,
            )
        )
        estimator.warmup()
        print(f"hf_mivolo_v2 OK: {estimator.model_version}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--pose", action="store_true")
    parser.add_argument("--pose-weights", default="models/yolo11n-pose.pt")
    parser.add_argument("--mivolo", action="store_true")
    parser.add_argument("--mivolo-detector-weights", default="models/yolov8x_person_face.pt")
    parser.add_argument("--mivolo-checkpoint", default="models/mivolo_imbd.pth.tar")
    parser.add_argument("--hf-mivolo-v2", action="store_true")
    parser.add_argument("--hf-mivolo-model-id", default="iitolstykh/mivolo_v2")
    parser.add_argument("--hf-mivolo-revision", default=None)
    parser.add_argument("--torch-dtype", default="float32")
    return parser.parse_args()


if __name__ == "__main__":
    main()
