# 무임승차 탐지 전략

> GateGuard 는 "**행동 + 결제**" 두 신호를 합쳐 진짜 무임승차를 잡는다.

---

## 1. 문제 정의

지하철 무임승차를 "**카드를 찍지 않고 게이트를 통과하는 행위**" 라고 정의할 때, 이 문제는 단일 데이터 소스로는 풀 수 없다.

| 접근 | 한계 |
|------|------|
| **CCTV 만 본다** | 사람이 통과한 건 보이지만 결제했는지 모름. 정상 보행으로 결제 안 한 사람을 못 잡음 |
| **결제 데이터만 본다** | 결제 안 된 게이트의 통과 여부 모름. 누가 우회/점프했는지 모름 |
| **둘 다 본다** | ✅ "통과는 있는데 결제가 없음" = 무임승차 확정 |

**핵심 통찰:** 무임승차는 **"있어야 할 결제가 없는 사건"**. 따라서 두 데이터를 **시간/공간 매칭** 으로 비교해야 한다.

---

## 2. 해결 전략 한 줄

> **CCTV → AI 행동 분석 + AFC → 결제 트랜잭션** 을 백엔드에서 **±1초 윈도로 매칭**, 매칭 안 된 통과를 무임승차로 확정한다.

---

## 3. 데이터 흐름

```
┌──────────────────┐                    ┌──────────────────────┐
│   CCTV 카메라    │                    │   게이트 카드 리더   │
│  (RTSP/30fps)    │                    │   (RFID/NFC AFC)     │
└────────┬─────────┘                    └──────────┬───────────┘
         │                                         │
         ▼                                         ▼
┌──────────────────┐                    ┌──────────────────────┐
│   AI 파이프라인  │                    │  AFC 시스템 /        │
│ YOLO + ByteTrack │                    │  게이트 컨트롤러     │
│ + 4종 룰 엔진    │                    │                      │
└────────┬─────────┘                    └──────────┬───────────┘
         │                                         │
         │ POST /api/events                        │ POST /api/fare-taps
         │ {gate_passage, jump, tailgating, ...}   │ {fare_tap, approved, ...}
         │                                         │
         └─────────────┬───────────────────────────┘
                       ▼
              ┌─────────────────────┐
              │   백엔드 매칭 엔진  │
              │  (시간/공간 cross-  │
              │   check, ±1초)      │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   판정 결과         │
              │  ✅ 매칭됨 (정상)   │
              │  🚨 통과만 (무임)   │
              │  ⚠️ 이상행동 + 결제 │
              │      (회색지대)     │
              └──────────┬──────────┘
                         ▼
                  운영자 대시보드
                  (실시간 알림 + 클립)
```

---

## 4. 데이터 소스 1: AI 행동 분석

CCTV 영상에서 다음 4종 부정 행위 + 정상 게이트 통과를 이벤트로 발행.

| 이벤트 타입 | 무엇을 잡나 | 핵심 신호 | 신뢰도 |
|-------------|------------|----------|--------|
| `gate_passage` | 사람이 게이트 entry_line 통과 | line crossing | 높음 |
| `jump` | 게이트 차단봉 뛰어넘기 | bbox 상단 수직 이동 속도 + 높이 변동 | 높음 |
| `tailgating` | 한 결제로 두 명 동시 입장 | 동일 게이트 1.5초 이내 2 트랙 통과 | 중간 (가족 동반 오탐 가능) |
| `crawling` | 차단봉 밑 기어가기 | bbox 높이가 baseline 55% 이하로 8 프레임 유지 | 미검증 |
| `unpaid` (룰 단계) | 게이트 우회 / 역방향 | entry 안 지나고 exit 만 통과 | 미검증 (MVP 임시 룰) |

**한계:** AI 는 "행동" 만 본다. "결제 여부" 는 모른다.

- → **이상 행동 발견** = 무임승차 가능성 높음 (강한 신호)
- → **정상 보행 통과** = 무임승차일 수도, 아닐 수도 (AI 만으로는 판정 불가)

상세 동작은 [`apps/ai/README.md`](../apps/ai/README.md) 참고.

---

## 5. 데이터 소스 2: AFC 결제 트랜잭션

실제 지하철 게이트는 카드 탭 시 **AFC (Automatic Fare Collection)** 시스템이 트랜잭션을 기록한다.

