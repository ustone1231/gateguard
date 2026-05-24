# GateGuard 아키텍처

> 이 문서는 **"어떻게 만들었나"** (트랙 분리, 기술 스택, 데이터 흐름) 를 다룹니다.
> **"왜 그렇게 만들었나"** (무임승차 탐지 전략, AI + AFC 매칭 근거) 는
> [detection-strategy.md](detection-strategy.md) 를 보세요.

## 전체 흐름

```
[CCTV]                        [게이트 카드 리더 / AFC]
  │  RTSP / mp4                 │  탭 트랜잭션
  ▼                             ▼
[apps/ai]                     [AFC 시스템 또는 Mock 시뮬레이터]
YOLO + ByteTrack + 룰          fare_tap 이벤트 발행
(점프/기어/꼬리/우회)
  │  POST /api/events           │  POST /api/fare-taps
  └──────────┬──────────────────┘
             ▼
[apps/backend]    이벤트 저장 (TimescaleDB) + 매칭 엔진 (±1초 윈도)
                  + 알림 (WebSocket)
             │  REST + WS
             ▼
[apps/frontend]   운영자 대시보드 (실시간 알림, 클립 재생, 매칭 결과)

[apps/infra]      docker-compose / 배포 / 모니터링 = 위 전부 묶는 레이어
[packages/schema] 위 화살표가 운반하는 데이터의 단일 정의
```

→ "AI 단독" 이 아니라 "**AI + AFC 결제 매칭**" 이 핵심.
근거와 시나리오별 판정 매트릭스는 [detection-strategy.md](detection-strategy.md) 참고.

## 트랙 책임

| 트랙 | 입력 | 출력 | 핵심 |
|------|------|------|------|
| AI  | 영상 프레임 | `Event` (JSON, 4종 룰 + gate_passage) | 탐지 + 추적 + 룰 |
| 백엔드 | `Event`, `fare_tap`, 운영자 요청 | DB, WS push, REST | 저장 + **매칭 엔진** + 조회 + 알림 |
| 프론트 | WS push, REST | UI | 실시간 알림, 클립 재생, 매칭 결과 표시 |
| 인프라 | (위 셋의 컨테이너 + Mock AFC) | 한 번에 띄움 | 통합 / 배포 / 운영 |

## 데이터 흐름의 단일 정의

`Event` 와 `GateSection` 의 모양은 [`packages/schema`](../packages/schema/) 한 곳에서만 정의됨.
세 트랙(AI / 백엔드 / 프론트)이 모두 이걸 참조 → 깨지지 않음.

스키마 변경은 [release.md](release.md) 의 "트랙 간 의존성 변경" 규칙 준수.
