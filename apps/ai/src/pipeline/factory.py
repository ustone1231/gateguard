"""config 기반 Pipeline 빌더.

config/pipeline.json 한 곳만 보면 전체 셋업이 어떻게 구성됐는지 보임.
구성 요소 교체 시 코드 변경 없이 config만 수정.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..detector import YoloDetector
from ..tracker import ByteTrackTracker
from ..publisher import FilePublisher, HttpPublisher
from ..rules import (
    RuleEngine, JumpRule, CrawlingRule, TailgatingRule, UnpaidRule,
)
from ..zone import SectionMatcher, load_sections
from .pipeline import Pipeline
from .visualizer import Visualizer


def build_from_config(
    pipeline_config_path: str | Path,
    sections_config_path: str | Path,
) -> Pipeline:
    cfg = json.loads(Path(pipeline_config_path).read_text(encoding="utf-8"))
    camera_id_from_sections, sections = load_sections(sections_config_path)
    camera_id = cfg["pipeline"].get("camera_id", camera_id_from_sections)

    # Detector
    m = cfg["model"]
    detector = YoloDetector(
        weights=m["weights"],
        device=m.get("device", "auto"),
        conf_threshold=m.get("conf_threshold", 0.4),
        iou_threshold=m.get("iou_threshold", 0.5),
        classes=m.get("classes", [0]),
    )

    # Tracker
    tracker = ByteTrackTracker()

    # Section matcher
    matcher = SectionMatcher(sections)

    # Rules
    rules_cfg = cfg["rules"]
    rules = []
    cooldown_by_type: dict[str, float] = {}
    if rules_cfg.get("jump", {}).get("enabled", True):
        rc = rules_cfg["jump"]
        rules.append(JumpRule(
            top_speed_threshold=rc.get("top_speed_threshold", 15.0),
            height_std_threshold=rc.get("height_std_threshold", 30.0),
            min_history_frames=rc.get("min_history_frames", 10),
        ))
        cooldown_by_type["jump"] = rc.get("cooldown_seconds", 3.0)
    if rules_cfg.get("crawling", {}).get("enabled", True):
        rc = rules_cfg["crawling"]
        rules.append(CrawlingRule(
            height_ratio_threshold=rc.get("height_ratio_threshold", 0.55),
            min_frames_crawling=rc.get("min_frames_crawling", 8),
        ))
        cooldown_by_type["crawling"] = rc.get("cooldown_seconds", 3.0)
    if rules_cfg.get("tailgating", {}).get("enabled", True):
        rc = rules_cfg["tailgating"]
        rules.append(TailgatingRule(max_gap_seconds=rc.get("max_gap_seconds", 1.5)))
        cooldown_by_type["tailgating"] = rc.get("cooldown_seconds", 3.0)
    if rules_cfg.get("unpaid", {}).get("enabled", True):
        rc = rules_cfg["unpaid"]
        rules.append(UnpaidRule())
        cooldown_by_type["unpaid"] = rc.get("cooldown_seconds", 5.0)

    engine = RuleEngine(rules, cooldown_seconds=cooldown_by_type)

    # Publisher
    pub_cfg = cfg["publisher"]
    if pub_cfg["type"] == "http":
        publisher = HttpPublisher(
            endpoint=pub_cfg["http_endpoint"],
            timeout=pub_cfg.get("http_timeout", 2.0),
            token=pub_cfg.get("http_token"),
            fallback_path=pub_cfg.get("file_path", "runs/events_failed.jsonl"),
        )
    else:
        publisher = FilePublisher(pub_cfg["file_path"])

    # Visualizer (시각화는 옵션)
    visualizer = Visualizer() if cfg["pipeline"].get("save_annotated_video", True) else None

    return Pipeline(
        detector=detector,
        tracker=tracker,
        matcher=matcher,
        rule_engine=engine,
        publisher=publisher,
        camera_id=camera_id,
        visualizer=visualizer,
    )