```
2026-05-24T14:23:15.847+09:00  station=강남  gate=03  card_hash=ab123  result=APPROVED
```

이 기록이 **"언제, 어느 게이트에서, 결제가 성공했는가"** 의 ground truth.

새 이벤트 타입 `fare_tap` 으로 백엔드에 인입:

```json
{
  "event_type": "fare_tap",
  "gate_section_id": "gate_03",
  "card_id_hash": "sha256:ab123...",
  "card_category": "senior",
  "holder_gender": "female",
  "timestamp": "2026-05-24T14:23:15.847+09:00",
  "result": "approved",
  "raw_meta": {
    "fare_amount": 1370,
    "card_type": "T-money"
  }
}
```

**개인정보 보호:** card_id 는 원본 저장 금지. 해시(sha256 + salt) 만 저장.

**우대 자격 필드:** `card_category` 는 카드의 할인/면제 자격, `holder_gender` 는 AFC 가 제공하는 카드 등록 성별이다. 결제 수단은 `raw_meta.card_type` 에 둔다.

---

## 6. 매칭 엔진

백엔드의 비동기 워커가 두 이벤트 스트림을 **±1초 슬라이딩 윈도** 로 매칭.

**의사코드:**

```python
def on_gate_passage(passage_event):
    matched_taps = FareTap.find(
        gate=passage_event.gate_section_id,
        time_range=(
            passage_event.timestamp - 1s,
            passage_event.timestamp + 1s,
        ),
        result="approved",
        unmatched=True,   # 이미 다른 통과에 매칭 안 된 것
    )
    if matched_taps:
        # 가장 가까운 시간의 tap 을 매칭
        FareMatch.create(passage=passage_event, tap=matched_taps[0])
        # 카드 자격과 AI 보조 신호가 불일치하면 confirmed_misuse,
        # 아니면 정상 통과로 분류 (별도 알림 X)
    else:
        # 결제 없는 통과 = 무임승차 확정
        Alert.emit(
            severity="HIGH",
            type="confirmed_unpaid",
            source_event=passage_event,
            clip_url=passage_event.clip_url,
        )
```

**왜 ±1초인가:**
- 카드 탭 → 게이트 열림 → 사람 통과 까지 보통 0.3~0.8 초
- 시스템 시간 동기화 오차 ±0.2 초 가정
- 너무 좁으면 매칭 누락 (false unpaid), 너무 넓으면 다른 사람과 잘못 매칭

**우대카드 부정사용 판단:** AI 는 나이/성별을 확정하지 않고 `signals.senior_probability`, `signals.child_probability`, `signals.perceived_gender`, `signals.gender_confidence` 만 제공한다. 백엔드는 매칭된 `fare_tap.card_category` / `fare_tap.holder_gender` 와 비교해 high confidence 불일치일 때만 `confirmed_misuse` 를 발행한다. confidence 낮은 경우는 자동 확정 금지.

---

## 7. 시나리오별 판정 매트릭스

매칭 결과 + AI 이상 행동 + 우대 자격 신호 조합으로 판정.

| AI 행동/자격 신호 | AFC 매칭 | 판정 | 운영자 처리 |
|------------------|----------|------|------------|
| 이상 행동 없음 + 자격 일치 | ✅ approved | 🟢 **정상** | 알림 없음 (로그만) |
| 이상 행동 없음 | ❌ approved 없음 | 🔴 **무임승차 확정** (`confirmed_unpaid`) | 즉시 알림, 클립 첨부 |
| jump/crawling/tailgating 등 | ✅ approved | 🟡 **회색지대** | 의심 알림 — 결제 후 추가 인원? |
| jump/crawling/tailgating 등 | ❌ approved 없음 | 🔴🔴 **명백한 무임승차** | 최고 우선순위 알림 |
| 우대 자격 high-confidence 불일치 | ✅ approved | 🔴 **우대카드 부정사용 의심** (`confirmed_misuse`) | 의심 큐 추가, 역무원 검토 |

**회색지대 사례:**
- "1명이 결제 + tailgating 발화" → 2명 중 1명만 결제 → 1명 무임
- "1명이 결제 + jump 발화" → 같은 사람이 점프했을 수도, 다른 사람이 동시 점프했을 수도

