"""단건 fare_tap 송신 스크립트 (시연/수동 테스트용).

사용:
    python scripts/mock_afc/send_tap.py --gate gate_01 --category senior
    python scripts/mock_afc/send_tap.py --gate gate_01 --category regular --result denied

환경 변수:
    BACKEND_URL        백엔드 base URL (기본: http://localhost:8000)
    AFC_SERVICE_TOKEN  서비스 토큰
    CARD_HASH_SALT     카드 해싱 salt (백엔드와 동일해야 함)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone


BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
AFC_TOKEN = os.environ.get("AFC_SERVICE_TOKEN", "dev-afc-service-token-please-change-32")
CARD_HASH_SALT = os.environ.get("CARD_HASH_SALT", "dev-card-hash-salt")


def main() -> None:
    args = parse_args()

    tap = build_tap(
        gate_section_id=args.gate,
        card_category=args.category,
        result=args.result,
    )

    print(f"송신 → {BACKEND_URL}/api/v1/fare-taps")
    print(json.dumps(tap, ensure_ascii=False, indent=2))

    url = f"{BACKEND_URL}/api/v1/fare-taps"
    body = json.dumps(tap).encode()
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
            result = json.loads(resp.read().decode())
            print(f"✅ {resp.status}  {result}")
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP {e.code}: {e.read().decode()}")
    except Exception as e:
        print(f"❌ 오류: {e}")


def build_tap(gate_section_id: str, card_category: str, result: str) -> dict:
    ts_ms = int(time.time() * 1000)
    uid = uuid.uuid4().hex[:8]
    card_raw = f"mock_card_{uid}"

    raw = f"{CARD_HASH_SALT}:{card_raw}".encode()
    card_id_hash = f"sha256:{hashlib.sha256(raw).hexdigest()}"

    fare_amount = 0 if card_category in ("senior", "child") else 1370

    tap: dict = {
        "fare_tap_id": f"tap_{ts_ms}_{uid}",
        "event_type": "fare_tap",
        "gate_section_id": gate_section_id,
        "card_id_hash": card_id_hash,
        "card_category": card_category,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "result": result,
        "raw_meta": {
            "fare_amount": fare_amount,
            "card_type": "T-money",
            "terminal_id": f"term_{gate_section_id}_a",
        },
    }
    if result == "denied":
        tap["raw_meta"]["denied_reason"] = "잔액 부족"

    return tap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="단건 fare_tap 송신")
    parser.add_argument("--gate", default="gate_01", help="gate_section_id (기본: gate_01)")
    parser.add_argument(
        "--category",
        default="regular",
        choices=["regular", "senior", "child", "disabled", "national_merit"],
        help="card_category (기본: regular)",
    )
    parser.add_argument(
        "--result",
        default="approved",
        choices=["approved", "denied", "error"],
        help="결제 결과 (기본: approved)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
