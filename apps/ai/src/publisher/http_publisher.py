"""실제 백엔드 연동용 Publisher. POST /api/v1/events.

특징:
- requests로 동기 POST (가벼움)
- 실패 시 로컬 JSONL에 fallback 저장 → 백엔드 복구 후 재전송 가능
- Bearer 토큰 옵션 (md의 OAuth2/JWT)
- endpoint 는 full URL (factory.resolve_http_endpoint 가 결정 — Issue #3)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import requests

from .base import EventPublisher
from ..types import Event

log = logging.getLogger(__name__)


class HttpPublisher(EventPublisher):
    def __init__(
        self,
        endpoint: str,
        timeout: float = 2.0,
        token: str | None = None,
        fallback_path: str | Path = "runs/events_failed.jsonl",
    ):
        self._endpoint = endpoint
        self._timeout = timeout
        self._headers: dict[str, str] = {"Content-Type": "application/json"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"
        self._fallback_path = Path(fallback_path)
        self._fallback_path.parent.mkdir(parents=True, exist_ok=True)
        self._session = requests.Session()

    def publish(self, event: Event) -> bool:
        payload = event.to_payload()
        try:
            resp = self._session.post(
                self._endpoint,
                json=payload,
                headers=self._headers,
                timeout=self._timeout,
            )
            if 200 <= resp.status_code < 300:
                return True
            log.warning("backend rejected event: %s %s", resp.status_code, resp.text[:200])
            self._save_fallback(payload)
            return False
        except requests.RequestException as e:
            log.warning("backend unreachable: %s", e)
            self._save_fallback(payload)
            return False

    def _save_fallback(self, payload: dict) -> None:
        with self._fallback_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:
            pass
