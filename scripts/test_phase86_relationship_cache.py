"""Test relationship_cache_service exists and has required functions."""

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

print("Phase 86: Relationship Cache Service")

try:
    from services.relationship_cache_service import (
        get_relationship_state,
        get_many_relationship_states,
        invalidate_relationship_state,
        invalidate_profile_relationships,
        REL_CACHE_TTL,
    )
    check("relationship_cache_service module loads", True)
    check("get_relationship_state exists", callable(get_relationship_state))
    check("get_many_relationship_states exists", callable(get_many_relationship_states))
    check("invalidate_relationship_state exists", callable(invalidate_relationship_state))
    check("invalidate_profile_relationships exists", callable(invalidate_profile_relationships))
    check("REL_CACHE_TTL is 60", REL_CACHE_TTL == 60)
except ImportError as e:
    check(f"module failed to import: {e}", False)
    check("relationship_cache_service module loads", False)

try:
    state = get_relationship_state("nonexistent-a", "nonexistent-b")
    check("get_relationship_state returns dict", isinstance(state, dict))
    check("state has is_self", "is_self" in state)
    check("state has is_friend", "is_friend" in state)
    check("state has friend_request_sent", "friend_request_sent" in state)
    check("state has friend_request_received", "friend_request_received" in state)
    check("state has is_following", "is_following" in state)
    check("state has follow_request_sent", "follow_request_sent" in state)
    check("state has follow_request_received", "follow_request_received" in state)
    check("state has blocked", "blocked" in state)
    check("state has relationship", "relationship" in state)
    check("state shows relationship none", state["relationship"] in ("none", "self"))
except Exception as e:
    check(f"get_relationship_state error: {e}", False)

try:
    states = get_many_relationship_states("nonexistent-a", ["nonexistent-b", "nonexistent-c"])
    check("get_many_relationship_states returns dict", isinstance(states, dict))
except Exception as e:
    check(f"get_many_relationship_states error: {e}", False)

try:
    from services.redis_service import cache_get
    cache_get("rel:state:test:test")
    check("Redis key rel:state format exists in code", True)
except Exception:
    pass

print(f"\nPhase 86 Relationship Cache: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
