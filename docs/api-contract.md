# GateGuard API Contract

> **이 문서가 다루는 것:** 트랙 간 통신 (REST endpoint, WebSocket, 인증, 에러, 재시도, 시퀀스).
> **이 문서가 다루지 않는 것:** 데이터 모양 → [`packages/schema/`](../packages/schema/) (single source of truth).
> 무엇을 만드는지 → [`mvp-features.md`](mvp-features.md).

---

## 0. 통신 패턴 개요

| 통신 | 프로토콜 | 인증 | 비고 |
|------|---------|------|------|
| AI → 백엔드 (이벤트 발행) | HTTP POST | 서비스 토큰 (Bearer) | 동기, 실패 시 AI fallback (JSONL) |
| Mock AFC → 백엔드 (결제 트랜잭션) | HTTP POST | 서비스 토큰 (Bearer) | 동기, 발신측 재시도 |
| 프론트엔드 → 백엔드 (인증/조회/검토) | HTTP REST | JWT (access + refresh) | 표준 REST |
| 백엔드 → 프론트엔드 (실시간 알림) | WebSocket | JWT (query string) | 자동 재연결 |
| 영상 클립 다운로드 | HTTP GET | 시간제한 서명 URL | 직접 스트리밍 |

**모든 시각:** UTC ISO-8601 timezone-aware (`2026-05-28T03:42:11.123456+00:00`).
**모든 시계:** NTP 동기화 의무 — ±1초 매칭 윈도우의 전제.
**모든 API URL:** `/api/v1/...` (v0.x 스키마 기간에도 URL 은 v1 시작).

---

## 1. 인증

### 1-1. 서비스 토큰 (AI / Mock AFC → 백엔드)

- 발급: 인프라 트랙이 환경 변수로 주입 (`AI_SERVICE_TOKEN`, `AFC_SERVICE_TOKEN`)
- 형식: 길이 ≥ 32 의 random hex 문자열
- 사용: HTTP 헤더 `Authorization: Bearer <token>`
- 회전 정책: MVP 는 정적, 운영 시 분기 회전

### 1-2. JWT (프론트엔드 → 백엔드)

```
POST /api/v1/auth/login
요청:  { "username": "...", "password": "..." }
응답:  { "access_token": "<jwt>", "refresh_token": "<jwt>", "expires_in": 900 }
       (access 15분 / refresh 7일)

POST /api/v1/auth/refresh
요청:  { "refresh_token": "<jwt>" }
응답:  { "access_token": "<jwt>", "expires_in": 900 }

POST /api/v1/auth/logout
요청:  Authorization: Bearer <refresh_token>
응답:  204 No Content

모든 보호된 요청:
       Authorization: Bearer <access_token>
```

**JWT claims (필수):**
- `sub` (역무원 ID)
- `role` (`operator` | `admin`)
- `iat`, `exp`

---

## 2. REST API 전체 명세

> 모든 요청/응답: `Content-Type: application/json`, UTF-8.
> 오류 응답 공통 형식: §5 참조.

### 2-1. AI → 백엔드

#### `POST /api/v1/events` — 이벤트 발행

- **누가 호출:** AI 트랙 (`apps/ai/src/publisher/http_publisher.py`)
- **인증:** `Authorization: Bearer <AI_SERVICE_TOKEN>`
- **요청 body:** `packages/schema/events/event.schema.json` v0.2.1 페이로드 (event_type ∈ {gate_passage, jump, crawling, tailgating, unpaid})
- **응답 201:** `{ "event_id": "evt_...", "stored_at": "2026-05-28T...Z" }`
- **응답 200:** `{ "event_id": "evt_...", "stored_at": "...", "deduped": true }` (event_id 가 이미 존재할 때 — **멱등성**)
- **응답 400:** 스키마 검증 실패 → AI fallback 으로 저장 + 재전송 안 함 (스키마 변경 안 하면 재전송해도 실패)
- **응답 401:** 인증 실패 → AI 가 즉시 로그 + 운영자 알림
- **응답 5xx / timeout:** AI 가 fallback (`runs/events_failed.jsonl`) 후 백오프 재시도 (최대 5회, 2^n 초)

> **`gate_passage` 가 매칭 엔진의 핵심 입력.** 백엔드가 받자마자 §2-3 매칭 엔진 트리거.

#### `POST /api/v1/fare-taps` — Mock AFC 결제 트랜잭션 수신

