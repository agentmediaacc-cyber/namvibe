"""
Phase 85 — Profile Command Center Schema
Creates/updates tables for post/reel settings, profile privacy, friendship.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.neon_service import write_query

TABLES = [
    # Friend requests (enhanced from Phase 84)
    """
    CREATE TABLE IF NOT EXISTS chain_friend_requests (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        sender_profile_id UUID NOT NULL,
        receiver_profile_id UUID NOT NULL,
        status TEXT DEFAULT 'pending',
        message TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        responded_at TIMESTAMPTZ,
        UNIQUE(sender_profile_id, receiver_profile_id)
    )
    """,
    # Friends (enhanced from Phase 84)
    """
    CREATE TABLE IF NOT EXISTS chain_friends (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id UUID NOT NULL,
        friend_profile_id UUID NOT NULL,
        friendship_type TEXT DEFAULT 'friend',
        is_close_friend BOOLEAN DEFAULT FALSE,
        is_best_friend BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(profile_id, friend_profile_id)
    )
    """,
    # Profile privacy settings
    """
    CREATE TABLE IF NOT EXISTS chain_profile_privacy (
        profile_id UUID PRIMARY KEY,
        who_can_follow TEXT DEFAULT 'everyone',
        who_can_message TEXT DEFAULT 'followers',
        who_can_call TEXT DEFAULT 'friends',
        who_can_view_posts TEXT DEFAULT 'public',
        who_can_view_reels TEXT DEFAULT 'public',
        require_coins_to_follow BOOLEAN DEFAULT FALSE,
        follow_coin_price INTEGER DEFAULT 0,
        premium_only_follow BOOLEAN DEFAULT FALSE,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    # Post settings
    """
    CREATE TABLE IF NOT EXISTS chain_post_settings (
        post_id UUID PRIMARY KEY,
        comments_enabled BOOLEAN DEFAULT TRUE,
        sharing_enabled BOOLEAN DEFAULT TRUE,
        visibility TEXT DEFAULT 'public',
        is_pinned BOOLEAN DEFAULT FALSE,
        is_archived BOOLEAN DEFAULT FALSE,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    # Reel settings
    """
    CREATE TABLE IF NOT EXISTS chain_reel_settings (
        reel_id UUID PRIMARY KEY,
        comments_enabled BOOLEAN DEFAULT TRUE,
        sharing_enabled BOOLEAN DEFAULT TRUE,
        visibility TEXT DEFAULT 'public',
        is_pinned BOOLEAN DEFAULT FALSE,
        is_archived BOOLEAN DEFAULT FALSE,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_friend_requests_receiver_status ON chain_friend_requests(receiver_profile_id, status, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_friend_requests_sender_status ON chain_friend_requests(sender_profile_id, status, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_friends_profile_created ON chain_friends(profile_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_friends_friend_created ON chain_friends(friend_profile_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_posts_profile_created ON chain_posts(profile_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_reels_profile_created ON chain_reels(profile_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_follows_follower_following ON chain_follows(follower_profile_id, following_profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_follows_following_created ON chain_follows(following_profile_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_notifications_recipient_read_created ON chain_notifications(recipient_profile_id, is_read, created_at DESC)",
]

SETTINGS_COLUMNS = [
    "ALTER TABLE chain_posts ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE",
    "ALTER TABLE chain_posts ADD COLUMN IF NOT EXISTS is_draft BOOLEAN DEFAULT FALSE",
    "ALTER TABLE chain_posts ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMPTZ",
    "ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT FALSE",
    "ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS is_draft BOOLEAN DEFAULT FALSE",
    "ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMPTZ",
]

def run():
    for stmt in TABLES:
        write_query(stmt)
        name = stmt.split("CREATE TABLE IF NOT EXISTS ")[1].split(" ")[0].split("(")[0]
        print(f"  Table ensured: {name}")
    for idx in INDEXES:
        write_query(idx)
        table_col = idx.split(" ON ")[1].split("(")[0] if " ON " in idx else idx
        print(f"  Index ensured: {table_col}")
    for col in SETTINGS_COLUMNS:
        write_query(col)
        parts = col.split("ADD COLUMN IF NOT EXISTS ")
        name = parts[1].split(" ")[0] if len(parts) > 1 else col
        print(f"  Column ensured: {name}")
    print("Phase 85 schema applied successfully.")

if __name__ == "__main__":
    run()
