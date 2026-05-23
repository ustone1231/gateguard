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
- event_type: `jump`, `crawling`, `tailgating`, `unpaid`

### v0.2.0 (예정)
- `action_recognition` 결과 통합 (Option B 학습 트랙)
- ...
