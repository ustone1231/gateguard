"""JSONL 파일에 이벤트 한 줄씩 append.

Day 1~10 동안 백엔드 없이 개발할 때 사용.
백엔드 떴으면 HttpPublisher로 교체.
"""
from __future__ import annotations

import json
from pathlib import Path

from .base import EventPublisher
from ..types import Event


class FilePublisher(EventPublisher):
    def __init__(self, file_path: str | Path):
        self._path = Path(file_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = self._path.open("a", encoding="utf-8")

    def publish(self, event: Event) -> bool:
        line = json.dumps(event.to_payload(), ensure_ascii=False)
        self._fp.write(line + "\n")
        self._fp.flush()
        return True

    def close(self) -> None:
        try:
            self._fp.close()
        except Exception:
            pass
