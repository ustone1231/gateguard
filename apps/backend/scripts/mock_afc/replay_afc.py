"""Mock AFC JSONL replay.

파일의 첫 timestamp를 현재 시각으로 보정하고,
이후 이벤트 간격대로 POST /api/v1/fare-taps를 호출한다.

사용:
    python scripts/mock_afc/replay_afc.py
    python scripts/mock_afc/replay_afc.py --file scripts/mock_afc/sample_afc.jsonl
    python scripts/mock_afc/replay_afc.py --file scripts/mock_afc/sample_afc.jsonl --speed 2.0

환경 변수:
    BACKEND_URL        백엔드 base URL (기본: http://localhost:8000)
    AFC_SERVICE_TOKEN  서비스 토큰 (기본: dev-afc-service-token-please-change-32)
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import urllib.request
import urllib.error


BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
AFC_TOKEN = os.environ.get("AFC_SERVICE_TOKEN", "dev-afc-service-token-please-change-32")
FALLBACK_FILE = Path("runs/mock_afc_failed.jsonl")


def main() -> None:
    args = parse_args()
    lines = Path(args.file).read_text(encoding="utf-8").splitlines()
    taps = [json.loads(line) for line in lines if line.strip()]

    if not taps:
        print("파일이 비어있습니다.")
        return

    # 첫 timestamp를 현재 시각으로 보정
    first_ts = datetime.fromisoformat(taps[0]["timestamp"])
    now = datetime.now(timezone.utc)
    offset = now - first_ts

    print(f"총 {len(taps)}건 재생 시작 (speed={args.speed}x) → {BACKEND_URL}")

    prev_ts = first_ts
    for tap in taps:
        original_ts = datetime.fromisoformat(tap["timestamp"])
        adjusted_ts = original_ts + offset
        tap["timestamp"] = adjusted_ts.isoformat()

        # 이전 이벤트와의 간격 대기
        gap = (original_ts - prev_ts).total_seconds()
        if gap > 0:
            time.sleep(gap / args.speed)
        prev_ts = original_ts

        ok = send_tap(tap)
        status = "✅" if ok else "❌ fallback"
        print(f"  {status}  {tap['fare_tap_id']}  {tap['gate_section_id']}  "
              f"{tap['card_category']}  {tap['result']}  {tap['timestamp']}")

    print("완료.")


def send_tap(payload: dict) -> bool:
    url = f"{BACKEND_URL}/api/v1/fare-taps"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AFC_TOKEN}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status < 300
    except urllib.error.HTTPError as e:
        print(f"    HTTP {e.code}: {e.read().decode()}")
    except Exception as e:
        print(f"    오류: {e}")

    _save_fallback(payload)
    return False


def _save_fallback(payload: dict) -> None:
    FALLBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with FALLBACK_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mock AFC JSONL replay")
    parser.add_argument(
        "--file",
        default="scripts/mock_afc/sample_afc.jsonl",
        help="재생할 JSONL 파일 경로",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="재생 속도 배율 (기본 1.0, 2.0이면 2배 빠르게)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
