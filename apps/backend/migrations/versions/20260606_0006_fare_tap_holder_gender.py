"""Add holder_gender to fare_taps.

Revision ID: 20260606_0006
Revises: 20260606_0005
Create Date: 2026-06-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260606_0006"
down_revision = "20260606_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fare_taps", sa.Column("holder_gender", sa.String(length=10), nullable=True))
    op.create_index("ix_fare_taps_holder_gender", "fare_taps", ["holder_gender"])


def downgrade() -> None:
    op.drop_index("ix_fare_taps_holder_gender", table_name="fare_taps")
    op.drop_column("fare_taps", "holder_gender")