- **누가 호출:** Mock AFC 송신기 (JSONL replay / Mock UI / Mock HTTP 송신기)
- **인증:** `Authorization: Bearer <AFC_SERVICE_TOKEN>`
- **요청 body:** `packages/schema/fare-taps/fare_tap.schema.json` v0.2.1 페이로드 (`fare_tap_id` 필수 — 멱등성 키)
- **응답 201:** `{ "fare_tap_id": "tap_...", "stored_at": "..." }`
- **응답 200:** `{ "fare_tap_id": "tap_...", "stored_at": "...", "deduped": true }` (fare_tap_id 중복 시 — **멱등성**)
- **응답 400:** 스키마 검증 실패 → 송신측 책임
- **응답 401:** 인증 실패
- **응답 5xx:** 송신측 재시도

> Mock AFC 송신기와 백엔드는 **동일 `CARD_HASH_SALT`** 를 환경변수로 공유해야 card_id_hash 가 일관됨.

#### 매칭 엔진 동작 (백엔드 내부 비동기 워커, API 아님)

핵심 입력: AI 의 `gate_passage` event + AFC `fare_tap`. 다음 알고리즘:

```python
# detection-strategy.md §6 + mvp-features.md §4-B-2 와 동일
def on_gate_passage(passage_event):
    # 1. ±1초 윈도우 검색
    matched_taps = FareTap.find(
        gate=passage_event.gate_section_id,
        time_range=(passage_event.timestamp - 1s, passage_event.timestamp + 1s),
        result="approved",
        unmatched=True,
    )

    # 2. 매칭 실패 → confirmed_unpaid 발행
    if not matched_taps:
        emit_confirmed_unpaid(source=passage_event)
        return

    # 3. 시간 가장 가까운 1쌍 (1:1 nearest neighbor)
    tap = nearest_by_time(matched_taps, passage_event.timestamp)
    FareMatch.create(passage=passage_event, tap=tap)
    update_afc_match(passage_event, tap)

    # 4. misuse 판정
    if (
        tap.card_category in {"senior", "child"}
        and passage_event.signals
        and passage_event.signals.senior_probability is not None
        and passage_event.signals.senior_probability < 0.20
        and passage_event.reliability == "high"
    ):
        emit_confirmed_misuse(source=passage_event, tap=tap)
```

**규칙:**
- 한 `fare_tap` 은 한 `gate_passage` 와만 매칭 (중복 매칭 금지)
- `confirmed_unpaid` / `confirmed_misuse` 의 `source_event_id` = 원본 `gate_passage.event_id`
- `confirmed_*` 발행도 `POST /api/v1/events` 와 같은 schema 사용 (백엔드 self-POST 또는 직접 DB 저장)

### 2-2. 프론트엔드 → 백엔드 — 이벤트 조회

#### `GET /api/v1/events`

- **인증:** JWT (access)
- **쿼리 파라미터:**
  - `from`, `to` (ISO-8601, 시간 범위)
  - `gate_section_id` (optional, 여러 개 가능: `gate_section_id=gate_01&gate_section_id=gate_02`)
  - `event_type` (optional, 여러 개 가능)
  - `severity` (optional)
  - `limit` (기본 50, 최대 200)
  - `cursor` (페이지네이션 토큰, 응답에서 받음)
- **응답 200:**
  ```json
  {
    "data": [ <Event v0.2.0>, ... ],
    "next_cursor": "..." | null,
    "total": 1234
  }
  ```

#### `GET /api/v1/events/{event_id}`

- **인증:** JWT
- **응답 200:** Event v0.2.0 페이로드
- **응답 404:** 이벤트 없음

#### `GET /api/v1/events/{event_id}/video-clip`

- **인증:** JWT
- **응답 302:** 서명된 영상 URL 로 redirect (만료 5분)
- **응답 404:** 영상 클립 미생성 또는 24h 경과 후 삭제됨

### 2-3. 프론트엔드 → 백엔드 — 의심 큐 (misuse 워크플로우 핵심)

#### `GET /api/v1/review-queue`

- **인증:** JWT
- **쿼리 파라미터:**
  - `status` (기본 `pending`, 다른 값: `confirmed`, `false_positive`, `all`)
  - `from`, `to`, `gate_section_id`, `limit`, `cursor` (events 와 동일)
- **응답 200:**
  ```json
  {
    "data": [
      {
        "queue_id": "rq_abc123",
        "event_id": "evt_b2c3...",
        "event": { ...Event v0.2.0... },
        "status": "pending",
        "added_at": "2026-05-28T03:45:23+00:00",
        "reviewer_id": null,
        "reviewed_at": null,
        "feedback": null
      },
      ...
    ],
    "next_cursor": "..." | null
  }
  ```

