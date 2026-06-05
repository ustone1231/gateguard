"""Add cameras, gate_sections tables and card columns to fare_taps.

Revision ID: 20260606_0003
Revises: 20260601_0002
Create Date: 2026-06-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260606_0003"
down_revision = "20260601_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # cameras 테이블 — 카메라별 해상도 정보 저장
    op.create_table(
        "cameras",
        sa.Column("camera_id", sa.String(length=120), nullable=False),
        sa.Column("frame_width", sa.Integer(), nullable=False),
        sa.Column("frame_height", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("camera_id"),
    )

    # gate_sections 테이블 — 카메라별 게이트 polygon / entry_line / exit_line 저장
    # AI 트랙이 이 테이블에서 구역 설정을 읽어 line crossing 감지에 사용
    op.create_table(
        "gate_sections",
        sa.Column("id", sa.String(length=120), nullable=False),
        sa.Column("camera_id", sa.String(length=120), nullable=False),
        sa.Column("polygon_json", sa.Text(), nullable=False),
        sa.Column("entry_line_json", sa.Text(), nullable=False),
        sa.Column("exit_line_json", sa.Text(), nullable=False),
        sa.Column("meta_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gate_sections_camera_id", "gate_sections", ["camera_id"])

    # fare_taps — card_id_hash / card_category 를 별도 컬럼으로 추출
    # 매칭 엔진이 WHERE card_category IN ('senior','child') 로 직접 조회하기 위해 인덱싱
    op.add_column("fare_taps", sa.Column("card_id_hash", sa.String(length=80), nullable=True))
    op.add_column("fare_taps", sa.Column("card_category", sa.String(length=30), nullable=True))
    op.create_index("ix_fare_taps_card_category", "fare_taps", ["card_category"])


def downgrade() -> None:
    op.drop_index("ix_fare_taps_card_category", table_name="fare_taps")
    op.drop_column("fare_taps", "card_category")
    op.drop_column("fare_taps", "card_id_hash")
    op.drop_index("ix_gate_sections_camera_id", table_name="gate_sections")
    op.drop_table("gate_sections")
    op.drop_table("cameras")
