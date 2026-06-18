"""Phase 79 — Relationship Privacy Service unit tests (pure logic only, no DB)."""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)

PASS = 0
FAIL = 0

def check(desc, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  OK  {desc}")
    else:
        FAIL += 1
        print(f"  FAIL {desc}")

print("Phase 79: Relationship Privacy Service")

# Import pure logic helpers only
from services.relationship_privacy_service import (
    normalize_visibility,
    normalize_interaction,
    get_reason,
    ALLOWED_VISIBILITY,
    ALLOWED_INTERACTION,
)

check("module importable", True)

# ── normalize_visibility ────────────────────────────────────────────
check("norm vis public", normalize_visibility("public") == "public")
check("norm vis friends_only", normalize_visibility("friends_only") == "friends_only")
check("norm vis followers_only", normalize_visibility("followers_only") == "followers_only")
check("norm vis private", normalize_visibility("private") == "private")
check("norm vis invalid -> public", normalize_visibility("invalid") == "public")
check("norm vis None -> public", normalize_visibility(None) == "public")
check("norm vis '' -> public", normalize_visibility("") == "public")
check("norm vis custom default", normalize_visibility(None, "private") == "private")
check("norm vis custom default 2", normalize_visibility("invalid", "friends_only") == "friends_only")

# ── normalize_interaction ───────────────────────────────────────────
check("norm int everyone", normalize_interaction("everyone") == "everyone")
check("norm int friends", normalize_interaction("friends") == "friends")
check("norm int followers", normalize_interaction("followers") == "followers")
check("norm int no_one", normalize_interaction("no_one") == "no_one")
check("norm int invalid -> everyone", normalize_interaction("invalid") == "everyone")
check("norm int None -> everyone", normalize_interaction(None) == "everyone")
check("norm int '' -> everyone", normalize_interaction("") == "everyone")
check("norm int custom default", normalize_interaction(None, "no_one") == "no_one")

# ── get_reason ──────────────────────────────────────────────────────
check("get_reason returns str", isinstance(get_reason({"a": True}, "a", "friend"), str))
check("get_reason allowed suffix", "allowed" in get_reason({"a": True}, "a", "friend"))
check("get_reason denied suffix", "denied" in get_reason({"a": False}, "a", "friend"))
check("get_reason key in output", get_reason({"x": True}, "x", "self") == "x_allowed")

# ── ALLOWED sets ────────────────────────────────────────────────────
check("ALLOWED_VISIBILITY count", len(ALLOWED_VISIBILITY) == 4)
check("public in visibility", "public" in ALLOWED_VISIBILITY)
check("friends_only in visibility", "friends_only" in ALLOWED_VISIBILITY)
check("followers_only in visibility", "followers_only" in ALLOWED_VISIBILITY)
check("private in visibility", "private" in ALLOWED_VISIBILITY)

check("ALLOWED_INTERACTION count", len(ALLOWED_INTERACTION) == 4)
check("everyone in interaction", "everyone" in ALLOWED_INTERACTION)
check("friends in interaction", "friends" in ALLOWED_INTERACTION)
check("followers in interaction", "followers" in ALLOWED_INTERACTION)
check("no_one in interaction", "no_one" in ALLOWED_INTERACTION)

# ── Source code structure checks ────────────────────────────────────
with open("services/relationship_privacy_service.py") as f:
    src = f.read()

check("has is_friend function", "def is_friend" in src)
check("has is_follower function", "def is_follower" in src)
check("has is_blocked_any function", "def is_blocked_any" in src)
check("has get_relationship function", "def get_relationship" in src)
check("has can_view_by_rule function", "def can_view_by_rule" in src)
check("has can_view_profile function", "def can_view_profile" in src)
check("has can_view_posts function", "def can_view_posts" in src)
check("has can_view_reels function", "def can_view_reels" in src)
check("has can_view_stories function", "def can_view_stories" in src)
check("has can_view_followers function", "def can_view_followers" in src)
check("has can_view_following function", "def can_view_following" in src)
check("has can_send_friend_request function", "def can_send_friend_request" in src)
check("has can_follow function", "def can_follow" in src)
check("has can_message function", "def can_message" in src)
check("has get_full_policy function", "def get_full_policy" in src)
check("has get_reason function", "def get_reason" in src)
check("has normalize_visibility function", "def normalize_visibility" in src)
check("has normalize_interaction function", "def normalize_interaction" in src)

# ── Social action policy imports ────────────────────────────────────
with open("services/social_action_policy.py") as f:
    sap = f.read()

check("sap imports relationship_privacy_service", "relationship_privacy_service" in sap)

# ── Profile service privacy ─────────────────────────────────────────
with open("services/profile_service.py") as f:
    ps = f.read()

check("profile_service handles who_can_see_posts", "who_can_see_posts" in ps)
check("profile_service handles who_can_see_reels", "who_can_see_reels" in ps)
check("profile_service handles who_can_see_stories", "who_can_see_stories" in ps)
check("profile_service handles who_can_see_followers", "who_can_see_followers" in ps)
check("profile_service handles who_can_see_following", "who_can_see_following" in ps)
check("profile_service handles who_can_send_friend_requests", "who_can_send_friend_requests" in ps)
check("profile_service handles who_can_follow_me", "who_can_follow_me" in ps)
check("profile_service handles who_can_message_me", "who_can_message_me" in ps)
check("profile_service handles profile_visibility", "profile_visibility" in ps)

print(f"\nPhase 79 Results: {PASS} passed, {FAIL} failed")
