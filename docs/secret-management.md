# Secret / 환경변수 관리 (인프라)

> 이슈 #13 인프라 액션 — GateGuard 의 dev/prod **secret 주입·분리 방식**을 정의한다.
> 트랙 경계: 컨테이너 **밖**(주입 메커니즘·`.env` 파일·운영 호스트) = 인프라 책임.
> 변수의 **이름/의미**는 각 트랙(backend·ai)이 소유하며, 이 문서는 그 이름을 그대로 재사용한다(인터페이스 신설 아님).

## 1. 원칙

- 단일 데스크탑 데모 호스트 전제 → Vault/secret manager 없이 **호스트 `.env` 파일** 방식.
- compose 에는 **실 secret 을 박지 않는다.** `${VAR:-dev기본값}` 보간으로 dev 는 무설정 기동, 실값은 `.env` / `.env.prod` 로 주입한다.
- dev 기본값은 **누구나 아는 무해한 placeholder** 이므로 커밋 가능. **진짜 secret 은 gitignore 된 `.env.prod` 에만** 존재한다.

## 2. 변수 분류

### Secret (prod 에서 반드시 교체)

| 변수 | 사용처 | 비고 |
|------|--------|------|
| `AI_SERVICE_TOKEN` | ai → backend `/api/v1/events` Bearer | ai·backend **동일 값** |
| `AFC_SERVICE_TOKEN` | Mock AFC → backend `/api/v1/fare-taps` Bearer | backend·AFC sender **동일 값** |
| `JWT_SECRET` | backend JWT 서명 | |
| `POSTGRES_PASSWORD` | db 비밀번호 · `DATABASE_URL` 부품 | pw 의 **단일 진실 원천** |
| `CARD_HASH_SALT` | backend · Mock AFC 카드 해싱 salt | 양쪽 **동일해야** 매칭됨 |

### Config (환경별·비민감, 커밋 가능)

| 변수 | 사용처 | dev 값 |
|------|--------|--------|
| `POSTGRES_USER` | db, `DATABASE_URL` 부품 | `gateguard` |
| `POSTGRES_DB` | db, `DATABASE_URL` 부품 | `gateguard` |
| `BACKEND_URL` | ai → backend base URL | `http://backend:8000` (compose 내부 고정) |
| `NEXT_PUBLIC_API_URL` | frontend → backend (브라우저 노출) | `http://localhost:8000` |
| `STORAGE_BACKEND` | backend 저장소 모드 | `sql` |
| `CORS_ALLOW_ORIGINS` | backend CORS 허용 오리진 | `*` (prod 은 프론트 오리진으로 제한) |

> 클립 저장 관련 backend env(`VIDEO_CLIP_DIR` / `VIDEO_CLIP_TTL_HOURS` / `VIDEO_CLIP_SIGNED_URL_TTL_SECONDS`)는
> 본 문서 범위 밖 — "클립 저장소" 마일스톤에서 별도 관리한다.

## 3. 주입 메커니즘

compose 는 `${VAR:-기본값}` 보간을 쓰고, `DATABASE_URL` 은 `POSTGRES_*` 부품으로 조립한다(pw 단일 원천).

```yaml
backend:
  environment:
    - DATABASE_URL=postgres://${POSTGRES_USER:-gateguard}:${POSTGRES_PASSWORD:-gateguard}@db:5432/${POSTGRES_DB:-gateguard}
    - AI_SERVICE_TOKEN=${AI_SERVICE_TOKEN:-dev-ai-service-token-please-change-32}
    - AFC_SERVICE_TOKEN=${AFC_SERVICE_TOKEN:-dev-afc-service-token-please-change-32}
    - JWT_SECRET=${JWT_SECRET:-dev-jwt-secret-please-change-before-prod}
    - CARD_HASH_SALT=${CARD_HASH_SALT:-dev-card-hash-salt}
    - STORAGE_BACKEND=${STORAGE_BACKEND:-sql}
    - CORS_ALLOW_ORIGINS=${CORS_ALLOW_ORIGINS:-*}
ai:
  environment:
    - AI_SERVICE_TOKEN=${AI_SERVICE_TOKEN:-dev-ai-service-token-please-change-32}
    - BACKEND_URL=${BACKEND_URL:-http://backend:8000}
db:
  environment:
    - POSTGRES_USER=${POSTGRES_USER:-gateguard}
    - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-gateguard}
    - POSTGRES_DB=${POSTGRES_DB:-gateguard}
```

