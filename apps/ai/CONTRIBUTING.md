# AI/CV 트랙 가이드

> AI/CV 트랙 4명이 어디서 무엇을 어떻게 작업하는지 한 페이지 정리.
> 처음 들어왔으면 이 문서 먼저 읽고 본인 영역 P0 작업부터 시작하면 됩니다.

---

## 0. 30초 요약

- **이 트랙이 하는 일:** CCTV 영상 → 사람 탐지/추적/룰 판정 → 백엔드 `POST /api/events` 로 이벤트 발행
- **현재 상태:** AI 도구로 **Day 1~10 베이스 코드를 미리 깔아둠.** 동작은 함 (`day10_full_pipeline.py` 까지 검증). 다만 안정성/테스트/튜닝 다수 미흡 → 각자 본인 영역 P0 부터 본격 작업
- **본인 영역 안에서만 작업.** 다른 사람 폴더 건드릴 일 있으면 미리 협의

---

## 1. 4명 역할 ↔ 폴더 매핑

| # | 담당자 | 역할 | 담당 폴더 | 핵심 책임 |
|---|--------|------|----------|-----------|
| 4 | **정우** | AI/CV Lead | `src/detector/` + `src/tracker/` + `src/pipeline/` | Detector/Tracker ABC, YOLO/ByteTrack 구현, 전체 통합 루프 |
| 5 | **수웅** | Data / Annotation | (`dataset/` 신규 + `scripts/`) | 라벨 컨벤션, train/val/test 분할, 데이터 균형 |
| 6 | **유석** | Gate Section Logic | `src/zone/` | polygon, line crossing, SectionMatcher |
| 7 | **민지** | Event Rule Engineer | `src/rules/` + `src/publisher/` | jump/crawling/tailgating/unpaid 룰, cooldown, 이벤트 발행 |

**원칙:** 본인 폴더만 만진다. `src/types.py` (공통 자료형) 변경은 4명 합의 사안.

---

## 2. 코드 구조

```
apps/ai/
├── config/
│   ├── gate_sections.json     # 카메라별 polygon / line (#6 책임)
│   └── pipeline.json          # 모델/룰/publisher 임계치 (전원 공유)
├── src/
│   ├── types.py               # 공통 자료형 (Detection, Track, Event) — 4명 합의
│   ├── detector/              # #4
│   │   ├── base.py            #   ← ABC: Detector
│   │   └── yolo_detector.py   #   ← 구현 1 (YOLO11n)
│   ├── tracker/               # #4
│   │   ├── base.py            #   ← ABC: Tracker
│   │   └── bytetrack_tracker.py
│   ├── zone/                  # #6
│   │   ├── section.py         #   ← GateSection 데이터 모델
│   │   ├── geometry.py        #   ← 순수 기하 함수
│   │   └── matcher.py         #   ← SectionMatcher
│   ├── rules/                 # #7
│   │   ├── base.py            #   ← ABC: Rule + RuleEngine + TrackHistory
│   │   ├── jump.py / crawling.py / tailgating.py / unpaid.py
│   ├── publisher/             # #7
│   │   ├── base.py            #   ← ABC: EventPublisher
│   │   ├── file_publisher.py
│   │   └── http_publisher.py
│   └── pipeline/              # #4 — 모든 모듈을 묶는 통합
│       ├── pipeline.py
│       ├── factory.py         #   ← config → 어떤 구현 쓸지 결정
│       └── visualizer.py
├── scripts/
│   ├── day1_hello_yolo.py     # 단계별 독립 실행 (베이스라인 검증용)
│   ├── day2_tracking.py
│   ├── day3_sections.py
│   ├── day5_line_crossing.py
│   ├── day6_jump_rule.py
│   ├── day8_all_rules.py
│   └── day10_full_pipeline.py # ← config 기반 전체 파이프라인
└── tests/
    ├── conftest.py
    ├── test_geometry.py       # #6 시범 사례 (27개 테스트 통과)
    ├── test_matcher.py
    └── test_section.py
```

### 의존성 규칙

```
모든 모듈 → src/types.py 만 import
rules → zone (GateSection 사용. 이게 유일한 cross-module 의존)
pipeline → 모든 모듈 (통합 책임이라 정상)
```

→ **본인 모듈 안에서 작업하면 다른 사람 영향 0.** 자료형 (types.py) 만 조심.

---

## 3. 코드 규칙

### 3-1. 트랙 경계
- 본인 폴더만 만진다. `CODEOWNERS` 가 다른 폴더 건드린 PR 에 다른 담당자 자동 호출
- 다른 폴더 손대야 할 이슈는 GitHub 또는 카톡으로 담당자에게 위임

### 3-2. `types.py` 변경 = 4명 합의
- `Detection`, `Track`, `Event` 의 필드/자료형은 4트랙 인터페이스. 변경 시 4명 동의 + 슬랙 공지

### 3-3. 모든 PR 에 단위 테스트
- 새 함수/메서드 추가 시 `tests/test_<모듈>.py` 에 테스트 1개 이상
- `tests/test_geometry.py` + `test_matcher.py` + `test_section.py` (zone 모듈) 가 시범 사례
- 실행: `./venv/bin/python -m pytest tests/`

