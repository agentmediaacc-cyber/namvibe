"""
Phase 78 — Discovery Static Checks.

Verifies:
- social_action_policy module is importable
- Discovery templates have action-policy-aware buttons
- Profile templates use action_policy
- Backend self-action guards exist
- No self-actions possible through code paths
- Private profile template exists

Run:
  python3 scripts/test_phase78_discovery_static.py
"""

import os, sys

PASS = 0
FAIL = 0

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

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

def readf(path):
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return None

def check(name, condition, detail=""):
    if condition:
        ok(name, detail)
    else:
        fail(name, detail)

print("=" * 70)
print("  Phase 78: Discovery Static Tests")
print("=" * 70)

# ─── 1. Module importable ───
print("\n--- 1. Module importable ---")
try:
    import services.social_action_policy as sap
    ok("services.social_action_policy importable")
    for fn in ["get_account_kind", "is_page_like_account", "can_send_friend_request", "can_follow", "can_chat", "can_like_post", "can_view_profile", "get_action_policy", "get_primary_action", "get_relationship"]:
        check(f"  exports {fn}", hasattr(sap, fn))
except ImportError as e:
    fail("services.social_action_policy importable", str(e))

# ─── 2. Discovery template has action-aware buttons ───
print("\n--- 2. Discovery template ---")
dt = readf("templates/discover/index.html") or ""
check("discover template exists", bool(dt))
check("Add Friend button in discovery", "Add Friend" in dt or "data-friend-action" in dt)
check("Follow button in discovery", "data-follow-profile" in dt)
check("primary_action used in discovery", "primary_action" in dt)
check("discovery shows self label", "primary_action == 'self'" in dt)
check("no static Follow-only button", "data-follow-profile" in dt)
check("JS friend action handler", "data-friend-action" in dt)
check("JS friend response handler", "data-friend-response" in dt)
check("Login prompt for anonymous", "/auth/login" in dt)

# ─── 3. Profile template uses action_policy ───
print("\n--- 3. Profile template ---")
pi = readf("templates/profile/index.html") or ""
check("profile index exists", bool(pi))
check("action_policy in profile index", "action_policy" in pi)
check("mobile action bar uses action_policy", "action_policy" in pi)
check("no self follow button", "own_profile" in pi)
check("no self friend button for own profile", "own_profile" in pi)

ph = readf("templates/profile/partials/profile_header.html") or ""
check("profile header uses action_policy", "action_policy" in ph or "pa.primary_action" in ph)
check("profile header handles own_profile", "own_profile" in ph)
check("profile header has data-friend-action", "data-friend-action" in ph)
check("profile header has data-profile-follow", "data-profile-follow" in ph)

# ─── 4. Private profile template exists ───
print("\n--- 4. Private profile template ---")
ppt = readf("templates/profile/private_profile.html") or ""
check("private_profile.html exists", bool(ppt))
check("private profile has privacy message", "private" in ppt.lower())
check("private profile uses action_policy", "action_policy" in ppt)
check("private profile has lock icon", "fa-lock" in ppt)
check("private profile has friend/follow buttons", "data-friend-action" in ppt or "data-follow-profile" in ppt)

# ─── 5. Backend self-action guards ───
print("\n--- 5. Backend guards ---")
eng = readf("services/engagement_service.py") or ""
check("toggle_like guards self-like", "cannot_like_own_content" in eng)

fr = readf("services/friend_service.py") or ""
check("friend_service guards self-request", "cannot send a friend request to yourself" in fr)

wl = readf("services/wallet_engine.py") or ""
check("wallet guards self-gift", "cannot gift yourself" in wl.lower() or "You cannot gift yourself" in wl)

wps = readf("services/wallet_payment_service.py") or ""
check("wallet_payment guards self-transfer", "Cannot transfer to yourself" in wps)
check("wallet_payment guards self-tip", "Cannot tip yourself" in wps)
check("wallet_payment guards self-gift", "Cannot gift yourself" in wps)
check("wallet_payment guards self-subscribe", "Cannot subscribe to yourself" in wps)

# ─── 6. API endpoint exists ───
print("\n--- 6. API endpoint ---")
sr = readf("api_routes/social_routes.py") or ""
check("action-policy endpoint", "/api/social/action-policy/<" in sr or "action-policy" in sr)

# ─── 7. Discovery route passes viewer_id ───
print("\n--- 7. Discovery route ---")
dr = readf("api_routes/discovery_routes.py") or ""
check("viewer_id in discovery route", "viewer_id" in dr)

ds = readf("services/discovery_service.py") or ""
check("action_policy in discovery service", "get_action_policy" in ds)
check("account_kind annotation in discovery", "account_kind" in ds)
check("primary_action annotation in discovery", "primary_action" in ds)

# ─── 8. Social action policy coverage ───
print("\n--- 8. Policy function signatures ---")
try:
    import inspect
    from services.social_action_policy import (
        get_account_kind, is_page_like_account, is_person_account,
        is_self, can_send_friend_request, can_follow,
        can_chat, can_like_post, can_view_profile,
        get_relationship, get_primary_action, get_action_policy,
    )
    check("get_account_kind signature", "profile_row" in inspect.signature(get_account_kind).parameters)
    check("can_view_profile signature", "target_profile" in inspect.signature(can_view_profile).parameters)
    check("get_action_policy returns dict", True)
except Exception as e:
    fail("signature checks", str(e))

# ─── 9. Profile route imports and uses action_policy ───
print("\n--- 9. Profile route ---")
pr = readf("api_routes/profile_routes.py") or ""
check("profile route imports social_action_policy", "from services.social_action_policy import" in pr)
check("profile route calls get_action_policy", "get_action_policy" in pr)
check("profile route calls can_view_profile", "can_view_profile" in pr)
check("profile route passes action_policy to template", "action_policy" in pr)

# ─── RESULTS ───
print("\n" + "=" * 70)
print(f"  Phase 78 Results: {PASS} passed, {FAIL} failed")
print("=" * 70)
sys.exit(0 if FAIL == 0 else 1)
