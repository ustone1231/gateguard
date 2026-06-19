# 스키마 버저닝

## 정책

[Semantic Versioning](https://semver.org/) 사용.

- **MAJOR** (`v1.0.0` → `v2.0.0`): 호환성 깨는 변경 (필드 제거, 타입 변경, 이름 변경)
- **MINOR** (`v1.0.0` → `v1.1.0`): 호환되는 추가 (optional 필드 신규)
- **PATCH** (`v1.0.0` → `v1.0.1`): 문서/예제만, 실제 스키마 변경 없음

MVP 기간 (v0.x) 에는 BREAKING도 자유롭게 가능. **v1.0 진입 후**부터 정책 엄격 적용.

## 변경 이력

### v0.1.0 (2026-05-23) — 초기
- `Event` 정의 (event_type, gate_section_id, camera_id, confidence, track_id, timestamp, clip_url, raw_meta)
- `GateSection` 정의 (id, polygon, entry_line, exit_line)
- `FareTap` 정의 (event_type, gate_section_id, card_id_hash, timestamp, result, raw_meta)
- event_type: `jump`, `crawling`, `tailgating`, `unpaid`

### v0.2.0 (2026-05-28) — misuse 룰 + AFC 매칭 메타데이터

**Event 스키마 변경 (MINOR — 호환되는 추가 + MAJOR 1건):**
- 🆕 **event_id** (required) — AI 가 발급하는 unique ID (`evt_<uuid4 hex>`). 백엔드 멱등성 키. **MAJOR: required 필드 추가**
- 🆕 event_type enum 에 `misuse` 추가 (우대카드 부정사용)
- 🆕 **signals** (optional) — 다중 신호 분석 결과 (face_age_estimate, pose/gait_senior_score, assistive_device_detected, senior_probability)
- 🆕 **reliability** (optional) — low/mid/high
- 🆕 **severity** (optional) — info/warning/critical (프론트엔드 알림 강도)
- 🆕 **afc_match** (optional) — 백엔드 매칭 엔진이 채우는 fare_tap 매칭 메타 (fare_tap_id, card_id_hash, card_category, tap_timestamp, time_delta_ms)

**FareTap 스키마 변경 (MINOR — 호환되는 추가):**
- 🆕 **card_category** (required) — 카드 자격 종류 enum: regular/senior/child/disabled/national_merit. **결제 수단 (raw_meta.card_type, 예: T-money) 과 의미 구분**. **MAJOR: required 필드 추가**

**버전 호환성 주의:**
- v0.1 → v0.2 는 MVP 기간 (v0.x) 이므로 BREAKING 허용
- 백엔드 / 프론트엔드 / AI 모두 v0.2 로 동시 전환 필요
- 배포 순서: schema 패키지 → AI / Mock AFC (발신측) → 백엔드 (수신측) — [`docs/release.md`](../../docs/release.md) 의 "트랙 간 의존성 변경" 규칙 적용

### v0.2.1 (2026-05-28) — 발행자별 event_type 분리 + 멱등성 키 추가

**Event 스키마 변경 (BREAKING within v0.x):**
- 🔁 **event_type enum 재정의** — 발행자별 분리:
  - AI 발행: `gate_passage` (신규), `jump`, `crawling`, `tailgating`, `unpaid` (=우회/역방향)
  - 백엔드 발행: `confirmed_unpaid` (신규), `confirmed_misuse` (신규)
  - ❌ `misuse` 제거 — AI 가 단독 판정 불가 (card_category 못 받음), 백엔드의 `confirmed_misuse` 로 대체
- 🆕 **source_event_id** (optional) — 백엔드 `confirmed_*` event 가 원본 AI event 참조
- 🆕 `signals.assistive_device_type` — 검출된 보조기구 종류 (cane / walker / wheelchair)
- 🔧 `afc_match.fare_tap_id` 패턴 명시 (`^tap_[a-zA-Z0-9_-]+$`)

**FareTap 스키마 변경 (BREAKING within v0.x):**
- 🆕 **fare_tap_id** (required) — 발신자가 발급하는 unique ID. 백엔드 멱등성 키. 형식: `^tap_[a-zA-Z0-9_-]+$`

**설계 결정 근거:**
- `detection-strategy.md` §4~§7 의 원래 설계 (AI 행동 신호 + 백엔드 매칭 엔진 책임 분리) 와 정합
- AI 는 영상만으로 판단 가능한 신호만 발행 (gate_passage, jump 등)
- AFC 매칭 + misuse 판정은 백엔드 매칭 엔진 책임 (AI 에 fare_tap 안 옴)
- `confirmed_misuse` 의 senior_probability 는 AI 의 eligibility_signals 가 gate_passage event 의 signals 필드에 채움 → 백엔드가 card_category 매칭 후 결합 판정

**v0.2.0 → v0.2.1 호환성:**
- v0.2.0 의 `misuse` 사용 코드 있다면 깨짐 (v0.2.0 은 짧게 존재했음, 실제 배포 없음)
- AI 트랙 `types.py` 동기화 완료
- 모든 examples 새 enum 으로 업데이트

### v0.2.2 (2026-06-14) — 우대 자격 일치 검증 필드 확장

**Event 스키마 변경 (BREAKING within v0.x):**
- 🆕 `signals.child_probability` — 어린이 카드 자격 불일치 판단용 보조 신호
- 🆕 `signals.estimated_age_group` / `signals.age_group_confidence` — UI/리뷰 보조용 연령대 추정
- 🆕 `signals.perceived_gender` / `signals.gender_confidence` — 영상상 성별 추정. 확정 성별이 아니며 confidence threshold 필수
- 🆕 `afc_match.holder_gender` — 매칭된 fare_tap 의 카드 등록 성별

**FareTap 스키마 변경 (BREAKING within v0.x):**
- 🆕 **holder_gender** (required) — AFC 가 카드 태그 시점에 제공하는 카드 등록 성별. enum: `male` / `female` / `unknown`

**설계 결정 근거:**
- 실제 AFC 태그 데이터에 카드 종류(`card_category`)와 등록 성별(`holder_gender`)이 함께 제공됨
- AI 는 나이/성별을 확정하지 않고 보조 신호만 제공
- 백엔드 매칭 엔진이 `gate_passage` + `fare_tap` 을 매칭한 뒤 연령 또는 성별 자격 불일치를 판단
- confidence 낮은 성별/연령 추정은 자동 `confirmed_misuse` 금지, review queue 후보로만 처리

### v0.3.0 (예정)
- `action_recognition` 결과 통합 (학습 기반 룰 추가 시)
- multi-camera 지원 강화 (필요 시)
