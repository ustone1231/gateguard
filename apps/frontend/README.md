# apps/frontend

GateGuard 운영자 대시보드.

## 책임
- 운영자 로그인 (백엔드 JWT/OAuth2)
- 실시간 이벤트 알림 (WebSocket 수신)
- 이벤트 목록 + 필터 (날짜, 카메라, event_type)
- 클립 재생 (`Event.clip_url`)
- (확장) Zone Editor — 카메라 영상 위에 polygon / entry_line / exit_line 그리기
  → `packages/schema` 의 `GateSection` 형식으로 export → AI 가 그대로 사용

## 스택
**미정.** 후보: React (Next.js) / Vue / Svelte.

결정되면:
1. 이 폴더에 코드 + Dockerfile
2. 루트 `docker-compose.dev.yml` 의 `frontend` 서비스 주석 해제
3. `.github/workflows/frontend-ci.yml` 채움

## 공통 스키마

수신/표시할 `Event`, 편집할 `GateSection` 의 모양은 [`packages/schema/`](../../packages/schema/) 정의.
TypeScript 라면 `json-schema-to-typescript` 등으로 타입 생성 추천.

## 시작하기 (스택 결정 후)
TODO
