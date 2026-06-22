#!/usr/bin/env python3
"""
Minimal idempotent migration for reel engagement tables.

Creates:
 - chain_reel_reactions
 - chain_reel_comments
 - chain_saved_items

Usage: set -a; source .env; set +a; python3 scripts/phase99_content_engagement_schema.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.neon_service import _get_dsn_kwargs
import psycopg2

SQL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS chain_reel_reactions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
  reel_id uuid REFERENCES chain_reels(id) ON DELETE CASCADE,
  reaction_type text DEFAULT 'like',
  created_at timestamptz DEFAULT now(),
  UNIQUE(profile_id, reel_id, reaction_type)
);
CREATE INDEX IF NOT EXISTS idx_chain_reel_reactions_reel ON chain_reel_reactions(reel_id);

CREATE TABLE IF NOT EXISTS chain_reel_comments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
  reel_id uuid REFERENCES chain_reels(id) ON DELETE CASCADE,
  body text NOT NULL,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chain_reel_comments_reel ON chain_reel_comments(reel_id, created_at DESC);

CREATE TABLE IF NOT EXISTS chain_saved_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
  item_type text NOT NULL,
  item_id uuid NOT NULL,
  created_at timestamptz DEFAULT now(),
  UNIQUE(profile_id, item_type, item_id)
);
CREATE INDEX IF NOT EXISTS idx_chain_saved_items_profile ON chain_saved_items(profile_id, created_at DESC);
"""


def main():
    kwargs = _get_dsn_kwargs()
    # connect and run migration
    conn = None
    try:
        conn = psycopg2.connect(**kwargs)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(SQL)
        cur.close()
        print("Migration applied (idempotent).")
    except Exception as e:
        print("Migration failed:", e)
        raise
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    main()