#### `POST /api/v1/review-queue/{queue_id}/feedback`

- **인증:** JWT
- **요청 body:**
  ```json
  {
    "decision": "confirmed" | "false_positive",
    "notes": "선택, 자유 텍스트, 최대 500자"
  }
  ```
- **응답 200:**
  ```json
  {
    "queue_id": "rq_abc123",
    "status": "confirmed",
    "reviewer_id": "op_user_001",
    "reviewed_at": "2026-05-28T03:50:11+00:00"
  }
  ```
- **응답 409:** 이미 다른 역무원이 검토 완료 (동시성 충돌)

### 2-4. 프론트엔드 → 백엔드 — 통계

#### `GET /api/v1/stats`

- **인증:** JWT
- **쿼리 파라미터:**
  - `period` (`day` | `week` | `month`, 기본 `day`)
  - `from`, `to` (ISO-8601)
  - `gate_section_id` (optional)
- **응답 200:**
  ```json
  {
    "period": "day",
    "from": "2026-05-28T00:00:00+00:00",
    "to": "2026-05-29T00:00:00+00:00",
    "by_type": {
      "jump": 12,
      "crawling": 3,
      "tailgating": 8,
      "unpaid": 21,
      "misuse": 5
    },
    "by_gate": {
      "gate_01": 30,
      "gate_02": 19
    },
    "by_hour": [ 1, 0, 0, 2, ..., 5 ]
  }
  ```

#### `GET /api/v1/loss-estimate`

- **인증:** JWT
- **쿼리 파라미터:**
  - `from`, `to`
  - `unit_loss_krw` (1회 손실 단가, 기본 1370 — 기본요금)
- **응답 200:**
  ```json
  {
    "period_from": "...",
    "period_to": "...",
    "total_incidents": 49,
    "unit_loss_krw": 1370,
    "estimated_total_loss_krw": 67130
  }
  ```

### 2-5. 헬스 체크

#### `GET /api/v1/health`

- **인증:** 없음
- **응답 200:** `{ "status": "ok", "uptime_sec": 12345, "schema_version": "0.2.0" }`
- **응답 503:** `{ "status": "degraded", "issues": ["db_slow", "ntp_drift_3s"] }`

---

## 3. WebSocket — 실시간 알림

### 3-1. 연결

- **URL:** `ws://backend/ws/v1/events?token=<jwt_access>`
- **인증:** Query string 의 JWT (header 안 됨 — 브라우저 제약)
- **연결 실패 시:** 401 코드 + close

### 3-2. 서버 → 클라이언트 메시지 (JSON)

```jsonc
{ "type": "event_new",          "data": <Event v0.2.0> }
{ "type": "event_updated",      "data": <Event v0.2.0> }  // afc_match 채워졌을 때 등
{ "type": "review_queue_added", "data": { "queue_id": "rq_...", "event_id": "evt_..." } }
{ "type": "heartbeat",          "data": { "ts": "..." } }  // 30초마다
```

### 3-3. 클라이언트 → 서버 메시지 (옵션)

```jsonc
{ "type": "subscribe",   "data": { "gate_section_ids": ["gate_01"] } }  // 필터 구독
{ "type": "unsubscribe", "data": { "gate_section_ids": ["gate_01"] } }
```

기본: 인증된 사용자는 모든 이벤트 수신. subscribe 호출하면 그 게이트로 필터.

### 3-4. 재연결 정책

- 클라이언트가 heartbeat 30초 동안 없으면 close + 재연결 시도
- 지수 백오프: 1s, 2s, 4s, 8s, 16s, 30s, 30s, ...
- 재연결 시: 마지막 수신한 `event_id` 를 query 로 `?since=evt_xyz` 전달 → 백엔드가 누락분 일괄 push

### 3-5. 대안: SSE (Server-Sent Events)

WebSocket 구현 부담 시 SSE 로 대체 가능 — 단방향 (서버→클라) 이지만 알림용으로 충분. URL 만 `/sse/v1/events?token=...` 로 바뀌고 나머지 동일.

---

