# apps/frontend

GateGuard 역무원 대시보드.

---

## 🚀 즉시 개발 시작 가이드

본 트랙 개발자는 다음 3개 문서를 먼저 읽으면 명세 100% 확보:

| 순서 | 문서 | 무엇이 적혀있나 |
|------|------|----------------|
| 1 | [`docs/mvp-features.md`](../../docs/mvp-features.md) §4-C | 만들어야 할 화면 + UI 요구사항 |
| 2 | [`docs/api-contract.md`](../../docs/api-contract.md) | 백엔드 REST + WebSocket 명세 + 인증 흐름 + 시퀀스 다이어그램 |
| 3 | [`packages/schema/`](../../packages/schema/) | 받는 Event / FareTap 데이터 모양 (TS 타입 생성용) |

→ 위 3개만 보면 더 묻지 않고 코딩 시작 가능.

---

## 책임

- 운영자 로그인 (백엔드 JWT)
- 실시간 이벤트 알림 (WebSocket `/ws/v1/events`)
- 이벤트 목록 + 필터 (날짜 / 게이트 / event_type / severity)
- 클립 재생 (`event.clip_url` — 백엔드 서명 URL)
- **의심 큐 페이지** ⭐ (confirmed_misuse 검토 + 정탐/오탐 라벨링)
- 통계 대시보드 (5종 비율 + 게이트별 hotspot + 손실 추정)
- 알림음 + 시각 강조 (severity 별 — info/warning/critical)
- (P1) Mock AFC 송신 UI (발표용 — 카드 종류 선택 + tap 버튼)
- (확장) Zone Editor — 카메라 영상 위에 polygon / entry_line / exit_line 그리기 → `GateSection` JSON export → AI 가 사용

---

## 스택 (확정)

| 항목 | 결정 |
|------|------|
| 빌드 도구 | Vite |
| 언어 | TypeScript |
| 프레임워크 | React 18 |
| 라우팅 | React Router v6 |
| 상태 관리 | Zustand 또는 TanStack Query (REST 캐싱) |
| WebSocket | native `WebSocket` API + 자동 재연결 wrapper |
| 차트 | Recharts 또는 Chart.js |
| UI | Tailwind CSS (선택), shadcn/ui |
| 알림음 | native `Audio().play()` (severity 별 다른 mp3) |

상세는 [`docs/api-contract.md`](../../docs/api-contract.md) §13.

---

## 시작하기

```bash
cd apps/frontend

# Node 18+ 권장
npm install

# 환경 변수
cp .env.example .env
# 편집:
#   VITE_API_BASE_URL=http://localhost:8000/api/v1
#   VITE_WS_URL=ws://localhost:8000/ws/v1/events

# 개발 서버
npm run dev
# → http://localhost:5173

# TS 타입 생성 (schema → TypeScript)
npx json-schema-to-typescript \
  ../../packages/schema/events/event.schema.json \
  -o src/types/event.ts
npx json-schema-to-typescript \
  ../../packages/schema/fare-taps/fare_tap.schema.json \
  -o src/types/fare_tap.ts
```

---

## 화면 구조 (라우트)

```
/login                  → 로그인 (백엔드 JWT)
/                       → 실시간 알림 대시보드 (홈)
/events                 → 이벤트 목록 + 필터
/events/:id             → 이벤트 상세 (영상 클립 + signals + afc_match)
/review-queue           → 의심 큐 (confirmed_misuse 검토)
/review-queue/:queue_id → 큐 항목 상세 (영상 + 정탐/오탐 버튼)
/stats                  → 통계 대시보드
/mock-afc               → (P1) Mock AFC 송신 UI (발표/시연용)
/zone-editor            → (확장) Polygon 편집
```

각 화면이 호출하는 API + WebSocket 메시지는 [`docs/api-contract.md`](../../docs/api-contract.md) §2, §3 참조.

---

## WebSocket 처리 (핵심)

```typescript
// JWT 만료 시 4401 close 처리 ([`api-contract.md`](../../docs/api-contract.md) §11-6)
const ws = new WebSocket(`${WS_URL}?token=${accessToken}`);
ws.onclose = (ev) => {
  if (ev.code === 4401) {
    // token expired → refresh + 재연결
    refreshToken().then(newToken => connectWebSocket(newToken));
  } else {
    // 지수 백오프 재연결 (§3-4)
    setTimeout(() => reconnect(), backoff());
  }
};
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  switch (msg.type) {
    case "event_new":          handleNewEvent(msg.data); break;
    case "event_updated":      handleUpdatedEvent(msg.data); break;
    case "review_queue_added": handleReviewQueueAdded(msg.data); break;
    case "heartbeat":          /* 그냥 무시 */ break;
  }
};
```

재연결 시 `?since=<last_event_id>` 로 누락분 동기화.

---

## 알림음 (severity 별)

| severity | 음원 | 시각 강조 |
|----------|------|---------|
| `info` | 짧은 비프 (~0.2s) | 회색 텍스트 |
| `warning` | 비프 2번 | 노랑 background |
| `critical` | 사이렌 톤 (~1s) | 빨강 깜빡임 (CSS animation) |

브라우저 알림 권한 요청 필수 (`Notification.requestPermission()`).

---

## CI/CD

`.github/workflows/frontend-ci.yml`:
- TS 컴파일 + lint (eslint + prettier)
- vitest 단위 테스트
- Playwright e2e (있으면)
- 빌드 → Docker 이미지
