from __future__ import annotations

import hmac
from hashlib import sha256
from pathlib import Path
from time import time

from fastapi import HTTPException

from app.core.config import settings
from app.models import Event
from app.services.store import now_utc


def cleanup_expired_clips() -> int:
    clip_dir = Path(settings.video_clip_dir)
    if not clip_dir.exists():
        return 0

    deleted = 0
    cutoff = time() - settings.video_clip_ttl_hours * 60 * 60
    for path in clip_dir.glob("**/*"):
        if not path.is_file():
            continue
        if path.stat().st_mtime <= cutoff:
            path.unlink(missing_ok=True)
            deleted += 1
    return deleted


def signed_clip_url(event: Event) -> str:
    path = clip_path_for_event(event)
    if path is None:
        raise HTTPException(status_code=404, detail={"code": "clip_not_found"})
    if (now_utc() - event.stored_at).total_seconds() > settings.video_clip_ttl_hours * 60 * 60:
        raise HTTPException(status_code=404, detail={"code": "clip_expired"})

    expires = int(time() + settings.video_clip_signed_url_ttl_seconds)
    signature = sign_clip(event.event_id, expires)
    return f"/api/v1/video-clips/{event.event_id}?expires={expires}&sig={signature}"


def clip_path_for_event(event: Event) -> Path | None:
    candidates: list[Path] = []
    if event.clip_url:
        if event.clip_url.startswith(("http://", "https://")):
            return None
        raw = Path(event.clip_url)
        candidates.append(raw if raw.is_absolute() else Path(settings.video_clip_dir) / raw)
    candidates.extend(
        Path(settings.video_clip_dir) / f"{event.event_id}{suffix}"
        for suffix in (".mp4", ".mov", ".webm")
    )
    for path in candidates:
        try:
            resolved = path.resolve()
            root = Path(settings.video_clip_dir).resolve()
        except FileNotFoundError:
            continue
        if root in resolved.parents or resolved == root:
            if resolved.is_file():
                return resolved
    return None


def validate_signed_clip(event_id: str, expires: int, signature: str) -> None:
    if expires < int(time()):
        raise HTTPException(status_code=404, detail={"code": "clip_url_expired"})
    expected = sign_clip(event_id, expires)
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail={"code": "bad_clip_signature"})


def sign_clip(event_id: str, expires: int) -> str:
    secret = f"{settings.jwt_secret}:{settings.card_hash_salt}".encode()
    payload = f"{event_id}:{expires}".encode()
    return hmac.new(secret, payload, sha256).hexdigest()