## 4. 에러 응답 공통 형식

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "card_id_hash does not match pattern",
    "details": {
      "field": "card_id_hash",
      "value": "abc..."
    },
    "request_id": "req_abc123"
  }
}
```

### 4-1. 표준 코드

| HTTP | code | 의미 |
|------|------|------|
| 400 | `VALIDATION_FAILED` | 스키마 검증 실패 |
| 400 | `BAD_REQUEST` | 일반 요청 오류 |
| 401 | `AUTH_REQUIRED` | 인증 헤더 없음 |
| 401 | `AUTH_INVALID` | 토큰 만료/유효하지 않음 |
| 403 | `FORBIDDEN` | 권한 없음 (role 부족) |
| 404 | `NOT_FOUND` | 리소스 없음 |
| 409 | `CONFLICT` | 동시 수정 충돌 (의심 큐 등) |
| 422 | `BUSINESS_RULE_VIOLATION` | 비즈니스 규칙 위반 |
| 429 | `RATE_LIMITED` | 레이트 리밋 초과 |
| 500 | `INTERNAL_ERROR` | 서버 내부 오류 |
| 503 | `SERVICE_UNAVAILABLE` | DB 다운 등 |

### 4-2. 재시도 정책

| 에러 | 클라이언트 동작 |
|------|---------------|
| 4xx (400-499) | 재시도 ❌ (요청 자체 문제) — 단 401 은 토큰 갱신 후 1회 재시도 |
| 429 | `Retry-After` 헤더 존중 후 재시도 |
| 5xx, timeout | 지수 백오프 (1s, 2s, 4s, ..., 최대 5회) |
| 네트워크 단절 | AI 트랙: `events_failed.jsonl` fallback. 백엔드 복구 시 수동 또는 자동 재전송 (미정) |

---

## 5. 멱등성 (Idempotency)

### 5-1. 이벤트 발행

- 발행자 (AI 또는 백엔드 매칭 엔진) 가 발급하는 `event_id` 가 멱등성 키
- 백엔드는 같은 `event_id` 재수신 시 **200 OK + `deduped: true`** 응답 (저장 1회만)
- AI 재시도 안전 보장

### 5-2. fare_tap 발행

- Mock AFC 송신기가 발급하는 `fare_tap_id` 가 멱등성 키 (v0.2.1 신규)
- 백엔드는 같은 `fare_tap_id` 재수신 시 **200 OK + `deduped: true`**

### 5-3. 의심 큐 피드백

- 동일 `queue_id` 에 대해 2명 이상 동시 피드백 → 첫 번째 성공, 두 번째 409 Conflict

---

## 6. 시퀀스 다이어그램

### 6-1. AI 이상 행동 발행 → 알림 → 표시 (jump 등)

```
AI                백엔드              프론트엔드           역무원
 │                  │                   │                  │
 │ POST /events ───→│                   │                  │
 │ (event_type=jump)│                   │                  │
 │                  │ DB 저장             │                  │
 │                  │ schema 검증         │                  │
 │←─ 201 +────────  │                   │                  │
 │   event_id       │                   │                  │
 │                  │ WS push ─────────→│                  │
 │                  │ (event_new)       │ 화면 갱신          │
 │                  │                   │ 알림음 재생 ──────→│
```

### 6-2. confirmed_unpaid 워크플로우 (정상 통과인데 결제 없음 = 무임 확정)

```
AI                       백엔드              Mock AFC
 │                          │                  │
 │ POST /events             │                  │
 │ (event_type=gate_passage,│                  │
 │  t=10:00:00.500)         │                  │
 │ ───────────────────────→│                  │
 │←─ 201 + event_id (P1)    │                  │
 │                          │ ±1초 윈도우 검색
 │                          │ → fare_tap 없음
 │                          │ ⏰ 1초 대기 (혹시 늦게 오는지)
 │                          │ → 여전히 없음
 │                          │ ▶ emit confirmed_unpaid
 │                          │   (source_event_id=P1, severity=critical)
 │                          │ ─────WS push─→ 프론트엔드 (긴급 알림)
```

### 6-3. AFC 매칭 성공 (정상 결제) — 알림 없음

```
AI                       백엔드              Mock AFC
 │                          │                  │
 │                          │←POST /fare-taps──│ (사람이 카드 찍음, t=10:00:00.300)
 │                          │  201 + tap_id ──→│
 │ POST /events             │
 │ (event_type=gate_passage,│
 │  t=10:00:00.500)         │
 │ ───────────────────────→│
 │←─ 201                    │
 │                          │ ±1초 윈도우 검색
 │                          │ → fare_tap 발견 (Δt=200ms)
 │                          │ FareMatch.create
 │                          │ gate_passage.afc_match 업데이트
 │                          │ card_category=regular → misuse 아님
 │                          │ ▶ (별도 알림 없음, DB 만 업데이트)