→ 회색지대는 운영자가 클립 보고 최종 판정. AI 가 "여기 의심스러움" 까지만 표시.

---

## 8. 시간 동기화 (Critical)

매칭의 정확도는 **AI 와 AFC 의 시계 정합성** 에 100% 의존.

- 둘 다 동일 **NTP 서버** 와 동기화 (운영사 NTP 또는 `time.google.com`)
- 시계 오차 모니터링: 1초 이상 차이나면 매칭 신뢰도 떨어짐 → 알림
- 이벤트 timestamp 는 모두 **UTC + ISO 8601** (`timezone-aware`) 로 저장

---

## 9. MVP 시연 vs 실서비스

### MVP 단계 (현재 ~ PoC 시연)

실제 AFC 시스템 접근권이 없으므로:

| 컴포넌트 | MVP 대체 |
|----------|----------|
| 실제 카드 리더 | **Mock AFC 시뮬레이터** — 운영자가 버튼 누르거나 시나리오 스크립트로 `fare_tap` 이벤트 발행 |
| 실제 지하철 게이트 영상 | 자체 촬영 영상 또는 공개 데이터셋 |
| 운영사 NTP | 공용 NTP (`pool.ntp.org`) |

**MVP 데모 흐름:**
1. 시연 영상 재생 (5명 통과)
2. 시뮬레이터에서 결제 3건 전송
3. 매칭 엔진 → 2명 무임승차 알림
4. 운영자 대시보드에서 클립으로 확인

### 실서비스 단계 (사업화 이후)

| 컴포넌트 | 필요 작업 |
|----------|-----------|
| AFC 연동 | 운영사 (서울교통공사/코레일) 와 PoC 협약 + real-time API 또는 일배치 |
| 카메라 설치 | 게이트별 카메라 위치 + 화각 조정 + Zone Editor 로 polygon 셋업 |
| 시계 동기화 | 운영사 NTP 서버 사용 |
| 개인정보 | card_id 해시화 + 영상 데이터 retention 정책 |

→ AFC 데이터 접근권이 가장 큰 사업적 장벽. PoC 단계에서는 자체 시뮬레이터로 시연하고, 실서비스는 운영사 협의 후.

---

## 10. 한계와 윤리적 고려

### 기술적 한계

| 한계 | 영향 | 대응 |
|------|------|------|
| 카메라 사각지대 | AI 가 통과를 놓침 → false negative | 게이트별 카메라 2대 또는 측면 + 위 |
| 동시 다발 통과 | 트랙 ↔ 결제 매칭 모호 | tailgating 룰 + 가장 가까운 시간 매칭 + 운영자 확인 |
| AFC ↔ AI 시계 어긋남 | 매칭 false negative | NTP 모니터링 |
| 룰 임계치 카메라 의존 | 점프/기는 자세 임계치가 카메라 각도에 따라 다름 | 카메라별 config 분리 + 운영 초기 튜닝 |

### 윤리적/법적 고려

- **개인 식별 금지**: 얼굴 인식 / 신원 파악 기능 일절 없음. 트랙 ID 는 세션 내에서만 유효, 영상 떠나면 사라짐
- **영상 보관 기간**: 알림 발생 클립 외에는 N일 후 자동 삭제 (운영 정책 협의)
- **카드 해시화**: card_id 원본 저장 금지. salt + sha256 후 30일 보관
- **운영자 권한**: 클립 다운로드 / 외부 공유 시 감사 로그 필수
- **오탐의 사회적 비용**: "정상인을 무임승차로 표시" 는 신뢰도 데미지 → 알림은 항상 "의심 / 확정" 등급 분리, 확정은 다중 신호 합치만

---

## 11. 한 줄 요약

> **AI 가 "어떻게" 통과했는지 보고, AFC 가 "결제했는지" 알려준다. 둘을 매칭해서 "결제 없는 통과 = 무임승차" 를 자동 확정한다. CCTV 단독으론 못 잡는다.**

---

## 관련 문서

- [전체 시스템 아키텍처](architecture.md) — 트랙 분리 / 기술 스택
- [AI 파이프라인 상세](../apps/ai/README.md) — 4종 룰 구현
- [공통 이벤트 스키마](../packages/schema/README.md) — Event 페이로드 정의
- [브랜치 전략](branching.md) — 협업 워크플로
