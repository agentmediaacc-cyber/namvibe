#!/usr/bin/env python3
"""Create relationship + notification indexes for query storm reduction."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

INDEXES = [
    (
        "idx_friends_pair_fast",
        "CREATE INDEX IF NOT EXISTS idx_friends_pair_fast ON chain_friends(profile_id_1, profile_id_2);",
    ),
    (
        "idx_friend_requests_pair_status_fast",
        "CREATE INDEX IF NOT EXISTS idx_friend_requests_pair_status_fast ON chain_friend_requests(sender_profile_id, recipient_profile_id, status);",
    ),
    (
        "idx_follows_pair_fast",
        "CREATE INDEX IF NOT EXISTS idx_follows_pair_fast ON chain_follows(follower_profile_id, following_profile_id);",
    ),
    (
        "idx_follow_requests_pair_status_fast",
        "CREATE INDEX IF NOT EXISTS idx_follow_requests_pair_status_fast ON chain_follow_requests(requester_profile_id, target_profile_id, status);",
    ),
    (
        "idx_notifications_unread_fast",
        "CREATE INDEX IF NOT EXISTS idx_notifications_unread_fast ON chain_notifications(recipient_profile_id, is_read, created_at DESC) WHERE deleted_at IS NULL;",
    ),
]


def main():
    try:
        from services.neon_service import write_query
    except Exception as e:
        print(f"SKIP database unavailable: {e}")
        return 0

    created = 0
    for name, sql in INDEXES:
        try:
            write_query(sql, timeout_ms=30000)
            print(f"  OK  {name}")
            created += 1
        except Exception as e:
            print(f"  FAIL {name}: {e}")

    print(f"\nphase86_relationship_indexes: {created} of {len(INDEXES)} indexes created")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