```

### 6-4. confirmed_misuse 워크플로우 (우대카드 부정사용)

```
AI                                    백엔드                  Mock AFC
 │                                       │                       │
 │                                       │←POST /fare-taps───────│ (senior 카드, t=10:00:00.301)
 │                                       │  card_category=senior
 │                                       │  201 + tap_id ───────→│
 │ POST /events                          │
 │ (event_type=gate_passage,             │
 │  signals.senior_probability=0.11,     │  ← AI 의 senior_classifier 가 채움
 │  reliability=high,                    │
 │  t=10:00:00.300)                      │
 │ ────────────────────────────────────→│
 │←─ 201 + event_id (GP1)                │
 │                                       │ ±1초 윈도우 검색
 │                                       │ → fare_tap 발견 (Δt=-1ms)
 │                                       │ card_category=senior + senior_probability<0.20
 │                                       │ + reliability=high → misuse 조건 충족
 │                                       │ ▶ emit confirmed_misuse
 │                                       │   (source_event_id=GP1, severity=warning)
 │                                       │ ▶ review_queue 자동 추가
 │                                       │ ─WS push─→ 프론트엔드 (의심 큐 알림)
```

### 6-5. 의심 큐 검토 (역무원 워크플로우)

```
백엔드           프론트엔드          역무원
 │                  │                  │
 │ WS push ────────→│                  │
 │ (review_queue_added)
 │                  │ "의심 큐 1건 새로 들어옴" 알림
 │                  │←── 화면 진입 ─────│
 │← GET /review-queue
 │  data: [...] ──→│ 목록 표시
 │                  │←── 영상 클립 클릭 ─│
 │← GET /video-clip
 │  302 redirect ─→│ 영상 재생
 │                  │←── [정탐] 클릭 ────│
 │← POST /feedback {decision: "confirmed"}
 │  200 OK ───────→│
 │ DB 업데이트
```

---

## 7. Mock AFC 송신기 명세

### 7-1. JSONL 파일 replay (옵션 A)

- 형식: 한 줄당 fare_tap v0.2.0 JSON
- 실행: `python scripts/replay_afc.py --file mocks/afc.jsonl --speed 1.0`
- 동작: 파일의 첫 timestamp 를 현재 시각으로 보정, 이후 timestamp 간격대로 POST /fare-taps 호출
- 인증: env `AFC_SERVICE_TOKEN`

### 7-2. Mock HTTP 송신기 (옵션 B)

- FastAPI 작은 서버, `/mock/send-tap` 으로 POST 받으면 백엔드 `/api/v1/fare-taps` 로 전달
- 통합 테스트용

### 7-3. 수동 UI (옵션 C, 발표용)

- 프론트엔드의 "Mock AFC 송신" 페이지 (운영 환경에서는 숨김)
- 카드 종류 선택 (regular/senior/...) + 게이트 선택 + 결과 (approved/denied)
- "전송" 클릭 → 백엔드 `/api/v1/fare-taps` 호출 (서비스 토큰)

---

## 8. CORS / Rate Limiting / 보안

### 8-1. CORS (프론트엔드용)

- 허용 origin: `https://gateguard.<env>.app` + 개발용 `http://localhost:3000`
- 허용 메서드: GET / POST / PUT / DELETE / OPTIONS
- credentials: include (refresh token 쿠키용, MVP 는 body 전달 OK)

### 8-2. Rate Limiting

| API | 제한 |
|-----|------|
| POST /api/v1/events (AI) | 100 req/sec (per token) |
| POST /api/v1/fare-taps (Mock AFC) | 100 req/sec (per token) |
| 사용자 API (JWT) | 60 req/min (per user) |
| POST /api/v1/auth/login | 5 req/min (per IP) — brute force 방지 |

429 응답 시 `Retry-After` 헤더 동봉.

### 8-3. 보안 의무사항

- 모든 HTTP 통신 = HTTPS (개발 환경 제외)
- `card_id_hash` 는 수신 즉시 검증 (`^sha256:[a-f0-9]{64}$`) — 원본 카드 ID 절대 저장 X
- `CARD_HASH_SALT` env 로 백엔드가 salt 보관 (운영 환경별 분리)
- 영상 클립 URL = 서명된 시간제한 URL (5분 유효)
- 영상 클립 24시간 후 자동 삭제 (스케줄러)
- JWT secret 은 환경 변수, 회전 가능

---

## 9. 시간 동기화

### 9-1. 의무사항

- AI 서버, 백엔드 서버, Mock AFC 송신기 모두 **NTP 동기화** (`chronyd` 또는 `ntpd`)
- 모든 timestamp **UTC ISO-8601 timezone-aware** (`+00:00` 필수)
- 시계 오차 ≥ 2초 → 백엔드 `/api/v1/health` 가 503 + `issues: ["ntp_drift_Xs"]` 반환

### 9-2. 검증

