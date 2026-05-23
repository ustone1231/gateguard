"""EventPublisher 추상.

AI가 이벤트를 어디로 보낼지 추상화.
- 개발 초기: FilePublisher (JSONL 파일)
- MVP 통합: HttpPublisher (POST /api/events)
- 확장: RedisPublisher, KafkaPublisher 등
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import Event


class EventPublisher(ABC):
    @abstractmethod
    def publish(self, event: Event) -> bool:
        """이벤트 발행. 성공 시 True."""
        ...

    @abstractmethod
    def close(self) -> None:
        ...
