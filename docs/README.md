# GateGuard 문서 인덱스

이 폴더의 4개 문서는 각각 다른 질문에 답합니다.

## 어떤 질문 ↔ 어떤 문서

| 궁금한 것 | 읽을 문서 |
|-----------|-----------|
| **"이 프로젝트가 정확히 무엇을 푸는가?"** | [`detection-strategy.md`](detection-strategy.md) |
| "왜 CCTV 만으로는 무임승차를 못 잡는가? 결제 데이터는 어떻게 합치는가?" | [`detection-strategy.md`](detection-strategy.md) |
| "어떤 시나리오는 잡히고 어떤 건 못 잡는가?" | [`detection-strategy.md`](detection-strategy.md) §7 판정 매트릭스 |
| "시연 (MVP) 과 실서비스의 차이는?" | [`detection-strategy.md`](detection-strategy.md) §9 |
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

### 🏗 [architecture.md](architecture.md) — "어떻게 구성했나"
트랙 분리 (AI / Backend / Frontend / Infra), 데이터 흐름, 공통 스키마 위치.

### 🌳 [branching.md](branching.md) — "어떻게 협업하나"
Git Flow (main / develop / feature/* / release/* / hotfix/*), 커밋 컨벤션, PR 흐름.

### 🚀 [release.md](release.md) — "어떻게 배포하나"
환경별 compose 분기, 트랙 간 의존성 변경 시 배포 순서, 롤백 절차, MVP 단계 간소화.

---

## 읽는 순서 (처음 합류한 경우)

1. **[detection-strategy.md](detection-strategy.md)** — 우리가 뭘 만드는지 (필수)
2. **[architecture.md](architecture.md)** — 어떻게 만드는지 (필수)
3. 본인 트랙 README (예: [`apps/ai/README.md`](../apps/ai/README.md))
4. **[branching.md](branching.md)** — 첫 PR 올리기 전 (필수)
5. [release.md](release.md) — 릴리즈 작업 할 때

---

## 관련 (이 폴더 밖)

- [루트 README](../README.md) — 저장소 구조, 트랙별 진입점, 협업 규칙 한 페이지
- [공통 스키마 README](../packages/schema/README.md) — Event / GateSection / FareTap 정의
- 각 트랙 README — [`apps/ai`](../apps/ai/README.md) · [`apps/backend`](../apps/backend/README.md) · [`apps/frontend`](../apps/frontend/README.md) · [`apps/infra`](../apps/infra/README.md)
