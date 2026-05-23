# 브랜치 전략 — Git Flow + 트랙 브랜치 하이브리드

GateGuard 는 **Git Flow + 트랙 브랜치** 하이브리드 모델을 씁니다.
정식 릴리즈 사이클 (main/develop/release/hotfix) + 트랙별 격리 (backend/ai/frontend/infra) 둘 다 가져옵니다.

---

## 브랜치 7종 한눈에

```
main      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ (production)
                       ▲                              ▲
                       │ release                      │ hotfix
                       │                              │
develop   ━━●━━━━━━━━━━●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ (integration)
            ▲          ▲          ▲          ▲
            │          │          │          │
   ┌────────┴────┐  ┌──┴────┐  ┌──┴────┐  ┌──┴────┐
   │  backend    │  │  ai   │  │ front │  │ infra │       (트랙)
   ▲             ▲  ▲      ▲   ▲     ▲    ▲      ▲
feat/be-       feat/ai- feat/fe-  feat/infra-              (feature)
 api-events    day3    dashboard  compose
```

| 브랜치 | 용도 | 따는 위치 | 머지 대상 | 보호 |
|--------|------|-----------|-----------|------|
| `main` | production 코드 | — | release/* + hotfix/* 만 | ★ 강 |
| `develop` | 통합 개발 | main | 트랙 브랜치만 | ★ 강 |
| `backend` | 백엔드 트랙 통합 | develop | develop | 중 |
| `ai` | AI 트랙 통합 | develop | develop | 중 |
| `frontend` | 프론트 트랙 통합 | develop | develop | 중 |
| `infra` | 인프라 트랙 통합 | develop | develop | 중 |
| `feature/*` | 작업 단위 | 자기 트랙 | 자기 트랙 | — |
| `release/*` | 릴리즈 준비 | develop | main + develop | — |
| `hotfix/*` | 긴급 운영 수정 | main | main + develop | — |

---

## 일상 흐름 (트랙 담당자)

### 작업 시작

```bash
# 1. 본인 트랙 브랜치로 이동 + 최신 동기화
git checkout ai          # 또는 backend / frontend / infra
git pull

# 2. 작업 브랜치 따기
git checkout -b feature/ai-day3-section-matcher
```

### 작업 진행

```bash
# 본인 트랙 폴더(apps/ai/)에서만 수정
git add apps/ai/
git commit -m "feat: add section matcher"
git push -u origin feature/ai-day3-section-matcher
```

### PR 생성 — **반드시 자기 트랙 브랜치로**

```
PR base: ai        ← 자기 트랙 브랜치
PR compare: feature/ai-day3-section-matcher
```

→ CODEOWNERS 가 AI 리더 자동 호출
→ ai-ci.yml 만 실행
→ 리뷰 승인 + CI 통과 → 머지
→ 브랜치 자동 삭제

### 트랙 → develop 동기화 (트랙 리더 책임)

**주 1~2회 또는 일정량의 feature 가 모이면 트랙 리더가 진행:**

```bash
# 1. develop 의 최신 변경을 트랙 브랜치에 먼저 받기 (역방향)
git checkout ai
git pull
git merge origin/develop      # 다른 트랙 변경 흡수
git push

# 2. 충돌 해결 + 테스트
# (이때 CI가 자동 실행됨)

# 3. 트랙 → develop PR
gh pr create --base develop --head ai \
  --title "merge: ai → develop (weekly sync)"
```

→ 다른 트랙 리더가 확인 후 머지

---

## release 사이클 (정식 릴리즈)

### 1. release 브랜치 따기

```bash
git checkout develop
git pull
git checkout -b release/v0.1.0
git push -u origin release/v0.1.0
```

### 2. release 브랜치에서 하는 작업

- 버전 번호 bump (`apps/*/version.txt` 또는 `package.json`)
- CHANGELOG 작성
- 마지막 QA + 버그 수정 (오직 fix 만, 새 기능 추가 X)

### 3. release → main 머지 (production 배포)

```bash
gh pr create --base main --head release/v0.1.0 \
  --title "release: v0.1.0"
