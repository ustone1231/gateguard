# apps/backend

GateGuard 백엔드 API + 매칭 엔진.

---

## 🚀 즉시 개발 시작 가이드

본 트랙 개발자는 다음 3개 문서를 먼저 읽으면 명세 100% 확보:

| 순서 | 문서 | 무엇이 적혀있나 |
|------|------|----------------|
| 1 | [`docs/mvp-features.md`](../../docs/mvp-features.md) §4-B | 백엔드가 만들어야 할 모든 기능 + DB 스키마 + 매칭 엔진 의사코드 |
| 2 | [`docs/api-contract.md`](../../docs/api-contract.md) | 모든 endpoint / WebSocket / 인증 / 에러 / corner case 정책 |
| 3 | [`packages/schema/`](../../packages/schema/) | 받는 / 보내는 데이터 JSON Schema |

→ 위 3개만 보면 더 묻지 않고 코딩 시작 가능.

---

## 책임

- **이벤트 수신** (`POST /api/v1/events`) — AI 트랙이 발행하는 모든 event (gate_passage / jump / crawling / tailgating / unpaid) 수신, DB 저장
- **AFC 수신** (`POST /api/v1/fare-taps`) — Mock AFC 송신기 결제 데이터 수신
- **매칭 엔진** ⭐ — gate_passage event ↔ fare_tap 을 ±1초 윈도로 매칭, 결과 따라 `confirmed_unpaid` / `confirmed_misuse` 발행
- **운영자 인증** (JWT access + refresh)
- **이벤트 조회 / 의심 큐 / 통계 API** (REST)
- **WebSocket 실시간 알림** (`/ws/v1/events`)
- **영상 클립 저장** + 24시간 자동 삭제 cron
- **Mock AFC 송신기 스크립트** (`scripts/mock_afc/` — 발표용 수동 UI 도 여기에)

---

## 스택 (확정)

| 항목 | 결정 |
|------|------|
| 언어 / 프레임워크 | Python 3.11 + FastAPI |
| DB | PostgreSQL 15 + TimescaleDB (events / fare_taps 시계열) |
| WebSocket | FastAPI 내장 `fastapi.WebSocket` |
| JWT | `python-jose` |
| Rate limiting | `slowapi` middleware |
| 백그라운드 작업 | FastAPI BackgroundTasks (매칭 엔진은 별도 worker 권장) |
| 영상 처리 | `ffmpeg` (subprocess) 또는 `moviepy` |
| 영상 저장 | 로컬 디스크 `/var/lib/gateguard/clips/` + 24h cron 삭제 |
| 컨테이너 | Docker (인프라 트랙 Dockerfile) |

상세는 [`docs/api-contract.md`](../../docs/api-contract.md) §13.

---

## 시작하기

```bash
cd apps/backend

# venv 셋업 (인프라 트랙의 Docker 환경에서 자동화될 예정)
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 환경 변수 (.env)
cp .env.example .env
# 편집:
#   DATABASE_URL=postgresql://gateguard:secret@localhost:5432/gateguard
#   AI_SERVICE_TOKEN=<32자 random hex>
#   AFC_SERVICE_TOKEN=<32자 random hex>
#   JWT_SECRET=<256bit random>
#   CARD_HASH_SALT=<32자 random> (Mock AFC 송신기와 동일하게 공유)
#   VIDEO_CLIP_DIR=/var/lib/gateguard/clips
#   VIDEO_CLIP_TTL_HOURS=24

# 개발 서버
uvicorn app.main:app --reload --port 8000
```

현재 서버 마일스톤은 **배포 가능한 Backend MVP** 입니다.

- in-memory / SQL 저장소 모드 지원
- `gate_passage` ↔ `fare_tap` ±1초 매칭 + 1초 buffer
- `confirmed_unpaid` / `confirmed_misuse` 파생 이벤트 발행
- denied fare tap 후 approved 가 없을 때 `confirmed_unpaid` 처리
- WebSocket 알림, 통계, 손실 추정, 영상 클립 서명 URL + 24h cleanup 지원

### 저장소 모드

기본값은 빠른 개발용 in-memory 저장소입니다.

```bash
uvicorn app.main:app --reload --port 8000
```

DB 저장소를 검증하려면 `STORAGE_BACKEND=sql` 과 `DATABASE_URL` 을 지정합니다.

```bash
STORAGE_BACKEND=sql \
DATABASE_URL=sqlite:///./dev-gateguard.db \
uvicorn app.main:app --reload --port 8000
```

