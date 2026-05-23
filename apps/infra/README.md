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
│   └── seed_data.sh
└── terraform/  or k8s/    # 클라우드 / 오케스트레이션 (확장 시)
```

## 책임의 경계

- **각 트랙은 본인 `apps/<track>/Dockerfile` 을 직접 들고 있어도 됨.**
  인프라는 그것들을 `docker-compose` 로 묶고, 배포/네트워크/볼륨을 결정.
- 즉 트랙 컨테이너 안 = 트랙 책임 / 컨테이너 밖 = 인프라 책임.

## 시작하기

```bash
cd /path/to/gateguard
docker compose -f docker-compose.dev.yml up
```

현재는 stub. 각 트랙이 Dockerfile 채울 때마다 `docker-compose.dev.yml` 에서
해당 서비스의 `build:` / `image:` 를 주석 해제.

## 릴리즈 절차

[`docs/release.md`](../../docs/release.md) 참고.
