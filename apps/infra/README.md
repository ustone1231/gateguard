# apps/infra

GateGuard 인프라 / 배포 / 운영 자원.

## 책임
- **dev 환경 통합 실행**: 4트랙(ai/backend/frontend + db/redis)을 한 번에 띄움
  → 루트 [`docker-compose.dev.yml`](../../docker-compose.dev.yml)
- **prod 배포**: `docker-compose.prod.yml` 의 이미지 태그 핀 + 운영 서버 갱신 스크립트
- **모니터링**: 메트릭/로그 수집 (Prometheus / Grafana 또는 외부 SaaS)
- **CCTV 입력**: RTSP 스트림 → AI 컨테이너로 전달하는 경로 정비
- **클립 저장소**: 생성된 클립 파일 호스팅 (로컬 볼륨 or S3 호환)

## 이 폴더에 들어갈 것 (예정)

```
apps/infra/
├── Dockerfile.ai          # apps/ai 빌드용 (필요 시 여기서 관리)
├── nginx/                 # 리버스 프록시 설정
├── monitoring/            # Prometheus / Grafana 설정
├── scripts/
│   ├── deploy.sh          # 운영 서버 배포
│   ├── rollback.sh
│   ├── seed_data.sh
│   └── verify_db.sh       # DB 마이그레이션/hypertable 스모크 검증 (이슈 #16)
└── terraform/  or k8s/    # 클라우드 / 오케스트레이션 (확장 시)
```

## 책임의 경계

- **각 트랙은 본인 `apps/<track>/Dockerfile` 을 직접 들고 있어도 됨.**
  인프라는 그것들을 `docker-compose` 로 묶고, 배포/네트워크/볼륨을 결정.
- 즉 트랙 컨테이너 안 = 트랙 책임 / 컨테이너 밖 = 인프라 책임.

## 서비스 간 환경변수

| 변수 | 서비스 | 값 (dev) | 설명 |
|------|--------|----------|------|
| `BACKEND_URL` | `ai` | `http://backend:8000` | AI HttpPublisher가 이벤트를 POST할 백엔드 base URL. 우선순위: env > `pipeline.json http_endpoint` > `localhost:8000` fallback (이슈 #3) |
| `AI_SERVICE_TOKEN` | `ai`, `backend` | `dev-ai-service-token-please-change-32` | AI → 백엔드 `/api/v1/events` 호출용 Bearer 토큰. AI와 백엔드 값이 같아야 함 |
| `AFC_SERVICE_TOKEN` | `backend` | `dev-afc-service-token-please-change-32` | Mock AFC → 백엔드 `/api/v1/fare-taps` 호출용 Bearer 토큰 |
| `DATABASE_URL` | `backend` | `postgres://gateguard:gateguard@db:5432/gateguard` | 백엔드 → TimescaleDB 연결 |
| `NEXT_PUBLIC_API_URL` | `frontend` | `http://localhost:8000` | 브라우저에서 백엔드 API 호출 시 사용 |
| `VIDEO_CLIP_DIR` | `backend` | `/var/lib/gateguard/clips` | 이벤트 영상 클립 저장 경로 |
| `VIDEO_CLIP_TTL_HOURS` | `backend` | `24` | 로컬 클립 보관 시간 |
| `VIDEO_CLIP_SIGNED_URL_TTL_SECONDS` | `backend` | `300` | 서명 클립 URL 유효 시간 |

## 시작하기

```bash
cd /path/to/gateguard
docker compose -f docker-compose.dev.yml up
```

각 트랙이 Dockerfile을 채울 때마다 `docker-compose.dev.yml` 에서
해당 서비스의 `build:` / `image:` 를 주석 해제.
현재 완료된 트랙: `ai` (Dockerfile.ai).

## 영상 클립 저장소

MVP에서는 별도 S3/MinIO를 붙이지 않고 로컬 디스크를 사용한다. dev compose는
호스트 `./videos/clips`를 backend 컨테이너의 `/var/lib/gateguard/clips`에
마운트한다. backend는 이벤트 `clip_url` 또는 `<event_id>.mp4|.mov|.webm`
파일을 이 디렉터리 아래에서 찾고, 인증된 요청에만 짧은 만료 시간을 가진
서명 URL을 발급한다.

RTX 3060 12GB 단일 PC 기준에서는 이 구조가 가장 가볍다. 저장량, 동시 재생,
여러 카메라 입력이 실제 병목이 되면 그때 Video/Storage Worker와 S3 호환
스토리지를 별도 마일스톤으로 분리한다.

## DB 스모크 검증

backend 컨테이너가 Alembic migration 을 실제로 적용했는지(TimescaleDB hypertable,
`alembic_version` = 최신 head, migration 0004 복합 PK) 재현 가능하게 확인:

```bash
docker compose -f docker-compose.dev.yml up -d --build db backend
apps/infra/scripts/verify_db.sh
```

fresh Docker DB 와 운영 DB 의 schema drift 방지용. 전부 통과하면 종료코드 `0`.
배경: 이슈 #16 (Docker backend 가 migration 미실행 → hypertable 미적용).

## 릴리즈 절차

[`docs/release.md`](../../docs/release.md) 참고.
