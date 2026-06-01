"""Create initial backend tables.

Revision ID: 20260601_0001
Revises:
Create Date: 2026-06-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260601_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("event_id", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("gate_section_id", sa.String(length=120), nullable=False),
        sa.Column("camera_id", sa.String(length=120), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("stored_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_events_event_type", "events", ["event_type"])
    op.create_index("ix_events_gate_section_id", "events", ["gate_section_id"])
    op.create_index("ix_events_camera_id", "events", ["camera_id"])
    op.create_index("ix_events_timestamp", "events", ["timestamp"])
    op.create_index("ix_events_severity", "events", ["severity"])

    op.create_table(
        "fare_taps",
        sa.Column("fare_tap_id", sa.String(length=120), nullable=False),
        sa.Column("gate_section_id", sa.String(length=120), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("stored_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("fare_tap_id"),
    )
    op.create_index("ix_fare_taps_gate_section_id", "fare_taps", ["gate_section_id"])
    op.create_index("ix_fare_taps_timestamp", "fare_taps", ["timestamp"])
    op.create_index("ix_fare_taps_result", "fare_taps", ["result"])

    op.create_table(
        "fare_matches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("gate_passage_event_id", sa.String(length=40), nullable=False),
        sa.Column("fare_tap_id", sa.String(length=120), nullable=False),
        sa.Column("time_delta_ms", sa.Integer(), nullable=True),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "gate_passage_event_id",
            name="uq_fare_matches_gate_passage_event_id",
        ),
        sa.UniqueConstraint("fare_tap_id", name="uq_fare_matches_fare_tap_id"),
    )
    op.create_index(
        "ix_fare_matches_gate_passage_event_id",
        "fare_matches",
        ["gate_passage_event_id"],
    )
    op.create_index("ix_fare_matches_fare_tap_id", "fare_matches", ["fare_tap_id"])


def downgrade() -> None:
    op.drop_index("ix_fare_matches_fare_tap_id", table_name="fare_matches")
    op.drop_index("ix_fare_matches_gate_passage_event_id", table_name="fare_matches")
    op.drop_table("fare_matches")
    op.drop_index("ix_fare_taps_result", table_name="fare_taps")
    op.drop_index("ix_fare_taps_timestamp", table_name="fare_taps")
    op.drop_index("ix_fare_taps_gate_section_id", table_name="fare_taps")
    op.drop_table("fare_taps")
    op.drop_index("ix_events_severity", table_name="events")
    op.drop_index("ix_events_timestamp", table_name="events")
    op.drop_index("ix_events_camera_id", table_name="events")
    op.drop_index("ix_events_gate_section_id", table_name="events")
    op.drop_index("ix_events_event_type", table_name="events")
    op.drop_table("events")
