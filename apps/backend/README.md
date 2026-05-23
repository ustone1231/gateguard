# apps/backend

GateGuard 백엔드 API.

## 책임
- AI 가 보낸 `Event` (POST `/api/events`) 수신 + DB 저장 (TimescaleDB)
- 운영자 인증 (JWT/OAuth2)
- 이벤트 조회 REST API
- WebSocket 으로 실시간 알림 push
- Celery + Redis 로 클립 생성 작업 큐잉
- 생성된 클립 URL 을 `Event.clip_url` 에 업데이트

## 스택
**미정.** 후보: FastAPI / Django / NestJS / Spring Boot.

결정되면:
1. 이 폴더에 코드 + Dockerfile 추가
2. 루트 `docker-compose.dev.yml` 의 `backend` 서비스 주석 해제
3. `.github/workflows/backend-ci.yml` 의 placeholder 를 실제 CI 로 교체

## 공통 스키마

받는 `Event` / 보내는 응답의 모양은 [`packages/schema/`](../../packages/schema/) 가 정의함.
백엔드는 여기를 import 해서 타입 검증.

## 시작하기 (스택 결정 후)
TODO
