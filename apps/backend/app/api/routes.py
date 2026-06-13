from __future__ import annotations

import time
from base64 import b64decode, b64encode
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, WebSocket, WebSocketDisconnect, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from app.api.deps import require_afc_token, require_ai_token, require_operator_token
from app.core.config import settings
from app.models import EventCreate, FareTap
from app.services.realtime import event_manager
from app.services.runtime import store
from app.services.stats import loss_estimate_payload, stats_payload
from app.services.store import now_utc
from app.services.video_clips import (
    cleanup_expired_clips,
    clip_path_for_event,
    signed_clip_url,
    validate_signed_clip,
)

router = APIRouter()

_APP_START = time.monotonic()
_SCHEMA_VERSION = "0.2.1"


def flush_matching_if_available() -> None:
    if hasattr(store, "flush_matching"):
        store.flush_matching()


@router.get("/api/v1/health")
def health() -> dict:
    return {
        "status": "ok",
        "uptime_sec": int(time.monotonic() - _APP_START),
        "schema_version": _SCHEMA_VERSION,
    }


def _encode_cursor(ts: datetime, event_id: str) -> str:
    return b64encode(f"{ts.isoformat()}|{event_id}".encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    raw = b64decode(cursor.encode()).decode()
    ts_str, event_id = raw.rsplit("|", 1)
    return datetime.fromisoformat(ts_str), event_id


@router.post("/api/v1/auth/login")
def login(payload: dict) -> dict:
    # TODO: real JWT/password verification. MVP dev auth returns a static operator token.
    if not payload.get("username") or not payload.get("password"):
        raise HTTPException(status_code=400, detail={"code": "bad_request"})
    return {
        "access_token": settings.jwt_secret,
        "refresh_token": settings.jwt_secret,
        "expires_in": 900,
    }


@router.post("/api/v1/auth/refresh")
def refresh_token(payload: dict) -> dict:
    token = payload.get("refresh_token", "")
    if token != settings.jwt_secret:
        raise HTTPException(status_code=401, detail={"code": "AUTH_INVALID", "message": "Invalid refresh token"})
    return {
        "access_token": settings.jwt_secret,
        "expires_in": 900,
    }


@router.post("/api/v1/auth/logout", status_code=204)
def logout(authorization: str | None = Header(default=None)) -> Response:
    if authorization is None:
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "Authorization header missing"})
    if authorization != f"Bearer {settings.jwt_secret}":
        raise HTTPException(status_code=401, detail={"code": "AUTH_INVALID", "message": "Invalid token"})
    return Response(status_code=204)


@router.post("/api/v1/events")
async def create_event(event: EventCreate, _: None = Depends(require_ai_token)) -> JSONResponse:
    stored, deduped, derived = store.save_event(event)
    response = {
        "event_id": stored.event_id,
        "stored_at": stored.stored_at,
    }
    if deduped:
        response["deduped"] = True
    if derived:
        response["derived_event_ids"] = [event.event_id for event in derived]
    if not deduped:
        await event_manager.broadcast("event_new", jsonable_encoder(stored))
    await broadcast_derived_events(derived)
    return ingest_response(response, deduped)


@router.post("/api/v1/fare-taps")
async def create_fare_tap(tap: FareTap, _: None = Depends(require_afc_token)) -> JSONResponse:
    stored, deduped, derived = store.save_fare_tap(tap)
    response = {
        "fare_tap_id": stored.fare_tap_id,
        "stored_at": stored.stored_at,
    }
    if deduped:
        response["deduped"] = True
    if derived:
        response["derived_event_ids"] = [event.event_id for event in derived]
    await broadcast_derived_events(derived)
    return ingest_response(response, deduped)


async def broadcast_derived_events(derived) -> None:
    for event in derived:
        await event_manager.broadcast("event_new", jsonable_encoder(event))
        if event.event_type == "confirmed_misuse":
            await event_manager.broadcast(
                "review_queue_added",
                {"queue_id": f"rq_{event.event_id[4:]}", "event_id": event.event_id},
            )


def ingest_response(response: dict, deduped: bool) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_200_OK if deduped else status.HTTP_201_CREATED,
        content=jsonable_encoder(response),
    )


@router.get("/api/v1/events")
def list_events(
    _: None = Depends(require_operator_token),
    event_type: str | None = None,
    gate_section_id: str | None = None,
    severity: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    cursor: str | None = None,
) -> dict:
    flush_matching_if_available()
    cursor_after: tuple[datetime, str] | None = None
    if cursor:
        try:
            cursor_after = _decode_cursor(cursor)
        except Exception:
            raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": "Invalid cursor"})
    events = store.list_events(
        event_type=event_type,
        gate_section_id=gate_section_id,
        severity=severity,
        limit=limit,
        from_time=from_time,
        to_time=to_time,
        cursor_after=cursor_after,
    )
    next_cursor = None
    if len(events) == limit:
        last = events[-1]
        next_cursor = _encode_cursor(last.timestamp, last.event_id)
    return {"data": events, "next_cursor": next_cursor, "total": len(events)}


