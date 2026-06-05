"""Add missing columns to events table per spec §4-B-3.

Revision ID: 20260606_0005
Revises: 20260606_0004
Create Date: 2026-06-06

spec(mvp-features.md §4-B-3) 기준 events 테이블에 누락된 컬럼 추가.
친구 PR 에서 payload_json 에 묻혀있던 필드들을 별도 컬럼으로 분리.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260606_0005"
down_revision = "20260606_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # source_event_id — confirmed_* 이벤트가 원본 gate_passage 를 참조하는 FK
    op.add_column("events", sa.Column("source_event_id", sa.String(length=40), nullable=True))
    op.create_index("ix_events_source_event_id", "events", ["source_event_id"])

    # confidence — 탐지 신뢰도 (0.0 ~ 1.0), 낮은 신뢰도 이벤트 필터링용
    op.add_column("events", sa.Column("confidence", sa.Float(), nullable=True))

    # track_id — ByteTrack 이 부여한 사람 추적 ID, 동일 인물 이벤트 추적용
    op.add_column("events", sa.Column("track_id", sa.Integer(), nullable=True))
    op.create_index("ix_events_track_id", "events", ["track_id"])

    # reliability — low/mid/high, 알림 우선순위 필터링용
    op.add_column("events", sa.Column("reliability", sa.String(length=10), nullable=True))
    op.create_index("ix_events_reliability", "events", ["reliability"])

    # clip_url — 영상 클립 URL, 24h 후 삭제 스케줄러가 관리
    op.add_column("events", sa.Column("clip_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("events", "clip_url")
    op.drop_index("ix_events_reliability", table_name="events")
    op.drop_column("events", "reliability")
    op.drop_index("ix_events_track_id", table_name="events")
    op.drop_column("events", "track_id")
    op.drop_column("events", "confidence")
    op.drop_index("ix_events_source_event_id", table_name="events")
    op.drop_column("events", "source_event_id")
