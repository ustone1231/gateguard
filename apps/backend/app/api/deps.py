from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_ai_token(authorization: str | None = Header(default=None)) -> None:
    require_bearer(authorization, settings.ai_service_token)


def require_afc_token(authorization: str | None = Header(default=None)) -> None:
    require_bearer(authorization, settings.afc_service_token)


def require_operator_token(authorization: str | None = Header(default=None)) -> None:
    require_bearer(authorization, settings.jwt_secret)


def require_bearer(authorization: str | None, expected: str) -> None:
    if authorization != f"Bearer {expected}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Invalid bearer token"},
        )
