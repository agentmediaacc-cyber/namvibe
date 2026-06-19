"""Phase 82: homepage performance safeguards are present."""
import os
import sys

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


def run():
    print("Phase 82: Homepage Performance Static")
    svc = open("services/homepage_service.py").read()
    indexer = open("scripts/phase82_homepage_indexes.py").read()

    check("homepage has tight query timeout", "_QUERY_TIMEOUT_MS" in svc and "1500" in svc)
    check("homepage section TTLs present", "_HOMEPAGE_SECTION_TTLS" in svc)
    check("homepage limits all main sections", "_HOMEPAGE_LIMITS" in svc)
    check("homepage catches section timeout fallback", "default=[]" in svc and "timeout_ms=100" in svc)
    check("homepage uses profile joins to avoid N+1", "LEFT JOIN chain_profiles" in svc)
    check("homepage records performance profile", "get_homepage_performance_profile" in svc)
    for token in [
        "idx_phase82_chain_stories_active_created",
        "idx_phase82_chain_reels_active_created",
        "idx_phase82_chain_posts_active_created",
        "idx_phase82_chain_profiles_active_created",
    ]:
        check(f"index helper has {token}", token in indexer)

    print(f"\nPhase 82 Homepage Performance: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