- 백엔드 헬스 체크가 각 트랙의 시간 보고:
  - AI 가 발행하는 Event.timestamp 와 백엔드 수신 시각 비교
  - fare_tap 도 동일
- 운영 시 Prometheus 메트릭으로 노출 (P1)

---

## 10. 버저닝

### 10-1. 스키마 vs API URL

- **스키마 (data)**: SemVer (`v0.2.0`). 변경 시 `packages/schema/VERSIONING.md` 업데이트
- **API URL (transport)**: `/api/v1/...` — major 변경 시 `/api/v2/` 로 분기 (v0.x 스키마라도 URL 은 v1 시작)

### 10-2. 호환성 정책

| 변경 종류 | 스키마 버전 | API URL |
|----------|-----------|---------|
| optional 필드 추가 | MINOR (0.x.0 → 0.(x+1).0) | URL 그대로 |
| required 필드 추가 | MAJOR (MVP 기간은 0.x.0 → 0.(x+1).0 허용) | URL 그대로 |
| 필드 제거/이름 변경 | MAJOR | 새 endpoint 또는 v2 분기 검토 |
| 호환 가능 (예제만) | PATCH | URL 그대로 |

MVP 기간 (v0.x) 은 BREAKING 자유. v1.0 진입 후 엄격 적용.

---

## 11. 매칭 엔진 운영 정책 (corner case 결정)

> 실무 배포 시 발생 가능한 분산 시스템 corner case 를 모두 default 로 결정. 4트랙 개발자는 이 정책 그대로 구현.

### 11-1. `fare_tap.result` 별 처리

| result | 매칭 사용 | 저장 | confirmed_unpaid 발화? |
|--------|---------|------|---------------------|
| `approved` | ✅ | ✅ | gate_passage 와 매칭 시 발화 안 함 (정상) |
| `denied` | ❌ (매칭 키 X) | ✅ (통계용) | 같은 카드/게이트에서 ±1초 내 approved 가 없으면 → 결제 실패 후 통과 = 무임 → confirmed_unpaid 발화 |
| `error` | ❌ | ✅ (장애 분석) | 매칭 미사용. 별도 alert (운영 시스템) |

**denied 후 approved 시퀀스 (정상):**
```
1. fare_tap denied (잔액 부족)  ┐
2. fare_tap approved (재시도)   ├ 둘 다 저장. approved 만 매칭 사용
3. gate_passage                 ┘
```

### 11-2. 이벤트 도착 순서 (buffer 정책)

매칭 엔진은 **양방향 1초 buffer**:

```
fare_tap 도착 시:    1초 동안 보관. gate_passage 늦게 와도 매칭 가능.
gate_passage 도착 시: 1초 동안 보관. fare_tap 늦게 와도 매칭 가능.
1초 경과 후:         매칭 안 됐으면 → fare_tap 은 "unmatched" 마킹 (소거 X, 통계용)
                                    gate_passage 는 → confirmed_unpaid 발행
```

→ **confirmed_unpaid 발행은 항상 gate_passage 도착 + 1초 후.** 즉시 발행 X.

### 11-3. 다중 매칭 충돌

**Case A — 한 fare_tap 에 gate_passage 후보 여러 개 (예: 1초 내 2명 통과):**
1. 시간 가장 가까운 gate_passage 1개에 매칭
2. 나머지 gate_passage 는 다른 fare_tap 후보 검색 → 없으면 confirmed_unpaid

**Case B — 한 gate_passage 에 fare_tap 후보 여러 개 (드물지만 가능):**
1. 시간 가장 가까운 fare_tap 1개에 매칭
2. 나머지 fare_tap 은 다른 gate_passage 후보 검색 → 없으면 unmatched

**Case C — tailgating (1결제 2명 통과):**
- 첫 번째 (시간 가까운) 사람 → fare_tap 과 매칭
- 두 번째 사람 → fare_tap 없음 → confirmed_unpaid
- 동시에 AI 의 `tailgating` event 도 발행됨 → 백엔드가 두 event 묶어서 알림 우선순위 ↑

### 11-4. Occlusion / Track ID 끊김

**MVP 정책: track_id 끊기면 새 사람으로 취급.**
- 같은 사람이 occlusion 후 다른 track_id 받으면 → gate_passage 2번 발행
- 매칭 시 fare_tap 도 1번이면 → 1번은 매칭, 나머지는 confirmed_unpaid (false positive 가능)
- **운영 통계로 false positive 비율 모니터링 → Phase 2 에서 re-identification 도입**

### 11-5. Multi-camera

