"""Phase 79 — Relationship Privacy Service unit tests (no-DB path)."""

import os, sys, uuid
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

print("Phase 79: Relationship Privacy Service")

from services.relationship_privacy_service import (
    normalize_visibility, normalize_interaction,
    can_view_by_rule, can_view_profile, can_view_posts,
    can_view_reels, can_view_stories, can_view_followers, can_view_following,
    can_send_friend_request, can_follow, can_message,
    get_full_policy, get_reason,
    ALLOWED_VISIBILITY, ALLOWED_INTERACTION,
    _is_self,
)

check("module importable", True)

# ── normalize_visibility ────────────────────────────────────────────
check("normalize_visibility public", normalize_visibility("public") == "public")
check("normalize_visibility friends_only", normalize_visibility("friends_only") == "friends_only")
check("normalize_visibility followers_only", normalize_visibility("followers_only") == "followers_only")
check("normalize_visibility private", normalize_visibility("private") == "private")
check("normalize_visibility invalid defaults to public", normalize_visibility("invalid") == "public")
check("normalize_visibility None defaults to public", normalize_visibility(None) == "public")
check("normalize_visibility empty defaults to public", normalize_visibility("") == "public")

# ── normalize_interaction ───────────────────────────────────────────
check("normalize_interaction everyone", normalize_interaction("everyone") == "everyone")
check("normalize_interaction friends", normalize_interaction("friends") == "friends")
check("normalize_interaction followers", normalize_interaction("followers") == "followers")
check("normalize_interaction no_one", normalize_interaction("no_one") == "no_one")
check("normalize_interaction invalid defaults to everyone", normalize_interaction("invalid") == "everyone")
check("normalize_interaction None defaults to everyone", normalize_interaction(None) == "everyone")

# ── _is_self ────────────────────────────────────────────────────────
UID_A = str(uuid.uuid4())
UID_B = str(uuid.uuid4())
check("_is_self same", _is_self(UID_A, UID_A))
check("_is_self different", not _is_self(UID_A, UID_B))
check("_is_self None viewer", not _is_self(None, UID_A))
check("_is_self None target", not _is_self(UID_A, None))
check("_is_self both None", not _is_self(None, None))
check("_is_self same string/int", _is_self("123", 123))

# ── can_view_by_rule (no DB path for public/private/None) ───────────
check("public rule allows anyone", can_view_by_rule(UID_B, UID_A, "public"))
check("public rule allows anonymous", can_view_by_rule(None, UID_A, "public"))
check("private rule denies other", not can_view_by_rule(UID_B, UID_A, "private"))
check("private rule denies anonymous", not can_view_by_rule(None, UID_A, "private"))
check("public rule with None viewer returns True", can_view_by_rule(None, UID_A, "public"))
check("private rule with None viewer returns False", not can_view_by_rule(None, UID_A, "private"))
check("invalid rule defaults to public=True for viewer", can_view_by_rule(UID_B, UID_A, "bogus"))
check("invalid rule defaults to public=True for anonymous", can_view_by_rule(None, UID_A, "bogus"))

# Self always allowed regardless of rule
check("self allowed with private rule", can_view_by_rule(UID_A, UID_A, "private"))
check("self allowed with friends_only rule", can_view_by_rule(UID_A, UID_A, "friends_only"))

# No owner_id
check("no owner_id returns False", not can_view_by_rule(UID_A, None, "public"))

# ── can_view_profile with mock profiles (no DB) ─────────────────────
mock_public = {"id": UID_A, "profile_visibility": "public"}
mock_private = {"id": UID_A, "profile_visibility": "private"}
mock_friends = {"id": UID_A, "profile_visibility": "friends_only"}
mock_followers = {"id": UID_A, "profile_visibility": "followers_only"}

check("self can view own public profile", can_view_profile(UID_A, mock_public))
check("self can view own private profile", can_view_profile(UID_A, mock_private))
check("self can view own friends_only profile", can_view_profile(UID_A, mock_friends))

check("other can view public profile", can_view_profile(UID_B, mock_public))
check("anonymous can view public profile", can_view_profile(None, mock_public))

check("other denied from private profile", not can_view_profile(UID_B, mock_private))
check("anonymous denied from private profile", not can_view_profile(None, mock_private))

# Empty profile returns False
check("None profile returns False", not can_view_profile(UID_B, None))

# ── can_view_posts with mock profiles ───────────────────────────────
check("self can view own private posts", can_view_posts(UID_A, mock_private))
check("other can view public posts", can_view_posts(UID_B, mock_public))
check("anonymous can view public posts", can_view_posts(None, mock_public))

mock_pvt_posts = {"id": UID_A, "who_can_see_posts": "private"}
check("other denied from private posts", not can_view_posts(UID_B, mock_pvt_posts))
check("anonymous denied from private posts", not can_view_posts(None, mock_pvt_posts))

# ── can_view_reels ──────────────────────────────────────────────────
check("self can view own private reels", can_view_reels(UID_A, mock_private))
check("other can view public reels", can_view_reels(UID_B, mock_public))

