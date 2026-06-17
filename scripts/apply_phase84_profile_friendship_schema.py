"""
Phase 84 — Friendship System Schema
Creates chain_friend_requests and chain_friends tables with indexes.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.neon_service import write_query, fast_query

TABLE_FRIEND_REQUESTS = """
CREATE TABLE IF NOT EXISTS chain_friend_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_profile_id UUID NOT NULL,
    receiver_profile_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    responded_at TIMESTAMPTZ
);
"""

TABLE_FRIENDS = """
CREATE TABLE IF NOT EXISTS chain_friends (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    friend_profile_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(profile_id, friend_profile_id)
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_friend_requests_sender ON chain_friend_requests(sender_profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_friend_requests_receiver ON chain_friend_requests(receiver_profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_friend_requests_status ON chain_friend_requests(status)",
    "CREATE INDEX IF NOT EXISTS idx_friends_profile ON chain_friends(profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_friends_friend ON chain_friends(friend_profile_id)",
]

PRIVACY_COLUMNS = [
    "ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS who_can_follow VARCHAR(30) DEFAULT 'everyone'",
    "ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS who_can_message VARCHAR(30) DEFAULT 'followers'",
    "ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS who_can_call VARCHAR(30) DEFAULT 'friends'",
    "ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS who_can_view_posts VARCHAR(30) DEFAULT 'public'",
    "ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS who_can_view_reels VARCHAR(30) DEFAULT 'public'",
    "ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS require_coins_to_follow BOOLEAN DEFAULT FALSE",
    "ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS premium_only_follow BOOLEAN DEFAULT FALSE",
]

def run():
    for stmt in [TABLE_FRIEND_REQUESTS, TABLE_FRIENDS]:
        write_query(stmt)
        print(f"  Table ensured: {stmt.split('(')[0].replace('CREATE TABLE IF NOT EXISTS ', '').strip()}")
    for idx in INDEXES:
        write_query(idx)
        print(f"  Index ensured: {idx.split('ON ')[1] if 'ON ' in idx else idx}")
    for col in PRIVACY_COLUMNS:
        write_query(col)
        print(f"  Column ensured: {col.split('ADD COLUMN IF NOT EXISTS ')[1].split(' VARCHAR')[0].split(' BOOLEAN')[0]}")
    print("Phase 84 schema applied successfully.")

if __name__ == "__main__":
    run()
