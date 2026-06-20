"""Phase 87F — Verify social route compatibility: old /api/friends/* vs /social/*."""

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

def run():
    global PASS, FAIL
    print("=" * 60)
    print("PHASE 87F — SOCIAL ROUTE COMPATIBILITY")
    print("=" * 60)

    # Check routes exist in api_routes
    print("\n--- Backend Routes ---")
    routes_dir = os.path.join(ROOT, "api_routes")
    
    # Social routes (/social/*)
    social_file = os.path.join(routes_dir, "social_routes.py")
    with open(social_file) as f:
        social_src = f.read()
    
    friend_file = os.path.join(routes_dir, "friend_routes.py")
    with open(friend_file) as f:
        friend_src = f.read()

    follow_file = os.path.join(routes_dir, "follow_request_routes.py")
    with open(follow_file) as f:
        follow_src = f.read()

    check("/social/friends/request exists", '/friends/request' in social_src)
    check("/social/friends/accept exists", '/friends/accept' in social_src)
    check("/social/friends/decline exists", '/friends/decline' in social_src)
    check("/social/friends/cancel exists", '/friends/cancel' in social_src)
    check("/social/follow/<profile_id> exists", '/follow/<profile_id>' in social_src)
    check("/social/api/status/<target_id> exists", '/api/status/<target_id>' in social_src)
    
    # Legacy routes still exist
    check("legacy /api/friends/request/<profile_id> exists", '/friends/request/<profile_id>' in friend_src)
    check("legacy /api/friends/accept/<request_id> exists", '/friends/accept/<request_id>' in friend_src)
    check("legacy /api/friends/decline/<request_id> exists", '/friends/decline/<request_id>' in friend_src)
    check("legacy /api/follow/approve/<request_id> exists", '/approve/<request_id>' in follow_src)
    check("legacy /api/follow/decline/<request_id> exists", '/decline/<request_id>' in follow_src)
    check("legacy /api/follow/request/<profile_id> exists", '/request/<profile_id>' in follow_src)

    # Frontend JS checks
    print("\n--- Frontend Routes ---")
    js_dir = os.path.join(ROOT, "static", "js")
    
    friend_js = os.path.join(js_dir, "friendship_controls.js")
    with open(friend_js) as f:
        friend_js_src = f.read()
    check("friendship_controls uses /social/friends/request", '/social/friends/request' in friend_js_src)
    check("friendship_controls uses /social/friends/accept", '/social/friends/accept' in friend_js_src)
    check("friendship_controls uses /social/friends/decline", '/social/friends/decline' in friend_js_src)
    check("friendship_controls uses /social/api/status", '/social/api/status' in friend_js_src)
    check("friendship_controls NO /api/friends/ prefix", '/api/friends/' not in friend_js_src)

    follow_js = os.path.join(js_dir, "follow_request_controls.js")
    with open(follow_js) as f:
        follow_js_src = f.read()
    check("follow_request uses /social/follow/", '/social/follow/' in follow_js_src)

    home_actions_js = os.path.join(js_dir, "home_real_actions.js")
    with open(home_actions_js) as f:
        home_js_src = f.read()
    check("home_real_actions uses /social/follow/", '/social/follow/' in home_js_src)
    check("home_real_actions NO /api/profile/*/follow", '/api/profile/' not in home_js_src)

    message_requests_js = os.path.join(js_dir, "message_requests.js")
    with open(message_requests_js) as f:
        msg_src = f.read()
    check("message_requests uses /social/friends/accept", '/social/friends/accept' in msg_src)
    check("message_requests uses /social/friends/decline", '/social/friends/decline' in msg_src)

    # Template checks
    discover_html = os.path.join(ROOT, "templates", "discover", "index.html")
    with open(discover_html) as f:
        disc_src = f.read()
    check("discover uses /social/friends/request", '/social/friends/request' in disc_src)
    check("discover NO /api/friends/request", '/api/friends/request' not in disc_src)

    print(f"\n{'=' * 60}")
    total = PASS + FAIL
    if FAIL == 0:
        print(f"PHASE 87F SOCIAL ROUTE COMPAT: PASS ({PASS}/{total})")
    else:
        print(f"PHASE 87F SOCIAL ROUTE COMPAT: FAIL ({PASS}/{total})")
    print(f"{'=' * 60}")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