@router.get("/api/v1/events/{event_id}")
def get_event(event_id: str, _: None = Depends(require_operator_token)):
    flush_matching_if_available()
    event = store.events.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return event


@router.get("/api/v1/events/{event_id}/video-clip")
def get_event_video_clip(event_id: str, _: None = Depends(require_operator_token)):
    cleanup_expired_clips()
    event = store.events.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return RedirectResponse(url=signed_clip_url(event), status_code=status.HTTP_302_FOUND)


@router.get("/api/v1/video-clips/{event_id}")
def download_signed_video_clip(event_id: str, expires: int, sig: str):
    cleanup_expired_clips()
    validate_signed_clip(event_id, expires, sig)
    event = store.events.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    path = clip_path_for_event(event)
    if path is None:
        raise HTTPException(status_code=404, detail={"code": "clip_not_found"})
    return FileResponse(path)


@router.get("/api/v1/review-queue")
def review_queue(
    _: None = Depends(require_operator_token),
    status_filter: str = Query(default="pending", alias="status"),
) -> dict:
    flush_matching_if_available()
    if hasattr(store, "list_review_queue"):
        rows = store.list_review_queue(status_filter=status_filter)
    else:
        rows = list(store.review_queue.values())
        if status_filter != "all":
            rows = [row for row in rows if row["status"] == status_filter]
    return {"data": rows, "next_cursor": None}


@router.post("/api/v1/review-queue/{queue_id}/feedback")
def review_feedback(
    queue_id: str,
    payload: dict,
    _: None = Depends(require_operator_token),
) -> dict:
    decision = payload.get("decision")
    if decision not in {"confirmed", "false_positive"}:
        raise HTTPException(status_code=400, detail={"code": "bad_decision"})

    if hasattr(store, "save_review_feedback"):
        try:
            row = store.save_review_feedback(queue_id, decision, payload.get("notes"))
        except KeyError:
            raise HTTPException(status_code=404, detail={"code": "not_found"}) from None
        except RuntimeError:
            raise HTTPException(status_code=409, detail={"code": "already_reviewed"}) from None
    else:
        row = store.review_queue.get(queue_id)
        if not row:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        if row["status"] != "pending":
            raise HTTPException(status_code=409, detail={"code": "already_reviewed"})
        row["status"] = decision
        row["reviewer_id"] = "dev-operator"
        row["reviewed_at"] = now_utc()
        row["feedback"] = payload.get("notes")
    return {
        "queue_id": queue_id,
        "status": row["status"],
        "reviewer_id": row["reviewer_id"],
        "reviewed_at": row["reviewed_at"],
    }


@router.get("/api/v1/stats")
def stats(
    _: None = Depends(require_operator_token),
    period: str = Query(default="day", pattern="^(day|week|month)$"),
    period_from: datetime | None = Query(default=None, alias="from"),
    period_to: datetime | None = Query(default=None, alias="to"),
    gate_section_id: str | None = None,
) -> dict:
    flush_matching_if_available()
    return stats_payload(
        list(store.events.values()),
        period=period,
        period_from=period_from,
        period_to=period_to,
        gate_section_id=gate_section_id,
    )


@router.get("/api/v1/loss-estimate")
def loss_estimate(
    _: None = Depends(require_operator_token),
    period_from: datetime | None = Query(default=None, alias="from"),
    period_to: datetime | None = Query(default=None, alias="to"),
    unit_loss_krw: int = Query(default=1370, ge=0),
) -> dict:
    flush_matching_if_available()
    return loss_estimate_payload(
        list(store.events.values()),
        period_from=period_from,
        period_to=period_to,
        unit_loss_krw=unit_loss_krw,
    )


@router.websocket("/ws/v1/events")
async def websocket_events(websocket: WebSocket, token: str | None = None, since: str | None = None):
    if token != settings.jwt_secret:
        await websocket.close(code=4401, reason="unauthorized")
        return

    await event_manager.connect(websocket)
    try:
        await send_missed_events(websocket, since)
        await event_manager.heartbeat(websocket)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        event_manager.disconnect(websocket)


async def send_missed_events(websocket: WebSocket, since: str | None) -> None:
    if not since:
        return
    events = list(store.events.values())
    marker = next((event for event in events if event.event_id == since), None)
    if marker is None:
        return
    missed = sorted(
        (event for event in events if event.stored_at > marker.stored_at),
        key=lambda event: event.stored_at,
    )
    for event in missed:
        await websocket.send_json({"type": "event_new", "data": jsonable_encoder(event)})
