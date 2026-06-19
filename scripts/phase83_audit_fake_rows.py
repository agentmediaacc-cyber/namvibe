#!/usr/bin/env python3
"""Report obvious fake/seed rows. Use --delete to remove only obvious matches."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TABLES = {
    "chain_profiles": ["username", "display_name", "email"],
    "chain_posts": ["caption", "body", "title", "hashtags"],
    "chain_reels": ["caption", "title", "music_title", "sound_title", "hashtags"],
    "chain_stories": ["caption", "title", "hashtags"],
    "chain_status_posts": ["caption", "body", "title"],
}

PATTERNS = [
    "phase8",
    "phase 8 production",
    "production reel",
    "test reel",
    "test post",
    "seed",
]


def _columns(table):
    from services.neon_service import fast_query

    rows = fast_query(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        """,
        (table,),
        timeout_ms=10000,
        default=[],
    )
    return {row["column_name"] for row in rows}


def _where_for(existing_columns):
    parts = []
    params = []
    if "username" in existing_columns:
        parts.append("LOWER(username) LIKE %s")
        params.append("phase8_%")
    for column in sorted(existing_columns):
        if column in {"username", "display_name", "caption", "body", "title", "music_title", "sound_title", "hashtags"}:
            for pattern in PATTERNS:
                parts.append(f"LOWER(COALESCE({column}::text, '')) LIKE %s")
                params.append(f"%{pattern}%")
    return " OR ".join(parts), params


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete", action="store_true")
    args = parser.parse_args()

    try:
        from services.neon_service import fast_query, write_query
    except Exception as error:
        print(f"SKIP database unavailable: {error}")
        return 0

    total = 0
    for table, candidate_columns in TABLES.items():
        try:
            existing = _columns(table)
        except Exception as error:
            print(f"{table}: SKIP {error}")
            continue
        if not existing:
            print(f"{table}: missing")
            continue
        where, params = _where_for(existing.intersection(candidate_columns + ["id"]))
        if not where:
            print(f"{table}: no auditable columns")
            continue
        try:
            rows = fast_query(
                f"SELECT id FROM {table} WHERE {where} LIMIT 50",
                tuple(params),
                timeout_ms=10000,
                default=[],
            )
        except Exception as error:
            print(f"{table}: SKIP {error}")
            continue
        count = len(rows or [])
        total += count
        print(f"{table}: {count} obvious fake rows")
        if args.delete and count:
            ids = [row["id"] for row in rows]
            placeholders = ",".join(["%s"] * len(ids))
            if "deleted_at" in existing:
                write_query(f"UPDATE {table} SET deleted_at = now() WHERE id IN ({placeholders})", tuple(ids))
            else:
                write_query(f"DELETE FROM {table} WHERE id IN ({placeholders})", tuple(ids))
            print(f"{table}: deleted {count}")

    print(f"total_obvious_fake_rows={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
