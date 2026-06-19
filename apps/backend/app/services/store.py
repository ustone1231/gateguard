from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from app.models import AfcMatch, Event, EventCreate, FareTap


MATCH_WINDOW_SECONDS = 1.0
MATCH_BUFFER_SECONDS = 1.0


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
        derived = self.flush_matching()
        return stored, False, derived

    def save_fare_tap(self, tap: FareTap) -> tuple[FareTap, bool, list[Event]]:
        existing = self.fare_taps.get(tap.fare_tap_id)
        if existing:
            return existing, True, []

        stored = tap.model_copy(update={"stored_at": now_utc()})
        self.fare_taps[stored.fare_tap_id] = stored
        derived = self.flush_matching()
        return stored, False, derived

    def flush_matching(self) -> list[Event]:
        """Run the idempotent AFC matching worker once.

        Approved taps can match as soon as both sides are present. Unmatched
        gate_passage events emit confirmed_unpaid only after the 1s arrival
        buffer has elapsed, preventing false positives when a fare_tap arrives
        slightly late.
        """

        derived: list[Event] = []

        gate_passages = sorted(
            (
                event for event in self.events.values()
                if event.event_type == "gate_passage"
            ),
            key=lambda event: event.timestamp,
        )

        for event in gate_passages:
            derived.extend(self._run_matching_for_event(event))

        for event in gate_passages:
            latest_event = self.events.get(event.event_id, event)
            derived.extend(self._emit_unpaid_if_mature(latest_event))

        return derived

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
        if event.afc_match or self._has_derived_event(event, "confirmed_unpaid"):
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
            if e.event_type == "gate_passage"
            and not e.afc_match
            and not self._has_derived_event(e, "confirmed_unpaid")
            and e.gate_section_id == tap.gate_section_id
        ]
        passages.sort(key=lambda e: abs((e.timestamp - tap.timestamp).total_seconds()))
        for event in passages:
            if abs((event.timestamp - tap.timestamp).total_seconds()) <= MATCH_WINDOW_SECONDS:
                return self._apply_match(event, tap)
        return []

    def _find_nearest_tap(self, event: Event) -> FareTap | None:
        candidates = [
            tap for tap in self.fare_taps.values()
            if tap.result == "approved"
            and tap.fare_tap_id not in self.matched_fare_tap_ids
            and tap.gate_section_id == event.gate_section_id
            and abs((event.timestamp - tap.timestamp).total_seconds()) <= MATCH_WINDOW_SECONDS
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda tap: abs((event.timestamp - tap.timestamp).total_seconds()))

    def _emit_unpaid_if_mature(self, event: Event) -> list[Event]:
        if event.event_type != "gate_passage":
            return []
        if event.afc_match or self._has_derived_event(event, "confirmed_unpaid"):
            return []
        if not self._buffer_elapsed(event):
            return []
        if self._find_nearest_tap(event):
            return self._run_matching_for_event(event)

        denied_tap = self._find_nearest_denied_tap(event)
        unpaid = self._derived_event(
            source=event,
            event_type="confirmed_unpaid",
            severity="critical",
            confidence=0.95,
            afc_match=None,
        )
        raw_meta = dict(unpaid.raw_meta)
        raw_meta["unpaid_reason"] = "denied_without_approved" if denied_tap else "no_approved_fare_tap"
        if denied_tap:
            raw_meta["denied_fare_tap_id"] = denied_tap.fare_tap_id
        unpaid = unpaid.model_copy(update={"raw_meta": raw_meta})
        self.events[unpaid.event_id] = unpaid
        return [unpaid]

    def _buffer_elapsed(self, event: Event) -> bool:
        return (now_utc() - event.stored_at).total_seconds() >= MATCH_BUFFER_SECONDS

    def _find_nearest_denied_tap(self, event: Event) -> FareTap | None:
        candidates = [
            tap for tap in self.fare_taps.values()
            if tap.result == "denied"
            and tap.gate_section_id == event.gate_section_id
            and abs((event.timestamp - tap.timestamp).total_seconds()) <= MATCH_WINDOW_SECONDS
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda tap: abs((event.timestamp - tap.timestamp).total_seconds()))

    def _has_derived_event(self, source: Event, event_type: str) -> bool:
        return any(
            event.event_type == event_type and event.source_event_id == source.event_id
            for event in self.events.values()
        )

    def _apply_match(self, event: Event, tap: FareTap) -> list[Event]:
        self.matched_fare_tap_ids.add(tap.fare_tap_id)
        afc_match = self._afc_match_for_tap(event, tap)
        updated = event.model_copy(update={"afc_match": afc_match})
        self.events[event.event_id] = updated

        if self._eligibility_mismatch(updated, tap):
            if self._has_derived_event(updated, "confirmed_misuse"):
                return []
            misuse = self._derived_event(
                source=updated,
                event_type="confirmed_misuse",
                severity="warning",
                confidence=0.9,
                afc_match=afc_match,
            )
            self.events[misuse.event_id] = misuse
            queue_id = f"rq_{misuse.event_id[4:]}"
            self.review_queue[queue_id] = {
                "queue_id": queue_id,
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

    def _eligibility_mismatch(self, event: Event, tap: FareTap) -> bool:
        signals = event.signals
        if event.reliability != "high" or signals is None:
            return False

        if (
            tap.card_category == "senior"
            and signals.senior_probability is not None
            and signals.senior_probability < 0.20
        ):
            return True
        if (
            tap.card_category == "child"
            and signals.child_probability is not None
            and signals.child_probability < 0.20
        ):
            return True
        return (
            tap.holder_gender in {"male", "female"}
            and signals.perceived_gender in {"male", "female"}
            and tap.holder_gender != signals.perceived_gender
            and signals.gender_confidence is not None
            and signals.gender_confidence >= 0.80
        )

    def _afc_match_for_tap(self, event: Event, tap: FareTap) -> AfcMatch:
        delta_ms = int((tap.timestamp - event.timestamp).total_seconds() * 1000)
        return AfcMatch(
            fare_tap_id=tap.fare_tap_id,
            card_id_hash=tap.card_id_hash,
            card_category=tap.card_category,
            holder_gender=tap.holder_gender,
            tap_timestamp=tap.timestamp,
            time_delta_ms=delta_ms,
        )

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
