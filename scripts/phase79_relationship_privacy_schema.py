"""Phase 79 — Relationship Privacy Schema.

Safely adds granular privacy columns to chain_profiles and supporting indexes.
Run: python3 scripts/phase79_relationship_privacy_schema.py
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.neon_service import fast_query, write_query

MIGRATION_NAME = "phase79_relationship_privacy"

COLUMNS = {
    "profile_visibility": "TEXT DEFAULT 'public'",
    "who_can_see_posts": "TEXT DEFAULT 'public'",
    "who_can_see_reels": "TEXT DEFAULT 'public'",
    "who_can_see_stories": "TEXT DEFAULT 'friends_only'",
    "who_can_see_followers": "TEXT DEFAULT 'public'",
    "who_can_see_following": "TEXT DEFAULT 'public'",
    "who_can_send_friend_requests": "TEXT DEFAULT 'everyone'",
    "who_can_follow_me": "TEXT DEFAULT 'everyone'",
    "who_can_message_me": "TEXT DEFAULT 'friends'",
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_profiles_profile_visibility ON chain_profiles(profile_visibility);",
    "CREATE INDEX IF NOT EXISTS idx_follows_pair_privacy ON chain_follows(follower_profile_id, following_profile_id);",
    "CREATE INDEX IF NOT EXISTS idx_friends_pair_privacy ON chain_friends(profile_id_1, profile_id_2, status);",
]

ALLOWED_VISIBILITY = {"public", "friends_only", "followers_only", "private"}
ALLOWED_INTERACTION = {"everyone", "friends", "followers", "no_one"}

def column_exists(column):
    rows = fast_query(
        "SELECT 1 FROM information_schema.columns WHERE table_name='chain_profiles' AND column_name=%s",
        [column], timeout_ms=2000, default=[]
    )
    return bool(rows)

def run():
    print(f"[{MIGRATION_NAME}] Starting schema migration...")
    added = 0
    for col, col_type in COLUMNS.items():
        if column_exists(col):
            print(f"  SKIP  {col} — already exists")
            continue
        sql = f"ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS {col} {col_type};"
        try:
            write_query(sql, [])
            print(f"  ADD   {col} {col_type}")
            added += 1
        except Exception as e:
            print(f"  FAIL  {col}: {e}")
    for idx_sql in INDEXES:
        try:
            write_query(idx_sql, [])
            print(f"  INDEX {idx_sql.split('ON')[1].split(';')[0].strip()}")
        except Exception as e:
            print(f"  FAIL  index: {e}")
    print(f"[{MIGRATION_NAME}] Done. {added} column(s) added.")
    return added == len(COLUMNS)

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
