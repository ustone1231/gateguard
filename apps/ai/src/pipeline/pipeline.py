"""메인 파이프라인.

흐름:
    프레임 → Detector → Tracker → SectionMatcher → (line crossing) →
    TrackHistory 업데이트 → RuleEngine → Publisher
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import cv2

from ..detector import Detector
from ..tracker import Tracker
from ..publisher import EventPublisher
from ..rules import RuleEngine, TrackHistory
from ..rules.base import TrackSnapshot
from ..zone import GateSection, SectionMatcher
from ..zone.geometry import foot_point, line_crossing_direction
from .visualizer import Visualizer

log = logging.getLogger(__name__)


class Pipeline:
    def __init__(
        self,
        detector: Detector,
        tracker: Tracker,
        matcher: SectionMatcher,
        rule_engine: RuleEngine,
        publisher: EventPublisher,
        camera_id: str,
        visualizer: Optional[Visualizer] = None,
    ):
        self._detector = detector
        self._tracker = tracker
        self._matcher = matcher
        self._engine = rule_engine
        self._publisher = publisher
        self._camera_id = camera_id
        self._visualizer = visualizer
        # track_id -> TrackHistory
        self._histories: dict[int, TrackHistory] = {}
        # track_id -> 직전 발 위치 (line crossing 판정용)
        self._prev_foot: dict[int, tuple[float, float]] = {}

    @property
    def sections(self) -> dict[str, GateSection]:
        return self._matcher.sections

    def run(
        self,
        source: str | int,
        output_video: Optional[str | Path] = None,
        max_frames: Optional[int] = None,
        show_window: bool = False,
    ) -> dict:
        """영상 입력 → 추론 → 이벤트 발행.

        Args:
            source: mp4 경로(str) 또는 웹캠 인덱스(int) 또는 RTSP URL(str)
            output_video: 시각화 영상 저장 경로
            max_frames: 디버깅용. None이면 끝까지
            show_window: 로컬 미리보기 창 띄울지

        Returns:
            요약 통계 dict
        """
        self._detector.warmup()
        self._tracker.reset()

        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            raise RuntimeError(f"영상 열기 실패: {source}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        writer = None
        if output_video:
            output_video = Path(output_video)
            output_video.parent.mkdir(parents=True, exist_ok=True)
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(output_video), fourcc, fps, (width, height))

        events_total = 0
        events_by_type: dict[str, int] = {}
        frame_idx = 0
        t_start = time.time()
        recent_events_for_overlay: list = []

        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if max_frames is not None and frame_idx >= max_frames:
                    break

                now_sec = frame_idx / fps

                # 1. detect → track
                detections = self._detector.detect(frame)
                tracks = self._tracker.update(detections, frame_idx)

                # 2. section match + line crossing + history 업데이트
                for tr in tracks:
                    sid = self._matcher.match(tr)
                    foot = foot_point(tr.bbox)
                    prev = self._prev_foot.get(tr.track_id)
                    crossed_entry = None
                    crossed_exit = None
                    if prev is not None:
                        for s_id, section in self.sections.items():
                            if line_crossing_direction(prev, foot, section.entry_line) != 0:
                                crossed_entry = s_id
                            if line_crossing_direction(prev, foot, section.exit_line) != 0:
                                crossed_exit = s_id
                    self._prev_foot[tr.track_id] = foot

                    hist = self._histories.setdefault(
                        tr.track_id, TrackHistory(track_id=tr.track_id)
                    )
                    hist.push(TrackSnapshot(
                        frame_idx=frame_idx,
                        timestamp_sec=now_sec,
                        bbox=tr.bbox,
                        section_id=sid,
                        crossed_entry=crossed_entry,
                        crossed_exit=crossed_exit,
                    ))

                # 3. 룰 평가
                events = self._engine.evaluate(
                    self._histories, self.sections, self._camera_id, now_sec
                )
                for ev in events:
                    ok_pub = self._publisher.publish(ev)
                    events_total += 1
                    events_by_type[ev.event_type] = events_by_type.get(ev.event_type, 0) + 1
                    log.info("event[%s] track=%d section=%s conf=%.2f published=%s",
                             ev.event_type, ev.track_id, ev.gate_section_id,
                             ev.confidence, ok_pub)
                    recent_events_for_overlay.append((frame_idx, ev))

                # 4. 시각화
                if self._visualizer and (writer or show_window):
                    annotated = self._visualizer.draw(
                        frame, tracks, self.sections, recent_events_for_overlay, frame_idx
                    )
                    if writer:
                        writer.write(annotated)
                    if show_window:
                        cv2.imshow("gateguard", annotated)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            break

                # 오래된 오버레이 이벤트 정리 (최근 60프레임만 유지)
                recent_events_for_overlay = [
                    (fi, ev) for (fi, ev) in recent_events_for_overlay
                    if frame_idx - fi <= 60
                ]
                frame_idx += 1
        finally:
            cap.release()
            if writer:
                writer.release()
            if show_window:
                cv2.destroyAllWindows()
            self._publisher.close()

        elapsed = time.time() - t_start
        return {
            "frames": frame_idx,
            "elapsed_sec": round(elapsed, 2),
            "fps": round(frame_idx / max(elapsed, 1e-6), 1),
            "events_total": events_total,
            "events_by_type": events_by_type,
            "model_version": self._detector.model_version,
        }
