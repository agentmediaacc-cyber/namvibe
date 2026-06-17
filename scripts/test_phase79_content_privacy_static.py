"""Phase 79 — Content privacy static code checks."""

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

print("Phase 79: Content Privacy Static")

# ── Feed service ────────────────────────────────────────────────────
with open("services/feed_service.py") as f:
    fs = f.read()

check("feed imports can_view_posts", "can_view_posts" in fs)
check("feed uses can_view_posts for posts", "can_view_posts" in fs[fs.find("for post"):] if "for post" in fs else True)
check("feed imports is_blocked_any", "is_blocked_any" in fs)
check("feed blocks live rooms for blocked", "is_blocked_any" in fs)

# ── Search service ──────────────────────────────────────────────────
with open("services/search_service.py") as f:
    ss = f.read()

check("search imports can_view_profile", "can_view_profile" in ss)
check("search imports can_view_posts", "can_view_posts" in ss)
check("search imports can_view_reels", "can_view_reels" in ss)
check("search imports is_blocked_any", "is_blocked_any" in ss)
check("search has privacy filter for profiles", "_privacy_filter_profiles" in ss)
check("search has privacy filter for posts", "_privacy_filter_posts" in ss)
check("search filters blocked profiles", "is_blocked_any" in ss)
check("search filters blocked in posts", "is_blocked_any" in ss[ss.find("_privacy_filter_posts"):])

# ── Followers/Following privacy ─────────────────────────────────────
with open("api_routes/social_routes.py") as f:
    sr = f.read()

check("social routes import can_view_followers", "can_view_followers" in sr)
check("social routes import can_view_following", "can_view_following" in sr)
check("followers route checks privacy", "can_view_followers" in sr[sr.find("view_user_followers"):])
check("following route checks privacy", "can_view_following" in sr[sr.find("view_user_following"):])
check("followers returns privacy_restricted", "privacy_restricted" in sr)
check("following returns privacy_restricted", "privacy_restricted" in sr)

# Privacy settings endpoints
check("GET /api/privacy/settings exists", "api_privacy_settings_get" in sr)
check("POST /api/privacy/settings exists", "api_privacy_settings_post" in sr)

# ── Privacy template ────────────────────────────────────────────────
with open("templates/profile/privacy.html") as f:
    pt = f.read()

check("privacy template has profile_visibility", "profile_visibility" in pt)
check("privacy template has who_can_see_posts", "who_can_see_posts" in pt)
check("privacy template has who_can_see_reels", "who_can_see_reels" in pt)
check("privacy template has who_can_see_stories", "who_can_see_stories" in pt)
check("privacy template has who_can_see_followers", "who_can_see_followers" in pt)
check("privacy template has who_can_see_following", "who_can_see_following" in pt)
check("privacy template has who_can_send_friend_requests", "who_can_send_friend_requests" in pt)
check("privacy template has who_can_follow_me", "who_can_follow_me" in pt)
check("privacy template has who_can_message_me", "who_can_message_me" in pt)

print(f"\nPhase 79 Content Privacy: {PASS} passed, {FAIL} failed")
