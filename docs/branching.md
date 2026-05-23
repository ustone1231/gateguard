# 브랜치 전략 — Git Flow

GateGuard 는 **Git Flow** 모델을 씁니다. 브랜치 5종.

---

## 한 장으로 보는 그림

```
main      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━●  (production)
                       ▲                              ▲
                       │ release/v0.1.0 머지          │ hotfix 머지
                       │                              │
develop   ●━●━━●━━●━━━━●━━━●━━━●━━━●━━━━━━━━━━━━━━━━━●  (개발 통합)
            ▲      ▲       ▲       ▲
            │      │       │       │
       feature/x  feature/y  feature/z  ...           (작업)
       (개발 후 develop으로 머지)

                                          hotfix/auth-bug
                                          (main → 수정 → main + develop)
```

---

## 브랜치 5종

| 브랜치 | 용도 | 어디서 따고 | 어디로 머지 | 수명 |
|--------|------|-------------|-------------|------|
| `main` | production 코드 | — | `release/*`, `hotfix/*` 만 | 영구 |
| `develop` | 개발 통합 | `main` | `feature/*` 만 받음 | 영구 |
| `feature/*` | 새 기능 작업 | `develop` | `develop` | 단명 (며칠) |
| `release/*` | 릴리즈 준비 | `develop` | `main` + `develop` | 단명 (1~2일) |
| `hotfix/*` | 긴급 운영 수정 | `main` | `main` + `develop` | 단명 (몇 시간) |

---

## 일상 흐름 — feature 작업

**95% 의 작업은 이 흐름만 알면 됨.**

```bash
# 1. develop 에서 시작
git checkout develop
git pull

# 2. feature 브랜치 따기
git checkout -b feature/ai-day3-section-matcher

# 3. 작업 + 커밋
git add apps/ai/
git commit -m "feat: add section matcher"
git push -u origin feature/ai-day3-section-matcher

# 4. PR 만들기 (base: develop)
#    GitHub 웹에서 "Compare & pull request" 클릭
#    base: develop  ←  compare: feature/ai-day3-section-matcher
```

→ CODEOWNERS 가 자동 리뷰어 호출 (폴더 기준)
→ CI 통과 + 리뷰 승인 → **Squash & merge to develop**
→ 브랜치 자동 삭제 → 끝.

---

## release 흐름 — 정식 배포할 때

```bash
# 1. develop 에서 release 브랜치 따기
git checkout develop
git pull
git checkout -b release/v0.1.0
git push -u origin release/v0.1.0

# 2. release 브랜치에서만 하는 작업
#    - 버전 번호 bump
#    - CHANGELOG 작성
#    - 마지막 버그 수정 (새 기능 추가 X)

# 3. release → main 머지 (PR)
gh pr create --base main --head release/v0.1.0 --title "release: v0.1.0"
# 머지 후
git checkout main && git pull
git tag v0.1.0
git push --tags

# 4. release → develop 역머지 (release 동안의 fix 가져옴)
gh pr create --base develop --head release/v0.1.0 --title "back-merge: v0.1.0 fixes"

# 5. release 브랜치 삭제
git push origin --delete release/v0.1.0
```

---

## hotfix 흐름 — production 긴급 수정

```bash
# 1. main 에서 hotfix 브랜치 따기
git checkout main
git pull
git checkout -b hotfix/critical-auth-bug

# 2. 수정 + 커밋
git commit -m "fix: critical auth bypass"
git push -u origin hotfix/critical-auth-bug

# 3. PR 2개 (main + develop 양쪽으로 동시)
gh pr create --base main --head hotfix/critical-auth-bug
gh pr create --base develop --head hotfix/critical-auth-bug

# 4. 두 PR 모두 머지 후 새 패치 태그
git checkout main && git pull
git tag v0.1.1
git push --tags

# 5. hotfix 브랜치 삭제
git push origin --delete hotfix/critical-auth-bug
```

---

## 브랜치 명 컨벤션

```
feature/<짧은-설명>
  예: feature/ai-day3-section-matcher
      feature/be-events-api
      feature/fe-dashboard-layout
      feature/infra-docker-compose-prod

release/v<버전>
  예: release/v0.1.0

hotfix/<짧은-설명>
  예: hotfix/critical-auth-bug
```

**팁:** feature 브랜치 이름 앞에 트랙 prefix 붙이면 GitHub 브랜치 목록이 자동 정렬되어 보기 좋음 (`ai-`, `be-`, `fe-`, `infra-`).

---

## 커밋 메시지 prefix

```
feat:     새 기능
fix:      버그 수정
docs:     문서
refactor: 리팩터링
test:     테스트
chore:    기타 (CI, deps 등)
release:  릴리즈 (예: "release: v0.1.0")
```

---

## 트랙 분리는 폴더 + CODEOWNERS 가 담당

브랜치는 5종이지만, **트랙 (백엔드/AI/프론트/인프라) 은 폴더로 분리됨**:

```
apps/ai/        ← AI 트랙 코드 (담당자만 수정)
apps/backend/   ← 백엔드 트랙
apps/frontend/  ← 프론트 트랙
apps/infra/     ← 인프라 트랙
packages/schema/ ← 공통 스키마 (변경 시 모든 트랙 리더 호출)
```

PR 만들 때 [`.github/CODEOWNERS`](.github/CODEOWNERS) 가 폴더별로 자동 리뷰어 지정 → 트랙 권한 자동 적용.

---

## 브랜치 보호 (GitHub Settings → Branches)

| 브랜치 | 보호 룰 |
|--------|---------|
| `main` | PR 필수 · 1+ 리뷰 · CI 통과 · **admin 우회 금지** |
| `develop` | PR 필수 · 1+ 리뷰 · CI 통과 |
| `feature/*`, `release/*`, `hotfix/*` | 보호 없음 (작업 브랜치) |

---

## 한 줄 원칙

> **평소엔 feature → develop. 배포는 release → main. 긴급은 hotfix → main + develop.**
>
> 95% 의 작업은 첫 줄만 알면 됨.
