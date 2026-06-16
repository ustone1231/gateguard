#!/usr/bin/env bash
# verify_db.sh — GateGuard DB 스키마/마이그레이션 스모크 검증 (이슈 #16 제안 4)
#
# backend 컨테이너가 Alembic migration 을 실제로 적용해서
#   - TimescaleDB hypertable (events, fare_taps)
#   - alembic_version = 최신 head
#   - migration 0004 의 복합 PK (event_id/fare_tap_id + timestamp)
# 가 반영됐는지 재현 가능하게 확인한다. fresh Docker DB 와 운영 DB 의
# schema drift 를 빠르게 잡기 위함.
#
# 사용:
#   docker compose -f docker-compose.dev.yml up -d --build db backend
#   apps/infra/scripts/verify_db.sh
#
# 종료코드: 0 = 전부 통과 / 1 = 실패 항목 있음 / 2 = 컨테이너 미기동
set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-gateguard-db}"
BACKEND_CONTAINER="${BACKEND_CONTAINER:-gateguard-backend}"
PGUSER="${POSTGRES_USER:-gateguard}"
PGDB="${POSTGRES_DB:-gateguard}"

fail=0
pass() { printf '  ✓ %s\n' "$1"; }
bad()  { printf '  ✗ %s\n' "$1"; fail=1; }

if ! docker ps --format '{{.Names}}' | grep -qx "$DB_CONTAINER"; then
  echo "ERROR: '$DB_CONTAINER' 컨테이너가 실행 중이 아닙니다." >&2
  echo "       먼저: docker compose -f docker-compose.dev.yml up -d --build db backend" >&2
  exit 2
fi

psql_q() { docker exec "$DB_CONTAINER" psql -U "$PGUSER" -d "$PGDB" -At -c "$1"; }

echo "== 1) TimescaleDB hypertables =="
hypertables="$(psql_q "select hypertable_name from timescaledb_information.hypertables order by 1;")"
for t in events fare_taps; do
  if grep -qx "$t" <<<"$hypertables"; then pass "hypertable: $t"; else bad "hypertable 누락: $t"; fi
done

echo "== 2) alembic_version =="
if [ "$(psql_q "select to_regclass('public.alembic_version') is not null;")" = "t" ]; then
  ver="$(psql_q "select version_num from alembic_version;")"
  if [ -n "$ver" ]; then
    pass "alembic_version = $ver"
    # head 비교: backend 컨테이너의 alembic heads 와 대조 (가능할 때만)
    if docker ps --format '{{.Names}}' | grep -qx "$BACKEND_CONTAINER"; then
      head="$(docker exec "$BACKEND_CONTAINER" alembic heads 2>/dev/null | awk 'NR==1{print $1}')" || head=""
      if [ -n "$head" ]; then
        if [ "$ver" = "$head" ]; then pass "head 일치 ($head)"; else bad "head 불일치: db=$ver, head=$head"; fi
      fi
    fi
  else
    bad "alembic_version 테이블이 비어있음"
  fi
else
  bad "alembic_version 테이블 없음 (migration 미실행)"
fi

echo "== 3) 복합 PK (migration 0004) =="
for spec in "events:event_id" "fare_taps:fare_tap_id"; do
  tbl="${spec%%:*}"; idcol="${spec##*:}"
  pkdef="$(psql_q "select pg_get_constraintdef(oid) from pg_constraint where contype='p' and conrelid='${tbl}'::regclass;")"
  if grep -q "timestamp" <<<"$pkdef" && grep -q "$idcol" <<<"$pkdef"; then
    pass "$tbl PK 복합키: $pkdef"
  else
    bad "$tbl PK 가 복합키 아님: ${pkdef:-(없음)}"
  fi
done

echo
if [ "$fail" -eq 0 ]; then
  echo "RESULT: ✅ 모든 검증 통과"
else
  echo "RESULT: ❌ 실패 항목 있음 (위 ✗ 확인)"
fi
exit "$fail"
