#!/usr/bin/env python3
"""Phase 92: Call logs schema hardening.

Idempotent, data-safe migration for chain_call_logs.
Adds missing columns and indexes. Never drops data.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.neon_service import get_connection, release_connection


CALL_LOG_COLUMNS = [
    ("started_at", "TIMESTAMPTZ NULL"),
    ("accepted_at", "TIMESTAMPTZ NULL"),
    ("ended_at", "TIMESTAMPTZ NULL"),
    ("missed_at", "TIMESTAMPTZ NULL"),
    ("rejected_at", "TIMESTAMPTZ NULL"),
    ("busy_at", "TIMESTAMPTZ NULL"),
    ("failure_reason", "TEXT NULL"),
    ("updated_at", "TIMESTAMPTZ DEFAULT now()"),
]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_p92_call_logs_caller_created ON chain_call_logs(profile_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_p92_call_logs_other_created ON chain_call_logs(other_profile_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_p92_call_logs_status ON chain_call_logs(status, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_p92_call_logs_type ON chain_call_logs(call_type, created_at DESC)",
]


def _column_exists(cur, table, column):
    cur.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s AND column_name = %s LIMIT 1",
        (table, column),
    )
    return bool(cur.fetchone())


def _index_exists(cur, index_name):
    cur.execute(
        "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = %s LIMIT 1",
        (index_name,),
    )
    return bool(cur.fetchone())


def run():
    conn = None
    applied = []
    try:
        conn = get_connection(timeout_ms=30000)
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS chain_call_logs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    call_id UUID,
                    profile_id UUID NOT NULL,
                    other_profile_id UUID,
                    direction TEXT NOT NULL,
                    call_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_seconds INTEGER,
                    created_at TIMESTAMPTZ DEFAULT now()
                )
                """
            )
            if not _column_exists(cur, "chain_call_logs", "id"):
                applied.append("chain_call_logs")

            for column, ddl in CALL_LOG_COLUMNS:
                if not _column_exists(cur, "chain_call_logs", column):
                    cur.execute(f"ALTER TABLE chain_call_logs ADD COLUMN {column} {ddl}")
                    applied.append(f"chain_call_logs.{column}")

            for sql in INDEXES:
                cur.execute(sql)
            applied.append("indexes")

        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            release_connection(conn)

    print("phase92_call_schema_upgrade_ok")
    print("applied=" + ",".join(applied))


if __name__ == "__main__":
    run()
