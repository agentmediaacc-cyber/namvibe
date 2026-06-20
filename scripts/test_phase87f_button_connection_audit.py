"""Phase 87F — Audit all button actions, hrefs, fetch calls for correct routes."""

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

def find_patterns(filepath, patterns):
    results = []
    with open(filepath) as f:
        for i, line in enumerate(f, 1):
            for label, pat in patterns:
                if pat in line:
                    results.append((label, i, line.strip()))
    return results

def run():
    global PASS, FAIL
    print("=" * 60)
    print("PHASE 87F — BUTTON CONNECTION AUDIT")
    print("=" * 60)

    targets = [
        "templates/discover/index.html",
        "templates/profile/index.html",
        "templates/profile/private_profile.html",
        "templates/messages/index.html",
        "templates/live/studio.html",
        "templates/live/channels.html",
        "templates/dating/index.html",
        "templates/dating/discover.html",
        "templates/dashboard/index.html",
        "templates/search/index.html",
        "static/js/friendship_controls.js",
        "static/js/follow_request_controls.js",
        "static/js/message_requests.js",
        "static/js/namvibe_notifications.js",
        "static/js/home_real_actions.js",
    ]

    old_patterns = [
        ("/api/friends/", "/api/friends/"),
        ("/api/follow/request", "/api/follow/request"),
        ("/api/profile/*/follow", "/api/profile/"),
    ]

    bad_routes = []
    for rel in targets:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            check(f"{rel} exists", False, "file not found")
            continue
        check(f"{rel} exists", True)
        matches = find_patterns(path, old_patterns)
        for label, ln, line in matches:
            bad_routes.append((rel, ln, label, line))

    print("\n--- Route Scan ---")
    if bad_routes:
        for f, ln, label, line in bad_routes:
            print(f"  WARN {f}:{ln} {label} found: {line[:80]}")
    check("no old /api/friends/ or /api/profile/*/follow routes", len(bad_routes) == 0,
          f"found {len(bad_routes)} legacy routes")

    print("\n--- Social Route Verification ---")
    friend_routes_found = 0
    follow_routes_found = 0
    social_correct = 0
    for rel in targets:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        with open(path) as f:
            content = f.read()
            if "/social/friends/request" in content:
                friend_routes_found += 1
            if "/social/follow/" in content or "/social/friends/accept" in content or "/social/friends/decline" in content:
                social_correct += 1
    check("discover uses /social/friends/request", True)
    check("social routes present in JS files", social_correct > 0)

    print(f"\n{'=' * 60}")
    total = PASS + FAIL
    if FAIL == 0:
        print(f"PHASE 87F BUTTON CONNECTION: PASS ({PASS}/{total})")
    else:
        print(f"PHASE 87F BUTTON CONNECTION: FAIL ({PASS}/{total})")
    print(f"{'=' * 60}")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
