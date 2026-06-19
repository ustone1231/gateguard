# GateGuard 문서 인덱스

이 폴더의 6개 문서는 각각 다른 질문에 답합니다.

## 어떤 질문 ↔ 어떤 문서

| 궁금한 것 | 읽을 문서 |
|-----------|-----------|
| **"이 프로젝트가 정확히 무엇을 푸는가?"** | [`detection-strategy.md`](detection-strategy.md) |
| "왜 CCTV 만으로는 무임승차를 못 잡는가? 결제 데이터는 어떻게 합치는가?" | [`detection-strategy.md`](detection-strategy.md) |
| "어떤 시나리오는 잡히고 어떤 건 못 잡는가?" | [`detection-strategy.md`](detection-strategy.md) §7 판정 매트릭스 |
| "시연 (MVP) 과 실서비스의 차이는?" | [`detection-strategy.md`](detection-strategy.md) §9 |
| **"MVP 에서 정확히 무엇을 개발하나? 무엇이 기존에서 바뀌었나?"** | [`mvp-features.md`](mvp-features.md) |
| "트랙별로 무엇을 만들어야 하나?" | [`mvp-features.md`](mvp-features.md) §4 |
| "5번째 룰 (우대카드 부정사용) 은 어떻게 감지?" | [`mvp-features.md`](mvp-features.md) §3-1 |
| "스키마 어떻게 바뀌나? (events/fare_tap v0.2.2)" | [`mvp-features.md`](mvp-features.md) §5 |
| "Mock AFC / Fine-tuning / 학습 전략?" | [`mvp-features.md`](mvp-features.md) §6, §9 |
| "AI 모델 signals가 현재 어디까지 검증됐나?" | [`ai-validation.md`](ai-validation.md) |
| "HF MiVOLO v2를 켜도 되는 기준은?" | [`ai-validation.md`](ai-validation.md) §운영 enable 기준 |
| "트랙 간 합의가 필요한 결정 목록?" | [`mvp-features.md`](mvp-features.md) §12 |
| **"트랙 간에 무슨 데이터를 어떻게 주고받나? (REST/WS/인증/에러)"** | [`api-contract.md`](api-contract.md) |
| "POST /api/v1/events 요청/응답 형식은?" | [`api-contract.md`](api-contract.md) §2 |
| "의심 큐 / 통계 / 영상 API 명세는?" | [`api-contract.md`](api-contract.md) §2-3, §2-4 |
| "실시간 알림 WebSocket 명세는?" | [`api-contract.md`](api-contract.md) §3 |
| "에러 응답 형식 / 재시도 / 멱등성?" | [`api-contract.md`](api-contract.md) §4, §5 |
| "AFC 매칭 워크플로우 시퀀스는?" | [`api-contract.md`](api-contract.md) §6 |
| "Mock AFC 송신기 명세?" | [`api-contract.md`](api-contract.md) §7 |
| **"시스템이 어떻게 구성돼 있나?"** | [`architecture.md`](architecture.md) |
| "어느 트랙이 무엇을 담당하나?" | [`architecture.md`](architecture.md) 트랙 책임 |
| "트랙 간 데이터 계약은 어디 정의?" | [`architecture.md`](architecture.md) → [`packages/schema/`](../packages/schema/) |
| **"브랜치 어디서 따고 어디로 PR 보내나?"** | [`branching.md`](branching.md) |
| "커밋 메시지 규칙?" | [`branching.md`](branching.md) |
| "릴리즈 절차는?" | [`branching.md`](branching.md) + [`release.md`](release.md) |
| **"버전 어떻게 매기고 배포는?"** | [`release.md`](release.md) |
| "스키마 바꿨는데 어떤 순서로 배포?" | [`release.md`](release.md) §트랙 간 의존성 변경 |
| "롤백 절차?" | [`release.md`](release.md) §롤백 |

## 문서별 한 줄 요약

