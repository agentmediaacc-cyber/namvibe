#!/usr/bin/env python3
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PROFILE_COLUMNS = [
    ("cover_path", "TEXT"),
    ("cover_url", "TEXT"),
    ("banner_url", "TEXT"),
    ("banner_path", "TEXT"),
    ("avatar_storage_path", "TEXT"),
    ("avatar_storage_bucket", "TEXT"),
    ("country", "TEXT"),
    ("current_country", "TEXT"),
    ("visibility", "TEXT DEFAULT 'public'"),
    ("profile_type", "TEXT DEFAULT 'personal'"),
    ("reels_count", "INTEGER DEFAULT 0"),
    ("saved_count", "INTEGER DEFAULT 0"),
    ("tagged_count", "INTEGER DEFAULT 0"),
    ("followers_count", "INTEGER DEFAULT 0"),
    ("following_count", "INTEGER DEFAULT 0"),
    ("posts_count", "INTEGER DEFAULT 0"),
    ("is_creator", "BOOLEAN DEFAULT FALSE"),
    ("is_verified", "BOOLEAN DEFAULT FALSE"),
    ("verified", "BOOLEAN DEFAULT FALSE"),
    ("profile_completed", "BOOLEAN DEFAULT FALSE"),
    ("terms_accepted_at", "TIMESTAMPTZ"),
    ("privacy_version", "TEXT"),
]


def main():
    os.chdir(ROOT)
    from services.neon_service import write_query

    applied = 0
    for name, definition in PROFILE_COLUMNS:
        write_query(
            f"ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS {name} {definition}",
            timeout_ms=20000,
        )
        applied += 1
    print(f"PASS: phase61 profile schema migration checked {applied} columns")
    return 0


if __name__ == "__main__":
    sys.exit(main())
