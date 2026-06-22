#!/usr/bin/env python3
"""
Phase 123 — Homepage/Reels Performance Indexes.

Safe CREATE INDEX IF NOT EXISTS for slow homepage and reels queries.
Uses normal CREATE INDEX IF NOT EXISTS (safe to run idempotently).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.neon_service import write_query, fast_query
from services.logging_service import log_info


INDEXES = [
    # ── chain_posts ──
    (
        "idx_posts_created_active",
        "CREATE INDEX IF NOT EXISTS idx_posts_created_active ON chain_posts (created_at DESC) WHERE deleted_at IS NULL",
    ),
    (
        "idx_posts_profile_created_active",
        "CREATE INDEX IF NOT EXISTS idx_posts_profile_created_active ON chain_posts (profile_id, created_at DESC) WHERE deleted_at IS NULL",
    ),
    # ── chain_reels ──
    (
        "idx_reels_created_active",
        "CREATE INDEX IF NOT EXISTS idx_reels_created_active ON chain_reels (created_at DESC) WHERE deleted_at IS NULL",
    ),
    (
        "idx_reels_profile_created_active",
        "CREATE INDEX IF NOT EXISTS idx_reels_profile_created_active ON chain_reels (profile_id, created_at DESC) WHERE deleted_at IS NULL",
    ),
    # ── chain_stories ──
    (
        "idx_stories_created_active",
        "CREATE INDEX IF NOT EXISTS idx_stories_created_active ON chain_stories (created_at DESC) WHERE deleted_at IS NULL",
    ),
    (
        "idx_stories_profile_created_active",
        "CREATE INDEX IF NOT EXISTS idx_stories_profile_created_active ON chain_stories (profile_id, created_at DESC) WHERE deleted_at IS NULL",
    ),
    # ── chain_status_posts ──
    (
        "idx_status_posts_created_active",
        "CREATE INDEX IF NOT EXISTS idx_status_posts_created_active ON chain_status_posts (created_at DESC) WHERE deleted_at IS NULL",
    ),
    (
        "idx_status_posts_profile_created_active",
        "CREATE INDEX IF NOT EXISTS idx_status_posts_profile_created_active ON chain_status_posts (profile_id, created_at DESC) WHERE deleted_at IS NULL",
    ),
    # ── chain_live_rooms ──
    (
        "idx_live_rooms_created_active",
        "CREATE INDEX IF NOT EXISTS idx_live_rooms_created_active ON chain_live_rooms (created_at DESC) WHERE deleted_at IS NULL",
    ),
    (
        "idx_live_rooms_is_live_created_active",
        "CREATE INDEX IF NOT EXISTS idx_live_rooms_is_live_created_active ON chain_live_rooms (is_live, created_at DESC) WHERE deleted_at IS NULL",
    ),
    # ── chain_profiles ──
    (
        "idx_profiles_created_active",
        "CREATE INDEX IF NOT EXISTS idx_profiles_created_active ON chain_profiles (created_at DESC) WHERE deleted_at IS NULL",
    ),
    (
        "idx_profiles_followers_active",
        "CREATE INDEX IF NOT EXISTS idx_profiles_followers_active ON chain_profiles (followers_count DESC) WHERE deleted_at IS NULL",
    ),
    (
        "idx_profiles_creator_followers_active",
        "CREATE INDEX IF NOT EXISTS idx_profiles_creator_followers_active ON chain_profiles (is_creator, followers_count DESC) WHERE deleted_at IS NULL",
    ),
    # ── chain_reel_events ──
    (
        "idx_reel_events_reel_created",
        "CREATE INDEX IF NOT EXISTS idx_reel_events_reel_created ON chain_reel_events (reel_id, created_at DESC)",
    ),
    (
        "idx_reel_events_user_created",
        "CREATE INDEX IF NOT EXISTS idx_reel_events_user_created ON chain_reel_events (user_id, created_at DESC)",
    ),
]


def index_exists(name):
    rows = fast_query(
        "SELECT 1 FROM pg_indexes WHERE indexname = %s",
        (name,),
        timeout_ms=2000,
        default=[],
    )
    return bool(rows)


def main():
    print("=" * 60)
    print("PHASE 123 — HOMEPAGE / REELS PERFORMANCE INDEXES")
    print("=" * 60)
    created = 0
    skipped = 0
    errors = 0

    for name, ddl in INDEXES:
        if index_exists(name):
            print(f"  [SKIP] {name} — already exists")
            skipped += 1
            continue
        try:
            write_query(ddl)
            print(f"  [CREATE] {name}")
            created += 1
        except Exception as e:
            error_msg = str(e).split("\n")[0][:100]
            print(f"  [ERROR] {name}: {error_msg}")
            errors += 1

    print(f"\n  Created: {created}, Skipped: {skipped}, Errors: {errors}")
    log_info(
        "phase123_indexes",
        created=created,
        skipped=skipped,
        errors=errors,
    )
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
