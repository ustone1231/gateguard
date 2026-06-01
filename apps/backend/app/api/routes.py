from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import require_afc_token, require_ai_token, require_operator_token
from app.core.config import settings
from app.models import EventCreate, FareTap
from app.services.runtime import store
from app.services.store import now_utc

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "gateguard-backend"}


@router.post("/api/v1/auth/login")
def login(payload: dict) -> dict:
    # MVP dev auth: real password/JWT is the next milestone.
    if not payload.get("username") or not payload.get("password"):
        raise HTTPException(status_code=400, detail={"code": "bad_request"})
    return {
        "access_token": settings.jwt_secret,
        "refresh_token": settings.jwt_secret,
        "expires_in": 900,
    }


@router.post("/api/v1/events", status_code=status.HTTP_201_CREATED)
def create_event(event: EventCreate, _: None = Depends(require_ai_token)) -> dict:
    stored, deduped, derived = store.save_event(event)
    response = {
        "event_id": stored.event_id,
        "stored_at": stored.stored_at,
    }
    if deduped:
        response["deduped"] = True
    if derived:
        response["derived_event_ids"] = [event.event_id for event in derived]
    return response


@router.post("/api/v1/fare-taps", status_code=status.HTTP_201_CREATED)
def create_fare_tap(tap: FareTap, _: None = Depends(require_afc_token)) -> dict:
    stored, deduped, derived = store.save_fare_tap(tap)
    response = {
        "fare_tap_id": stored.fare_tap_id,
        "stored_at": stored.stored_at,
    }
    if deduped:
        response["deduped"] = True
    if derived:
        response["derived_event_ids"] = [event.event_id for event in derived]
    return response


@router.get("/api/v1/events")
def list_events(
    _: None = Depends(require_operator_token),
    event_type: str | None = None,
    gate_section_id: str | None = None,
    severity: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    events = store.list_events(
        event_type=event_type,
        gate_section_id=gate_section_id,
        severity=severity,
        limit=limit,
    )
    return {"data": events, "next_cursor": None, "total": len(events)}


@router.get("/api/v1/events/{event_id}")
def get_event(event_id: str, _: None = Depends(require_operator_token)):
    event = store.events.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return event


@router.get("/api/v1/review-queue")
def review_queue(
    _: None = Depends(require_operator_token),
    status_filter: str = Query(default="pending", alias="status"),
) -> dict:
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
def stats(_: None = Depends(require_operator_token)) -> dict:
    by_type: dict[str, int] = {}
    by_gate: dict[str, int] = {}
    for event in store.events.values():
        by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
        by_gate[event.gate_section_id] = by_gate.get(event.gate_section_id, 0) + 1
    return {
        "period": "all",
        "total": len(store.events),
        "by_type": by_type,
        "by_gate": by_gate,
    }
