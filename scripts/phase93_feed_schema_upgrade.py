#!/usr/bin/env python3
"""Idempotent Phase 93 schema migration: feed, reel, story, trending tables."""

import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.neon_service import fast_query, write_query

MIGRATIONS = [
    # chain_reel_watch_events
    """
    CREATE TABLE IF NOT EXISTS chain_reel_watch_events (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        reel_id UUID NOT NULL REFERENCES chain_reels(id) ON DELETE CASCADE,
        user_id UUID,
        session_id TEXT,
        watch_seconds REAL DEFAULT 0,
        completion_percent REAL DEFAULT 0,
        replay_count INT DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_reel_watch_reel_created ON chain_reel_watch_events (reel_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_reel_watch_user_created ON chain_reel_watch_events (user_id, created_at)",

    # chain_story_views
    """
    CREATE TABLE IF NOT EXISTS chain_story_views (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        story_id UUID NOT NULL REFERENCES chain_status_posts(id) ON DELETE CASCADE,
        viewer_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
        viewed_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_story_views_unique
    ON chain_story_views (story_id, viewer_id)
    """,

    # chain_story_reactions
    """
    CREATE TABLE IF NOT EXISTS chain_story_reactions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        story_id UUID NOT NULL REFERENCES chain_status_posts(id) ON DELETE CASCADE,
        user_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
        reaction TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_story_reactions_unique
    ON chain_story_reactions (story_id, user_id)
    """,

    # chain_story_replies
    """
    CREATE TABLE IF NOT EXISTS chain_story_replies (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        story_id UUID NOT NULL REFERENCES chain_status_posts(id) ON DELETE CASCADE,
        sender_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
        owner_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
        message_id UUID,
        body TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,

    # chain_content_saves
    """
    CREATE TABLE IF NOT EXISTS chain_content_saves (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        content_type TEXT NOT NULL,
        content_id UUID NOT NULL,
        user_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_content_saves_unique
    ON chain_content_saves (content_type, content_id, user_id)
    """,

    # chain_content_shares
    """
    CREATE TABLE IF NOT EXISTS chain_content_shares (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        content_type TEXT NOT NULL,
        content_id UUID NOT NULL,
        user_id UUID,
        share_target TEXT,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,

    # chain_hashtag_stats
    """
    CREATE TABLE IF NOT EXISTS chain_hashtag_stats (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        hashtag TEXT NOT NULL,
        content_type TEXT DEFAULT 'post',
        usage_count INT DEFAULT 0,
        engagement_score REAL DEFAULT 0,
        location TEXT,
        last_used_at TIMESTAMPTZ DEFAULT now(),
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ DEFAULT now()
    )
    """,

    # ALTER existing tables for missing columns
    "ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS watch_score REAL DEFAULT 0",

    # Indexes on existing tables
    "CREATE INDEX IF NOT EXISTS idx_chain_posts_created ON chain_posts (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_chain_posts_profile_created ON chain_posts (profile_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_chain_reels_created ON chain_reels (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_chain_reels_profile_created ON chain_reels (profile_id, created_at DESC)",
    """
    CREATE INDEX IF NOT EXISTS idx_chain_stories_user_created
    ON chain_status_posts (profile_id, created_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_chain_stories_expires
    ON chain_status_posts (expires_at DESC)
    """,
]

def run():
    applied = []
    for sql in MIGRATIONS:
        try:
            write_query(sql)
            applied.append(sql.strip()[:80])
        except Exception as e:
            print(f"SKIP: {e}")
    print(json.dumps({"ok": True, "applied_count": len(applied), "phase": "phase93_feed_schema_upgrade_ok"}))

if __name__ == "__main__":
    run()
