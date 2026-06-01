from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from app.models import AfcMatch, Event, EventCreate, FareTap


@dataclass
class InMemoryStore:
    events: dict[str, Event] = field(default_factory=dict)
    fare_taps: dict[str, FareTap] = field(default_factory=dict)
    matched_fare_tap_ids: set[str] = field(default_factory=set)
    review_queue: dict[str, dict] = field(default_factory=dict)

    def reset(self) -> None:
        self.events.clear()
        self.fare_taps.clear()
        self.matched_fare_tap_ids.clear()
        self.review_queue.clear()

    def save_event(self, event: EventCreate) -> tuple[Event, bool, list[Event]]:
        existing = self.events.get(event.event_id)
        if existing:
            return existing, True, []

        stored = Event(**event.model_dump(), stored_at=now_utc())
        self.events[stored.event_id] = stored
        derived = self._run_matching_for_event(stored)
        return stored, False, derived

    def save_fare_tap(self, tap: FareTap) -> tuple[FareTap, bool, list[Event]]:
        existing = self.fare_taps.get(tap.fare_tap_id)
        if existing:
            return existing, True, []

        stored = tap.model_copy(update={"stored_at": now_utc()})
        self.fare_taps[stored.fare_tap_id] = stored
        derived = self._run_matching_for_tap(stored)
        return stored, False, derived

    def list_events(
        self,
        event_type: str | None = None,
        gate_section_id: str | None = None,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[Event]:
        events = sorted(self.events.values(), key=lambda e: e.timestamp, reverse=True)
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if gate_section_id:
            events = [e for e in events if e.gate_section_id == gate_section_id]
        if severity:
            events = [e for e in events if e.severity == severity]
        return events[:limit]

    def _run_matching_for_event(self, event: Event) -> list[Event]:
        if event.event_type != "gate_passage":
            return []
        tap = self._find_nearest_tap(event)
        if not tap:
            return []
        return self._apply_match(event, tap)

    def _run_matching_for_tap(self, tap: FareTap) -> list[Event]:
        if tap.result != "approved" or tap.fare_tap_id in self.matched_fare_tap_ids:
            return []
        passages = [
            e for e in self.events.values()
            if e.event_type == "gate_passage" and e.gate_section_id == tap.gate_section_id
        ]
        passages.sort(key=lambda e: abs((e.timestamp - tap.timestamp).total_seconds()))
        for event in passages:
            if abs((event.timestamp - tap.timestamp).total_seconds()) <= 1:
                return self._apply_match(event, tap)
        return []

    def _find_nearest_tap(self, event: Event) -> FareTap | None:
        candidates = [
            tap for tap in self.fare_taps.values()
            if tap.result == "approved"
            and tap.fare_tap_id not in self.matched_fare_tap_ids
            and tap.gate_section_id == event.gate_section_id
            and abs((event.timestamp - tap.timestamp).total_seconds()) <= 1
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda tap: abs((event.timestamp - tap.timestamp).total_seconds()))

    def _apply_match(self, event: Event, tap: FareTap) -> list[Event]:
        self.matched_fare_tap_ids.add(tap.fare_tap_id)
        delta_ms = int((tap.timestamp - event.timestamp).total_seconds() * 1000)
        afc_match = AfcMatch(
            fare_tap_id=tap.fare_tap_id,
            card_id_hash=tap.card_id_hash,
            card_category=tap.card_category,
            tap_timestamp=tap.timestamp,
            time_delta_ms=delta_ms,
        )
        updated = event.model_copy(update={"afc_match": afc_match})
        self.events[event.event_id] = updated

        if (
            tap.card_category in {"senior", "child"}
            and updated.signals
            and updated.signals.senior_probability is not None
            and updated.signals.senior_probability < 0.20
            and updated.reliability == "high"
        ):
            misuse = self._derived_event(
                source=updated,
                event_type="confirmed_misuse",
                severity="warning",
                confidence=0.9,
                afc_match=afc_match,
            )
            self.events[misuse.event_id] = misuse
            self.review_queue[f"rq_{misuse.event_id[4:12]}"] = {
                "queue_id": f"rq_{misuse.event_id[4:12]}",
                "event_id": misuse.event_id,
                "event": misuse,
                "status": "pending",
                "added_at": now_utc(),
                "reviewer_id": None,
                "reviewed_at": None,
                "feedback": None,
            }
            return [misuse]
        return []

    def _derived_event(
        self,
        source: Event,
        event_type: str,
        severity: str,
        confidence: float,
        afc_match: AfcMatch | None,
    ) -> Event:
        return Event(
            event_id=f"evt_{uuid4().hex}",
            event_type=event_type,
            source_event_id=source.event_id,
            gate_section_id=source.gate_section_id,
            camera_id=source.camera_id,
            confidence=confidence,
            track_id=source.track_id,
            timestamp=now_utc(),
            clip_url=source.clip_url,
            signals=source.signals,
            reliability="high",
            severity=severity,
            afc_match=afc_match,
            raw_meta={"generated_by": "matching_engine"},
            stored_at=now_utc(),
        )


def now_utc() -> datetime:
    return datetime.now(UTC)


store = InMemoryStore()