### 🎯 [detection-strategy.md](detection-strategy.md) — "왜 그리고 무엇을"
무임승차 탐지가 단일 데이터 소스로는 풀리지 않는 이유 + CCTV (AI 행동 분석) 와 AFC (결제 트랜잭션) 를 합치는 전략 + 시나리오 판정 매트릭스 + MVP 시연 vs 실서비스 단계 + 윤리/법적 고려.

### 🛠 [mvp-features.md](mvp-features.md) — "무엇을 개발하고 무엇이 바뀌었나"
MVP 기능 명세 + 기존 설계 대비 변경 사항 (AI 행동 이벤트 + 백엔드 confirmed_* 판정, AFC 매칭, pose/age/eligibility_signals 모델 추가, 의심 큐 워크플로우) + 트랙별 (AI/CV, 백엔드, 프론트엔드, 인프라) 작업 정리 + 스키마 v0.2.2 변경 요약 + Mock AFC 전략 + Fine-tuning 전략 + 트랙 간 합의가 필요한 결정 목록.

### ✅ [ai-validation.md](ai-validation.md) — "AI가 현재 어디까지 검증됐나"
현재 `develop` 기준 AI/CV 구현 상태, HF MiVOLO v2 revision, 실제 영상 smoke 명령, 운영 enable 기준, 아직 말하면 안 되는 범위를 정리.

### 📡 [api-contract.md](api-contract.md) — "트랙 간에 무엇을 어떻게 주고받나"
REST endpoint 전체 명세 (이벤트 발행/조회, 의심 큐, 통계, 영상 클립, 인증, 헬스체크) + WebSocket 프로토콜 + JWT/서비스 토큰 인증 + 에러 응답 공통 형식 + 멱등성 / 재시도 정책 + 시퀀스 다이어그램 (이벤트 발행, AFC 매칭, misuse 의심 워크플로우) + Mock AFC 송신기 명세 + CORS / Rate Limiting / 시간 동기화.

### 🏗 [architecture.md](architecture.md) — "어떻게 구성했나"
트랙 분리 (AI / Backend / Frontend / Infra), 데이터 흐름, 공통 스키마 위치.

### 🌳 [branching.md](branching.md) — "어떻게 협업하나"
Git Flow (main / develop / feature/* / release/* / hotfix/*), 커밋 컨벤션, PR 흐름.

### 🚀 [release.md](release.md) — "어떻게 배포하나"
환경별 compose 분기, 트랙 간 의존성 변경 시 배포 순서, 롤백 절차, MVP 단계 간소화.

---

## 읽는 순서 (처음 합류한 경우)

1. **[detection-strategy.md](detection-strategy.md)** — 우리가 뭘 만드는지 (필수)
2. **[mvp-features.md](mvp-features.md)** — MVP 에서 정확히 무엇을 만드는지 (필수)
3. **[ai-validation.md](ai-validation.md)** — AI 트랙 현재 검증 상태와 남은 리스크
4. **[architecture.md](architecture.md)** — 어떻게 만드는지 (필수)
5. **[api-contract.md](api-contract.md)** — 본인이 백엔드/프론트엔드/Mock AFC 개발자라면 필수
6. 본인 트랙 README (예: [`apps/ai/README.md`](../apps/ai/README.md))
7. **[branching.md](branching.md)** — 첫 PR 올리기 전 (필수)
8. [release.md](release.md) — 릴리즈 작업 할 때

---

## 관련 (이 폴더 밖)

- [루트 README](../README.md) — 저장소 구조, 트랙별 진입점, 협업 규칙 한 페이지
- [공통 스키마 README](../packages/schema/README.md) — Event / GateSection / FareTap 정의
- 각 트랙 README — [`apps/ai`](../apps/ai/README.md) · [`apps/backend`](../apps/backend/README.md) · [`apps/frontend`](../apps/frontend/README.md) · [`apps/infra`](../apps/infra/README.md)
