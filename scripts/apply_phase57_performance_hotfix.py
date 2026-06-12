#!/usr/bin/env python3
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "phase57_performance_hotfix.sql"


def _statements(sql_text):
    return [stmt.strip() for stmt in sql_text.split(";") if stmt.strip()]


def _has_column(cur, table_name, column_name):
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def main():
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / ".env.production", override=False)
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("FAIL: DATABASE_URL is not configured")
        return 1
    if not SQL_PATH.exists():
        print(f"FAIL: missing {SQL_PATH.relative_to(ROOT)}")
        return 1

    sql_text = SQL_PATH.read_text(encoding="utf-8")
    try:
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                has_idempotency_key = _has_column(cur, "chain_background_jobs", "idempotency_key")
                applied = 0
                skipped = 0
                for stmt in _statements(sql_text):
                    if "idx_chain_background_jobs_idempotency_key" in stmt and not has_idempotency_key:
                        skipped += 1
                        print("PASS: skipped optional idempotency_key index because column is missing")
                        continue
                    cur.execute(stmt + ";")
                    applied += 1
                conn.commit()
        print(f"PASS: phase57 performance hotfix applied statements={applied} skipped_optional={skipped}")
        return 0
    except Exception as error:
        print(f"FAIL: phase57 performance hotfix failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
