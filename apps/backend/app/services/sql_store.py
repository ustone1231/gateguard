from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.models import Event, EventCreate, FareTap
from app.services.store import InMemoryStore, now_utc


class Base(DeclarativeBase):
    pass


class EventRow(Base):
    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    gate_section_id: Mapped[str] = mapped_column(String(120), index=True)
    camera_id: Mapped[str] = mapped_column(String(120), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    source_event_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    reliability: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    clip_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FareTapRow(Base):
    __tablename__ = "fare_taps"

    fare_tap_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    gate_section_id: Mapped[str] = mapped_column(String(120), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    result: Mapped[str] = mapped_column(String(20), index=True)
    card_id_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    card_category: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FareMatchRow(Base):
    __tablename__ = "fare_matches"
    __table_args__ = (
        UniqueConstraint("gate_passage_event_id", name="uq_fare_matches_gate_passage_event_id"),
        UniqueConstraint("fare_tap_id", name="uq_fare_matches_fare_tap_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gate_passage_event_id: Mapped[str] = mapped_column(String(40), index=True)
    fare_tap_id: Mapped[str] = mapped_column(String(120), index=True)
    time_delta_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CameraRow(Base):
    __tablename__ = "cameras"

    camera_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    frame_width: Mapped[int] = mapped_column(Integer, nullable=False)
    frame_height: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GateSectionRow(Base):
    __tablename__ = "gate_sections"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    camera_id: Mapped[str] = mapped_column(String(120), index=True)
    polygon_json: Mapped[str] = mapped_column(Text, nullable=False)
    entry_line_json: Mapped[str] = mapped_column(Text, nullable=False)
    exit_line_json: Mapped[str] = mapped_column(Text, nullable=False)
    meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReviewQueueRow(Base):
    __tablename__ = "review_queue"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_review_queue_event_id"),
    )

    queue_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reviewer_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)


class SqlStore:
    """SQL-backed store with the same public API as InMemoryStore.

    Matching still reuses the in-memory algorithm after hydrating current rows.
    This keeps the first DB milestone small while preserving API behavior.
    """

    def __init__(self, database_url: str):
        self.engine = create_engine(normalize_database_url(database_url), future=True)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False, future=True)
        Base.metadata.create_all(self.engine)

    def reset(self) -> None:
        with self.session_factory() as session:
            session.query(ReviewQueueRow).delete()
            session.query(FareMatchRow).delete()
            session.query(EventRow).delete()
            session.query(FareTapRow).delete()
            session.commit()

    def save_event(self, event: EventCreate) -> tuple[Event, bool, list[Event]]:
        with self.session_factory() as session:
            existing = session.get(EventRow, event.event_id)
            if existing:
                return event_from_row(existing), True, []

            stored = Event(**event.model_dump(), stored_at=now_utc())
            session.add(event_to_row(stored))
            session.commit()

        derived = self._run_matching()
        return self.get_event(stored.event_id), False, derived

    def save_fare_tap(self, tap: FareTap) -> tuple[FareTap, bool, list[Event]]:
        with self.session_factory() as session:
            existing = session.get(FareTapRow, tap.fare_tap_id)
            if existing:
                return fare_tap_from_row(existing), True, []

            stored = tap.model_copy(update={"stored_at": now_utc()})
            session.add(fare_tap_to_row(stored))
            session.commit()

        derived = self._run_matching()
        return self.get_fare_tap(stored.fare_tap_id), False, derived

    def list_events(
        self,
        event_type: str | None = None,
        gate_section_id: str | None = None,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[Event]:
        self.flush_matching()
        with self.session_factory() as session:
            query = select(EventRow).order_by(EventRow.timestamp.desc())
            if event_type:
                query = query.where(EventRow.event_type == event_type)
            if gate_section_id:
                query = query.where(EventRow.gate_section_id == gate_section_id)
            if severity:
                query = query.where(EventRow.severity == severity)
            rows = session.execute(query.limit(limit)).scalars().all()
            return [event_from_row(row) for row in rows]

    @property
    def events(self) -> dict[str, Event]:
        self.flush_matching()
        with self.session_factory() as session:
            rows = session.execute(select(EventRow)).scalars().all()
            return {row.event_id: event_from_row(row) for row in rows}

    @property
    def review_queue(self) -> dict[str, dict]:
        rows = self.list_review_queue(status_filter="all")
        return {row["queue_id"]: row for row in rows}

    def list_review_queue(self, status_filter: str = "pending") -> list[dict]:
        self.flush_matching()
        with self.session_factory() as session:
            self._sync_review_queue(session)
            query = select(ReviewQueueRow).order_by(ReviewQueueRow.added_at.desc())
            if status_filter != "all":
                query = query.where(ReviewQueueRow.status == status_filter)
            rows = session.execute(query).scalars().all()
            return [self._review_queue_payload(session, row) for row in rows]

    def save_review_feedback(
        self,
        queue_id: str,
        decision: str,
        notes: str | None,
        reviewer_id: str = "dev-operator",
    ) -> dict:
        with self.session_factory() as session:
            row = session.get(ReviewQueueRow, queue_id)
            if row is None:
                raise KeyError(queue_id)
            if row.status != "pending":
                raise RuntimeError("already_reviewed")

            row.status = decision
            row.reviewer_id = reviewer_id
            row.reviewed_at = now_utc()
            row.feedback = notes
            session.commit()
            return self._review_queue_payload(session, row)

    def get_event(self, event_id: str) -> Event:
        self.flush_matching()
        with self.session_factory() as session:
            row = session.get(EventRow, event_id)
            if row is None:
                raise KeyError(event_id)
            return event_from_row(row)

    def get_fare_tap(self, fare_tap_id: str) -> FareTap:
        with self.session_factory() as session:
            row = session.get(FareTapRow, fare_tap_id)
            if row is None:
                raise KeyError(fare_tap_id)
            return fare_tap_from_row(row)

    def flush_matching(self) -> list[Event]:
        return self._run_matching()

    def _run_matching(self) -> list[Event]:
        hydrated = InMemoryStore()
        with self.session_factory() as session:
            event_rows = session.execute(select(EventRow)).scalars().all()
            tap_rows = session.execute(select(FareTapRow)).scalars().all()
            match_rows = session.execute(select(FareMatchRow)).scalars().all()

        hydrated.events.update({row.event_id: event_from_row(row) for row in event_rows})
        hydrated.fare_taps.update({row.fare_tap_id: fare_tap_from_row(row) for row in tap_rows})
        hydrated.matched_fare_tap_ids.update(row.fare_tap_id for row in match_rows)

        before = set(hydrated.events)
        derived = hydrated.flush_matching()

        with self.session_factory() as session:
            for event_id, event in hydrated.events.items():
                row = session.get(EventRow, event_id)
                if row is None:
                    session.add(event_to_row(event))
                else:
                    row.payload_json = event.model_dump_json()
                    row.severity = event.severity
                if event.event_type == "gate_passage" and event.afc_match:
                    existing_match = session.execute(
                        select(FareMatchRow).where(
                            FareMatchRow.gate_passage_event_id == event.event_id
                        )
                    ).scalar_one_or_none()
                    if existing_match is None:
                        session.add(FareMatchRow(
                            gate_passage_event_id=event.event_id,
                            fare_tap_id=event.afc_match.fare_tap_id,
                            time_delta_ms=event.afc_match.time_delta_ms,
                            matched_at=now_utc(),
                        ))
                if event.event_type == "confirmed_misuse":
                    self._ensure_review_queue_item(session, event)
            session.commit()

        derived_ids = set(hydrated.events) - before
        return [event for event in derived if event.event_id in derived_ids]

    def _sync_review_queue(self, session: Session) -> None:
        events = session.execute(
            select(EventRow).where(EventRow.event_type == "confirmed_misuse")
        ).scalars().all()
        changed = False
        for event_row in events:
            event = event_from_row(event_row)
            if self._ensure_review_queue_item(session, event):
                changed = True
        if changed:
            session.commit()

    def _ensure_review_queue_item(self, session: Session, event: Event) -> bool:
        existing = session.execute(
            select(ReviewQueueRow).where(ReviewQueueRow.event_id == event.event_id)
        ).scalar_one_or_none()
        if existing is not None:
            return False

        session.add(
            ReviewQueueRow(
                queue_id=review_queue_id_for_event(event.event_id),
                event_id=event.event_id,
                status="pending",
                added_at=event.stored_at,
            )
        )
        return True

    def _review_queue_payload(self, session: Session, row: ReviewQueueRow) -> dict:
        event_row = session.get(EventRow, row.event_id)
        if event_row is None:
            raise KeyError(row.event_id)
        return {
            "queue_id": row.queue_id,
            "event_id": row.event_id,
            "event": event_from_row(event_row),
            "status": row.status,
            "added_at": row.added_at,
            "reviewer_id": row.reviewer_id,
            "reviewed_at": row.reviewed_at,
            "feedback": row.feedback,
        }


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def review_queue_id_for_event(event_id: str) -> str:
    if event_id.startswith("evt_"):
        return event_id.replace("evt_", "rq_", 1)
    return f"rq_{event_id}"


def event_to_row(event: Event) -> EventRow:
    return EventRow(
        event_id=event.event_id,
        event_type=event.event_type,
        gate_section_id=event.gate_section_id,
        camera_id=event.camera_id,
        timestamp=event.timestamp,
        severity=event.severity,
        source_event_id=event.source_event_id,
        confidence=event.confidence,
        track_id=event.track_id,
        reliability=event.reliability,
        clip_url=event.clip_url,
        payload_json=event.model_dump_json(),
        stored_at=event.stored_at,
    )


def event_from_row(row: EventRow) -> Event:
    return Event.model_validate_json(row.payload_json)


def fare_tap_to_row(tap: FareTap) -> FareTapRow:
    return FareTapRow(
        fare_tap_id=tap.fare_tap_id,
        gate_section_id=tap.gate_section_id,
        timestamp=tap.timestamp,
        result=tap.result,
        card_id_hash=tap.card_id_hash,
        card_category=tap.card_category,
        payload_json=tap.model_dump_json(),
        stored_at=tap.stored_at or now_utc(),
    )


def fare_tap_from_row(row: FareTapRow) -> FareTap:
    return FareTap.model_validate_json(row.payload_json)
