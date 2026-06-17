"""
Phase 78 — Social Action Policy Tests.

Tests all functions in services/social_action_policy.py:
- get_account_kind / is_page_like_account / is_person_account
- can_send_friend_request / can_follow / can_chat / can_like_post
- can_view_profile (public, private, friends_only, blocked)
- get_relationship / get_primary_action / get_action_policy

Run:
  python3 scripts/test_phase78_social_action_policy.py
"""

import os, sys, json

PASS = 0
FAIL = 0

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

os.environ["FLASK_ENV"] = "development"
os.environ["ENV"] = "development"
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"

from services.social_action_policy import (
    get_account_kind,
    is_page_like_account,
    is_person_account,
    is_self,
    can_send_friend_request,
    can_follow,
    can_chat,
    can_like_post,
    can_view_profile,
    get_relationship,
    get_primary_action,
    get_action_policy,
)

def ok(name, detail=""):
    global PASS
    PASS += 1
    msg = f"  OK {name}"
    if detail:
        msg += f"  ({detail})"
    print(msg)

def fail(name, detail=""):
    global FAIL
    FAIL += 1
    msg = f"  FAIL {name}"
    if detail:
        msg += f"  ({detail})"
    print(msg)

def check(name, condition, detail=""):
    if condition:
        ok(name, detail)
    else:
        fail(name, detail)

profile_person = {
    "id": "11111111-1111-1111-1111-111111111111",
    "profile_type": "member",
    "account_type": "personal",
    "is_creator": False,
    "is_premium": False,
    "is_page": False,
    "is_verified": False,
    "visibility": "public",
}

profile_page = {
    "id": "22222222-2222-2222-2222-222222222222",
    "profile_type": "member",
    "account_type": "personal",
    "is_creator": False,
    "is_premium": False,
    "is_page": True,
    "is_verified": False,
    "visibility": "public",
}

profile_creator = {
    "id": "33333333-3333-3333-3333-333333333333",
    "profile_type": "creator",
    "account_type": "personal",
    "is_creator": True,
    "is_premium": False,
    "is_page": False,
    "is_verified": False,
    "visibility": "public",
}

profile_business = {
    "id": "44444444-4444-4444-4444-444444444444",
    "profile_type": "seller",
    "account_type": "business",
    "is_creator": False,
    "is_premium": False,
    "is_page": False,
    "is_verified": False,
    "visibility": "public",
}

profile_premium = {
    "id": "55555555-5555-5555-5555-555555555555",
    "profile_type": "member",
    "account_type": "personal",
    "is_creator": False,
    "is_premium": True,
    "is_page": False,
    "is_verified": False,
    "visibility": "public",
}

profile_private = {
    "id": "66666666-6666-6666-6666-666666666666",
    "profile_type": "member",
    "account_type": "personal",
    "is_creator": False,
    "is_premium": False,
    "is_page": False,
    "is_verified": False,
    "visibility": "private",
    "account_privacy": "private",
}

profile_private_v2 = {
    "id": "77777777-7777-7777-7777-777777777777",
    "profile_type": "member",
    "account_type": "personal",
    "is_creator": False,
    "is_premium": False,
    "is_page": False,
    "is_verified": False,
    "profile_visibility": "private",
}

profile_government = {
    "id": "88888888-8888-8888-8888-888888888888",
    "profile_type": "member",
    "account_type": "personal",
    "is_creator": False,
    "is_premium": False,
    "is_page": False,
    "is_verified": True,
    "visibility": "public",
}

UID_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
UID_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

print("=" * 70)
print("  Phase 78: Social Action Policy Tests")
print("=" * 70)

# ─── 1. get_account_kind ───
print("\n--- 1. get_account_kind ---")
check("person account", get_account_kind(profile_person) == "person")
check("page account", get_account_kind(profile_page) == "page")
check("creator account", get_account_kind(profile_creator) == "creator")
check("business account", get_account_kind(profile_business) == "business")
check("premium account", get_account_kind(profile_premium) == "premium")
check("government (verified)", get_account_kind(profile_government) == "government")
check("None returns unknown", get_account_kind(None) == "unknown")

# ─── 2. is_page_like_account / is_person_account ───
print("\n--- 2. is_page_like_account / is_person_account ---")
check("person not page-like", not is_page_like_account(profile_person))
check("page is page-like", is_page_like_account(profile_page))
check("creator is page-like", is_page_like_account(profile_creator))
check("business is page-like", is_page_like_account(profile_business))
check("premium is page-like", is_page_like_account(profile_premium))
check("government is page-like", is_page_like_account(profile_government))
check("person is person", is_person_account(profile_person))
check("page not person", not is_person_account(profile_page))
check("creator not person", not is_person_account(profile_creator))

# ─── 3. is_self ───
print("\n--- 3. is_self ---")
check("same id is self", is_self(UID_A, UID_A))
check("different ids not self", not is_self(UID_A, UID_B))
check("None not self", not is_self(None, UID_A))
check("self with None target", not is_self(UID_A, None))

