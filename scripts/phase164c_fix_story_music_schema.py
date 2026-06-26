#!/usr/bin/env python3
"""Ensure story music metadata columns exist for Phase 164C step 8."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.env_service import load_project_env
from services.neon_service import write_query

load_project_env()


STATEMENTS = [
    "ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS background_color text",
    "ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS text_content text",
    "ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS music_url text",
    "ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS music_title text",
    "ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS music_artist text",
    "ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS music_start_seconds integer DEFAULT 0",
    "ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS music_duration_seconds integer DEFAULT 0",
    "ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS owner_id uuid",
    "ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS duration_seconds integer DEFAULT 0",
]


def main():
    print("phase164c_story_music_schema_fix")
    for statement in STATEMENTS:
        write_query(statement, timeout_ms=15000)
        print(f"OK: {statement}")


if __name__ == "__main__":
    main()
