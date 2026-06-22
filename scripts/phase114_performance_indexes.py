#!/usr/bin/env python3
"""Phase 114 — Performance Indexes (idempotent).

Adds missing indexes identified during phase114 performance hardening:
- chain_follows: follower + following active lookups
- chain_friend_requests: send/receive status lookups
- chain_friends: pair status lookup
- chain_blocks: bidirectional block check
- chain_thread_members: profile→thread + thread→profile
- chain_messages: thread_id + created_at DESC (active filter)
- chain_profiles: discovery ordering by created_at DESC
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip("'\"")
                if v:
                    os.environ[k] = v

from services.neon_service import write_query, fast_query


INDEXES = [
    (
        "idx_chain_follows_follower_active",
        "CREATE INDEX IF NOT EXISTS idx_chain_follows_follower_active ON chain_follows(follower_profile_id, following_profile_id) WHERE deleted_at IS NULL",
    ),
    (
        "idx_chain_follows_following_active",
        "CREATE INDEX IF NOT EXISTS idx_chain_follows_following_active ON chain_follows(following_profile_id, follower_profile_id) WHERE deleted_at IS NULL",
    ),
    (
        "idx_chain_friend_requests_sender_status",
        "CREATE INDEX IF NOT EXISTS idx_chain_friend_requests_sender_status ON chain_friend_requests(sender_profile_id, recipient_profile_id, status)",
    ),
    (
        "idx_chain_friend_requests_recipient_status",
        "CREATE INDEX IF NOT EXISTS idx_chain_friend_requests_recipient_status ON chain_friend_requests(recipient_profile_id, sender_profile_id, status)",
    ),
    (
        "idx_chain_friends_pair_status",
        "CREATE INDEX IF NOT EXISTS idx_chain_friends_pair_status ON chain_friends(profile_id_1, profile_id_2, status) WHERE deleted_at IS NULL",
    ),
    (
        "idx_chain_blocks_pair_active",
        "CREATE INDEX IF NOT EXISTS idx_chain_blocks_pair_active ON chain_blocks(blocker_profile_id, blocked_profile_id) WHERE deleted_at IS NULL",
    ),
    (
        "idx_chain_thread_members_profile_thread",
        "CREATE INDEX IF NOT EXISTS idx_chain_thread_members_profile_thread ON chain_thread_members(profile_id, thread_id)",
    ),
    (
        "idx_chain_thread_members_thread_profile",
        "CREATE INDEX IF NOT EXISTS idx_chain_thread_members_thread_profile ON chain_thread_members(thread_id, profile_id)",
    ),
    (
        "idx_chain_messages_thread_created",
        "CREATE INDEX IF NOT EXISTS idx_chain_messages_thread_created ON chain_messages(thread_id, created_at DESC) WHERE deleted_at IS NULL",
    ),
    (
        "idx_chain_profiles_discovery_active",
        "CREATE INDEX IF NOT EXISTS idx_chain_profiles_discovery_active ON chain_profiles(created_at DESC) WHERE deleted_at IS NULL",
    ),
]


def main():
    ok = 0
    fail = 0
    for name, ddl in INDEXES:
        try:
            fast_query(ddl, default=[])
            print(f"  OK  {name}")
            ok += 1
        except Exception as e:
            try:
                write_query(ddl)
                print(f"  OK  {name}")
                ok += 1
            except Exception as e2:
                print(f"  FAIL {name}: {e2}")
                fail += 1
    print(f"\nResult: {ok}/{len(INDEXES)} OK, {fail} FAIL")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
