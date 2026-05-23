# GateGuard

지하철 무임승차 탐지 시스템 — AI/CV + Backend + Frontend + Infra 통합 모노레포.

> 6주 MVP + 1주 버퍼. CCTV 영상에서 점프 / 기어가기 / 꼬리물기 / 우회를 룰 기반으로 탐지하고,
> 백엔드가 이벤트를 저장 · 알림하며, 운영자 대시보드에서 클립을 확인.

---

## 저장소 구조

```
gateguard/
├── apps/
│   ├── ai/           # AI/CV 파이프라인 (Python, YOLO11 + ByteTrack + 룰)
│   ├── backend/      # API 서버 (스택 미정)
│   ├── frontend/     # 운영자 대시보드 (스택 미정)
│   └── infra/        # docker-compose / 배포 스크립트
├── packages/
│   └── schema/       # 공통 Event / GateSection JSON Schema (모든 트랙 참조)
├── docs/             # 아키텍처 / 합의 문서
├── docker-compose.dev.yml   # 4트랙 통합 dev 실행
└── .github/
    ├── CODEOWNERS    # 트랙별 자동 리뷰어
    └── workflows/    # 트랙별 CI (변경된 폴더만 돈다)
```

---

## 트랙별 진입점

| 트랙 | 폴더 | README |
|------|------|--------|
| AI / CV   | `apps/ai/`       | [apps/ai/README.md](apps/ai/README.md) |
| 백엔드    | `apps/backend/`  | [apps/backend/README.md](apps/backend/README.md) |
| 프론트    | `apps/frontend/` | [apps/frontend/README.md](apps/frontend/README.md) |
| 인프라    | `apps/infra/`    | [apps/infra/README.md](apps/infra/README.md) |
| 공통 스키마 | `packages/schema/` | [packages/schema/README.md](packages/schema/README.md) |

---

## 협업 규칙 (한 페이지)

### 권한 / 브랜치
- 모든 협업자에게 Write 권한 부여 (Org 멤버라면 자동).
- `main` 직접 push 금지 — **PR만**.
- 작업 브랜치 명: `feat/짧은설명`, `fix/짧은설명`, `chore/...`
- 머지 후 브랜치 삭제.

### "본인 트랙 폴더만 만진다"
- 시스템적 강제는 없지만, [`CODEOWNERS`](.github/CODEOWNERS) 가 본인 트랙 외 폴더를 건드린 PR에 다른 트랙 리더를 자동 리뷰어로 호출함.
- 즉 권한은 다 있지만 사회적 알람이 작동.

### 트랙 간 인터페이스 변경
- Event 페이로드 등 공통 스키마를 바꿔야 한다면 → **`packages/schema/` PR 먼저** → 슬랙 공지 → 각 트랙이 본인 폴더에서 따라옴.
- **순서: "받는 쪽 (consumer) 먼저 배포, 보내는 쪽 (producer) 나중"** — 안 그러면 잠깐 깨짐.

### 커밋 메시지
```
feat:   새 기능
fix:    버그 수정
docs:   문서
refactor: 리팩터링
test:   테스트
chore:  기타 (CI, deps 등)
```

### PR 머지 기준
- CI 통과
- CODEOWNERS 리뷰 1명 이상 승인
- 다른 트랙에 영향 있으면 그 트랙 리더 추가 승인

---

## 전체 dev 환경 한 번에 띄우기

```bash
docker compose -f docker-compose.dev.yml up
```

> 인프라 트랙이 채워 넣을 자리. 지금은 stub 상태.

---

## 릴리즈 절차

자세한 건 [docs/release.md](docs/release.md) 참고. 요약:

```
각 트랙: 자기 폴더의 코드/이미지 버전 태그 (semver)
        ↓
인프라:  docker-compose.prod.yml 에 "이 조합으로 간다" 명시
        ↓
인프라 레포 태그 (release-YYYY-MM-DD) = prod 배포 스냅샷
```

---

## 라이선스

미정 (MVP 단계). 사내 코드로 취급.
