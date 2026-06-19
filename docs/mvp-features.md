# GateGuard MVP 기능 명세

> **이 문서가 다루는 것:** MVP 에서 무엇을 개발하고, 무엇이 기존 설계에서 바뀌었으며, 트랙별로 누가 무엇을 해야 하는지 정리.
>
> **이 문서가 다루지 않는 것:** 일정/마일스톤 (별도 관리), 코드 레벨 세부 구현 (각 트랙 README 참고).

---

## 0. 한 줄 정의

**지하철 CCTV + 카드 결제 데이터를 매칭해서 5종 부정승차를 감지 → 역무원 대시보드에 알림 + 통계 제공.**

---

## 1. 변경 이력 (기존 설계 → 새 MVP)

### 1-1. 부정승차 판정: AI 행동 신호 + 백엔드 확정 판정

| | 기존 | 변경 후 |
|---|------|---------|
| 1 | jump | jump |
| 2 | crawling | crawling |
| 3 | tailgating | tailgating |
| 4 | unpaid | unpaid |
| 5 | — | **confirmed_misuse (우대카드 부정사용, 백엔드 확정 판정)** ⭐ |

**왜 추가:** 서울교통공사 추정 부정승차 손실의 가장 큰 비중이 우대카드 부정사용 (특히 노인 카드). 시스템 차별점.

### 1-2. AFC (Automatic Fare Collection) 매칭 도입

- **기존:** CCTV 만으로 무임승차 판단 시도 → 한계 (카드 안 찍은 사람을 영상만으로 못 구분)
- **변경:** CCTV 통과 이벤트 ↔ AFC 결제 이벤트 시간 매칭 (±1초)
- **MVP 에서 실제 AFC 시스템 연동 X** → **Mock AFC (JSONL replay + 수동 UI) 로 시연**

### 1-3. AI 모델 추가

| 신규 모델 | 용도 |
|----------|------|
| **YOLOv8-Pose** | 자세 분석 (척추 각도, 굽은 등 등) |
| **MiVOLO** | 얼굴 나이 추정 |
| (지팡이/워커 보조 클래스) | 보조기구 검출 (YOLO11n 에 학습 추가) |

### 1-4. Fine-tuning 도입

- **나이 추정 (MiVOLO)** — AFAD (Asian Face Age Dataset) 로 head-only fine-tuning (한국인 정확도 보강)
- **보조기구 검출** — YOLO 에 지팡이/워커/휠체어 클래스 학습 추가
- 다른 모델 (YOLO11n 사람 탐지, ByteTrack, YOLOv8-Pose) 는 사전학습 그대로 사용

### 1-5. 워크플로우 변경: 자동 처벌 → 의심 큐

- **기존 가정:** AI 가 감지 → 이벤트 발행 → 끝
- **변경:** AI 가 감지 → **의심 큐** → 역무원 영상 확인 + 정탐/오탐 라벨링
- 우대카드 부정사용은 자동 차단/사이렌 절대 ❌ (윤리/법적 안전장치)

### 1-6. 스키마 버전업

- `events.schema.json` → **v0.2.2** (gate_passage/confirmed_* 분리 + signals/reliability/severity/afc_match 필드 확정)
- `fare_tap.schema.json` → **v0.2.2** (`card_category`, `holder_gender`, `fare_tap_id` 확정)

---

## 2. 시스템 구조 (전체)

```
[CCTV 영상]                                [Mock AFC (JSONL/수동 UI)]
      ↓                                              ↓
┌─────────────────────────────┐         ┌─────────────────────────┐
│ AI/CV 트랙 (apps/ai)         │         │ 백엔드 트랙              │
│ - detector (YOLO11n)        │ ←─매칭─→ │ - AFC 수신 endpoint      │
│ - tracker (ByteTrack)       │         │ - 이벤트 저장           │
│ - zone (matcher)            │         │ - 의심 큐 API            │
│ - pose_estimator (신규)      │         │ - 영상 클립 관리         │
│ - age_estimator (신규)       │         │ - 통계 집계 API          │
│ - eligibility_signals (신규) │         └─────────────────────────┘
│ - rules (jump/crawl/tail/    │                    ↓
│          unpaid/gate_passage)│         ┌─────────────────────────┐
│ - publisher (HTTP/file)     │ ───────→│ 프론트엔드 트랙           │
└─────────────────────────────┘ POST    │ - 실시간 알림 + 알림음    │
                                events  │ - 의심 큐 화면 (영상+검토)│
                                        │ - 통계 대시보드          │
                                        │ - 라벨링 인터페이스       │
                                        └─────────────────────────┘
                                                    ↑
                                        ┌─────────────────────────┐
                                        │ 인프라 트랙              │
                                        │ - GPU 환경 (Docker)     │
                                        │ - 영상 저장소 (24h 삭제) │
                                        │ - DB / 메시지 채널       │
                                        │ - 모델 파일 배포         │
                                        └─────────────────────────┘
```

---

## 3. 부정승차 감지 명세 (이벤트 발행자별 분리)

### 3-1. AI 발행 이벤트 (행동 신호)

AI 트랙은 **영상만으로 판단 가능한 행동 신호** 만 발행. AFC 결제 데이터는 보지 못함.

| # | event_type | 의미 | 감지 방식 | 룰 위치 |
|---|-----------|------|----------|---------|
| 1 | **`gate_passage`** | 사람이 게이트 entry/exit line 통과 | line crossing | `rules/gate_passage.py` (신규) |
| 2 | **`jump`** | 게이트 차단봉 뛰어넘기 | bbox 상단 수직 이동 + 높이 변동 | `rules/jump.py` |
| 3 | **`crawling`** | 차단봉 밑 기어가기 | bbox 높이 baseline 55% 이하 8 프레임 | `rules/crawling.py` |
| 4 | **`tailgating`** | 한 결제로 2명 동시 입장 | 동일 게이트 1.5초 이내 2 트랙 통과 | `rules/tailgating.py` |
| 5 | **`unpaid`** | **게이트 우회 / 역방향** (≠ 결제 안 함) | entry 안 지나고 exit 만 통과 | `rules/unpaid.py` |

