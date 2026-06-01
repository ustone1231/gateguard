"""Persist review queue feedback.

Revision ID: 20260601_0002
Revises: 20260601_0001
Create Date: 2026-06-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260601_0002"
down_revision = "20260601_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_queue",
        sa.Column("queue_id", sa.String(length=120), nullable=False),
        sa.Column("event_id", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewer_id", sa.String(length=120), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("queue_id"),
        sa.UniqueConstraint("event_id", name="uq_review_queue_event_id"),
    )
    op.create_index("ix_review_queue_event_id", "review_queue", ["event_id"])
    op.create_index("ix_review_queue_status", "review_queue", ["status"])


def downgrade() -> None:
    op.drop_index("ix_review_queue_status", table_name="review_queue")
    op.drop_index("ix_review_queue_event_id", table_name="review_queue")
    op.drop_table("review_queue")