> `CARD_HASH_SALT` 는 기존 compose 에서 backend 에 주입되지 않았고, backend 자체 기본값
> (`config.py`: `dev-card-hash-salt-change-before-prod`)과 Mock AFC sender 기본값
> (`send_tap.py`: `dev-card-hash-salt`)이 **서로 달라** 무설정 시 카드 매칭이 깨질 수 있다.
> 본 설계는 backend 에 `CARD_HASH_SALT` 를 주입해 단일 값(`dev-card-hash-salt`)으로 통일한다.
> backend 트랙은 위 두 코드 기본값을 동일하게 정리하는 것을 권장한다(값 소유: backend).

## 4. 파일 구조 (repo 루트)

| 파일 | git | 용도 |
|------|-----|------|
| `.env.example` | **커밋** | 전체 변수 + dev placeholder + 주석. 템플릿/문서 역할. |
| `.env` | gitignore | 로컬 dev 실값 (선택 — 기본값으로 충분하면 불필요). |
| `.env.prod` | gitignore | **운영(데스크탑) 실 secret.** 절대 커밋 금지. |

`.gitignore` 는 이미 아래를 갖고 있어 **수정 불필요**:

```
.env
.env.*
!.env.example
```

## 5. 실행 흐름

**dev** (무설정 기동, 기본값 사용):

```bash
docker compose -f docker-compose.dev.yml up
# 값을 바꾸려면: cp .env.example .env  후 .env 편집
```

**prod** (데스크탑 호스트, `.env.prod` 실값으로 override):

```bash
# 최초 1회: cp .env.example .env.prod  후 .env.prod 의 secret 을 전부 실값으로 교체
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

> `docker-compose.prod.yml` 은 아직 없다(별도 마일스톤). 그 전까지의 잠정 운영은
> `docker compose --env-file .env.prod -f docker-compose.dev.yml up -d` 로 dev compose 에
> `.env.prod` 실값을 주입해 띄울 수 있다. 단 이 경우 §6 strict 안전장치가 없으므로
> `.env.prod` 누락에 주의한다.

## 6. prod 안전장치

`${VAR:-기본값}` 은 `.env.prod` 누락 시 **dev 토큰으로 조용히 기동**되는 위험이 있다. 따라서:

- 향후 `docker-compose.prod.yml`(별도 마일스톤 — prod/staging compose 분리)에서는 secret 에 **기본값 없는 strict 형**을 쓴다:

  ```yaml
  - JWT_SECRET=${JWT_SECRET:?prod 는 .env.prod 에 JWT_SECRET 설정 필수}
  ```

  → 미설정 시 compose 가 즉시 실패해, dev secret 으로 운영이 뜨는 사고를 막는다.
- dev compose(`docker-compose.dev.yml`)는 편의를 위해 기본값 형을 유지한다.

## 7. 운영 호스트(데스크탑) 주의

- `.env.prod` 는 24/7 데스크탑 호스트(`tyler-pc`)에만 두고 파일 권한을 제한한다.
- 데스크탑은 **Tailscale**로 접근한다(`tyler-pc.tail87a6d1.ts.net`). 팀/Mac → 서버 접근이 Tailscale 주소로 이뤄지므로 LAN 개방·방화벽 인바운드가 필요 없다. 따라서 prod `.env.prod` 의 `NEXT_PUBLIC_API_URL` 은 Tailscale MagicDNS 주소(예: `http://tyler-pc.tail87a6d1.ts.net:8000`)로 둔다.
- staging 이 필요해지면 `.env.staging` 1파일 추가로 동일 패턴 확장(지금은 만들지 않음 — YAGNI).

## 8. 구현 체크리스트 (이 문서 = spec)

- [ ] `docker-compose.dev.yml`: secret 하드코딩 → `${VAR:-기본값}`, `DATABASE_URL` 부품 조립, `CARD_HASH_SALT` 주입 추가
- [ ] 루트 `.env.example` 신규 (§2 변수 전체 + dev placeholder + secret/config 구분 주석)
- [ ] `apps/infra/README.md` 에 본 문서 링크 + 한 줄 요약
- [ ] (prod compose 마일스톤에서) strict 형 적용

## 경계

수정 대상: 루트 `docker-compose.dev.yml` · 루트 `.env.example` · `docs/secret-management.md` · `apps/infra/README.md` (전부 인프라 소유). 변수명 불변 → backend·ai·frontend 코드 무수정.