# ── can_view_stories ────────────────────────────────────────────────
check("self can view own stories", can_view_stories(UID_A, mock_private))
check("anonymous denied from friends_only stories", not can_view_stories(None, mock_public))

# ── can_view_followers / following ──────────────────────────────────
check("self can view own followers", can_view_followers(UID_A, mock_private))
check("self can view own following", can_view_following(UID_A, mock_private))
check("other can view public followers", can_view_followers(UID_B, mock_public))
check("other can view public following", can_view_following(UID_B, mock_public))

mock_pvt_followers = {"id": UID_A, "who_can_see_followers": "private"}
mock_pvt_following = {"id": UID_A, "who_can_see_following": "private"}
check("other denied from private followers", not can_view_followers(UID_B, mock_pvt_followers))
check("other denied from private following", not can_view_following(UID_B, mock_pvt_following))

# ── Interaction rules ───────────────────────────────────────────────
mock_no_fr = {"id": UID_A, "who_can_send_friend_requests": "no_one"}
mock_no_follow = {"id": UID_A, "who_can_follow_me": "no_one"}
mock_no_msg = {"id": UID_A, "who_can_message_me": "no_one"}

check("no_one disables friend request", not can_send_friend_request(UID_B, mock_no_fr))
check("no_one disables follow", not can_follow(UID_B, mock_no_follow))
check("no_one disables message", not can_message(UID_B, mock_no_msg))

mock_everyone_fr = {"id": UID_A, "who_can_send_friend_requests": "everyone"}
check("everyone allows friend request", can_send_friend_request(UID_B, mock_everyone_fr))

mock_everyone_follow = {"id": UID_A, "who_can_follow_me": "everyone"}
check("everyone allows follow", can_follow(UID_B, mock_everyone_follow))

mock_everyone_msg = {"id": UID_A, "who_can_message_me": "everyone"}
check("everyone allows message", can_message(UID_B, mock_everyone_msg))

# Self always denied for interactions
check("self cannot send friend request", not can_send_friend_request(UID_A, mock_everyone_fr))
check("self cannot follow", not can_follow(UID_A, mock_everyone_follow))
check("self cannot message", not can_message(UID_A, mock_everyone_msg))

# Missing target id
check("no target id = no friend req", not can_send_friend_request(UID_B, {"no_id": True}))
check("no target id = no follow", not can_follow(UID_B, {"no_id": True}))
check("no target id = no message", not can_message(UID_B, {"no_id": True}))

# ── get_full_policy ─────────────────────────────────────────────────
fp = get_full_policy(UID_B, mock_public)
check("get_full_policy returns dict", isinstance(fp, dict))
check("get_full_policy has relationship", "relationship" in fp)
check("get_full_policy has profile_visibility", "profile_visibility" in fp)
check("get_full_policy has can_view_profile", "can_view_profile" in fp)
check("get_full_policy has can_view_posts", "can_view_posts" in fp)
check("get_full_policy has can_view_reels", "can_view_reels" in fp)
check("get_full_policy has can_view_stories", "can_view_stories" in fp)
check("get_full_policy has can_view_followers", "can_view_followers" in fp)
check("get_full_policy has can_view_following", "can_view_following" in fp)
check("get_full_policy has can_send_friend_request", "can_send_friend_request" in fp)
check("get_full_policy has can_follow", "can_follow" in fp)
check("get_full_policy has can_message", "can_message" in fp)
check("get_full_policy has reason", "reason" in fp)
check("get_full_policy 11 keys", len(fp) == 11)

# Public profile for other is allowed
check("public profile allowed for other", fp.get("can_view_profile") == True)

fp_private = get_full_policy(UID_B, mock_private)
check("private profile denied for other", fp_private.get("can_view_profile") == False)

fp_self = get_full_policy(UID_A, mock_private)
check("self sees own private profile", fp_self.get("can_view_profile") == True)
check("self can view own posts", fp_self.get("can_view_posts") == True)
check("self can view own reels", fp_self.get("can_view_reels") == True)
check("self can view own stories", fp_self.get("can_view_stories") == True)
check("self can view own followers", fp_self.get("can_view_followers") == True)
check("self can view own following", fp_self.get("can_view_following") == True)
check("self cannot send self friend req", fp_self.get("can_send_friend_request") == False)
check("self cannot follow self", fp_self.get("can_follow") == False)
check("self cannot message self", fp_self.get("can_message") == False)

# None profile
check("get_full_policy None for no profile", get_full_policy(UID_B, None) is None)

# ── get_reason ──────────────────────────────────────────────────────
check("get_reason returns string", isinstance(get_reason({"can_view_profile": True}, "can_view_profile", "friend"), str))
check("get_reason allowed", get_reason({"can_view_profile": True}, "can_view_profile", "friend") == "can_view_profile_allowed")
check("get_reason denied", "denied" in get_reason({"can_view_profile": False}, "can_view_profile", "friend"))

# ── ALLOWED sets ────────────────────────────────────────────────────
check("ALLOWED_VISIBILITY count", len(ALLOWED_VISIBILITY) == 4)
check("ALLOWED_INTERACTION count", len(ALLOWED_INTERACTION) == 4)

print(f"\nPhase 79 Results: {PASS} passed, {FAIL} failed")
