# 릴리즈 절차

## 핵심 개념

**합병해서 배포가 아니라, 각 트랙 산출물의 버전을 인프라가 고정**.

```
[1] 각 트랙: 본인 폴더에서 코드 완성 → semver 태그
        ↓
[2] CI: 이미지 빌드 + 레지스트리 push
        ↓
[3] 인프라: docker-compose.prod.yml 의 image 태그를 갱신
        ↓
[4] 인프라: release-YYYY-MM-DD 태그 push = "이 조합이 prod"
        ↓
[5] 운영 서버: 그 태그 pull + restart
```

---

## 환경 분기

| 환경 | compose 파일 | 이미지 태그 |
|------|-------------|------------|
| dev | `docker-compose.dev.yml` | `:dev` 또는 로컬 build |
| staging | `docker-compose.staging.yml` | `:vX.Y.Z` 또는 `:sha-xxxxx` |
| prod | `docker-compose.prod.yml` | `:vX.Y.Z` (semver 핀) |

---

## 트랙 간 의존성 변경 (스키마 바뀔 때)

**규칙: 받는 쪽 먼저, 보내는 쪽 나중.**

예) AI 가 Event 페이로드에 `pose_keypoints` 필드 추가:

```
1. packages/schema PR → 머지
2. 백엔드: pose_keypoints (optional) 받을 수 있게 → 배포
3. AI: pose_keypoints 보내기 시작 → 배포
4. (선택) 백엔드: optional 처리 코드 제거 (모든 AI가 v2+면)
```

순서 바뀌면 잠깐 깨짐 = 사용자 보임 = 사고.

---

## 롤백

```bash
cd /opt/gateguard
git checkout release-2026-05-20    # 이전 안정 태그
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

이미지 태그를 semver 로 핀해뒀기 때문에 git checkout 만으로 시점 이동.

---

## MVP 단계 (1~6주차) 간소화

처음부터 풀세팅 가지 말 것:

- **1-2주차**: 레지스트리 없음. `docker-compose.dev.yml` 로컬 build 만.
- **3-4주차**: ghcr.io 사용 시작. main 머지 시 `:latest` 자동 push.
- **5-6주차**: 본격 semver 태그 + prod compose 분리.

## 인프라 후속 마일스톤 순서

실제 MVP 후보 장비는 Windows + Docker Desktop WSL2 + RTX 3060 12GB 단일
PC이다. 이 단계에서는 GPU scale-out, Kubernetes, 풀 모니터링 스택을 먼저
붙이지 않고 Compose 기반 운영 안정화를 우선한다.

후속 인프라 작업은 아래 순서로 분리한다.

1. **dev/prod 환경 분리 안정화**
   - secret/config 보간화
   - backend `/api/v1/health` healthcheck 유지
   - AI가 backend healthy 이후 시작하도록 compose 의존성 유지
2. **staging/prod compose 분리**
   - 로컬 build 중심의 dev compose와 image tag 중심의 staging/prod compose를 분리
   - prod는 `.env.prod` 또는 배포 서버 secret 주입을 전제로 함
3. **GHCR 이미지 레지스트리**
   - 처음에는 `:latest` 또는 `:sha-xxxxx`로 시작
   - 운영 배포가 안정화되면 semver tag pin으로 전환
4. **nginx 리버스 프록시**
   - backend/frontend 외부 노출 경로 정리
   - TLS, CORS, 업로드/클립 다운로드 timeout 정책을 여기서 고정
5. **Prometheus/Grafana 모니터링**
   - `/api/v1/health`와 컨테이너 로그로 충분하지 않을 때 붙임
   - GPU/VRAM, backend latency, DB 상태, clip storage 사용량을 우선 지표로 둠

즉, 지금 단계에서 GHCR/nginx/Prometheus/Grafana를 한 PR에 모두 묶지 않는다.
먼저 compose와 healthcheck가 안정된 뒤 하나씩 붙인다.
