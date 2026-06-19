#!/usr/bin/env python3
"""Audit or delete obvious fake Phase/test rows from production tables."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TABLES = {
    "chain_comments": ["body", "content"],
    "chain_notifications": ["title", "body"],
    "chain_hashtags": ["tag", "name"],
    "chain_stories": ["caption", "title", "hashtags"],
    "chain_status_posts": ["caption", "body", "title"],
    "chain_reels": ["caption", "title", "music_title", "sound_title", "hashtags"],
    "chain_posts": ["caption", "body", "title", "hashtags"],
    "chain_live_rooms": ["title", "category"],
    "chain_profiles": ["username", "display_name", "full_name", "email"],
}
SAFE_USERNAMES = {"moon", "namvibe", "final"}
PATTERNS = ["phase8", "phase 8 production", "production reel", "test reel", "seed"]


def columns_for(table):
    from services.neon_service import fast_query

    rows = fast_query(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
        (table,),
        timeout_ms=10000,
        default=[],
    )
    return {row["column_name"] for row in rows}


def build_where(table, columns):
    parts, params = [], []
    if table == "chain_profiles" and "username" in columns:
        parts.append("LOWER(username) LIKE %s")
        params.append("phase8_%")
    for column in TABLES[table]:
        if column not in columns:
            continue
        for pattern in PATTERNS:
            parts.append(f"LOWER(COALESCE({column}::text, '')) LIKE %s")
            params.append(f"%{pattern}%")
    if {"music_title", "sound_title"}.intersection(columns):
        sound_cols = [c for c in ("music_title", "sound_title", "title") if c in columns]
        marker_cols = [c for c in ("caption", "body", "hashtags", "username") if c in columns]
        if sound_cols and marker_cols:
            sound_expr = " OR ".join(f"LOWER(COALESCE({c}::text, '')) LIKE %s" for c in sound_cols)
            marker_expr = " OR ".join(f"LOWER(COALESCE({c}::text, '')) LIKE %s" for c in marker_cols)
            parts.append(f"(({sound_expr}) AND ({marker_expr}))")
            params.extend(["%original sound%"] * len(sound_cols))
            params.extend(["%phase%"] * len(marker_cols))
    return " OR ".join(f"({p})" for p in parts), params


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", action="store_true", help="Audit only; default.")
    parser.add_argument("--delete", action="store_true", help="Delete obvious fake rows.")
    parser.add_argument("--dry-run", action="store_true", help="Print SQL without executing deletes.")
    args = parser.parse_args()

    try:
        from services.neon_service import fast_query, write_query
    except Exception as error:
        print(f"SKIP database unavailable: {error}")
        return 0

    total = 0
    for table in TABLES:
        try:
            cols = columns_for(table)
        except Exception as error:
            print(f"{table}: SKIP {error}")
            continue
        if "id" not in cols:
            print(f"{table}: missing or no id")
            continue
        where, params = build_where(table, cols)
        if not where:
            print(f"{table}: no auditable columns")
            continue
        if table == "chain_profiles" and "username" in cols:
            where = f"({where}) AND LOWER(COALESCE(username, '')) NOT IN (%s, %s, %s)"
            params.extend(sorted(SAFE_USERNAMES))
        sql = f"SELECT id FROM {table} WHERE {where} LIMIT 100"
        rows = fast_query(sql, tuple(params), timeout_ms=10000, default=[]) or []
        count = len(rows)
        total += count
        print(f"{table}: {count} obvious fake rows")
        if count and args.delete:
            ids = [row["id"] for row in rows]
            placeholders = ", ".join(["%s"] * len(ids))
            delete_sql = f"DELETE FROM {table} WHERE id IN ({placeholders})"
            if args.dry_run:
                print(f"DRY RUN {delete_sql} -- {ids}")
            else:
                write_query("BEGIN", timeout_ms=5000)
                try:
                    write_query(delete_sql, tuple(ids), timeout_ms=15000)
                    write_query("COMMIT", timeout_ms=5000)
                    print(f"{table}: deleted {count}")
                except Exception:
                    write_query("ROLLBACK", timeout_ms=5000)
                    raise
    print(f"phase85_clean_fake_rows: total_obvious_fake_rows={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
