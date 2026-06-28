#!/usr/bin/env python3
"""
Audit live Postgres schema truth against static NamVibe schema claims.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.env_service import load_project_env, get_env
from services.neon_service import CHAIN_STATIC_COLUMNS

load_project_env()

TABLES = [
    "chain_stories",
    "chain_status_posts",
    "chain_reels",
    "chain_live_rooms",
    "chain_posts",
    "chain_profiles",
    "chain_messages",
    "chain_thread_members",
]
FLAGS = ["video_url", "status", "host_id", "creator_id", "media_url", "thumbnail_url"]


def connect():
    import psycopg2

    dsn = (get_env("DATABASE_URL", "") or "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is not configured")
    return psycopg2.connect(dsn)


def fetch_live_columns(conn, tables):
    sql = """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = ANY(%s)
        ORDER BY table_name, ordinal_position
    """
    result = {table: [] for table in tables}
    with conn.cursor() as cur:
        cur.execute(sql, (tables,))
        for table_name, column_name in cur.fetchall():
            result.setdefault(table_name, []).append(column_name)
    return result


def print_schema_truth(live_columns):
    print("=" * 88)
    print("LIVE SCHEMA TRUTH")
    print("=" * 88)
    header = f"{'table':<22} {'cols':>4}  " + "  ".join(f"{name:<13}" for name in FLAGS)
    print(header)
    print("-" * len(header))
    for table in TABLES:
        cols = set(live_columns.get(table, []))
        flags = ["yes" if name in cols else "no" for name in FLAGS]
        print(f"{table:<22} {len(cols):>4}  " + "  ".join(f"{value:<13}" for value in flags))
        print(f"  actual columns: {', '.join(sorted(cols)) if cols else '(none)'}")


def print_mismatches(live_columns):
    print("\n" + "=" * 88)
    print("STATIC VS LIVE MISMATCH")
    print("=" * 88)
    print(f"{'table':<22} {'static_missing_in_db':<32} {'db_missing_in_static'}")
    print("-" * 88)
    for table in TABLES:
        actual = set(live_columns.get(table, []))
        static = set(CHAIN_STATIC_COLUMNS.get(table, set()))
        missing_in_db = sorted(static - actual)
        missing_in_static = sorted(actual - static)
        left = ", ".join(missing_in_db) if missing_in_db else "-"
        right = ", ".join(missing_in_static) if missing_in_static else "-"
        print(f"{table:<22} {left:<32} {right}")


def main():
    conn = connect()
    try:
        live_columns = fetch_live_columns(conn, TABLES)
    finally:
        conn.close()
    print_schema_truth(live_columns)
    print_mismatches(live_columns)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
