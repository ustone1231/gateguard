# AI/CV Validation Status

이 문서는 `docs/mvp-features.md`의 AI/CV 목표를 현재 `develop` 코드 기준으로
검증 가능한 상태와 아직 남은 상태로 나눈다. 코드와 문서가 다르게 보이면
현재 코드를 우선하고, 이 문서를 갱신한다.

## 현재 결론

AI 트랙은 `gate_passage` 이벤트에 v0.2.2 `signals`를 붙이는 경로까지 구현했다.
기본 설정은 모델을 끈 휴리스틱 경로이고, PoC 검증 시 `age_estimator.enabled=true`
로 HF MiVOLO v2 모델 기반 나이/성별 보조 신호를 켤 수 있다.

운영/발표에서 말할 수 있는 범위:

- 가능: 실제 영상에서 `gate_passage` 이벤트 생성
- 가능: HF MiVOLO v2 출력이 `signals.face_age_estimate`, `signals.perceived_gender`,
  `signals.gender_confidence`로 들어가는 smoke 검증
- 가능: 백엔드가 AFC `fare_tap`과 매칭할 수 있는 payload contract 유지
- 금지: 자동 처벌/자동 신고/개인 식별 주장
- 금지: AFAD fine-tuning 완료 주장
- 금지: 장애인/국가유공자 카드 외관 판정 주장

## 구현 상태

| 요구 | 현재 상태 | 근거 |
|------|-----------|------|
| `gate_passage` 이벤트 | 완료 | `apps/ai/src/rules/gate_passage.py` |
| v0.2.2 `Event.signals` | 완료 | `apps/ai/src/types.py`, `apps/ai/src/eligibility_signals/` |
| 모델 없는 기본 휴리스틱 | 완료 | `age_estimator.enabled=false`, `eligibility_signals` |
| Pose estimator 구조 | 완료 | `apps/ai/src/pose_estimator/` |
| HF MiVOLO v2 age/gender 경로 | 완료 | `apps/ai/src/age_estimator/hf_mivolo_v2.py` |
| 원본 MiVOLO `.pth.tar` 경로 | 보존 | `apps/ai/src/age_estimator/mivolo_estimator.py` |
| 실제 영상 + 모델 signals smoke | 완료 | `apps/ai/scripts/smoke_model_gate_passage.py` |
| 짧은 line-crossing jitter 억제 | 완료 | `min_same_line_gap_frames` |
| AFAD fine-tuning | 미완료/P1 | 데이터셋/학습/MAE 검증 없음 |
| 보조기구 검출 | 미완료/P1 | detector/class 확장 없음 |
| 운영 품질 검증 | 미완료 | 다양한 게이트/조명/인물 샘플 부족 |

## 모델 설정

기본 config:

- `age_estimator.enabled=false`
- `age_estimator.type=hf_mivolo_v2`
- `age_estimator.revision=53393526c220e34cdd7b722b36d22b6f9e5f4241`

이 기본값은 서비스 기본 실행을 무겁게 만들지 않으면서, PoC 검증 때 같은 모델
revision을 재현하게 하기 위한 설정이다.

주의:

- HF MiVOLO v2는 `trust_remote_code=True`를 사용한다.
- HF remote code가 `mivolo` 패키지를 import하므로 optional runtime 설치가 필요하다.
- 현재 wrapper는 별도 face crop 없이 ByteTrack person bbox를 body 입력으로 넣는다.
- 이 출력은 백엔드 판정용 보조 신호이지 법적/개인 식별 신호가 아니다.

## 필수 검증 명령

AI 단위/회귀:

```bash
cd apps/ai
python -m pytest -q
ruff check src scripts tests
```

백엔드 계약 회귀:

```bash
cd apps/backend
python -m pytest -q
```

Compose 설정:

```bash
docker compose -f docker-compose.dev.yml config --quiet
```

모델 setup smoke:

```bash
cd apps/ai
python scripts/check_model_setup.py \
  --hf-mivolo-v2 \
  --device cpu \
  --torch-dtype float32 \
  --hf-mivolo-revision 53393526c220e34cdd7b722b36d22b6f9e5f4241
```

실제 영상 gate passage signals smoke:

```bash
cd apps/ai
python scripts/smoke_model_gate_passage.py ../../videos/gateguard_test_video.mov \
  --sections config/gate_sections.local.json \
  --start-sec 11.5 \
  --max-frames 90
```

현재 검증된 smoke 기대값:

- `summary.gate_passage_count == 3`
- `summary.model_signal_gate_passage_count == 3`
- 이벤트 JSONL에 `signals.face_age_estimate`, `signals.estimated_age_group`,
  `signals.perceived_gender`, `signals.gender_confidence` 포함

## 운영 enable 기준

`age_estimator.enabled=true`를 운영/통합 demo 기본값으로 바꾸기 전 조건:

1. 최소 3개 이상의 서로 다른 게이트/각도/조명 샘플에서
   `smoke_model_gate_passage.py` 통과
2. 정상 통과 케이스에서 line jitter 중복이 허용 범위인지 확인
3. `gender_confidence >= 0.80` 조건이 과도한 오탐을 만들지 않는지 샘플 리뷰
4. senior/child mismatch는 자동 확정이 아니라 review queue 우선순위 보조로 표시
5. 모델 runtime 의존성(`mivolo`, `transformers`, `accelerate`)을 인프라 이미지에
   넣을지 별도 AI worker venv로 둘지 결정

## 품질 기준

MVP/발표에서 쓸 표현:

- "의심 사건을 정리하는 검토 보조 시스템"
- "나이/성별은 보조 신호이며 자동 처벌 근거가 아니다"
- "우대카드 부정사용은 백엔드가 AFC 카드 기록과 AI 보조 신호를 함께 보고
  review queue에 올린다"

아직 쓰면 안 되는 표현:

- "한국인 fine-tuning 완료"
- "우대카드 부정사용 자동 확정"
- "나이/성별 정확도 보장"
- "장애인/국가유공자 카드 외관 판단"