Docker compose 환경에서는 `STORAGE_BACKEND=sql` 과 Postgres `DATABASE_URL` 을 사용합니다.

### 서버 확인

```bash
curl http://localhost:8000/health
```

운영자 조회 API 는 개발용 토큰을 사용합니다.

```bash
curl -H "Authorization: Bearer dev-jwt-secret-please-change-before-prod" \
  http://localhost:8000/api/v1/events
```

### 구현된 API 빠른 확인

| 기능 | Endpoint |
|------|----------|
| AI 이벤트 수신 | `POST /api/v1/events` |
| AFC fare tap 수신 | `POST /api/v1/fare-taps` |
| 이벤트 조회 | `GET /api/v1/events`, `GET /api/v1/events/{event_id}` |
| 영상 클립 서명 redirect | `GET /api/v1/events/{event_id}/video-clip` |
| 검토 큐 | `GET /api/v1/review-queue`, `POST /api/v1/review-queue/{queue_id}/feedback` |
| 통계 | `GET /api/v1/stats?period=day&from=...&to=...` |
| 손실 추정 | `GET /api/v1/loss-estimate?unit_loss_krw=1370` |
| 실시간 알림 | `WS /ws/v1/events?token=<access_token>` |

WebSocket 메시지는 `event_new`, `review_queue_added`, `heartbeat` 타입을 전송합니다.
영상 클립은 `VIDEO_CLIP_DIR` 아래 `<event_id>.mp4|.mov|.webm` 또는 event `clip_url` 상대경로를 찾고,
인증된 `/video-clip` 요청에서 5분 유효한 내부 서명 URL 로 redirect 합니다.

---

## 공통 스키마

받는 `Event` / `FareTap` 의 모양은 [`packages/schema/`](../../packages/schema/) 가 정의함.
백엔드는 여기를 참조해서 Pydantic 모델 자동 생성 추천:

```bash
# datamodel-code-generator 로 schema → Pydantic
datamodel-codegen \
  --input ../../packages/schema/events/event.schema.json \
  --output app/models/event_v022.py \
  --output-model-type pydantic_v2.BaseModel
```

---

## 매칭 엔진 핵심

[`docs/api-contract.md`](../../docs/api-contract.md) §2-1 매칭 엔진 동작 + §11-1 ~ §11-12 corner case 정책 그대로 구현.

핵심 알고리즘 (의사코드):
```python
def on_gate_passage(passage):
    matched = FareTap.find(gate=passage.gate, time=±1s, result="approved", unmatched=True)
    if not matched:
        emit_confirmed_unpaid(source=passage)
        return
    tap = nearest_by_time(matched, passage.timestamp)
    update_afc_match(passage, tap)
    if eligibility_mismatch(tap, passage.signals) and passage.reliability == "high":
        emit_confirmed_misuse(source=passage, tap=tap)
```

**buffer 정책 (§11-2):** gate_passage / fare_tap 둘 다 도착 후 1초 보관 → 늦은 짝 매칭 가능.

구현 메모:
- `approved` fare tap 만 gate_passage 와 1:1 매칭됩니다.
- `denied` / `error` fare tap 은 저장하지만 매칭 키로 사용하지 않습니다.
- `denied` tap 이 ±1초 내 존재하고, 같은 window 안에 `approved` tap 이 없으면 buffer 이후 `confirmed_unpaid` 를 발행합니다.
- `confirmed_misuse` 는 `card_category` / `holder_gender` 와 AI `signals` 의 high-confidence 불일치일 때만 발행합니다.
- 파생 이벤트는 멱등적으로 생성되어 같은 source event 에 대해 중복 발행되지 않습니다.

---

## 테스트

| 종류 | 도구 | 위치 |
|------|------|------|
| 단위 테스트 | pytest | `tests/test_*.py` |
| 매칭 엔진 알고리즘 | pytest + 시뮬레이션 fixture | `tests/test_matching_engine.py` |
| API 통합 테스트 | pytest + httpx | `tests/integration/` |
| 스키마 round-trip | `check-jsonschema` | CI 자동 |

로컬 검증:

```bash
cd apps/backend
venv/bin/pytest -q
python3 -m compileall -q app tests
```

---

## CI/CD

`.github/workflows/backend-ci.yml` 의 placeholder 를 실제 CI 로 교체:
- pytest 실행
- 스키마 호환성 검증 (events v0.2.2 / fare_tap v0.2.2)
- Docker 이미지 빌드 (Tyler 의 인프라 Dockerfile 참조)
