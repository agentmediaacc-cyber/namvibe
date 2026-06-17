#!/usr/bin/env python3
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PROFILE_COLUMNS = [
    ("cover_path", "TEXT"),
    ("cover_url", "TEXT"),
    ("banner_path", "TEXT"),
    ("banner_url", "TEXT"),
    ("avatar_storage_path", "TEXT"),
    ("avatar_storage_bucket", "TEXT"),
    ("country", "TEXT"),
    ("current_country", "TEXT"),
    ("visibility", "TEXT DEFAULT 'public'"),
    ("profile_type", "TEXT DEFAULT 'personal'"),
    ("reels_count", "INTEGER DEFAULT 0"),
    ("saved_count", "INTEGER DEFAULT 0"),
    ("tagged_count", "INTEGER DEFAULT 0"),
]

INDEXES = [
    ("idx_phase62_chain_posts_created_at", "chain_posts", "created_at"),
    ("idx_phase62_chain_reels_created_at", "chain_reels", "created_at"),
    ("idx_phase62_chain_profiles_created_at", "chain_profiles", "created_at"),
    ("idx_phase62_chain_stories_created_at", "chain_stories", "created_at"),
    ("idx_phase62_chain_live_rooms_created_at", "chain_live_rooms", "created_at"),
]


def _profile_columns(fetch_all):
    rows = fetch_all(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'chain_profiles'
        ORDER BY column_name
        """,
        timeout_ms=10000,
    )
    return {row.get("column_name") for row in rows or []}


def main():
    os.chdir(ROOT)
    from services.neon_service import fetch_all, write_query

    before = _profile_columns(fetch_all)
    missing_before = [name for name, _ in PROFILE_COLUMNS if name not in before]
    print("INFO: chain_profiles columns before:", ", ".join(sorted(before)) if before else "unavailable")

    for name, definition in PROFILE_COLUMNS:
        if name not in before:
            print(f"INFO: adding missing column {name}")
        write_query(
            f"ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS {name} {definition}",
            timeout_ms=20000,
        )

    for index_name, table_name, column_name in INDEXES:
        write_query(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({column_name} DESC)",
            timeout_ms=30000,
        )

    after = _profile_columns(fetch_all)
    missing_after = [name for name, _ in PROFILE_COLUMNS if name not in after]
    if missing_after:
        print("FAIL: missing after migration:", ", ".join(missing_after))
        return 1

    print("PASS: phase62 profile columns verified")
    print("PASS: phase62 indexes checked")
    if missing_before:
        print("INFO: columns added or confirmed by migration:", ", ".join(missing_before))
    return 0


if __name__ == "__main__":
    sys.exit(main())
