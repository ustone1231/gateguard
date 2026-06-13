# @gateguard/schema

GateGuard 트랙 간 공통 데이터 계약. **모든 트랙이 여기를 참조**합니다.

## 왜 별도 패키지?

- AI 가 만들고 → 백엔드가 받고 → 프론트가 보여주는 데이터(`Event`, `GateSection`)는
  세 트랙이 똑같이 이해해야 깨지지 않음.
- 한 곳에 두면 변경 이력 추적 / 버전 관리가 단일.

## 변경 규칙

스키마는 트랙 간 **단일 진실(single source of truth)** 이므로, 변경 시 절차:

1. 본 폴더에 PR (필드 추가/이름 변경/타입 변경 등)
2. CODEOWNERS 가 백엔드 / AI / 프론트 리더 자동 호출
3. 머지되면 슬랙 #gateguard-dev 공지
4. **"받는 쪽" 먼저 새 버전 배포, "보내는 쪽" 나중에 배포** (호환성)

## 파일

| 파일 | 설명 |
|------|------|
| `events/event.schema.json` | AI → 백엔드로 POST되는 이벤트. gate_passage 에 연령/성별 보조 신호(`signals`)를 실을 수 있음 |
| `sections/gate_sections.schema.json` | 카메라별 polygon / entry_line / exit_line |
| `fare-taps/fare_tap.schema.json` | AFC(카드 리더) → 백엔드로 POST되는 결제 트랜잭션. `card_category`, `holder_gender` 를 Event signals 와 ±1초 윈도로 cross-check |
| `examples/event_jump.json` | jump 이벤트 샘플 |
| `examples/gate_sections_sample.json` | 카메라 1대 섹션 샘플 |
| `examples/fare_tap_approved.json` | 결제 성공 fare_tap 샘플 |
| `examples/fare_tap_denied.json` | 결제 실패 (잔액 부족) fare_tap 샘플 |
| `VERSIONING.md` | 호환성 정책 / 버전 변경 이력 |

## 왜 fare_tap 이 별도 이벤트인가

AI 의 `Event` 는 "행동 발견" (점프/꼬리물기/통과 등) 을 표현하고,
`fare_tap` 은 "결제 트랜잭션" 을 표현합니다. 두 스트림은 발행자도, 시간 정밀도도,
개인정보 민감도도 다르므로 스키마를 분리. 백엔드 매칭 엔진이 이 둘을 매칭해서
무임승차 및 우대 자격 불일치를 확정합니다. 상세 전략: [`docs/detection-strategy.md`](../../docs/detection-strategy.md).

## 버저닝

SemVer 사용. `v0.x` = MVP (호환성 깰 수 있음), `v1.0` = 안정화 후.
