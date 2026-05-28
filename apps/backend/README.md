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

# DB 마이그레이션
alembic upgrade head

# 개발 서버
uvicorn app.main:app --reload --port 8000

# 매칭 엔진 워커 (별도 프로세스)
python -m app.matching_engine.worker

# 영상 클립 삭제 cron (또는 systemd timer)
python scripts/cleanup_clips.py    # 24h 경과 클립 삭제
```

---

## 공통 스키마

받는 `Event` / `FareTap` 의 모양은 [`packages/schema/`](../../packages/schema/) 가 정의함.
백엔드는 여기를 참조해서 Pydantic 모델 자동 생성 추천:

```bash
# datamodel-code-generator 로 schema → Pydantic
datamodel-codegen \
  --input ../../packages/schema/events/event.schema.json \
  --output app/models/event_v021.py \
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
    if tap.card_category in {"senior", "child"} and passage.signals.senior_probability < 0.20:
        emit_confirmed_misuse(source=passage, tap=tap)
```

**buffer 정책 (§11-2):** gate_passage / fare_tap 둘 다 도착 후 1초 보관 → 늦은 짝 매칭 가능.

---

## 테스트

| 종류 | 도구 | 위치 |
|------|------|------|
| 단위 테스트 | pytest | `tests/test_*.py` |
| 매칭 엔진 알고리즘 | pytest + 시뮬레이션 fixture | `tests/test_matching_engine.py` |
| API 통합 테스트 | pytest + httpx | `tests/integration/` |
| 스키마 round-trip | `check-jsonschema` | CI 자동 |

---

## CI/CD

`.github/workflows/backend-ci.yml` 의 placeholder 를 실제 CI 로 교체:
- pytest 실행
- 스키마 호환성 검증 (events v0.2.1 / fare_tap v0.2.1)
- Docker 이미지 빌드 (Tyler 의 인프라 Dockerfile 참조)
