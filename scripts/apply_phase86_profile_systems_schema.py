"""
Phase 86 — Profile Systems Schema
Idempotent: all CREATEs use IF NOT EXISTS
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"

from services.neon_service import write_query, fast_query, get_pool_status
from services.logging_service import log_info

def run():
    print("=" * 60)
    print("Phase 86 — Profile Systems Schema Migration")
    print("=" * 60)

    if not (os.getenv("FLASK_TESTING") == "1" or get_pool_status().get("pool_ready")):
        print("[SKIP] No database pool available — running in test mode")
        return

    statements = [
        # 1. chain_friend_requests
        """CREATE TABLE IF NOT EXISTS chain_friend_requests (
            id UUID PRIMARY KEY,
            sender_profile_id UUID NOT NULL,
            receiver_profile_id UUID NOT NULL,
            status TEXT DEFAULT 'pending',
            message TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            responded_at TIMESTAMPTZ,
            UNIQUE(sender_profile_id, receiver_profile_id)
        )""",
        # 2. chain_friends
        """CREATE TABLE IF NOT EXISTS chain_friends (
            id UUID PRIMARY KEY,
            profile_id UUID NOT NULL,
            friend_profile_id UUID NOT NULL,
            friendship_type TEXT DEFAULT 'friend',
            is_close_friend BOOLEAN DEFAULT false,
            is_best_friend BOOLEAN DEFAULT false,
            created_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(profile_id, friend_profile_id)
        )""",
        # 3. chain_post_settings
        """CREATE TABLE IF NOT EXISTS chain_post_settings (
            post_id UUID PRIMARY KEY,
            comments_enabled BOOLEAN DEFAULT true,
            sharing_enabled BOOLEAN DEFAULT true,
            visibility TEXT DEFAULT 'public',
            is_pinned BOOLEAN DEFAULT false,
            is_archived BOOLEAN DEFAULT false,
            updated_at TIMESTAMPTZ DEFAULT now()
        )""",
        # 4. chain_reel_settings
        """CREATE TABLE IF NOT EXISTS chain_reel_settings (
            reel_id UUID PRIMARY KEY,
            comments_enabled BOOLEAN DEFAULT true,
            sharing_enabled BOOLEAN DEFAULT true,
            visibility TEXT DEFAULT 'public',
            is_pinned BOOLEAN DEFAULT false,
            is_archived BOOLEAN DEFAULT false,
            updated_at TIMESTAMPTZ DEFAULT now()
        )""",
        # 5. chain_profile_privacy
        """CREATE TABLE IF NOT EXISTS chain_profile_privacy (
            profile_id UUID PRIMARY KEY,
            who_can_follow TEXT DEFAULT 'everyone',
            who_can_message TEXT DEFAULT 'followers',
            who_can_call TEXT DEFAULT 'friends',
            who_can_view_posts TEXT DEFAULT 'public',
            who_can_view_reels TEXT DEFAULT 'public',
            require_coins_to_follow BOOLEAN DEFAULT false,
            follow_coin_price INTEGER DEFAULT 0,
            premium_only_follow BOOLEAN DEFAULT false,
            updated_at TIMESTAMPTZ DEFAULT now()
        )""",
    ]

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_chain_posts_profile_created ON chain_posts(profile_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_chain_reels_profile_created ON chain_reels(profile_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_chain_follows_follower ON chain_follows(follower_profile_id, following_profile_id)",
        "CREATE INDEX IF NOT EXISTS idx_chain_follows_following ON chain_follows(following_profile_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_friend_req_receiver ON chain_friend_requests(receiver_profile_id, status, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_friend_req_sender ON chain_friend_requests(sender_profile_id, status, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_chain_friends_profile ON chain_friends(profile_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_chain_friends_friend ON chain_friends(friend_profile_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_notif_recipient_read ON chain_notifications(recipient_profile_id, is_read, created_at DESC)",
    ]

    for i, sql in enumerate(statements):
        try:
            write_query(sql)
            print(f"  [OK] Table {i+1}/{len(statements)}")
        except Exception as e:
            print(f"  [WARN] Table {i+1}: {e}")

    for i, sql in enumerate(indexes):
        try:
            write_query(sql)
            print(f"  [OK] Index {i+1}/{len(indexes)}")
        except Exception as e:
            print(f"  [WARN] Index {i+1}: {e}")

    # Verify
    tables = ["chain_friend_requests", "chain_friends", "chain_post_settings", "chain_reel_settings", "chain_profile_privacy"]
    for t in tables:
        rows = fast_query(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{t}') AS e", default=[{"e": False}])
        exists = rows[0]["e"] if rows else False
        print(f"  {'EXISTS' if exists else 'MISSING'} {t}")

    print("=" * 60)
    print("Phase 86 schema complete")
    print("=" * 60)

if __name__ == "__main__":
    run()
