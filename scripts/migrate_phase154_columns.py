#!/usr/bin/env python3
"""Add missing columns to chain_status_posts, chain_posts, chain_reels for Phase 154."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.env_service import load_project_env
load_project_env()
from services.neon_service import write_query, fast_query

MIGRATIONS = [
    # chain_status_posts
    "ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS media_type text",
    "ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS storage_bucket text",
    "ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS storage_path text",
    "ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS mime_type text",
    "ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS size_bytes bigint",
    "ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS views_count integer DEFAULT 0",
    "ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS comments_count integer DEFAULT 0",
    # chain_posts
    "ALTER TABLE chain_posts ADD COLUMN IF NOT EXISTS media_bucket text",
    "ALTER TABLE chain_posts ADD COLUMN IF NOT EXISTS media_path text",
    "ALTER TABLE chain_posts ADD COLUMN IF NOT EXISTS mime_type text",
    "ALTER TABLE chain_posts ADD COLUMN IF NOT EXISTS size_bytes bigint",
    # chain_reels
    "ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS media_bucket text",
    "ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS media_path text",
    "ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS size_bytes bigint",
]

print("Running Phase 154 column migrations...")
for sql in MIGRATIONS:
    try:
        write_query(sql, timeout_ms=10000)
        print(f"  OK: {sql}")
    except Exception as e:
        print(f"  FAIL: {sql}: {e}")

print("\nVerifying columns...")
for table in ["chain_status_posts", "chain_posts", "chain_reels"]:
    rows = fast_query(
        "SELECT a.attname FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid WHERE c.relname = %s AND a.attnum > 0 AND NOT a.attisdropped",
        (table,), timeout_ms=5000, default=[]
    )
    cols = [r["attname"] for r in rows] if rows else []
    print(f"  {table}: {', '.join(sorted(cols))}")

print("\nMigration complete.")
