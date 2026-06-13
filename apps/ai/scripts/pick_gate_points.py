"""Pick gate section coordinates from the first video frame.

Controls:
    left click  add point
    u           undo last point in current stage
    c           clear current stage
    n / enter / space
                finish current stage
    q / esc     quit

Stages:
    1. polygon: click 3+ points around the gate area
    2. entry_line: click 2 points
    3. exit_line: click 2 points

Usage:
    python scripts/pick_gate_points.py path/to/video.mov
    python scripts/pick_gate_points.py path/to/video.mov --output config/gate_sections.local.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2


STAGES = ("polygon", "entry_line", "exit_line")


def main() -> None:
    args = parse_args()
    frame = read_first_frame(args.video)
    height, width = frame.shape[:2]
    display, scale = resize_for_display(frame, args.max_width, args.max_height)

    picker = PointPicker(display, scale)
    result = picker.run()
    if result is None:
        print("cancelled")
        return

    payload = {
        "camera_id": args.camera_id,
        "frame_size": {"width": width, "height": height},
        "sections": [
            {
                "id": args.section_id,
                "section_no": args.section_no,
                "name": args.name or args.section_id,
                "polygon": result["polygon"],
                "entry_line": result["entry_line"],
                "exit_line": result["exit_line"],
                "active": True,
            }
        ],
    }

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", help="Video path")
    parser.add_argument("--camera-id", default="camera_001")
    parser.add_argument("--section-id", default="gate_01")
    parser.add_argument("--section-no", type=int, default=1)
    parser.add_argument("--name", default=None)
    parser.add_argument("--output", default=None, help="Optional JSON output path")
    parser.add_argument("--max-width", type=int, default=1400)
    parser.add_argument("--max-height", type=int, default=900)
    return parser.parse_args()


def read_first_frame(video_path: str):
    cap = cv2.VideoCapture(video_path)
    try:
        if not cap.isOpened():
            raise RuntimeError(f"open failed: {video_path}")
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError(f"first frame read failed: {video_path}")
        return frame
    finally:
        cap.release()


def resize_for_display(frame, max_width: int, max_height: int):
    height, width = frame.shape[:2]
    scale = min(max_width / width, max_height / height, 1.0)
    if scale == 1.0:
        return frame.copy(), scale
    display = cv2.resize(
        frame,
        (int(width * scale), int(height * scale)),
        interpolation=cv2.INTER_AREA,
    )
    return display, scale


class PointPicker:
    def __init__(self, image, scale: float):
        self._base = image
        self._scale = scale
        self._stage_index = 0
        self._points: dict[str, list[list[int]]] = {stage: [] for stage in STAGES}
        self._window = "pick_gate_points"

    def run(self) -> dict[str, list[list[int]]] | None:
        cv2.namedWindow(self._window, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(self._window, self._on_mouse)
        print("click the image window before pressing keys.")
        print(f"stage: {self._current_stage()}")

        while True:
            cv2.imshow(self._window, self._draw())
            key = cv2.waitKey(20) & 0xFF
            if key in (27, ord("q")):
                cv2.destroyWindow(self._window)
                return None
            if key in (10, 13, 32, ord("n")):
                if self._advance_stage():
                    cv2.destroyWindow(self._window)
                    return self._points
            elif key == ord("u"):
                current = self._current_stage()
                if self._points[current]:
                    removed = self._points[current].pop()
                    print(f"{current}: removed {removed} ({len(self._points[current])} points)")
            elif key == ord("c"):
                self._points[self._current_stage()].clear()
                print(f"{self._current_stage()}: cleared")

    def _on_mouse(self, event, x, y, flags, param) -> None:
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        original_x = int(round(x / self._scale))
        original_y = int(round(y / self._scale))
        stage = self._current_stage()
        point = [original_x, original_y]
        self._points[stage].append(point)
        print(f"{stage}: added {point} ({len(self._points[stage])} points)")

    def _advance_stage(self) -> bool:
        stage = self._current_stage()
        count = len(self._points[stage])
        if stage == "polygon" and count < 3:
            print("polygon needs at least 3 points")
            return False
        if stage in {"entry_line", "exit_line"} and count != 2:
            print(f"{stage} needs exactly 2 points")
            return False

        self._stage_index += 1
        if self._stage_index >= len(STAGES):
            return True
        print(f"next stage: {self._current_stage()}")
        return False

    def _current_stage(self) -> str:
        return STAGES[self._stage_index]

    def _draw(self):
        image = self._base.copy()
        colors = {
            "polygon": (0, 220, 220),
            "entry_line": (0, 255, 0),
            "exit_line": (0, 0, 255),
        }

        for stage, points in self._points.items():
            scaled = [self._scale_point(point) for point in points]
            color = colors[stage]
            for point in scaled:
                cv2.circle(image, point, 5, color, -1)
            if stage == "polygon" and len(scaled) >= 2:
                for start, end in zip(scaled, scaled[1:]):
                    cv2.line(image, start, end, color, 2)
                if stage != self._current_stage() and len(scaled) >= 3:
                    cv2.line(image, scaled[-1], scaled[0], color, 2)
            elif stage in {"entry_line", "exit_line"} and len(scaled) == 2:
                cv2.line(image, scaled[0], scaled[1], color, 3)

        stage = self._current_stage()
        help_text = f"{stage}: click points | n/enter/space next | u undo | c clear | q quit"
        cv2.rectangle(image, (0, 0), (image.shape[1], 38), (0, 0, 0), -1)
        cv2.putText(
            image,
            help_text,
            (12, 26),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        return image

    def _scale_point(self, point: list[int]) -> tuple[int, int]:
        return (int(round(point[0] * self._scale)), int(round(point[1] * self._scale)))


if __name__ == "__main__":
    main()
