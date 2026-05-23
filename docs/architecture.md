# GateGuard 아키텍처

## 전체 흐름

```
[CCTV]
  │  RTSP / mp4
  ▼
[apps/ai]                  YOLO + ByteTrack + 룰 (점프/기어/꼬리/우회)
  │  POST /api/events
  ▼
[apps/backend]             이벤트 저장 (TimescaleDB) + 알림 (WebSocket)
  │  REST + WS
  ▼
[apps/frontend]            운영자 대시보드 (실시간 알림, 클립 재생)

[apps/infra]               docker-compose / 배포 / 모니터링 = 위 전부 묶는 레이어
[packages/schema]          위 화살표가 운반하는 데이터의 단일 정의
```

## 트랙 책임

| 트랙 | 입력 | 출력 | 핵심 |
|------|------|------|------|
| AI  | 영상 프레임 | `Event` (JSON) | 탐지 + 추적 + 룰 |
| 백엔드 | `Event`, 운영자 요청 | DB, WS push, REST | 저장 + 조회 + 알림 |
| 프론트 | WS push, REST | UI | 실시간 알림, 클립 재생 |
| 인프라 | (위 셋의 컨테이너) | 한 번에 띄움 | 통합 / 배포 / 운영 |

## 데이터 흐름의 단일 정의

`Event` 와 `GateSection` 의 모양은 [`packages/schema`](../packages/schema/) 한 곳에서만 정의됨.
세 트랙(AI / 백엔드 / 프론트)이 모두 이걸 참조 → 깨지지 않음.

스키마 변경은 [release.md](release.md) 의 "트랙 간 의존성 변경" 규칙 준수.