### 3-4. 브랜치 / 커밋
- 브랜치: `feature/ai-<역할>-<짧은 설명>` 예: `feature/ai-zone-hysteresis`
- 커밋: `feat(ai/zone): SectionMatcher 에 hysteresis 도입` (Conventional Commits)
- PR base = `develop` (Git Flow). 상세: 루트 [`docs/branching.md`](../../docs/branching.md)

### 3-5. config 변경
- `config/pipeline.json` 의 임계치는 본인 영역 (`rules.jump.*` 는 #7) 만 수정
- 새 임계치 추가 시 README 또는 docstring 에 기본값 근거 명시

---

## 4. 현재 상태 (2026-05-25)

### ✅ 검증된 것
- Day 1 사람 탐지, Day 2 추적, Day 3 섹션 매칭
- Day 5 line crossing (양방향 감지 OK)
- Day 6 jump 룰 (5건 발화)
- Day 8 4종 룰 통합 (jump 5 + tailgating 3 발화)
- Day 10 풀 파이프라인 (events.jsonl 형식 백엔드 명세와 1:1 일치)
- zone 모듈 단위 테스트 27개 통과

### ❌ 미흡한 것 (= 각자 작업 거리)
- **트랙 진동** — day5 에서 한 트랙이 같은 line 16번 발화. cooldown 만으론 부족
- **테스트 부족** — `tests/` 에 zone 모듈만 있음. 다른 모듈은 0
- **카메라 의존 임계치** — 카메라 각도/거리 바뀌면 룰 발화 깨짐
- **crawling/unpaid 룰 미검증** — 시나리오 영상 없음
- **HttpPublisher** 백엔드 미구축이라 file mode 만 검증

---

## 5. 본인 영역별 작업 거리 (우선순위순)

각자 본인 영역에서 P0 부터.

### 🔴 `src/zone/` — 유석 (#6 Gate Section Logic)
- **[P0] SectionMatcher 진동 → hysteresis 도입**
  - 발 위치가 polygon 경계에서 들락거리면 매칭이 흔들림 (day5 에서 발견)
  - N프레임 연속 같은 결과여야 확정 / EMA / margin
- **[P1] 정규화 좌표 변환** — 영상 해상도 바뀌면 polygon 좌표 다 깨짐 (config 의 `_coord_note` 참고)
- **[P1] 다중 카메라 지원** — 현재 `load_sections` 가 카메라 1대만 다룸
- **[P2] polygon validation** — 자기교차, 점 3개 미만 등 거부

### 🔴 `src/detector/` + `src/tracker/` + `src/pipeline/` — 정우 (#4 Lead)
- **[P0] 카메라별 임계치 config 노출** — 모델 conf/iou 가 카메라 의존적
- **[P0] supervision ByteTrack deprecation 마이그**
  - 현재 `supervision 0.28.0`, `v0.30.0` 에서 ByteTrack 제거됨
  - 마이그 가이드 따라 교체
- **[P1] detector/tracker 단위 테스트 추가** (zone 모듈 시범 참고)

### 🔴 `src/rules/` + `src/publisher/` — 민지 (#7 Event Rule Engineer)
- **[P0] 동일 트랙 다중 발화 완화** — day10 에서 같은 jump 가 4번 발화. cooldown 만으론 부족 → confidence 평균화 / 트랙 평활화 도입
- **[P1] crawling / unpaid 룰 실증** — 시나리오 영상 직접 촬영 후 회귀 테스트로 등록
- **[P1] HttpPublisher `BACKEND_URL` env 지원** — 인프라 PR #1 후속 (현재 `pipeline.json` 만 읽음)
- **[P1] rules / publisher 단위 테스트 추가**

### 🔴 `dataset/` + `scripts/` — 수웅 (#5 Data / Annotation)
- **[P0] 데이터 폴더 구조 + 라벨 코드 통일** — `crawling/jump/tailgating/unpaid/normal` 라벨 컨벤션 확정
- **[P0] train / val / test 분할 스크립트** (역·카메라 단위로 leakage 없게)
- **[P1] crawling / unpaid 영상 확보** — 현재 영상에 시나리오 없음
- **[P1] 데이터셋 README** — 다른 멤버가 보고 바로 학습 돌리게

---

## 6. 시작 가이드 (5분)

```bash
# 1. 클론 + 본인 영역 폴더로 이동
git clone https://github.com/ustone1231/gateguard.git
cd gateguard/apps/ai

# 2. venv 셋업
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pytest                      # 테스트용

# 3. 테스트 실행 → 27개 통과 보면 환경 OK
python -m pytest tests/

# 4. 직접 영상 한 번 돌려보기 (test.mp4 본인이 준비)
python scripts/day10_full_pipeline.py test.mp4
# → 콘솔에 stats 출력, runs/events.jsonl 생성

# 5. 본인 영역 P0 작업 시작
git checkout develop
git pull
git checkout -b feature/ai-<역할>-<설명>
# 작업 후
git commit -m "feat(ai/<역할>): <설명>"
# push 는 작업 끝나면 카톡으로 알려주세요 (PR review 후 머지)
```

---

## 7. 관련 문서

- [루트 README](../../README.md)
- [무임승차 탐지 전략](../../docs/detection-strategy.md) — 우리가 왜 이걸 만드는가
- [전체 시스템 아키텍처](../../docs/architecture.md)
- [브랜치 전략 / 커밋 규칙](../../docs/branching.md)
- [공통 스키마](../../packages/schema/README.md) — Event / GateSection / FareTap

---

질문/막힘 → 카톡 AI 트랙 톡방.
