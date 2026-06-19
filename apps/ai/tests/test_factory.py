"""factory.resolve_http_endpoint 우선순위 테스트.

규칙 (Issue #3 합의):
- BACKEND_URL env > pipeline.json http_endpoint > http://localhost:8000 fallback
- 입력은 base URL, 반환은 /api/v1/events 가 결합된 full URL
"""
from __future__ import annotations

from src.pipeline.factory import (
    DEFAULT_BACKEND_BASE_URL,
    EVENTS_PATH,
    resolve_http_endpoint,
    resolve_http_token,
)


def test_env_takes_priority(monkeypatch):
    monkeypatch.setenv("BACKEND_URL", "http://backend:8000")
    assert resolve_http_endpoint("http://other:9999") == "http://backend:8000/api/v1/events"


def test_pipeline_config_used_when_env_missing(monkeypatch):
    monkeypatch.delenv("BACKEND_URL", raising=False)
    assert resolve_http_endpoint("http://configured:8080") == "http://configured:8080/api/v1/events"


def test_fallback_when_both_missing(monkeypatch):
    monkeypatch.delenv("BACKEND_URL", raising=False)
    assert resolve_http_endpoint(None) == f"{DEFAULT_BACKEND_BASE_URL}{EVENTS_PATH}"


def test_trailing_slash_in_base_url_stripped(monkeypatch):
    monkeypatch.setenv("BACKEND_URL", "http://backend:8000/")
    assert resolve_http_endpoint(None) == "http://backend:8000/api/v1/events"


def test_empty_env_falls_through_to_config(monkeypatch):
    monkeypatch.setenv("BACKEND_URL", "")
    assert resolve_http_endpoint("http://configured:8080") == "http://configured:8080/api/v1/events"


def test_ai_service_token_env_takes_priority(monkeypatch):
    monkeypatch.setenv("AI_SERVICE_TOKEN", "env-token")
    assert resolve_http_token("config-token") == "env-token"


def test_http_token_config_used_when_env_missing(monkeypatch):
    monkeypatch.delenv("AI_SERVICE_TOKEN", raising=False)
    assert resolve_http_token("config-token") == "config-token"


def test_empty_ai_service_token_falls_through_to_config(monkeypatch):
    monkeypatch.setenv("AI_SERVICE_TOKEN", "")
    assert resolve_http_token("config-token") == "config-token"
