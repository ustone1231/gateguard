"""Enable TimescaleDB hypertables for events and fare_taps.

Revision ID: 20260606_0004
Revises: 20260606_0003
Create Date: 2026-06-06

PostgreSQL + TimescaleDB 환경에서만 적용됩니다.
SQLite(로컬 개발) 환경에서는 자동으로 스킵됩니다.

TimescaleDB 하이퍼테이블은 time 컬럼이 PK에 포함되어야 하므로
events / fare_taps 의 PK를 복합키 (id, timestamp) 로 변경합니다.
"""
from __future__ import annotations

from alembic import op


revision = "20260606_0004"
down_revision = "20260606_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite 개발 환경에서는 스킵

    # TimescaleDB 익스텐션 활성화
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")

    # events: PK를 (event_id, timestamp) 복합키로 변경 → 하이퍼테이블 전환
    op.execute("ALTER TABLE events DROP CONSTRAINT events_pkey;")
    op.execute("ALTER TABLE events ADD PRIMARY KEY (event_id, timestamp);")
    op.execute(
        "SELECT create_hypertable('events', 'timestamp',"
        " if_not_exists => TRUE, migrate_data => TRUE);"
    )

    # fare_taps: PK를 (fare_tap_id, timestamp) 복합키로 변경 → 하이퍼테이블 전환
    op.execute("ALTER TABLE fare_taps DROP CONSTRAINT fare_taps_pkey;")
    op.execute("ALTER TABLE fare_taps ADD PRIMARY KEY (fare_tap_id, timestamp);")
    op.execute(
        "SELECT create_hypertable('fare_taps', 'timestamp',"
        " if_not_exists => TRUE, migrate_data => TRUE);"
    )


def downgrade() -> None:
    # TimescaleDB 하이퍼테이블은 일반 테이블로 되돌리기 불가
    # 롤백 필요 시 테이블 재생성 필요 (운영 환경에서는 DBA 수동 작업)
    pass
