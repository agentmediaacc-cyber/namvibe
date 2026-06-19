"""Static audit: verify discovery/home/profile/suggestions use batch relationship lookup."""

import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0

def check(name, condition):
    global PASS, FAIL
    if condition:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name}")
        FAIL += 1

print("Phase 86: No Relationship Loop Static")

# Check discovery_service imports get_many_relationship_states
with open("services/discovery_service.py") as f:
    ds = f.read()
check("discovery_service imports get_many_relationship_states", "get_many_relationship_states" in ds)

# Check smart_suggestion_service imports get_many_relationship_states
with open("services/smart_suggestion_service.py") as f:
    ss = f.read()
check("smart_suggestion_service imports get_many_relationship_states", "get_many_relationship_states" in ss)

# Check social_action_policy imports get_relationship_state (not direct friends/follows query)
with open("services/social_action_policy.py") as f:
    sap = f.read()
check("social_action_policy imports get_relationship_state", "get_relationship_state" in sap)
check("social_action_policy no direct chain_friends SELECT 1", "SELECT 1 FROM chain_friends" not in sap)
check("social_action_policy no direct chain_follows SELECT 1", "SELECT 1 FROM chain_follows" not in sap)
check("social_action_policy no direct chain_friend_requests SELECT 1", "SELECT 1 FROM chain_friend_requests" not in sap)
check("social_action_policy no direct chain_follow_requests SELECT 1", "SELECT 1 FROM chain_follow_requests" not in sap)

# Check relationship_privacy_service imports get_relationship_state
with open("services/relationship_privacy_service.py") as f:
    rps = f.read()
check("relationship_privacy_service imports get_relationship_state", "get_relationship_state" in rps)
check("relationship_privacy_service no direct are_friends import", "from services.friend_service import are_friends" not in rps)

# Check friendship_service imports get_relationship_state
with open("services/friendship_service.py") as f:
    fs = f.read()
check("friendship_service imports get_relationship_state", "get_relationship_state" in fs)
check("friendship_service no direct chain_friend_requests SELECT id", "SELECT id, status FROM chain_friend_requests" not in fs)

# Check follow_request_service imports get_relationship_state
with open("services/follow_request_service.py") as f:
    frs = f.read()
check("follow_request_service imports get_relationship_state", "get_relationship_state" in frs)

# Check neon_service includes log_rate_limit
with open("services/neon_service.py") as f:
    ns = f.read()
check("neon_service imports log_rate_limit", "from services.log_rate_limit_service import" in ns)

print(f"\nPhase 86 No Relationship Loop: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
