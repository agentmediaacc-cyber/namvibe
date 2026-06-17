"""Phase 79 — Self-action protection audit tests."""

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

print("Phase 79: Self-Action Guards")

# ── Like own post ───────────────────────────────────────────────────
with open("services/engagement_service.py") as f:
    es = f.read()
check("toggle_like blocks self-like", "cannot_like_own_content" in es)

# ── Like own comment ────────────────────────────────────────────────
with open("services/comments_service.py") as f:
    cs = f.read()
check("react_to_comment blocks self-like", "cannot_like_own_comment" in cs)
check("react_to_comment fetches comment author", "SELECT user_id FROM chain_comments" in cs)

# ── Follow self ─────────────────────────────────────────────────────
with open("services/engagement_service.py") as f:
    es2 = f.read()
check("follow_profile blocks self", "You cannot follow yourself" in es2 or "cannot_follow_self" in es2)

# ── Friend self ─────────────────────────────────────────────────────
with open("services/friend_service.py") as f:
    fserv = f.read()
check("send_friend_request blocks self", "cannot send a friend request to yourself" in fserv.lower() or "cannot_friend_self" in fserv.lower())

# ── Message self ────────────────────────────────────────────────────
with open("services/relationship_gate_service.py") as f:
    rgs = f.read()
check("can_message blocks self", "Cannot message yourself" in rgs or "cannot_message_self" in rgs)

# ── Call self ───────────────────────────────────────────────────────
with open("services/relationship_gate_service.py") as f:
    rgs2 = f.read()
check("can_call blocks self", "Cannot call yourself" in rgs2 or "cannot_call_self" in rgs2)

# ── Wallet self-actions ─────────────────────────────────────────────
with open("services/wallet_payment_service.py") as f:
    wps = f.read()
check("transfer blocks self", "Cannot transfer to yourself" in wps or "self_transfer" in wps)
check("gift blocks self", "Cannot gift yourself" in wps or "cannot_gift_self" in wps)
check("tip blocks self", "Cannot tip yourself" in wps or "cannot_tip_self" in wps)
check("subscribe blocks self", "Cannot subscribe to yourself" in wps or "cannot_subscribe_self" in wps)

# ── Social action policy guards ─────────────────────────────────────
with open("services/social_action_policy.py") as f:
    sap = f.read()
check("can_like_post blocks self", "is_self(current_profile_id, owner_id)" in sap)
check("can_follow blocks self", "is_self(current_profile_id, target_id)" in sap)
check("can_send_friend_request blocks self", "is_self(current_profile_id, target_id)" in sap)
check("can_chat blocks self", "is_self(current_profile_id, target_profile_id)" in sap)

# ── PRIVACY integration: can_view_profile delegates to rp ───────────
check("can_view_profile uses rp_can_view_profile", "rp_can_view_profile" in sap)

# ── get_action_policy uses get_full_policy ──────────────────────────
check("get_action_policy uses get_full_policy", "get_full_policy" in sap)

print(f"\nPhase 79 Self-Action Guards: {PASS} passed, {FAIL} failed")
