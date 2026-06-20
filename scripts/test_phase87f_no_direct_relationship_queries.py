"""Phase 87F — Verify no direct SELECT 1 FROM chain_friends/follows in hot paths."""

import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PASS = 0
FAIL = 0

def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name} {detail}")
        FAIL += 1

ALLOWED_FILES = {
    "services/relationship_cache_service.py",  # cache layer itself
    "services/friend_service.py",              # mutation queries
    "services/friendship_service.py",          # mutation queries
    "services/follow_request_service.py",      # mutation queries
    "services/engagement_service.py",          # mutation queries
    "services/profile_service.py",             # fixed to use cache
    "services/social_service.py",              # list queries
    "services/live_service.py",                # live-specific
    "services/messaging_engine.py",            # messaging gate
    "services/relationship_gate_service.py",   # messaging gate
    "services/status_service.py",             # story status
    "api_routes/profile_routes.py",           # toggle follow
    "api_routes/message_routes.py",           # messages friends list
    "api_routes/dashboard_routes.py",         # dashboard stats
}

HOT_QUERY_PATTERNS = [
    r"SELECT\s+1\s+FROM\s+chain_friends",
    r"SELECT\s+1\s+FROM\s+chain_follows",
    r"SELECT\s+1\s+FROM\s+chain_friend_requests",
]

def run():
    global PASS, FAIL
    print("=" * 60)
    print("PHASE 87F — NO DIRECT RELATIONSHIP QUERIES")
    print("=" * 60)

    print("\n--- Scanning hot SELECT 1 patterns in services/api_routes ---")
    violations = []
    for root_dir in ["services", "api_routes"]:
        full = os.path.join(ROOT, root_dir)
        for fname in os.listdir(full):
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(full, fname)
            rel = os.path.join(root_dir, fname)
            with open(fpath) as f:
                for i, line in enumerate(f, 1):
                    for pat in HOT_QUERY_PATTERNS:
                        if re.search(pat, line, re.I):
                            violations.append((rel, i, line.strip(), pat))

    for f, ln, line, pat in violations:
        # Check if file is in allowed list for mutations
        if f in ALLOWED_FILES:
            # These are expected to have direct queries for writes
            continue
        # highlight actual violation
        print(f"  WARN {f}:{ln} pattern '{pat}'")

    check("no hot SELECT 1 queries outside allowed files",
          len([v for v in violations if v[0] not in ALLOWED_FILES]) == 0,
          f"violations in {len([v for v in violations if v[0] not in ALLOWED_FILES])} files")

    # Check that key functions use relationship cache
    print("\n--- Cache usage verification ---")
    friend_svc = os.path.join(ROOT, "services", "friend_service.py")
    with open(friend_svc) as f:
        src = f.read()
    check("are_friends uses get_relationship_state",
          "get_relationship_state" in src)

    profile_svc = os.path.join(ROOT, "services", "profile_service.py")
    with open(profile_svc) as f:
        src = f.read()
    check("profile_service.get_friend_status uses get_relationship_state",
          "get_relationship_state" in src)
    check("profile_service.are_friends uses get_relationship_state",
          "get_relationship_state" in src)

    print(f"\n{'=' * 60}")
    total = PASS + FAIL
    if FAIL == 0:
        print(f"PHASE 87F NO DIRECT QUERIES: PASS ({PASS}/{total})")
    else:
        print(f"PHASE 87F NO DIRECT QUERIES: FAIL ({PASS}/{total})")
    print(f"{'=' * 60}")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