# 머지 후
git checkout main
git pull
git tag v0.1.0
git push --tags
```

### 4. release → develop 역머지 (release 동안의 fix 반영)

```bash
gh pr create --base develop --head release/v0.1.0 \
  --title "back-merge: v0.1.0 fixes → develop"
```

### 5. release 브랜치 삭제

```bash
git push origin --delete release/v0.1.0
```

---

## hotfix 사이클 (긴급 수정)

production 에서 치명적 버그 발견 시:

```bash
# 1. main 에서 hotfix 브랜치 따기
git checkout main
git pull
git checkout -b hotfix/critical-auth-bug
# 수정
git commit -m "fix: critical auth bypass"
git push -u origin hotfix/critical-auth-bug

# 2. main 으로 PR (즉시 머지)
gh pr create --base main --head hotfix/critical-auth-bug

# 3. develop 으로도 동일 PR (수정 사항 반영)
gh pr create --base develop --head hotfix/critical-auth-bug

# 4. 새 패치 버전 태그
git checkout main && git pull
git tag v0.1.1 && git push --tags

# 5. hotfix 브랜치 삭제
git push origin --delete hotfix/critical-auth-bug
```

---

## 충돌 방지 규칙 (트랙 리더용)

1. **트랙 브랜치는 매주 1회 이상 develop 에서 pull** (충돌 누적 방지)
2. **feature 브랜치는 1주 이내 머지 끝내기** (장수하면 죽음)
3. **트랙 → develop 머지는 작게 자주** (분기당 1번 거대 머지 ✗)
4. **packages/schema 변경은 develop 에 직접 PR** (트랙 우회 — 모든 트랙이 영향받으므로)
5. **다른 트랙 폴더 건드릴 일 있으면** → 본인 트랙 PR 하지 말고, **develop 에 직접 PR** + 해당 트랙 리더 호출

---

## 브랜치 보호 룰 (GitHub Settings → Branches)

| 브랜치 패턴 | 설정 |
|------------|------|
| `main` | PR 필수, 1+ 리뷰, CI 통과, **admin도 우회 금지** |
| `develop` | PR 필수, 1+ 리뷰, CI 통과 |
| `backend`, `ai`, `frontend`, `infra` | PR 필수, 1+ 리뷰, CODEOWNERS 리뷰 필수 |
| `feature/*`, `release/*`, `hotfix/*` | 보호 없음 (작업 브랜치) |

---

## 브랜치 명 컨벤션

```
feature/<track-prefix>-<짧은설명>
  예: feature/ai-day3-section-matcher
      feature/be-events-api
      feature/fe-dashboard-layout
      feature/infra-docker-compose-prod

release/v<버전>
  예: release/v0.1.0
      release/v1.0.0

hotfix/<짧은설명>
  예: hotfix/critical-auth-bug
      hotfix/db-connection-leak
```

---

## 커밋 메시지 prefix

```
feat:     새 기능
fix:      버그 수정
docs:     문서
refactor: 리팩터링
test:     테스트
chore:    기타 (CI, deps 등)
merge:    트랙 간 머지 (예: "merge: ai → develop")
release:  릴리즈 (예: "release: v0.1.0")
```

---

## 시각화 (3주차쯤 모습)

```
main     ●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━●  (v0.1.0)
                                                    ▲
                                                    │
                                    release/v0.1.0 ●  (1주만 살다 머지)
                                                    ▲
develop  ●━━●━━●━━●━━●━━●━━●━━●━━●━━●━━●━━●━━●━━●━●
            ▲     ▲     ▲     ▲     ▲     ▲     ▲
            │     │     │     │     │     │     │
   (트랙 → develop 머지들. 작게 자주.)

ai       ●━━●━━●━━●━━●━━●━━●━━━━━━━━━━━━━━━━━━━━━━━●  (계속 살아있음)
            ▲     ▲     ▲
         feat/  feat/ feat/
         day3   day6  day10

backend  ●━━●━━●━━●━━●━━●━━●━━━━━━━━━━━━━━━━━━━━━━━●
            ▲     ▲     ▲
         feat/  feat/ feat/
         api   auth   ws
```

---

## 한 줄 원칙

> **feature → 트랙 → develop → release → main** 의 5단 흐름. hotfix 만 main 에서 직접 따고 main + develop 양쪽으로 머지.