**MVP 정책: 한 게이트 = 한 카메라 가정.**
- 한 게이트를 여러 카메라가 동시 모니터링하지 않음 (cost / 복잡도)
- 운영 시 (Phase 2): camera 별 zone 정의 + 같은 gate_section_id 에 대한 multi-camera dedupe 검토

### 11-6. WebSocket JWT 만료

```
정상 흐름:
  access token 만료 5분 전 → 클라이언트가 /api/v1/auth/refresh 호출 → 새 access token 받음
  → WebSocket 끊고 새 토큰으로 재연결 (4-stage handshake)

만료 후:
  서버: WebSocket close code 4401 + reason "token_expired"
  클라이언트: 4401 받으면 → refresh → 재연결 → ?since=<last_event_id> 로 누락분 동기화
```

### 11-7. CARD_HASH_SALT 정책

```
MVP: 정적 salt. 한 번 정하면 운영 종료까지 유지.
운영 (Phase 2): 분기 회전. 회전 시:
  1. 새 salt 활성화 시점 t0 결정
  2. t0 이전 fare_tap 은 old salt hash, t0 이후는 new salt hash
  3. DB 에 salt_version 컬럼 추가 (old/new)
  4. 매칭 시 같은 salt_version 끼리만 매칭
```

**보안 의무:**
- Mock AFC 송신기와 백엔드가 같은 `CARD_HASH_SALT` env 공유 (인프라 트랙이 secrets manager 로 주입)
- `.env` 파일 절대 git 커밋 금지 → `.env.example` 만 커밋

### 11-8. Mock AFC 송신기 fallback

AI 의 HttpPublisher 와 동일 패턴:

```python
# Mock AFC 송신기 (백엔드 트랙이 만듦)
def send_fare_tap(payload):
    try:
        resp = requests.post(BACKEND_URL + "/api/v1/fare-taps", json=payload, ...)
        if resp.status_code < 300:
            return True
    except:
        pass
    # 실패 시 local fallback
    with open("runs/mock_afc_failed.jsonl", "a") as f:
        f.write(json.dumps(payload) + "\n")
    return False

# 복구 후 수동 또는 cron 으로 재전송:
#   python scripts/replay_failed.py --file runs/mock_afc_failed.jsonl
```

### 11-9. review_queue 적체 / SLA

**MVP:** SLA 없음. status 는 `pending` / `confirmed` / `false_positive` 3개.
**운영 (Phase 2):**
- pending 48시간 초과 → 자동 `escalated` status 로 전환
- 일일 적체 알림 (운영자 대시보드에 "검토 대기 N건 / 24h 이상 적체 M건")

### 11-10. 매칭 엔진 다운 / 복구

매칭 엔진은 **idempotent stateless worker**:

```
정상 상태:
  events / fare_taps DB 에 unmatched 마킹된 행 존재
  매칭 엔진이 5초마다 polling → unmatched 처리 → 결과 저장

다운 시:
  unmatched 행이 쌓임 (DB 에 보존)

복구 후:
  같은 polling 재개 → 시간순으로 처리 → catch-up
  (timestamp 기반 매칭이므로 처리 지연돼도 결과 동일)
```

**구현:**
- 매칭 엔진은 stateless. 멱등. 동시 instance 여러 개 가능 (DB 의 row-level lock)
- 처리 완료된 행은 `matched_at` 타임스탬프 마킹 → polling 시 제외

### 11-11. 백엔드 (events) 다운 / 복구

```
AI 트랙:    events_failed.jsonl 에 fallback 저장 (이미 구현)
Mock AFC:  mock_afc_failed.jsonl 에 fallback 저장 (§11-8)
복구 후:    cron 으로 매 5분 재전송 시도 (멱등 키 덕분에 중복 안전)
           수동 재전송: python scripts/replay_failed.py --file <jsonl>
```

### 11-12. 시계 오차 detection + 대응

```
백엔드의 비동기 워커가 매 1분:
  1. AI 트랙 최근 100개 event 의 (저장시각 - timestamp) 평균 측정
  2. AFC 트랙 최근 100개 fare_tap 의 같은 메트릭 측정
  3. |drift| > 2초 → /api/v1/health 가 503 + issues: ["ai_clock_drift_3s"]

매칭 윈도우 자동 확장 안 함 (정확도 우선). 운영자가 NTP 수동 점검.
```

---

## 12. 관측가능성 (Observability) — MVP

### 12-1. 로깅 (구조화 JSON)

모든 트랙이 다음 형식의 JSON 로그:

