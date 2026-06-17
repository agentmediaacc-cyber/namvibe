#!/usr/bin/env python3
"""
Phase 83 – Performance Index Migration.
Creates indexes for speed: homepage, messages, notifications, reels, etc.
All statements use IF NOT EXISTS for idempotency.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.neon_service import fast_query, write_query

INDEXES = [
    # chain_posts
    "CREATE INDEX IF NOT EXISTS idx_83_posts_deleted_created ON chain_posts (deleted_at, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_83_posts_profile_created ON chain_posts (profile_id, created_at DESC)",

    # chain_reels
    "CREATE INDEX IF NOT EXISTS idx_83_reels_deleted_created ON chain_reels (deleted_at, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_83_reels_profile_created ON chain_reels (profile_id, created_at DESC)",

    # chain_stories
    "CREATE INDEX IF NOT EXISTS idx_83_stories_deleted_created ON chain_stories (deleted_at, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_83_stories_profile_created ON chain_stories (profile_id, created_at DESC)",

    # chain_live_rooms
    "CREATE INDEX IF NOT EXISTS idx_83_live_deleted_live_created ON chain_live_rooms (deleted_at, is_live, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_83_live_status_created ON chain_live_rooms (status, created_at DESC)",

    # chain_profiles
    "CREATE INDEX IF NOT EXISTS idx_83_profiles_deleted_created ON chain_profiles (deleted_at, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_83_profiles_creator_deleted_followers ON chain_profiles (is_creator, deleted_at, followers_count DESC)",
    "CREATE INDEX IF NOT EXISTS idx_83_profiles_username_lower ON chain_profiles (lower(username))",
    "CREATE INDEX IF NOT EXISTS idx_83_profiles_town ON chain_profiles (town)",

    # chain_follows
    "CREATE INDEX IF NOT EXISTS idx_83_follows_pair ON chain_follows (follower_profile_id, following_profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_83_follows_follower ON chain_follows (follower_profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_83_follows_following ON chain_follows (following_profile_id)",

    # chain_notifications
    "CREATE INDEX IF NOT EXISTS idx_83_notif_recipient_read_deleted ON chain_notifications (recipient_profile_id, is_read, deleted_at)",
    "CREATE INDEX IF NOT EXISTS idx_83_notif_recipient_created ON chain_notifications (recipient_profile_id, created_at DESC)",

    # chain_wallets
    "CREATE INDEX IF NOT EXISTS idx_83_wallets_profile ON chain_wallets (profile_id)",

    # chain_messages
    "CREATE INDEX IF NOT EXISTS idx_83_messages_thread_created ON chain_messages (thread_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_83_messages_sender_created ON chain_messages (sender_profile_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_83_messages_recipient_seen_created ON chain_messages (recipient_profile_id, is_seen, created_at DESC)",

    # chain_message_threads
    "CREATE INDEX IF NOT EXISTS idx_83_threads_updated ON chain_message_threads (updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_83_threads_created ON chain_message_threads (created_at DESC)",

    # chain_thread_members
    "CREATE INDEX IF NOT EXISTS idx_83_thread_members_profile_thread ON chain_thread_members (profile_id, thread_id)",
    "CREATE INDEX IF NOT EXISTS idx_83_thread_members_thread_profile ON chain_thread_members (thread_id, profile_id)",

    # chain_call_sessions
    "CREATE INDEX IF NOT EXISTS idx_83_calls_caller_created ON chain_call_sessions (caller_profile_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_83_calls_receiver_created ON chain_call_sessions (receiver_profile_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_83_calls_status_created ON chain_call_sessions (call_status, created_at DESC)",
]

pass_count = 0
skip_count = 0
fail_count = 0

for sql in INDEXES:
    try:
        write_query(sql)
        print(f"  [CREATE] {sql[:80]}...")
        pass_count += 1
    except Exception as e:
        err = str(e).lower()
        if "already exists" in err:
            print(f"  [SKIP]   {sql[:80]}... (already exists)")
            skip_count += 1
        else:
            print(f"  [FAIL]   {sql[:80]}... {e}")
            fail_count += 1

print(f"\nIndexes applied: {pass_count} created, {skip_count} skipped, {fail_count} failed")
if fail_count:
    sys.exit(1)
