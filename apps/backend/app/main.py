from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import settings
from app.services.video_clips import cleanup_expired_clips


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    origins = cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials="*" not in origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.include_router(router)
    return app


def cors_origins() -> list[str]:
    return [
        origin.strip()
        for origin in settings.cors_allow_origins.split(",")
        if origin.strip()
    ] or ["*"]


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("code", "http_error"))
        message = str(detail.get("message", code))
    else:
        code = "http_error"
        message = str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(request, code, message),
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_payload(request, "validation_error", "Request validation failed"),
    )


def error_payload(request: Request, code: str, message: str) -> dict:
    request_id = request.headers.get("x-request-id") or f"req_{uuid4().hex}"
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        }
    }


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    cleanup_expired_clips()
    task = asyncio.create_task(clip_cleanup_loop())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def clip_cleanup_loop() -> None:
    while True:
        cleanup_expired_clips()
        await asyncio.sleep(60 * 60)


app = create_app()
