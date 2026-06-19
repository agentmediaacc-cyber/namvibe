"""Phase 87 — Performance Indexes.

Adds/verifies all performance indexes safely.
Skips missing tables/columns without errors.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.neon_service import fast_query, write_query


INDEXES = [
    # chain_friends
    ("idx_friends_pair_fast_87", "CREATE INDEX IF NOT EXISTS idx_friends_pair_fast_87 ON chain_friends(profile_id_1, profile_id_2)"),
    ("idx_friends_pair2_87", "CREATE INDEX IF NOT EXISTS idx_friends_pair2_87 ON chain_friends(profile_id_2, profile_id_1)"),

    # chain_friend_requests
    ("idx_fr_sender_recip_status_87", "CREATE INDEX IF NOT EXISTS idx_fr_sender_recip_status_87 ON chain_friend_requests(sender_profile_id, recipient_profile_id, status)"),
    ("idx_fr_recip_status_created_87", "CREATE INDEX IF NOT EXISTS idx_fr_recip_status_created_87 ON chain_friend_requests(recipient_profile_id, status, created_at DESC)"),

    # chain_follows
    ("idx_follows_follower_following_87", "CREATE INDEX IF NOT EXISTS idx_follows_follower_following_87 ON chain_follows(follower_profile_id, following_profile_id)"),
    ("idx_follows_following_created_87", "CREATE INDEX IF NOT EXISTS idx_follows_following_created_87 ON chain_follows(following_profile_id, created_at DESC)"),

    # chain_follow_requests
    ("idx_fol_req_requester_target_status_87", "CREATE INDEX IF NOT EXISTS idx_fol_req_requester_target_status_87 ON chain_follow_requests(requester_profile_id, target_profile_id, status)"),
    ("idx_fol_req_target_status_created_87", "CREATE INDEX IF NOT EXISTS idx_fol_req_target_status_created_87 ON chain_follow_requests(target_profile_id, status, created_at DESC)"),

    # chain_notifications (partial index)
    ("idx_notif_unread_87", "CREATE INDEX IF NOT EXISTS idx_notif_unread_87 ON chain_notifications(recipient_profile_id, is_read, created_at DESC) WHERE deleted_at IS NULL"),

    # chain_profiles
    ("idx_profiles_username_87", "CREATE INDEX IF NOT EXISTS idx_profiles_username_87 ON chain_profiles(username)"),
    ("idx_profiles_deleted_created_87", "CREATE INDEX IF NOT EXISTS idx_profiles_deleted_created_87 ON chain_profiles(deleted_at, created_at DESC)"),
    ("idx_profiles_visibility_87", "CREATE INDEX IF NOT EXISTS idx_profiles_visibility_87 ON chain_profiles(profile_visibility)"),

    # chain_posts
    ("idx_posts_profile_created_87", "CREATE INDEX IF NOT EXISTS idx_posts_profile_created_87 ON chain_posts(profile_id, created_at DESC)"),
    ("idx_posts_created_active_87", "CREATE INDEX IF NOT EXISTS idx_posts_created_active_87 ON chain_posts(created_at DESC) WHERE deleted_at IS NULL"),

    # chain_reels
    ("idx_reels_profile_created_87", "CREATE INDEX IF NOT EXISTS idx_reels_profile_created_87 ON chain_reels(profile_id, created_at DESC)"),
    ("idx_reels_created_active_87", "CREATE INDEX IF NOT EXISTS idx_reels_created_active_87 ON chain_reels(created_at DESC) WHERE deleted_at IS NULL"),

    # chain_stories
    ("idx_stories_profile_created_87", "CREATE INDEX IF NOT EXISTS idx_stories_profile_created_87 ON chain_stories(profile_id, created_at DESC)"),
    ("idx_stories_created_active_87", "CREATE INDEX IF NOT EXISTS idx_stories_created_active_87 ON chain_stories(created_at DESC) WHERE deleted_at IS NULL"),

    # chain_live_rooms
    ("idx_live_rooms_profile_created_87", "CREATE INDEX IF NOT EXISTS idx_live_rooms_profile_created_87 ON chain_live_rooms(profile_id, created_at DESC)"),
    ("idx_live_rooms_status_live_87", "CREATE INDEX IF NOT EXISTS idx_live_rooms_status_live_87 ON chain_live_rooms(status, is_live, created_at DESC)"),
]


def run():
    total = len(INDEXES)
    ok = 0
    skipped = 0
    failed = 0
    print("Phase 87: Performance Indexes")

    for name, sql in INDEXES:
        try:
            write_query(sql)
            print(f"  OK   {name}")
            ok += 1
        except Exception as e:
            err = str(e)
            if "already exists" in err.lower() or "duplicate" in err.lower():
                print(f"  OK   {name} (already exists)")
                ok += 1
            elif "does not exist" in err.lower() or "relation" in err.lower():
                print(f"  SKIP {name} ({err[:80]})")
                skipped += 1
            else:
                print(f"  FAIL {name} ({err[:80]})")
                failed += 1

    print(f"\nphase87_performance_indexes: {ok} ok, {skipped} skipped, {failed} failed of {total} total")
    return failed == 0


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
