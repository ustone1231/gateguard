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

### Gate passage smoke test

샘플 영상이나 백엔드 없이 `gate_passage` 이벤트 발행만 빠르게 확인:

```bash
python scripts/smoke_gate_passage.py
```

확인할 것:
- `runs/gate_passage_smoke.jsonl` 생성
- `event_type` 이 `gate_passage`
- `camera_id` 가 `camera_001`
- `gate_section_id` 가 `gate_01`
- `raw_meta.line_type` 이 `entry`, `exit` 두 건으로 기록

이 테스트가 통과하면 AI 룰이 “게이트 통과 이벤트를 만들 수 있음”까지 확인된 것.
실제 영상 검증은 그 다음 단계로 `day10_full_pipeline.py <video_path>` 를 사용.

### Model-backed gate passage smoke test

실제 영상에서 `age_estimator`를 켠 뒤, 발행된 `gate_passage` 이벤트에
모델 기반 `signals`가 붙는지 자동으로 확인:

```bash
python scripts/smoke_model_gate_passage.py ../../videos/gateguard_test_video.mov \
  --sections config/gate_sections.local.json \
  --start-sec 11.5 \
  --max-frames 90
```

확인할 것:
- `summary.model_signal_gate_passage_count >= 1`
- JSONL 이벤트의 `signals.face_age_estimate`, `signals.perceived_gender`,
  `signals.gender_confidence` 존재
- 같은 track/section/line의 짧은 crossing jitter가 중복 이벤트로 남지 않는지 확인

이 테스트는 HF MiVOLO v2와 YOLO를 함께 CPU에서 돌리므로 단위 테스트보다 느리다.
모델 revision이나 gate section 좌표를 바꾼 뒤에는 반드시 다시 실행한다.

### Gate section 좌표 찍기

실제 영상 첫 프레임에서 `polygon`, `entry_line`, `exit_line` 좌표를 클릭해서 JSON으로 출력:

```bash
python scripts/pick_gate_points.py ../../videos/gateguard_test_video.mov
```

조작:
- `polygon`: 게이트 영역을 둘러싸는 점 3개 이상 클릭 후 `n`
- `entry_line`: 선 양끝 2개 클릭 후 `n`
- `exit_line`: 선 양끝 2개 클릭 후 `n`
- `u`: 마지막 점 되돌리기
- `c`: 현재 단계 점 지우기
- `q`: 종료

파일로 바로 저장:

