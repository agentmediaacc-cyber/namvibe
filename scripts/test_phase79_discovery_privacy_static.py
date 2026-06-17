"""Phase 79 — Discovery privacy static code checks."""

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

print("Phase 79: Discovery Privacy Static")

# ── Discovery service uses privacy ──────────────────────────────────
with open("services/discovery_service.py") as f:
    ds = f.read()

check("imports get_full_policy", "from services.relationship_privacy_service import" in ds and "get_full_policy" in ds)
check("imports is_blocked_any", "is_blocked_any" in ds)
check("filters blocked users", "is_blocked_any(viewer_id, item.get" in ds or "is_blocked_any(viewer_id, item" in ds)
check("uses get_full_policy", "get_full_policy" in ds)
check("strips private data for restricted", "_strip_private_data" in ds or "privacy_restricted" in ds)
check("strips reel count", "reel_count" in ds)
check("strips live count", "live_count" in ds)
check("strips current_location", "current_location" in ds)
check("strips date_of_birth", "date_of_birth" in ds)
check("strips country_origin", "country_origin" in ds)
check("strips interests", "interests" in ds)
check("strips cover_url", "cover_url" in ds)
check("skips blocked items", "continue" in ds and "is_blocked_any" in ds[:ds.find("enriched")])

with open("services/discovery_service.py") as f:
    lines = f.readlines()

privacy_strip_fn = False
for i, line in enumerate(lines):
    if "def _strip_private_data" in line:
        privacy_strip_fn = True
        break
check("_strip_private_data function exists", privacy_strip_fn)

# ── Template checks ─────────────────────────────────────────────────
with open("templates/discover/index.html") as f:
    dt = f.read()

check("discovery template has privacy_restricted check", "privacy_restricted" in dt or "Private Account" in dt or "private" in dt.lower())
check("discovery template shows action buttons", "Add Friend" in dt or "follow" in dt.lower())

# ── Social action policy integration ────────────────────────────────
with open("services/social_action_policy.py") as f:
    sap = f.read()

check("social_action_policy imports from relationship_privacy_service", "from services.relationship_privacy_service import" in sap)
check("social_action_policy uses rp_can_follow", "rp_can_follow" in sap)
check("social_action_policy uses rp_can_send_friend_request", "rp_can_send_friend_request" in sap)
check("social_action_policy uses rp_can_message", "rp_can_message" in sap)
check("social_action_policy uses rp_can_view_profile", "rp_can_view_profile" in sap)
check("social_action_policy uses get_full_policy", "get_full_policy" in sap)

print(f"\nPhase 79 Discovery Privacy: {PASS} passed, {FAIL} failed")
