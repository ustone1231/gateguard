"""config 기반 Pipeline 빌더.

config/pipeline.json 한 곳만 보면 전체 셋업이 어떻게 구성됐는지 보임.
구성 요소 교체 시 코드 변경 없이 config만 수정.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from ..age_estimator import (
    HfMivoloV2AgeGenderEstimator,
    HfMivoloV2Config,
    MivoloAgeGenderEstimator,
    MivoloConfig,
    NullAgeGenderEstimator,
)
from ..detector import YoloDetector
from ..eligibility_signals import EligibilitySignalConfig, EligibilitySignalEstimator
from ..pose_estimator import NullPoseEstimator, UltralyticsPoseEstimator
from ..tracker import ByteTrackTracker
from ..publisher import FilePublisher, HttpPublisher
from ..rules import (
    RuleEngine, JumpRule, GatePassageRule, CrawlingRule, TailgatingRule, UnpaidRule,
)
from ..zone import SectionMatcher, load_sections
from .pipeline import Pipeline
from .visualizer import Visualizer

EVENTS_PATH = "/api/v1/events"
DEFAULT_BACKEND_BASE_URL = "http://localhost:8000"
AI_SERVICE_TOKEN_ENV = "AI_SERVICE_TOKEN"


def resolve_http_endpoint(pipeline_endpoint: str | None) -> str:
    """이벤트 발행 full URL 결정.

    우선순위: BACKEND_URL env > pipeline.json http_endpoint > localhost fallback.
    입력은 base URL (예: http://backend:8000), 반환은 path 결합한 full URL.
    """
    base = os.getenv("BACKEND_URL") or pipeline_endpoint or DEFAULT_BACKEND_BASE_URL
    return f"{base.rstrip('/')}{EVENTS_PATH}"


def resolve_http_token(pipeline_token: str | None) -> str | None:
    """백엔드 AI 서비스 인증 토큰 결정.

    우선순위: AI_SERVICE_TOKEN env > pipeline.json http_token.
    값은 Bearer prefix 없는 raw token으로 받음.
    """
    return os.getenv(AI_SERVICE_TOKEN_ENV) or pipeline_token


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

    pose_estimator = _build_pose_estimator(cfg)
    age_gender_estimator = _build_age_gender_estimator(cfg)

    # Section matcher
    matcher = SectionMatcher(sections)

    # Rules
    rules_cfg = cfg["rules"]
    rules = []
    cooldown_by_type: dict[str, float] = {}
    if rules_cfg.get("gate_passage", {}).get("enabled", True):
        rc = rules_cfg.get("gate_passage", {})
        signal_cfg = cfg.get("eligibility_signals", {})
        eligibility_estimator = EligibilitySignalEstimator(
            EligibilitySignalConfig(
                enabled=signal_cfg.get("enabled", True),
                slow_speed_px_per_sec=signal_cfg.get("slow_speed_px_per_sec", 80.0),
                fast_speed_px_per_sec=signal_cfg.get("fast_speed_px_per_sec", 220.0),
                child_bbox_height_px=signal_cfg.get("child_bbox_height_px", 90.0),
                adult_bbox_height_px=signal_cfg.get("adult_bbox_height_px", 150.0),
                min_age_group_confidence=signal_cfg.get("min_age_group_confidence", 0.35),
            )
        )
        rules.append(GatePassageRule(
            recent_window_frames=rc.get("recent_window_frames", 3),
            min_same_line_gap_frames=rc.get("min_same_line_gap_frames", 3),
            eligibility_estimator=eligibility_estimator,
        ))
        cooldown_by_type["gate_passage"] = rc.get("cooldown_seconds", 0.0)
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
            endpoint=resolve_http_endpoint(pub_cfg.get("http_endpoint")),
            timeout=pub_cfg.get("http_timeout", 2.0),
            token=resolve_http_token(pub_cfg.get("http_token")),
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
        pose_estimator=pose_estimator,
        age_gender_estimator=age_gender_estimator,
    )


def _build_pose_estimator(cfg: dict):
    pose_cfg = cfg.get("pose_estimator", {})
    if not pose_cfg.get("enabled", False):
        return NullPoseEstimator()
    return UltralyticsPoseEstimator(
        weights=pose_cfg.get("weights", "models/yolo11n-pose.pt"),
        device=pose_cfg.get("device", cfg.get("model", {}).get("device", "auto")),
        conf_threshold=pose_cfg.get("conf_threshold", 0.35),
        iou_match_threshold=pose_cfg.get("iou_match_threshold", 0.30),
    )


def _build_age_gender_estimator(cfg: dict):
    age_cfg = cfg.get("age_estimator", {})
    if not age_cfg.get("enabled", False):
        return NullAgeGenderEstimator()
    estimator_type = age_cfg.get("type", "hf_mivolo_v2")
    if estimator_type == "hf_mivolo_v2":
        return HfMivoloV2AgeGenderEstimator(
            HfMivoloV2Config(
                model_id=age_cfg.get("model_id", "iitolstykh/mivolo_v2"),
                device=age_cfg.get("device", cfg.get("model", {}).get("device", "cpu")),
                torch_dtype=age_cfg.get("torch_dtype", "float32"),
                revision=age_cfg.get("revision"),
            )
        )
    if estimator_type != "mivolo":
        raise ValueError(f"Unsupported age_estimator.type: {estimator_type}")
    return MivoloAgeGenderEstimator(
        MivoloConfig(
            detector_weights=age_cfg.get("detector_weights", "models/yolov8x_person_face.pt"),
            checkpoint=age_cfg.get("checkpoint", "models/mivolo_imbd.pth.tar"),
            device=age_cfg.get("device", cfg.get("model", {}).get("device", "cpu")),
            with_persons=age_cfg.get("with_persons", True),
            disable_faces=age_cfg.get("disable_faces", False),
            iou_match_threshold=age_cfg.get("iou_match_threshold", 0.30),
        )
    )