```json
{
  "ts": "2026-05-28T03:42:11.123Z",
  "level": "INFO|WARN|ERROR",
  "service": "ai|backend|frontend|mock_afc",
  "event_id": "evt_...",        // 있으면 동봉 (이벤트 추적)
  "fare_tap_id": "tap_...",      // 있으면 동봉
  "request_id": "req_...",       // HTTP 요청별 trace ID
  "msg": "사람이 읽는 메시지",
  "data": { ... }                // 자유 필드
}
```

**필수 로깅 시점:**
- AI: event 발행 시 (event_id + event_type)
- 백엔드: 모든 API 요청 (request_id + path + status + duration_ms)
- 백엔드: 매칭 엔진 매칭 성공 / 실패 (event_id + fare_tap_id or None)
- 백엔드: confirmed_* 발행 (event_id + source_event_id)
- Mock AFC: fare_tap 발행 (fare_tap_id)

### 12-2. 메트릭 (MVP — 백엔드 `/api/v1/health` 만)

```
GET /api/v1/health
응답 200 OK:
{
  "status": "ok",
  "uptime_sec": 12345,
  "schema_version": "0.2.1",
  "metrics": {
    "events_received_per_min": 42,
    "fare_taps_received_per_min": 30,
    "unmatched_gate_passage_count": 3,
    "review_queue_pending_count": 5,
    "ai_clock_drift_sec": 0.1,
    "afc_clock_drift_sec": 0.2
  }
}
```

**Phase 2 (운영):** Prometheus exporter + Grafana 대시보드.

### 12-3. Alert (실시간)

| 상황 | 채널 | 우선순위 |
|------|------|---------|
| `confirmed_unpaid` 발행 | WebSocket push (`severity: critical`) | 즉시 |
| `confirmed_misuse` 발행 | WebSocket push (`severity: warning`) | 즉시 |
| jump/tailgating 발화 (gate_passage 매칭 없음) | WebSocket push (`severity: critical`) | 즉시 |
| 시계 drift > 2초 | `/api/v1/health` 503 | 운영자 monitoring |
| AI 트랙 연결 끊김 (5분 동안 event 없음) | 운영자 console | 5분 |
| 백엔드 DB 다운 | `/api/v1/health` 503 | 즉시 (운영) |

**MVP:** Alert 채널은 WebSocket + 대시보드만. Slack/email/SMS 는 Phase 2.

### 12-4. 추적 (Tracing)

MVP 는 구조화 로그의 `event_id` / `fare_tap_id` / `request_id` 로 grep 추적. 분산 트레이싱 (OpenTelemetry) 은 Phase 2.

---

## 13. 운영 환경 사양 (확정)

| 항목 | MVP | Phase 2 (운영) |
|------|-----|---------------|
| **DB** | PostgreSQL 15 + TimescaleDB (events / fare_taps 시계열) | 같음 + read replica |
| **백엔드 프레임워크** | FastAPI (Python 3.11) | 같음 |
| **프론트엔드** | React (Vite) + TypeScript | 같음 |
| **WebSocket 라이브러리** | 백엔드: `fastapi.WebSocket` / 프론트: native `WebSocket` API | 같음 |
| **JWT 라이브러리** | 백엔드: `python-jose` | 같음 |
| **영상 클립 저장** | 로컬 디스크 (`/var/lib/gateguard/clips/`) + 24h cron 삭제 | S3 + lifecycle policy |
| **Mock AFC 송신기** | Python 스크립트 (`apps/backend/scripts/mock_afc/`) | 실제 AFC 연동 (PoC 협약) |
| **Rate limiting** | FastAPI middleware (`slowapi`) | 같음 + API gateway |
| **JWT secret 회전** | 정적 (재시작 시 invalidate) | 분기 회전 |
| **모니터링** | `/api/v1/health` polling | Prometheus + Grafana |
| **NTP** | `pool.ntp.org` (시스템 chronyd) | 운영사 NTP |
| **시간대** | UTC (모든 timestamp). 표시는 프론트엔드가 KST 변환 | 같음 |

→ 위 사양으로 4트랙 즉시 개발 시작 가능. 변경 시 4트랙 합의.

---

## 14. 관련 문서

- [`packages/schema/`](../packages/schema/) — 데이터 모양 (single source of truth)
- [`mvp-features.md`](mvp-features.md) — 무엇을 만드는가
- [`architecture.md`](architecture.md) — 시스템 전체 구조
- [`detection-strategy.md`](detection-strategy.md) — 무임승차 탐지 전략
- [`branching.md`](branching.md) — 브랜치/커밋 규칙
- [`release.md`](release.md) — 배포 순서 (특히 스키마 변경 시)
