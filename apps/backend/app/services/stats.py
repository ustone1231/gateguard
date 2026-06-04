from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models import Event


INCIDENT_EVENT_TYPES = {"confirmed_unpaid", "confirmed_misuse"}


def stats_payload(
    events: list[Event],
    period: str = "day",
    period_from: datetime | None = None,
    period_to: datetime | None = None,
    gate_section_id: str | None = None,
) -> dict:
    period_from, period_to = resolve_period(period, period_from, period_to)
    filtered = filter_events(events, period_from, period_to, gate_section_id)

    by_type: dict[str, int] = {}
    by_gate: dict[str, int] = {}
    by_hour = [0] * 24
    for event in filtered:
        by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
        by_gate[event.gate_section_id] = by_gate.get(event.gate_section_id, 0) + 1
        by_hour[event.timestamp.astimezone(UTC).hour] += 1

    return {
        "period": period,
        "from": period_from.isoformat(),
        "to": period_to.isoformat(),
        "total": len(filtered),
        "by_type": by_type,
        "by_gate": by_gate,
        "by_hour": by_hour,
    }


def loss_estimate_payload(
    events: list[Event],
    period_from: datetime | None = None,
    period_to: datetime | None = None,
    unit_loss_krw: int = 1370,
) -> dict:
    period_from, period_to = resolve_period("day", period_from, period_to)
    incidents = [
        event for event in filter_events(events, period_from, period_to)
        if event.event_type in INCIDENT_EVENT_TYPES
    ]
    return {
        "period_from": period_from.isoformat(),
        "period_to": period_to.isoformat(),
        "total_incidents": len(incidents),
        "unit_loss_krw": unit_loss_krw,
        "estimated_loss_krw": len(incidents) * unit_loss_krw,
        "by_type": count_by_type(incidents),
    }


def filter_events(
    events: list[Event],
    period_from: datetime,
    period_to: datetime,
    gate_section_id: str | None = None,
) -> list[Event]:
    return [
        event for event in events
        if period_from <= event.timestamp.astimezone(UTC) < period_to
        and (gate_section_id is None or event.gate_section_id == gate_section_id)
    ]


def resolve_period(
    period: str,
    period_from: datetime | None,
    period_to: datetime | None,
) -> tuple[datetime, datetime]:
    if period_from and period_to:
        return period_from.astimezone(UTC), period_to.astimezone(UTC)

    now = datetime.now(UTC)
    if period == "week":
        start = datetime(now.year, now.month, now.day, tzinfo=UTC) - timedelta(days=now.weekday())
        end = start + timedelta(days=7)
    elif period == "month":
        start = datetime(now.year, now.month, 1, tzinfo=UTC)
        end = datetime(now.year + (now.month // 12), (now.month % 12) + 1, 1, tzinfo=UTC)
    else:
        start = datetime(now.year, now.month, now.day, tzinfo=UTC)
        end = start + timedelta(days=1)
    return (period_from.astimezone(UTC) if period_from else start), (
        period_to.astimezone(UTC) if period_to else end
    )


def count_by_type(events: list[Event]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        counts[event.event_type] = counts.get(event.event_type, 0) + 1
    return counts
