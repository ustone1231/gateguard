from __future__ import annotations

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    app_name: str = "GateGuard Backend"
    ai_service_token: str = getenv("AI_SERVICE_TOKEN", "dev-ai-service-token-please-change-32")
    afc_service_token: str = getenv("AFC_SERVICE_TOKEN", "dev-afc-service-token-please-change-32")
    jwt_secret: str = getenv("JWT_SECRET", "dev-jwt-secret-please-change-before-prod")
    database_url: str = getenv("DATABASE_URL", "sqlite:///./gateguard.db")
    storage_backend: str = getenv("STORAGE_BACKEND", "memory")
    cors_allow_origins: str = getenv("CORS_ALLOW_ORIGINS", "*")
    card_hash_salt: str = getenv("CARD_HASH_SALT", "dev-card-hash-salt-change-before-prod")
    video_clip_dir: str = getenv("VIDEO_CLIP_DIR", "/tmp/gateguard-clips")
    video_clip_ttl_hours: int = int(getenv("VIDEO_CLIP_TTL_HOURS", "24"))
    video_clip_signed_url_ttl_seconds: int = int(getenv("VIDEO_CLIP_SIGNED_URL_TTL_SECONDS", "300"))


settings = Settings()