**⚠️ 중요:** AI 의 `unpaid` 는 "결제 안 함" 이 아니라 **"우회/역방향"** 의미. AFC 결제 데이터 매칭 없이 영상만으로 판단. "결제 안 함" 은 백엔드의 `confirmed_unpaid` 가 담당.

**`gate_passage` 발화 시점:** entry_line 또는 exit_line crossing 시. 모든 통과를 발행해야 백엔드 매칭 엔진이 AFC 와 cross-check 가능. signals 필드에 eligibility_signals 결과 첨부.

### 3-2. 백엔드 발행 이벤트 (AFC 매칭 결과)

백엔드 매칭 엔진이 AI event + AFC fare_tap 을 ±1초 윈도로 매칭한 후 발행.

| # | event_type | 의미 | 판정 조건 |
|---|-----------|------|----------|
| 6 | **`confirmed_unpaid`** | 결제 없는 통과 = 무임승차 확정 | gate_passage 발화 + 매칭되는 fare_tap 없음 |
| 7 | **`confirmed_misuse`** ⭐ | 우대카드 부정사용 확정 | gate_passage 발화 + 매칭된 fare_tap 의 카드 자격(`card_category`, `holder_gender`)과 AI 보조 신호(`signals`) 불일치 |

각 백엔드 발행 이벤트는 `source_event_id` 로 원본 AI event (보통 gate_passage) 참조. 영상 클립 / track_id / camera_id 등 메타 정보는 source event 의 것을 그대로 사용.

### 3-3. confirmed_misuse 판정 상세 (우대 자격 불일치)

**AFC 가 제공해야 하는 카드 자격 필드:**
- `card_category`: `regular` / `senior` / `child` / `disabled` / `national_merit`
- `holder_gender`: `male` / `female` / `unknown` — 카드 태그 시점에 제공되는 카드 등록 성별

**AI 가 제공해야 하는 보조 신호 (`event.signals`):**
- `senior_probability`: 영상상 노인 가능성
- `child_probability`: 영상상 어린이 가능성
- `estimated_age_group`: `child` / `youth` / `adult` / `senior` / `unknown`
- `age_group_confidence`: 연령대 추정 신뢰도
- `perceived_gender`: `male` / `female` / `unknown`
- `gender_confidence`: 영상상 성별 추정 신뢰도

**대상 카드 종류:**
- ✅ 노인 (만 65세 이상) — `card_category: "senior"`
- ✅ 어린이 (만 13세 미만) — `card_category: "child"`
- ✅ 성별 제한/등록 성별이 있는 우대카드 — `holder_gender` 와 AI `perceived_gender` 비교
- ❌ 청소년 / 장애인 / 국가유공자 — 외관 판단 불가 또는 윤리적 제외

**연령/성별 보조 신호 계산 (AI 의 eligibility signal 모듈, gate_passage event 의 signals 에 첨부):**
```
senior_probability =
    얼굴 나이 추정 점수      × 0.40   (MiVOLO)
  + 자세 분석 점수          × 0.25   (YOLOv8-Pose)
  + 보행 분석 점수          × 0.20   (track 시간 분석)
  + 보조기구 검출 점수       × 0.15   (지팡이/워커/휠체어)

perceived_gender / gender_confidence =
    얼굴/상반신 기반 모델 결과. 단독 확정 금지. confidence 낮으면 review_needed 성격으로만 사용.
```

**백엔드 판정 조건 (rules/misuse.py 가 아니라 백엔드 매칭 엔진의 로직):**
```
1. gate_passage event 수신 (signals 첨부됨)
2. ±1초 윈도 내 같은 gate_section_id 의 fare_tap 매칭
3. 연령 자격 불일치:
   - fare_tap.card_category == "senior" AND signals.senior_probability < 0.20
   - 또는 fare_tap.card_category == "child" AND signals.child_probability < 0.20
4. 성별 자격 불일치:
   - fare_tap.holder_gender ∈ {"male", "female"}
   - AND signals.perceived_gender ∈ {"male", "female"}
   - AND fare_tap.holder_gender != signals.perceived_gender
   - AND signals.gender_confidence >= 0.80
5. 위 3 또는 4가 true
6. AND gate_passage.reliability == "high"
→ confirmed_misuse event 발행 (source_event_id = gate_passage.event_id)
```

**회색지대 정책:** `senior_probability` / `child_probability` 가 0.20~0.50 이거나 `gender_confidence < 0.80` 이면 자동 `confirmed_misuse` 금지. 이 경우 review queue 의 낮은 우선순위 후보로만 보낼 수 있다.

### 3-4. 시나리오 판정 매트릭스 (detection-strategy.md §7 와 일치)

| AI 이상 행동 (jump 등) | AFC 매칭 | gate_passage 발화 | 판정 (백엔드) |
|---------------------|---------|------------------|-------------|
| ❌ 없음 | ✅ approved | ✅ | 🟢 정상 (알림 없음) |
| ❌ 없음 | ❌ 없음 | ✅ | 🔴 `confirmed_unpaid` |
| ✅ 있음 (jump 등) | ✅ approved | ✅ | 🟡 회색지대 알림 (영상 검토) |
| ✅ 있음 | ❌ 없음 | ✅ | 🔴🔴 명백한 무임 (critical) |
| ❌ 없음 | ✅ 우대카드 자격 불일치 | ✅ | 🔴 `confirmed_misuse` |

---

## 4. 트랙별 작업 (전체)

---

## 4-A. AI/CV 트랙 (`apps/ai/`)

### 4-A-1. 새로 만드는 모듈

