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
