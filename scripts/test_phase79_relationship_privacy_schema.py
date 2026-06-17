"""Phase 79 — Relationship Privacy Schema tests.
Checks that migration script exists, columns are defined, and indexes are correct.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)

def check(desc, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  OK  {desc}")
    else:
        FAIL += 1
        print(f"  FAIL {desc}")

print("Phase 79: Relationship Privacy Schema")

# Migration script exists
check("migration script exists", os.path.isfile("scripts/phase79_relationship_privacy_schema.py"))

# Read the migration script
with open("scripts/phase79_relationship_privacy_schema.py") as f:
    content = f.read()

# Column definitions
check("profile_visibility column", "profile_visibility" in content)
check("who_can_see_posts column", "who_can_see_posts" in content)
check("who_can_see_reels column", "who_can_see_reels" in content)
check("who_can_see_stories column", "who_can_see_stories" in content)
check("who_can_see_followers column", "who_can_see_followers" in content)
check("who_can_see_following column", "who_can_see_following" in content)
check("who_can_send_friend_requests column", "who_can_send_friend_requests" in content)
check("who_can_follow_me column", "who_can_follow_me" in content)
check("who_can_message_me column", "who_can_message_me" in content)

# All 9 columns
check("9 columns defined", content.count("TEXT DEFAULT") == 9)

# Index definitions
check("profile_visibility index", "idx_profiles_profile_visibility" in content)
check("follows_pair_privacy index", "idx_follows_pair_privacy" in content)
check("friends_pair_privacy index", "idx_friends_pair_privacy" in content)
check("3 indexes defined", content.count("CREATE INDEX") == 3)

# Allowed values
check("visibility values defined", "ALLOWED_VISIBILITY" in content)
check("interaction values defined", "ALLOWED_INTERACTION" in content)
check("public in visibility", '"public"' in content)
check("friends_only in visibility", '"friends_only"' in content)
check("followers_only in visibility", '"followers_only"' in content)
check("private in visibility", '"private"' in content)
check("everyone in interaction", '"everyone"' in content)
check("friends in interaction", '"friends"' in content)
check("followers in interaction", '"followers"' in content)
check("no_one in interaction", '"no_one"' in content)

# Default values
import re
check("profile_visibility default public", "DEFAULT 'public'" in content)
check("who_can_see_stories default friends_only", bool(re.search(r"who_can_see_stories['\"]?.*friends_only", content)))
check("who_can_message_me default friends", bool(re.search(r"who_can_message_me['\"]?.*friends", content)))

# IDEMPOTENT — uses IF NOT EXISTS / ADD COLUMN IF NOT EXISTS
check("uses ADD COLUMN IF NOT EXISTS", "ADD COLUMN IF NOT EXISTS" in content)
check("uses CREATE INDEX IF NOT EXISTS", "CREATE INDEX IF NOT EXISTS" in content)

# Can import migration function
try:
    from scripts.phase79_relationship_privacy_schema import run, COLUMNS, INDEXES
    check("run() function importable", callable(run))
    check("COLUMNS dict exists", isinstance(COLUMNS, dict))
    check("INDEXES list exists", isinstance(INDEXES, list))
    check("all 9 columns in COLUMNS", len(COLUMNS) == 9)
    check("all 3 indexes in INDEXES", len(INDEXES) == 3)
except Exception as e:
    print(f"  FAIL import: {e}")

# Privacy service columns match migration
try:
    from services.relationship_privacy_service import ALLOWED_VISIBILITY, ALLOWED_INTERACTION
    check("visibility values match service", ALLOWED_VISIBILITY == {"public", "friends_only", "followers_only", "private"})
    check("interaction values match service", ALLOWED_INTERACTION == {"everyone", "friends", "followers", "no_one"})
except Exception as e:
    print(f"  FAIL service import: {e}")

print(f"\nPhase 79 Schema Results: {PASS} passed, {FAIL} failed")
