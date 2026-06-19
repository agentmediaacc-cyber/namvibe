"""Phase 87 — Relationship Cache Final Test."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.relationship_cache_service import (
    get_relationship_state, get_many_relationship_states,
    invalidate_relationship_state, invalidate_profile_relationships,
    is_uuid, REL_CACHE_TTL,
)

PASS = 0
FAIL = 0

def check(name, ok):
    global PASS, FAIL
    if ok:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name}")
        FAIL += 1

def run():
    global PASS, FAIL
    print("Phase 87: Relationship Cache Final")

    check("REL_CACHE_TTL is 60", REL_CACHE_TTL == 60)
    check("is_uuid True for valid", is_uuid("550e8400-e29b-41d4-a716-446655440000"))
    check("is_uuid False for invalid", not is_uuid("not-a-uuid"))
    check("is_uuid False for empty", not is_uuid(""))
    check("is_uuid False for None", not is_uuid(None))

    # get_relationship_state with None
    state = get_relationship_state(None, None)
    check("None returns empty state", isinstance(state, dict))
    check("None state is_self false", state.get("is_self") is False)

    # get_relationship_state with invalid UUID
    state = get_relationship_state("bad-uuid", "also-bad")
    check("bad UUID returns empty state", isinstance(state, dict))
    check("bad UUID state is_following false", state.get("is_following") is False)

    # get_many_relationship_states with invalid
    states = get_many_relationship_states("bad", ["bad2", "bad3"])
    check("batch bad UUID returns dict", isinstance(states, dict))

    # get_many_relationship_states with None viewer
    states = get_many_relationship_states(None, ["some-id"])
    check("batch None viewer returns empty", states == {})

    # Functions exist
    check("invalidate_relationship_state exists", callable(invalidate_relationship_state))
    check("invalidate_profile_relationships exists", callable(invalidate_profile_relationships))

    print(f"\nPhase 87 Relationship Cache Final: {PASS} passed, {FAIL} failed")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
