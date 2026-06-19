#!/usr/bin/env bash
set -euo pipefail

MODEL_DIR="${MODEL_DIR:-models}"
POSE_WEIGHTS="${POSE_WEIGHTS:-yolo11n-pose.pt}"
FACE_PERSON_WEIGHTS="${FACE_PERSON_WEIGHTS:-yolov8x_person_face.pt}"
PYTHON_BIN="${PYTHON:-python3}"

mkdir -p "$MODEL_DIR"

echo "[models] directory: $MODEL_DIR"

"$PYTHON_BIN" - <<'PY'
import os
from pathlib import Path

model_dir = Path(os.environ.get("MODEL_DIR", "models"))
pose_weights = os.environ.get("POSE_WEIGHTS", "yolo11n-pose.pt")
target = model_dir / pose_weights

if target.exists():
    print(f"[pose] already exists: {target}")
else:
    print(f"[pose] downloading via ultralytics: {pose_weights}")
    from ultralytics import YOLO

    # Ultralytics downloads known model names on first use.
    model = YOLO(pose_weights)
    downloaded = Path(pose_weights)
    if downloaded.exists() and downloaded.resolve() != target.resolve():
        downloaded.replace(target)
    elif not target.exists():
        # Some versions keep the resolved path inside model.ckpt_path.
        ckpt_path = Path(getattr(model, "ckpt_path", pose_weights))
        if ckpt_path.exists():
            ckpt_path.replace(target)
    if not target.exists():
        raise SystemExit(f"[pose] failed to materialize {target}")
    print(f"[pose] ready: {target}")
PY

"$PYTHON_BIN" - <<'PY'
import os
from pathlib import Path

from huggingface_hub import hf_hub_download

model_dir = Path(os.environ.get("MODEL_DIR", "models"))
target_name = os.environ.get("FACE_PERSON_WEIGHTS", "yolov8x_person_face.pt")
target = model_dir / target_name

if target.exists():
    print(f"[mivolo-detector] already exists: {target}")
else:
    print("[mivolo-detector] downloading from iitolstykh/YOLO-Face-Person-Detector")
    path = Path(hf_hub_download(
        repo_id="iitolstykh/YOLO-Face-Person-Detector",
        filename=target_name,
        local_dir=str(model_dir),
        local_dir_use_symlinks=False,
    ))
    if path.resolve() != target.resolve():
        path.replace(target)
    print(f"[mivolo-detector] ready: {target}")
PY

cat <<'EOF'
[hf-mivolo-v2] HuggingFace MiVOLO v2 is cached by the setup check:
           python scripts/check_model_setup.py --hf-mivolo-v2
         It still requires the optional mivolo runtime package; see README.

[mivolo] original age/gender checkpoint is not auto-downloaded by this script.
         The original MiVOLO package expects a .pth.tar checkpoint such as
         models/mivolo_imbd.pth.tar from the upstream README's checkpoint link.
         After placing it there, run:
           python scripts/check_model_setup.py --mivolo
EOF