| 모듈 | 책임 | 담당 |
|------|------|------|
| `src/pose_estimator/` | YOLOv8-Pose 래핑, 키포인트 추출 | 정우 |
| `src/age_estimator/` | MiVOLO 래핑, 얼굴 나이 추정 | 정우 |
| `src/eligibility_signals/` | 다중 신호 결합 (얼굴+자세+보행+보조기구+성별 보조 신호) → senior_probability / child_probability / perceived_gender 출력. **gate_passage event 의 `signals` 필드에 첨부** | 정우 또는 민지 |
| `src/rules/gate_passage.py` | 모든 게이트 통과를 이벤트로 발행 (line crossing 시점). eligibility_signals 결과 첨부 | 민지 |

**⚠️ `rules/misuse.py` 는 만들지 않음.** AI 는 fare_tap 의 `card_category` 를 받지 못하므로 misuse 판정 불가. 백엔드 매칭 엔진이 confirmed_misuse 발행.

### 4-A-2. 기존 모듈 변경

| 모듈 | 변경 사항 | 담당 |
|------|----------|------|
| `src/types.py` | `Event` 에 `event_id`, `source_event_id`, `signals`, `reliability`, `severity`, `afc_match` 필드 추가 + event_type enum 확장 (gate_passage 등). ✅ v0.2.2 반영 필요 | 4명 합의 |
| `src/zone/matcher.py` | hysteresis 도입 (P0 - 진동 해결) | 유석 |
| `src/zone/section.py` | (변경 없음 — entry_line / exit_line 이미 정의됨) | 유석 |
| `src/rules/unpaid.py` | (변경 없음 — 의미는 "우회/역방향" 그대로) | 민지 |
| `src/rules/*.py` (jump 등) | reliability / severity 필드 채우기 | 민지 |
| `src/publisher/*.py` | severity 필드 처리 (대시보드 알림 강도) | 민지 |
| `src/pipeline/factory.py` | 신규 모듈 (pose/age/eligibility_signals/gate_passage rule) 등록 + config 로딩 | 정우 |
| `config/pipeline.json` | pose/age/eligibility_signals/gate_passage 임계치 추가 | 4명 합의 |

### 4-A-3. 신규 의존성 (requirements.txt)

```
# 추가 (PyPI)
insightface>=0.7      # 얼굴 검출 (MiVOLO 의존)
timm>=1.0             # PyTorch 백본 (MiVOLO 의존)
onnxruntime>=1.16     # MiVOLO 추론
torch>=2.0            # 이미 깔려있다면 생략
torchvision>=0.15     # 이미 깔려있다면 생략

# 추가 (GitHub — PyPI 패키지 없음, ⚠️)
git+https://github.com/WildChlamydia/MiVOLO.git@main#egg=mivolo
```

**왜 mivolo 만 GitHub:** 저자들이 PyPI 에 publish 안 함. 직접 install 또는 모델 가중치만 받고 inference 코드 자작 (둘 다 가능, GitHub install 이 빠름).

YOLOv8-Pose 는 기존 `ultralytics` 패키지에 이미 포함 (별도 install 불필요).

### 4-A-3-1. 설치 절차 (정우)

```bash
cd apps/ai
source venv/bin/activate
pip install -r requirements.txt
pip install insightface timm onnxruntime
pip install git+https://github.com/WildChlamydia/MiVOLO.git@main
bash scripts/download_models.sh   # 모델 가중치 다운로드
python -c "from mivolo.predictor import Predictor; print('mivolo OK')"  # smoke test
```

**대안 (mivolo GitHub install 실패 시):**
모델 가중치 (.pth) 만 다운받고 `src/age_estimator/mivolo_wrapper.py` 에서 PyTorch 로 직접 로드.
MiVOLO 의 모델 아키텍처는 timm 기반이라 자작 inference 가능.

### 4-A-4. 신규 모델 파일

| 파일 | 출처 | 크기 |
|------|------|------|
| `yolov8n-pose.pt` | Ultralytics | ~10MB |
| `mivolo_d1.pth` | MiVOLO GitHub | ~100MB |
| `mivolo_d1_kr.pth` (fine-tuned) | 우리 학습 결과물 | ~100MB |

**저장 정책:** `models/` 폴더 — `.gitignore` 처리, `scripts/download_models.sh` 로 다운로드.

### 4-A-5. Fine-tuning 작업

**MiVOLO Fine-tuning (Head-only):**
- 데이터: AFAD (Asian Face Age Dataset, 한국/중국 16만장)
- 방식: 마지막 회귀 head 만 한국인 분포에 맞춰 재학습
- 목표: MAE ±7~10세 → **MAE ±4~6세**
- 담당: 수웅 (데이터 로더) + 정우 (학습 스크립트)

**보조기구 검출 (YOLO 새 클래스):**
- 데이터: Roboflow 공개 데이터셋 + 자체 라벨링
- 클래스: 지팡이 / 워커 / 휠체어
- 담당: 수웅 (라벨링) + 정우 (학습)

### 4-A-6. 테스트

| 모듈 | 단위 테스트 위치 | 담당 |
|------|-----------------|------|
| `zone/` | `tests/test_geometry.py`, `test_matcher.py`, `test_section.py` (✅ 완료) | 유석 |
| `detector/`, `tracker/` | `tests/test_detector.py`, `test_tracker.py` (신규) | 정우 |
| `rules/` (jump, crawling, tailgating, unpaid, gate_passage), `eligibility_signals/` | `tests/test_rules_*.py`, `test_eligibility_signals.py` (신규) | 민지 |
| `pose_estimator/`, `age_estimator/` | `tests/test_pose.py`, `test_age.py` (신규) | 정우 |

### 4-A-7. 팀 역할별 P0 작업 (AI/CV)

