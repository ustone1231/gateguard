## 어느 트랙
<!-- 해당하는 곳에 [x] 표시 -->
- [ ] AI / CV (`apps/ai`)
- [ ] 백엔드 (`apps/backend`)
- [ ] 프론트 (`apps/frontend`)
- [ ] 인프라 (`apps/infra`)
- [ ] 공통 스키마 (`packages/schema`)
- [ ] 루트 / 문서

## PR 종류 / base 브랜치 확인
<!-- 본 PR 의 base 가 맞는지 체크. 자세한 흐름은 docs/branching.md -->
- [ ] `feature/*` → `develop` (일상 작업, 95%)
- [ ] `release/*` → `main` (정식 릴리즈)
- [ ] `release/*` → `develop` (릴리즈 fix 역머지)
- [ ] `hotfix/*` → `main` + `develop` (긴급 수정)

## 무엇을, 왜
<!-- 한두 문장으로 -->

## 변경 사항
<!-- 주요 변경점 bullet -->
-
-

## 테스트
<!-- 어떻게 동작 확인했는지 -->
- [ ] 로컬에서 실행 확인
- [ ] 테스트 추가/수정 (해당되면)
- [ ] 다른 트랙에 영향 없음

## 스키마 변경?
<!-- packages/schema 건드린 경우만 -->
- [ ] 영향 받는 트랙: <!-- AI / BE / FE 등 -->
- [ ] 받는 쪽 (consumer) 먼저 배포되도록 순서 합의 완료

## 스크린샷 / 로그
<!-- UI/이벤트 결과물 있으면 -->

## 체크리스트
- [ ] CI 통과
- [ ] CODEOWNERS 리뷰 받음
- [ ] 관련 이슈 링크 (있으면): #