```bash
python scripts/pick_gate_points.py ../../videos/gateguard_test_video.mov \
  --output config/gate_sections.local.json
```

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
│   ├── pose_estimator/        # YOLO pose wrapper (optional model-backed signals)
│   ├── age_estimator/         # MiVOLO wrapper (optional model-backed signals)
│   ├── eligibility_signals/    # v0.2.2 우대 자격 보조 신호(MVP 휴리스틱)
│   ├── rules/                 # Rule ABC + 4종 + RuleEngine
│   ├── publisher/             # EventPublisher ABC + File/Http
│   └── pipeline/              # Pipeline + Visualizer + factory
└── scripts/                   # Day별 독립 실행 스크립트
```

## md 명세 ↔ 코드 매핑

현재 구현/검증 상태와 운영 enable 기준은
[`docs/ai-validation.md`](../../docs/ai-validation.md)를 함께 본다.

| md 명세 | 위치 |
|---------|------|
| Detector.detect / Tracker.update 인터페이스 | `src/detector/base.py`, `src/tracker/base.py` |
| YOLO11n + ByteTrack baseline | `yolo_detector.py`, `bytetrack_tracker.py` |
| gate_sections (polygon, entry/exit line) | `config/gate_sections.json` + `src/zone/section.py` |
| 이벤트 페이로드 (event_type, gate_section_id, ...) | `src/types.py` Event |
| pose 기반 보조 신호 | `src/pose_estimator/` |
| 나이/성별 기반 보조 신호 | `src/age_estimator/` |
| gate_passage 우대 자격 보조 신호 | `src/eligibility_signals/` → `Event.signals` |
| 4종 룰 + cooldown + confidence | `src/rules/` |
| model_versions 추적 | `Detector.model_version` → `Event.raw_meta` |
| POST /api/v1/events | `src/publisher/http_publisher.py` |

### v0.2.2 eligibility signals

`gate_passage` 이벤트는 백엔드의 우대카드 부정사용 매칭을 위해 `signals`를 첨부할 수 있다.
기본 설정은 모델 없이 track 속도와 bbox scale에서 약한 연령대 보조 신호만 만든다.
`pose_estimator.enabled` 또는 `age_estimator.enabled`를 켜면 모델 결과를 우선 사용한다.
성별은 `age_estimator.enabled=false` 상태에서는 `perceived_gender="unknown"`으로 둔다.
HF MiVOLO v2 같은 실제 모델을 켜면 모델이 반환한 `perceived_gender`와
`gender_confidence`를 보조 신호로 첨부하되, 자동 확정 판단은 백엔드의 confidence 정책을 따른다.

### Optional model setup

모델 가중치는 git에 올리지 않는다. 필요한 파일은 `models/` 아래에 둔다.

```bash
cd apps/ai
pip install -r requirements.txt
bash scripts/download_models.sh
python scripts/check_model_setup.py --pose
```

나이/성별 추정의 우선 후보는 HuggingFace MiVOLO v2다. 원본 `.pth.tar`
체크포인트 없이 공개 모델을 내려받아 smoke test까지 할 수 있다.
단, HuggingFace remote code가 내부에서 `mivolo` 패키지를 import하므로
런타임 패키지는 별도로 설치해야 한다.

```bash
pip install "setuptools<81"
pip install --no-build-isolation git+https://github.com/WildChlamydia/MiVOLO.git@main
python scripts/check_model_setup.py --hf-mivolo-v2
```

주의:
- `hf_mivolo_v2`는 `trust_remote_code=True`를 사용한다. 현재
  `config/pipeline.json`은 smoke 검증한 HuggingFace revision에 고정되어 있다.
  revision을 바꾸면 model setup smoke와 실제 gate passage smoke를 다시 돌린다.
- 현재 wrapper는 별도 face detector crop 없이 ByteTrack person bbox를 body 입력으로 사용한다.
  얼굴 crop 품질까지 높이려면 face/person detector 연결을 추가 검증해야 한다.
- 원본 MiVOLO 패키지는 자체 dependency로 `ultralytics==8.1.0`,
  `timm==0.8.13.dev0`를 요구한다. 기본 AI 파이프라인 검증 환경과 섞기 전에
  별도 venv 또는 constraints로 충돌을 확인해야 한다.

원본 MiVOLO `.pth.tar` 경로도 남겨둔다. 이 방식은 upstream checkpoint가 필요하다.

```bash
# upstream checkpoint를 models/mivolo_imbd.pth.tar 로 배치한 뒤
python scripts/check_model_setup.py --mivolo
```

모델 파일이 없으면 wrapper는 조용히 휴리스틱으로 속이지 않고 명시적으로 실패한다.

## 백엔드 연동

### 1. 코드 변경 없이 config로 전환

`config/pipeline.json`:
```json
{
  "publisher": {
    "type": "http",                          // file → http
    "http_endpoint": "http://backend:8000",  // base URL only
    "http_timeout": 2.0,
    "http_token": "raw bearer token"
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

#### 인증 토큰 우선순위 (Issue #7)

`HttpPublisher` 가 백엔드에 보내는 Bearer 토큰 결정 규칙:

1. `AI_SERVICE_TOKEN` env (예: docker-compose 의 `AI_SERVICE_TOKEN=...`)
2. `pipeline.json` 의 `publisher.http_token`

값은 `Bearer ` prefix 없는 raw token으로 넣는다. `HttpPublisher`가 요청 헤더에 `Authorization: Bearer <token>` 형식으로 붙인다.

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
