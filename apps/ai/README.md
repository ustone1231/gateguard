# GateGuard AI/CV Pipeline

영상 → 사람 탐지 → 추적 → 섹션 매칭 → 룰 판정 → 이벤트 발행.
백엔드 POST `/api/v1/events` 와 연동되는 추론 파이프라인.

## 빠른 시작

```bash
# 1. 환경
python -m venv venv
source venv/bin/activate      # mac/linux
pip install -r requirements.txt

# 2. 테스트 영상 준비 (휴대폰 30초 영상 or YouTube 다운)
#    파일명 자유. 예: test.mp4

# 3. Day별 실행
python scripts/day1_hello_yolo.py test.mp4       # 사람 bbox
python scripts/day2_tracking.py test.mp4         # + track_id
python scripts/day3_sections.py test.mp4         # + 섹션 매칭
python scripts/day5_line_crossing.py test.mp4    # + line crossing
python scripts/day6_jump_rule.py test.mp4        # + jump 룰
python scripts/day8_all_rules.py test.mp4        # + 4종 룰
python scripts/day10_full_pipeline.py test.mp4   # config 기반 전체
```

결과는 `runs/dayN_output.mp4` 와 `runs/events_*.jsonl` 로 저장됨.

## 구조 — 한 눈에

```
gateguard-ai/
├── config/
│   ├── gate_sections.json     # 카메라별 polygon/line (= DB schema 1:1)
│   └── pipeline.json          # 모델/룰/publisher 설정
├── src/
│   ├── types.py               # Event = POST 페이로드 (백엔드와 1:1)
│   ├── detector/              # Detector ABC + YoloDetector
│   ├── tracker/               # Tracker ABC + ByteTrackTracker
│   ├── zone/                  # GateSection + geometry + matcher
│   ├── rules/                 # Rule ABC + 4종 + RuleEngine
│   ├── publisher/             # EventPublisher ABC + File/Http
│   └── pipeline/              # Pipeline + Visualizer + factory
└── scripts/                   # Day별 독립 실행 스크립트
```

## md 명세 ↔ 코드 매핑

| md 명세 | 위치 |
|---------|------|
| Detector.detect / Tracker.update 인터페이스 | `src/detector/base.py`, `src/tracker/base.py` |
| YOLO11n + ByteTrack baseline | `yolo_detector.py`, `bytetrack_tracker.py` |
| gate_sections (polygon, entry/exit line) | `config/gate_sections.json` + `src/zone/section.py` |
| 이벤트 페이로드 (event_type, gate_section_id, ...) | `src/types.py` Event |
| 4종 룰 + cooldown + confidence | `src/rules/` |
| model_versions 추적 | `Detector.model_version` → `Event.raw_meta` |
| POST /api/v1/events | `src/publisher/http_publisher.py` |

## 백엔드 연동

### 1. 코드 변경 없이 config로 전환

`config/pipeline.json`:
```json
{
  "publisher": {
    "type": "http",                          // file → http
    "http_endpoint": "http://backend:8000",  // base URL only
    "http_timeout": 2.0,
    "http_token": "Bearer 토큰"
  }
}
```

이게 끝. 파이프라인은 재실행만.

#### endpoint 우선순위 (Issue #3)

`HttpPublisher` 가 백엔드 호출에 쓰는 URL 결정 규칙:

1. `BACKEND_URL` env (예: docker-compose 의 `BACKEND_URL=http://backend:8000`)
2. `pipeline.json` 의 `publisher.http_endpoint`
3. `http://localhost:8000` (개발 fallback)

세 경우 모두 **base URL** 만 받고, path `/api/v1/events` 는 코드에서 결합 (`src/pipeline/factory.py` `resolve_http_endpoint`).
컨테이너 배포 시 인프라가 env 만 주입하면 config 수정 없이 동작.

### 2. POST 페이로드 (백엔드가 받는 형식)

```json
{
  "event_type": "jump",
  "gate_section_id": "gate_01",
  "camera_id": "camera_001",
  "confidence": 0.872,
  "track_id": 7,
  "timestamp": "2026-05-23T03:42:11.123456+00:00",
  "clip_url": null,
  "raw_meta": {
    "top_speed_up_px_per_frame": 18.3,
    "height_std_px": 42.1,
    "frames_evaluated": 10
  }
}
```

이게 md 명세의 페이로드와 1:1. 백엔드 DB의 `events` 테이블에 그대로 들어감.

### 3. 백엔드 다운 시 동작

`HttpPublisher`는 POST 실패하면 `runs/events_failed.jsonl` 에 자동 저장.
백엔드 복구 후:
```bash
# 실패 큐 재전송 (별도 스크립트로 만들 수 있음)
cat runs/events_failed.jsonl | xargs -I {} curl -X POST ...
```

### 4. clip_url 채워넣기

현재 AI 파이프라인은 `clip_url=None`을 보냄. Video Worker (Infra 트랙)가
이벤트 timestamp 기준 ±N초로 클립을 자른 뒤 백엔드가 `clip_url`을 업데이트.
즉 AI는 발행만, 클립 첨부는 비동기.

## 인프라 연동 (Docker)

`Dockerfile` 예시 (Infra 트랙이 작성):
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "scripts/day10_full_pipeline.py", "/videos/input.mp4"]
```

`docker-compose.yml` 추가:
```yaml
ai-worker:
  build: ./gateguard-ai
  volumes:
    - ./gateguard-ai/config:/app/config
    - ./videos:/videos
    - ./runs:/app/runs
    - ./models:/root/.cache/torch/hub
  environment:
    - PYTHONUNBUFFERED=1
  depends_on:
    - backend
```

## 확장 — Option B (학습 트랙)

기존 코드 0줄 수정. 새 룰 1개 추가만:

```python
# src/rules/action_recognition.py (가상)
class ActionRecognitionRule(Rule):
    event_type = "jump_verified"   # 또는 기존 타입에 합쳐도 됨

    def __init__(self, weights):
        self._model = load_slowfast(weights)

    def evaluate(self, history, sections, all_histories, camera_id):
        clip = extract_clip_from_history(history)
        pred = self._model(clip)
        if pred.label == "jump" and pred.conf > 0.9:
            return Event(...)
        return None

# 사용처 (메인 스크립트)
engine.add_rule(ActionRecognitionRule("checkpoints/slowfast.pt"))
```

룰 기반 + 학습 모델이 동시 가동 (앙상블). MVP는 안 깨짐.

## 트러블슈팅

| 증상 | 해결 |
|------|------|
| `Could not open video` | 경로 확인. 절대경로 권장 |
| GPU 안 잡힘 | `config/pipeline.json`의 `model.device` 를 `"cuda"` 또는 `"mps"` 로 |
| 추적 ID가 자꾸 바뀜 | `bytetrack_tracker.py`의 `lost_track_buffer` 증가 |
| 오탐 많음 | `config/pipeline.json`의 룰별 임계치 상향 |
| polygon이 영상에 안 맞음 | `config/gate_sections.json` 좌표 재조정 (Zone Editor가 할 일) |

## 다음 작업

- [ ] 학습 트랙 (Option B) — 행동 인식 모델 fine-tuning
- [ ] Pose Estimation 추가 (`src/detector/pose_detector.py`)
- [ ] RTSP 실시간 입력 (`pipeline.py` source 분기 강화)
- [ ] 메트릭 엔드포인트 (FPS, GPU, 큐 사이즈)