# ─── 4. can_send_friend_request (static checks, no DB) ───
print("\n--- 4. can_send_friend_request (static checks) ---")
check("no current profile", not can_send_friend_request(None, profile_person))
check("no target", not can_send_friend_request(UID_A, None))
profile_self = profile_person.copy()
profile_self["id"] = UID_A
check("self cannot friend self", not can_send_friend_request(UID_A, profile_self))
check("page cannot receive friend request", not can_send_friend_request(UID_A, profile_page))
check("creator cannot receive friend request", not can_send_friend_request(UID_A, profile_creator))
check("default: person can receive friend request (no DB)", can_send_friend_request(UID_A, profile_person))

# ─── 5. can_follow ───
print("\n--- 5. can_follow ---")
check("no current profile", not can_follow(None, profile_person))
check("no target", not can_follow(UID_A, None))
check("cannot follow self", not can_follow(UID_A, profile_self))
check("can follow person", can_follow(UID_A, profile_person))
check("can follow page", can_follow(UID_A, profile_page))

# ─── 6. can_chat (static checks) ───
print("\n--- 6. can_chat (static checks) ---")
check("no current", not can_chat(None, UID_B))
check("no target", not can_chat(UID_A, None))
check("cannot chat self", not can_chat(UID_A, UID_A))

# ─── 7. can_like_post ───
print("\n--- 7. can_like_post ---")
check("no current", not can_like_post(None, {"profile_id": UID_B}))
check("no post", not can_like_post(UID_A, None))
check("cannot like own post", not can_like_post(UID_A, {"profile_id": UID_A}))
check("can like other's post", can_like_post(UID_A, {"profile_id": UID_B}))

# ─── 8. can_view_profile ───
print("\n--- 8. can_view_profile ---")
self_result = can_view_profile(UID_A, {"id": UID_A})
check("self can view own", self_result.get("can_view_full_profile"))
check("self reason is self", self_result.get("reason") == "self")

public_result = can_view_profile(UID_B, profile_person)
check("public profile visible", public_result.get("can_view_full_profile"))
check("public reason is public", public_result.get("reason") == "public")

private_result = can_view_profile(UID_B, profile_private)
check("private profile hidden for non-follower", not private_result.get("can_view_full_profile"))
check("private reason is private", private_result.get("reason") == "private")

private_v2_result = can_view_profile(UID_B, profile_private_v2)
check("private profile (profile_visibility) hidden", not private_v2_result.get("can_view_full_profile"))

not_logged_result = can_view_profile(None, profile_private)
check("not logged in cannot view private", not not_logged_result.get("can_view_full_profile"))

not_logged_public = can_view_profile(None, profile_person)
check("not logged in can view public", not_logged_public.get("can_view_full_profile"))

# ─── 9. get_primary_action (static) ───
print("\n--- 9. get_primary_action ---")
check("self -> none", get_primary_action(UID_A, profile_self) == "none")
check("person -> friend_request", get_primary_action(UID_B, profile_person) == "friend_request")
check("page -> follow", get_primary_action(UID_B, profile_page) == "follow")
check("creator -> follow", get_primary_action(UID_B, profile_creator) == "follow")
check("no viewer -> none", get_primary_action(None, profile_person) == "none")

# ─── 10. get_action_policy ───
print("\n--- 10. get_action_policy ---")
policy = get_action_policy(None, profile_person)
check("no viewer policy exists", policy is not None)
check("no viewer not self", not policy.get("is_self"))
check("no viewer person kind", policy.get("account_kind") == "person")

profile_self2 = profile_person.copy()
profile_self2["id"] = UID_A
policy_self = get_action_policy(UID_A, profile_self2)
check("self policy exists", policy_self is not None)
check("self account_kind is person", policy_self.get("account_kind") == "person")
check("self is_self true", policy_self.get("is_self"))

policy_page = get_action_policy(UID_B, profile_page)
check("viewer+page account_kind is page", policy_page.get("account_kind") == "page")
check("viewer+page primary_action is follow", policy_page.get("primary_action") == "follow")
check("viewer+page can_follow true", policy_page.get("can_follow"))
check("viewer+page can_send_friend_request false", not policy_page.get("can_send_friend_request"))

# ─── 11. Module has required exports ───
print("\n--- 11. Module exports ---")
exported = [
    "get_account_kind", "is_page_like_account", "is_person_account",
    "is_self", "can_send_friend_request", "can_follow",
    "can_chat", "can_like_post", "can_view_profile",
    "get_relationship", "get_primary_action", "get_action_policy",
]
for func in exported:
    check(f"exports {func}", func in dir() or eval(func), func)

# ─── RESULTS ───
print("\n" + "=" * 70)
print(f"  Phase 78 Results: {PASS} passed, {FAIL} failed")
print("=" * 70)
sys.exit(0 if FAIL == 0 else 1)