**정우 (#4 Lead) — `detector/`, `tracker/`, `pipeline/`, `pose_estimator/`, `age_estimator/`**
- ByteTrack deprecation 마이그
- 카메라별 임계치 config 노출
- YOLOv8-Pose 통합 (신규)
- MiVOLO 통합 + 한국인 빠른 검증 (신규)
- MiVOLO AFAD fine-tuning (필요 시)
- pipeline 에 신규 모듈 통합

**수웅 (#5 Data) — `dataset/`, `scripts/`, 보조기구 라벨링**
- 데이터 폴더 구조 + 라벨 코드 통일
- train/val/test 분할 스크립트
- AFAD 다운로드 + 데이터 로더
- 한국인 검증셋 만들기 (우리 영상 라벨링)
- 지팡이/워커 보조기구 라벨링
- (P1) 노인/청년 자원봉사 영상 수집

**유석 (#6 Gate Section) — `zone/`**
- SectionMatcher hysteresis 도입
- (P1) 다중 카메라 지원
- (P1) 정규화 좌표 변환
- 비고: AFC 매칭은 백엔드 책임 — AI/zone 영역 아님

**민지 (#7 Rule) — `rules/`, `publisher/`, `eligibility_signals/`**
- 동일 트랙 다중 발화 cooldown 강화
- **`rules/gate_passage.py` 신규 작성** (line crossing 시점에 모든 통과 이벤트 발행 + signals 첨부)
- **`eligibility_signals/` 다중 신호 결합 로직** (얼굴/자세/보행/보조기구/성별 보조 신호 → senior_probability, child_probability, perceived_gender)
- 기존 룰 (jump 등) 에 reliability / severity 필드 채우기
- (P1) crawling 실증 회귀 테스트
- (P1) HttpPublisher env 지원
- 비고: **`rules/misuse.py` 는 만들지 않음** — misuse 판정은 백엔드 매칭 엔진의 책임 (AI 는 card_category 못 받음)

---

## 4-B. 백엔드 트랙

### 4-B-1. 새로 만드는 것

| 기능 | 설명 |
|------|------|
| **이벤트 수신 endpoint** | `POST /api/v1/events` — AI 트랙이 발행하는 모든 event (gate_passage/jump/crawling/tailgating/unpaid) 수신, DB 저장. 백엔드 자체 발행 (confirmed_*) 도 같은 endpoint 에 self-POST 또는 직접 DB 저장 |
| **AFC 수신 endpoint** | `POST /api/v1/fare-taps` — Mock AFC 송신기 결제 이벤트 수신 |
| **매칭 엔진** ⭐ | 비동기 워커. gate_passage event 와 fare_tap 을 ±1초 윈도로 매칭. 매칭 실패 → `confirmed_unpaid` 발행. 매칭 + 우대 자격 불일치 → `confirmed_misuse` 발행 |
| **AFC Mock 송신기** | JSONL replay 도구 + 수동 UI 트리거 (백엔드 트랙이 만드는 게 자연스러움) |
| **의심 큐 API** | `GET /api/v1/review-queue` — 역무원이 확인할 의심 케이스 목록 (confirmed_misuse + 회색지대 자동 추가) |
| **의심 큐 피드백 API** | `POST /api/v1/review-queue/{id}/feedback` — 정탐/오탐 라벨링 수집 |
| **영상 클립 저장/조회** | 이벤트 발생 ±5초 클립 저장, URL 생성, **24시간 후 자동 삭제 스케줄러** |
| **통계 집계 API** | `GET /api/v1/stats?period=day|week|month` — 이벤트 타입별 + 게이트별 + 시간대별 |
| **손실 추정 API** | `GET /api/v1/loss-estimate` — 단가 × confirmed_unpaid + confirmed_misuse 건수 |

### 4-B-2. 매칭 엔진 의사코드 (핵심 로직)

```python
# detection-strategy.md §6 의 의사코드를 v0.2.2 schema 에 맞게 확장
def on_gate_passage(passage_event):
    matched_taps = FareTap.find(
        gate=passage_event.gate_section_id,
        time_range=(passage_event.timestamp - 1s, passage_event.timestamp + 1s),
        result="approved",
        unmatched=True,
    )
    if not matched_taps:
        # 결제 없는 통과 = 무임승차 확정
        emit(Event(
            event_type="confirmed_unpaid",
            source_event_id=passage_event.event_id,
            gate_section_id=passage_event.gate_section_id,
            camera_id=passage_event.camera_id,
            track_id=passage_event.track_id,
            severity="critical",
            reliability="high",
            ...
        ))
        return

    # 시간 가장 가까운 1쌍 매칭
    tap = nearest_by_time(matched_taps, passage_event.timestamp)
    FareMatch.create(passage=passage_event, tap=tap)

    # afc_match 채워서 gate_passage 업데이트
    passage_event.afc_match = AfcMatch(
        fare_tap_id=tap.fare_tap_id,
        card_id_hash=tap.card_id_hash,
        card_category=tap.card_category,
        holder_gender=tap.holder_gender,
        tap_timestamp=tap.timestamp,
        time_delta_ms=int((tap.timestamp - passage_event.timestamp).total_seconds() * 1000),
    )

    # misuse 판정 (우대 자격 불일치)
    if eligibility_mismatch(tap, passage_event.signals) and passage_event.reliability == "high":
        emit(Event(
            event_type="confirmed_misuse",
            source_event_id=passage_event.event_id,
            gate_section_id=passage_event.gate_section_id,
            camera_id=passage_event.camera_id,
            track_id=passage_event.track_id,
            signals=passage_event.signals,
            afc_match=passage_event.afc_match,
            severity="warning",
            reliability="high",
            ...
        ))
```

### 4-B-3. 데이터 모델 (DB 스키마, 권장)

```
events                  -- AI 발행 + 백엔드 발행 모든 이벤트
  event_id (PK), event_type (enum), source_event_id (nullable, FK→events.event_id),
  timestamp, gate_section_id, camera_id, confidence, track_id,
  signals (JSON), reliability, severity, afc_match (JSON),
  clip_url, raw_meta (JSON),
  stored_at

fare_taps               -- Mock AFC 수신 데이터
  fare_tap_id (PK), timestamp, gate_section_id,
  card_id_hash, card_category (enum), holder_gender (enum), result (enum),
  raw_meta (JSON), stored_at

fare_matches            -- 매칭 엔진 결과 (gate_passage event ↔ fare_tap)
  id (PK), gate_passage_event_id (FK), fare_tap_id (FK),
  time_delta_ms, matched_at

review_queue            -- 의심 큐 (confirmed_misuse + 회색지대 자동 추가)
  queue_id (PK), event_id (FK→events.event_id),
  status (pending/confirmed/false_positive),
  reviewer_id, reviewed_at, notes
```

### 4-B-4. 스키마 합의 필요 (4트랙 공통)

- `packages/schema/events/event.schema.json` v0.2.2
- `packages/schema/fare-taps/fare_tap.schema.json` v0.2.2
- 백엔드는 이 스키마를 받는 쪽 + DB 저장 쪽 + confirmed_* 발행 쪽

### 4-B-5. 안전장치

- 카드 ID 는 수신 즉시 SHA-256 해시 검증 (`^sha256:[a-f0-9]{64}$`) — 원본 절대 저장 X
- `CARD_HASH_SALT` env 로 백엔드가 salt 보관 (Mock AFC 송신기와 동일 salt 공유)
- 영상 클립 24시간 후 자동 삭제 (스케줄러 cron)
- `confirmed_misuse` 발행 시 자동으로 `review_queue` 에 추가, 자동 처벌 X — 역무원 수동 검토

---

## 4-C. 프론트엔드 / 대시보드 트랙

### 4-C-1. 새로 만드는 화면

| 화면 | 설명 |
|------|------|
| **실시간 알림 페이지** | 5종 이벤트 실시간 표시 + 알림음 (severity 별 다른 톤) |
| **의심 큐 페이지** ⭐ | 우대카드 부정사용 의심 케이스 목록 + 영상 클립 재생 + AFC 정보 + senior_probability 시각화 + 정탐/오탐 버튼 |
| **이벤트 상세 페이지** | 한 이벤트의 모든 정보 (영상, 신호, AFC 매칭) |
| **통계 대시보드** | 일/주/월 추이 + 5종 비율 + 게이트별 hotspot + 손실 추정 금액 |
| **(P1) Mock AFC 수동 UI** | 발표/시연용 — 카드 종류 선택 + tap 버튼 → 백엔드로 송신 |

### 4-C-2. UI 요구사항

- 5종 이벤트마다 색상 + 아이콘 통일 (디자인 시스템)
- 의심 큐 페이지에서 영상 ±5초 클립 재생 가능 (HTML5 video)
- 알림 권한 요청 (브라우저 Notification API)
- `new Audio().play()` 로 severity 별 알림음 (info: 짧은 비프, warning: 두 번, critical: 사이렌톤)
- 라벨링 버튼 클릭 시 백엔드 피드백 API 호출

### 4-C-3. 스키마 의존성

- 이벤트 페이로드 (`events.schema.json` v2) — 5종 + signals + reliability + severity 표시
- AFC 페이로드 (`fare_tap.schema.json` v0.2.2) — card_category / holder_gender 별 다른 처리

---

## 4-D. 인프라 트랙

### 4-D-1. GPU 환경

- 기존 추정: detector(YOLO11n) + tracker = ~2GB VRAM
- 변경 후: + pose_estimator + age_estimator = **~3~4GB VRAM**
- **요구사항: GPU VRAM ≥ 6GB (RTX 3060 8GB 이상 권장)**
- Docker GPU 패스스루 (Tyler PR #1) 검증 완료, 모델 4개 동시 inference 검증 필요

### 4-D-2. 모델 파일 배포

- Git LFS 또는 다운로드 스크립트 (`scripts/download_models.sh`)
- `models/` 는 `.gitignore` 처리
- CI/CD 파이프라인에서 자동 다운로드 단계 추가

### 4-D-3. 영상 클립 저장소

- 저장 위치: S3 또는 로컬 디스크 (MVP 는 로컬 OK)
- **24시간 후 자동 삭제 스케줄러** (cron 또는 systemd timer)
- 용량 모니터링 (디스크 가득 차면 알림)

### 4-D-4. 데이터셋 저장소

- AFAD (~수 GB) — 학습 서버에 로컬 저장, git 에 안 올림
- 자체 수집 영상 (P1) — 별도 저장소, 백업 정책

### 4-D-5. 환경 변수 관리

| 환경변수 | 용도 | 담당 |
|---------|------|------|
| `BACKEND_URL` | AI → 백엔드 이벤트 발행 endpoint | 백엔드 + 인프라 |
| `AFC_INGEST_URL` | Mock AFC 송신 → 백엔드 | 백엔드 + 인프라 |
| `MODEL_DIR` | 모델 파일 경로 | AI/CV + 인프라 |
| `VIDEO_CLIP_DIR` | 영상 클립 저장 디렉토리 | 백엔드 + 인프라 |
| `VIDEO_CLIP_TTL_HOURS` | 영상 클립 보관 시간 (기본 24) | 백엔드 |
| `CARD_HASH_SALT` | 카드 ID 해싱 salt | 백엔드 (보안) |

### 4-D-6. 시간 동기화

- AI 서버, 백엔드 서버, Mock AFC 송신기 모두 동일 시각 기준 (NTP 동기화)
- 시간 윈도우 ±1초 매칭의 전제 조건

### 4-D-7. CI/CD

- 기존 `schema-ci.yml` 에 `event.schema.json` v0.2.2 + `fare_tap.schema.json` v0.2.2 검증 추가
- 모델 파일 다운로드 단계 추가
- (P1) GPU inference smoke test

---

## 5. 공통 스키마 (4트랙 합의 사항)

스키마 실제 파일은 [`packages/schema/`](../packages/schema/) 에 있음 (single source of truth). 본 절은 v0.1.0 → v0.2.2 **변경 요약** 만. 정확한 명세는 schema 파일을 직접 참조.

### 5-1. `events/event.schema.json` v0.1.0 → **v0.2.2** 변경 요약

| 필드 | 변경 | 비고 |
|------|------|------|
| `event_id` | 🆕 **신규 required** | AI 가 발급 (`evt_<uuid4 hex>`), 백엔드 멱등성 키 (중복 저장 방지) |
| `event_type` enum | ➕ `gate_passage`, `confirmed_unpaid`, `confirmed_misuse` 추가 / ❌ `misuse` 제거 | AI 는 행동 신호만 발행, 백엔드가 AFC 매칭 후 confirmed_* 발행 |
| `gate_section_id`, `camera_id`, `track_id`, `confidence`, `timestamp`, `clip_url`, `raw_meta` | 변경 없음 | 기존 v0.1 그대로 — 코드 영향 0 |
| `signals` | 🆕 신규 optional | face_age_estimate, pose/gait_senior_score, assistive_device_detected, senior_probability, child_probability, estimated_age_group, perceived_gender, gender_confidence |
| `reliability` | 🆕 신규 optional | enum: low / mid / high |
| `severity` | 🆕 신규 optional | enum: info / warning / critical (프론트엔드 알림 강도) |
| `afc_match` | 🆕 신규 optional | 백엔드 매칭 엔진이 채움. AI 는 null 로 발행. fare_tap_id + card_id_hash + card_category + holder_gender + tap_timestamp + time_delta_ms |

### 5-2. `fare-taps/fare_tap.schema.json` v0.1.0 → **v0.2.2** 변경 요약

| 필드 | 변경 | 비고 |
|------|------|------|
| `card_category` | 🆕 **신규 required** top-level | enum: regular / senior / child / disabled / national_merit. **카드 자격 종류** (할인/면제 기준). misuse 룰의 매칭 기준 |
| `holder_gender` | 🆕 **신규 required** top-level | enum: male / female / unknown. 카드 태그 시점에 AFC 가 제공하는 카드 등록 성별. AI 의 `signals.perceived_gender` 와 비교 |
| `raw_meta.card_type` | 변경 없음 | **결제 수단** (T-money / 캐시비 등). `card_category` 와 의미 다름 — 혼동 금지 |
| `event_type`, `gate_section_id`, `card_id_hash`, `timestamp`, `result` | 변경 없음 | 기존 v0.1 그대로 |
| `card_id_hash` 패턴 | 변경 없음 | `^sha256:[a-f0-9]{64}$` (접두사 `sha256:` 포함) |

### 5-3. v0.2.2 핵심 결정 사항 (충돌 회피)

1. **`event_type` 구조 유지** — 별도 `type` 필드 만들지 않음. AI 발행과 백엔드 발행을 enum 값으로 분리
2. **`card_type` 이름 충돌 회피** — 신규 자격 필드는 `card_category`, 카드 등록 성별은 `holder_gender`. 기존 `raw_meta.card_type` (결제수단) 과 분리
3. **`event_id` AI 발급** — UUID v4 hex, 백엔드 멱등성 키
4. **`afc_match` 는 백엔드가 채움** — AI 발행 시 None. 백엔드 매칭 엔진이 ±1초 윈도로 fare_tap 찾아서 업데이트
5. **`clip_url` 이름 유지** — `video_clip_url` 같은 이름 변경 안 함 (기존 코드/예제 호환)

### 5-4. 변경 시 합의 절차

`packages/schema/` 의 어떤 파일이든 변경 = **4트랙 합의 + PR + 모든 트랙 리뷰 후 머지**.
배포 순서: schema 패키지 → 발신측 (AI / Mock AFC) → 수신측 (백엔드). 상세는 [`release.md`](release.md) 의 "트랙 간 의존성 변경" 규칙.

### 5-5. 검증

- 모든 schema + examples 는 `check-jsonschema` 로 CI 자동 검증 ([`.github/workflows/schema-ci.yml`](../.github/workflows/schema-ci.yml))
- AI 트랙: `apps/ai/src/types.py` 의 `Event` dataclass 가 schema v0.2.2 와 1:1 매칭되어야 함 — 단위 테스트로 회귀 보호
- 예제 파일: `event_jump.json`, `event_confirmed_misuse.json`, `fare_tap_approved.json`, `fare_tap_denied.json`, `fare_tap_senior.json`

### 5-6. API endpoint / 통신 프로토콜 / 인증 / 에러 처리

스키마는 **데이터 모양** 만 정의. **어떻게 주고받는지** (HTTP endpoint 명세, WebSocket, 인증, 에러 코드, 재시도, 시퀀스 등) 는 별도 문서 → [`api-contract.md`](api-contract.md).

---

## 6. Mock AFC 전략 (MVP 한정)

### 6-1. 왜 Mock 인가

실제 서울교통공사 AFC 시스템 연동은 학생 프로젝트 범위 밖. MVP 는 Mock 으로 시연/평가 + 우리 아키텍처가 실제 AFC 도 그대로 받을 수 있음을 보여줌 (source-agnostic).

### 6-2. Mock AFC 의 3가지 형태

| 방식 | 용도 | 담당 |
|------|------|------|
| **A. JSONL 파일 replay** | 자동 회귀 테스트, 영상 sync | AI/CV (테스트 자산) |
| **B. Mock HTTP 송신기** | 백엔드 endpoint 통합 검증 | 백엔드 |
| **C. 수동 UI (버튼 클릭)** | 발표/시연 인터랙티브 | 프론트엔드 |

세 가지 모두 동일 `fare_tap.schema.json` v0.2.2 페이로드 사용 — 우리 매칭 엔진 입장에서 source 무관.

### 6-3. 미래 (Phase 2, MVP 범위 외)

실제 AFC 시스템 연동 시 우리 AI 코드는 **단 한 줄도 안 바뀜**. AFC 송신기만 진짜로 교체.

---

## 7. 안전장치 / 윤리적 제약 (전 트랙)

### 7-1. 절대 안 하는 것

- ❌ 자동 게이트 차단
- ❌ 자동 사이렌 / 경광등
- ❌ 자동 신고
- ❌ 얼굴 인식 기반 개인 식별
- ❌ 영상 영구 보관
- ❌ 장애인 / 국가유공자 우대카드 외관 판단

### 7-2. 무조건 하는 것

- ✅ 카드 ID 는 SHA-256 해시로만 저장 (원본 불가)
- ✅ 영상 클립 24시간 후 자동 삭제
- ✅ 우대카드 의심 케이스 = 의심 큐만 (역무원 수동 판단)
- ✅ 모든 의심 이벤트에 `reliability` 명시
- ✅ 발표 자료에 "통계/연구 목적, 즉시 처벌 도구 아님" 명기

---

## 8. 기술 스택 (확정)

| 영역 | 기술 | 비고 |
|------|------|------|
| **사람 탐지** | YOLO11n (Ultralytics) | 사전학습 그대로 |
| **추적** | ByteTrack (supervision) | 사전학습 그대로 |
| **자세 추정** | YOLOv8-Pose (Ultralytics) | 사전학습 그대로 |
| **나이 추정** | MiVOLO | 사전학습 + AFAD fine-tuning |
| **보조기구 검출** | YOLO11n (클래스 확장) | 자체 학습 |
| **행동 인식** (P1) | ST-GCN | Phase B 학습 |
| **백엔드** | (백엔드 트랙 결정) | — |
| **DB** | (백엔드 트랙 결정) | events + fare_taps + review_queue |
| **대시보드** | (프론트엔드 트랙 결정) | 웹 |
| **스키마 검증** | JSON Schema Draft 2020-12 + check-jsonschema | 기존 schema-ci.yml |
| **이벤트 직렬화** | events.jsonl (line-delimited JSON) | 기존 형식 |
| **컨테이너** | Docker + GPU 패스스루 | Tyler PR #1 |

---

## 9. 학습 / Fine-tuning 전략 정리

| 모델 | 학습 필요? | 데이터 | 담당 |
|------|----------|--------|------|
| YOLO11n (사람 탐지) | ❌ 사전학습 그대로 | — | — |
| ByteTrack (추적) | ❌ 거의 없음 | — | — |
| YOLOv8-Pose (자세) | ❌ 사전학습 그대로 | — | — |
| **MiVOLO (나이)** | ⭕ **Fine-tuning (head-only)** | AFAD | 정우 + 수웅 |
| **보조기구 검출** | ⭕ **클래스 확장 학습** | Roboflow + 자체 | 정우 + 수웅 |
| (P1) ST-GCN 행동 인식 | ⭕ Full training | 자체 수집 | Phase B |

### 9-1. MiVOLO Fine-tuning 절차

1. AFAD 데이터셋 다운로드 (수웅)
2. 데이터 로더 작성 (수웅)
3. MiVOLO 모델의 backbone freeze, head 만 학습 가능하게 설정 (정우)
4. SmoothL1Loss + Adam optimizer 로 head fine-tune (정우)
5. 한국인 검증셋 (자체 영상 라벨링) 으로 MAE 측정 (수웅 + 정우)
6. `models/mivolo_d1_kr.pth` 저장 후 `age_estimator/` 에 통합 (정우)

### 9-2. 보조기구 검출 학습 절차

1. Roboflow 공개 데이터셋 다운로드 또는 자체 라벨링 (수웅)
2. 지팡이/워커/휠체어 3 클래스로 YOLO11n 학습 (정우)
3. `detector/` 또는 별도 `assistive_detector/` 로 통합 (정우)

---

## 10. 평가 지표

| 항목 | 목표 |
|------|------|
| 5종 룰 모두 동작 (events.jsonl 출력) | ✅ |
| jump/crawling/tailgating 시연 영상 검출률 | ≥ 90% |
| unpaid 검출 정확도 (AFC 매칭) | ≥ 95% |
| **misuse Precision (의심 중 진짜 부정사용)** | **≥ 85%** |
| **misuse Recall (명백한 케이스)** | **≥ 60%** |
| **정상 노인 false positive rate** | **≤ 2%** |
| 전체 파이프라인 처리 속도 | ≥ 10 FPS (모델 4개 동시) |
| MiVOLO 한국인 MAE (fine-tune 후) | ≤ 6세 |

평가 우선순위: **Precision > Recall.** 잡는 양 줄어도 잡을 때만큼은 정확하게.

---

## 11. 발표 / 평가 차별점

1. **5번째 룰 (우대카드 부정사용)** — 다른 팀에 없는 카테고리, 손실 임팩트 최대
2. **다중 신호 결합** — 얼굴만 보는 게 아니라 자세+보행+AFC 종합 → 단일 모델 약점 보완
3. **CCTV + AFC 매칭 아키텍처** — Source-agnostic 설계, mock → 실제 AFC 전환 시 AI 코드 0줄 수정
4. **윤리적 설계** — 자동 차단 ❌, 의심 큐만, 장애인 카드 제외, 영상 24시간 삭제
5. **한국인 Fine-tuning** — AFAD 로 MiVOLO head fine-tune, 한국인 정확도 보강
6. **확장 가능한 모듈 구조** — 새 룰 추가가 `rules/` 폴더에 파일 하나 추가로 끝
7. **단위 테스트 시범** — zone 모듈 27개 테스트 (다른 모듈 확산 권장)

---

## 12. 트랙 간 결정 사항 (모두 확정)

이전 버전에 "미정" 으로 남았던 항목들 모두 결정 완료. 4트랙 개발자는 명세 그대로 구현.

| # | 결정 사항 | 결정 | 명시 위치 |
|---|---------|------|----------|
| 1 | events.schema.json 필드 | ✅ v0.2.2 확정 | [`packages/schema/events/event.schema.json`](../packages/schema/events/event.schema.json) |
| 2 | fare_tap.schema.json 필드 | ✅ v0.2.2 확정 (`card_category`, `holder_gender` 별도 필드, `fare_tap_id` 멱등성 키) | [`packages/schema/fare-taps/fare_tap.schema.json`](../packages/schema/fare-taps/fare_tap.schema.json) |
| 3 | Mock AFC 송신 채널 | HTTP POST `/api/v1/fare-taps`. fallback: 로컬 JSONL | [`api-contract.md`](api-contract.md) §11-8 |
| 4 | 영상 클립 저장 | 로컬 디스크 `/var/lib/gateguard/clips/` + 24h cron 삭제 + 서명 URL | [`api-contract.md`](api-contract.md) §13 |
| 5 | 카드 ID 해싱 시점 | Mock AFC 송신기가 송신 전 해시. 백엔드는 검증만 (원본 절대 수신 X) | [`api-contract.md`](api-contract.md) §8-3, §11-7 |
| 6 | 시간 동기화 | UTC ISO-8601 강제 + 시스템 chronyd + 백엔드 drift 모니터링 | [`api-contract.md`](api-contract.md) §9, §11-12 |
| 7 | GPU VRAM 요구사항 | 6GB 이상 (RTX 3060 8GB 권장). Tyler PR #1 GPU 패스스루 검증 필요 | [`mvp-features.md`](mvp-features.md) §4-D-1 |
| 8 | 의심 큐 워크플로우 | confirmed_misuse 발화 시 자동 큐 추가. 역무원이 영상 + 정탐/오탐 라벨링 | [`api-contract.md`](api-contract.md) §2-3, §6-5 |
| 9 | 알림음 톤 (severity 별) | info: 짧은 비프, warning: 두 번, critical: 사이렌톤 (browser `Audio.play()`) | [`api-contract.md`](api-contract.md) (mvp-features.md §4-C-2) |
| 10 | 통계 단가 (손실 추정) | 기본 1370원 (지하철 기본요금) + 운영자가 쿼리 파라미터로 변경 가능 | [`api-contract.md`](api-contract.md) §2-4 (`/api/v1/loss-estimate`) |
| 11 | DB 스택 | PostgreSQL 15 + TimescaleDB | [`api-contract.md`](api-contract.md) §13 |
| 12 | 백엔드 프레임워크 | FastAPI (Python 3.11) | [`api-contract.md`](api-contract.md) §13 |
| 13 | 프론트엔드 스택 | React (Vite) + TypeScript | [`api-contract.md`](api-contract.md) §13 |
| 14 | WebSocket vs SSE | WebSocket (`/ws/v1/events`) | [`api-contract.md`](api-contract.md) §3 |
| 15 | 인증 | 서비스 토큰 (AI/AFC) + JWT (역무원) | [`api-contract.md`](api-contract.md) §1 |
| 16 | 멱등성 정책 | event_id / fare_tap_id 둘 다 발신자 발급 | [`api-contract.md`](api-contract.md) §5 |
| 17 | 매칭 윈도우 | ±1초 + 양방향 1초 buffer | [`api-contract.md`](api-contract.md) §11-2 |
| 18 | denied fare_tap 처리 | 매칭 X. 같은 카드/게이트 ±1초 내 approved 없으면 confirmed_unpaid | [`api-contract.md`](api-contract.md) §11-1 |
| 19 | 다중 매칭 충돌 | 시간 가장 가까운 1:1 nearest neighbor | [`api-contract.md`](api-contract.md) §11-3 |
| 20 | Multi-camera | MVP 는 게이트당 카메라 1대. multi-camera dedupe 는 Phase 2 | [`api-contract.md`](api-contract.md) §11-5 |

→ **변경 시:** 본 표 + 해당 명시 위치 둘 다 업데이트 후 4트랙 합의.

---

## 13. 관련 문서

- [전체 README](../README.md)
- [무임승차 감지 전략 (CCTV + AFC 매칭)](./detection-strategy.md)
- [전체 아키텍처](./architecture.md)
- [브랜치 / 커밋 규칙](./branching.md)
- [AI/CV 트랙 가이드](../apps/ai/CONTRIBUTING.md)
- [공통 스키마](../packages/schema/README.md)

---

## 14. 변경 요약 (TL;DR)

**기존 (4종 룰):**
```
CCTV → 사람 탐지/추적 → jump/crawling/tailgating/unpaid 룰 → 이벤트 발행
```

**MVP (AI 행동 이벤트 + AFC 매칭 + 백엔드 확정 판정):**
```
CCTV → 사람 탐지/추적 → zone 매칭                  ┐
                            ↓                       │
                       pose/age 추정                │── 결합
                            ↓                       │
                  eligibility_signals (다중 신호)    │
                            ↓                       │
Mock AFC → fare_tap (card_category + holder_gender) ─ 매칭 ┘
                            ↓
       AI 행동 룰 (jump/crawling/tailgating/unpaid/gate_passage)
                            ↓
           이벤트 발행 (signals + reliability + severity)
                            ↓
      백엔드 → 의심 큐 → 역무원 검토 → 정탐/오탐 피드백
```

**핵심 추가:**
- 백엔드 confirmed_misuse 판정
- AFC 매칭
- pose/age/eligibility_signals 모듈
- 의심 큐 워크플로우
- 한국인 Fine-tuning
- Mock AFC (3가지 형태)
- 윤리/보안 안전장치 (해싱/24h 삭제/자동 차단 금지)
