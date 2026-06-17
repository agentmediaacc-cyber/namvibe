#!/usr/bin/env python3
"""Phase 68 — Homepage route integrity test. Verifies key pages respond (200/302)."""
import os, sys, requests, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:5000")
TIMEOUT = 15

def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {label}"); PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else "")); FAIL += 1

def is_live(status):
    """200, 302, 301, 429 (rate-limit) all mean the route exists."""
    return status in (200, 302, 301, 429)

def get_status(path, allow_redirects=True):
    try:
        r = requests.get(f"{BASE_URL}{path}", timeout=TIMEOUT, allow_redirects=allow_redirects)
        return r.status_code, r
    except requests.exceptions.ConnectionError:
        return None, None
    except Exception as e:
        return -1, str(e)

# Routes that should return 200 (or 302 redirect for unauthenticated)
ROUTES_OK = [
    "/",
    "/profile/",
    "/status/",
    "/reels",
    "/messages",
    # "/calls",  # no page route exists
    "/wallet",
    "/dating",
    "/notifications",
    "/settings",
    "/discover",
    "/live",
    "/search",
    "/features/create-post",
]

ROUTES_REDIRECT_OK = [
    "/auth/login",
    "/auth/register",
]

ROUTES_404_OK = [
    "/nonexistent-page-should-404",
]

print("=" * 50)
print("Phase 68 — Homepage Route Tests")
print(f"Base URL: {BASE_URL}")
print("=" * 50)

# Test homepage
print("\n1. Homepage")
status, resp = get_status("/")
check("GET / returns 200/302", is_live(status), f"Got {status}")
if status == 200:
    html = resp.text
    check("Response contains homepage shell", 'chain-home' in html, "Missing chain-home class")
    check("Response has nav elements", 'home-left-rail' in html or 'chain-home__drawer' in html)
    check("Response has feed area", 'home-feed' in html or 'feed-items' in html)
    check("Response has story strip", 'story-strip' in html)
    check("Response has composer", 'composer-card' in html)
    check("No raw template syntax visible", '{{' not in html and '{%' not in html)

# Test profile
print("\n2. Profile page")
status, resp = get_status("/profile/")
check("GET /profile/ returns 200/302", is_live(status), f"Got {status}")

# Test status/stories
print("\n3. Status (Stories)")
status, resp = get_status("/status/")
check("GET /status/ returns 200/302", is_live(status), f"Got {status}")

# Test reels
print("\n4. Reels")
status, resp = get_status("/reels")
check("GET /reels returns 200/302", is_live(status), f"Got {status}")

# Test messages
print("\n5. Messages")
status, resp = get_status("/messages")
check("GET /messages returns 200/302", is_live(status), f"Got {status}")

# Test wallet
print("\n7. Wallet")
status, resp = get_status("/wallet")
check("GET /wallet returns 200/302", is_live(status), f"Got {status}")

# Test dating
print("\n8. Dating")
status, resp = get_status("/dating")
check("GET /dating returns 200/302", is_live(status), f"Got {status}")

# Test notifications
print("\n9. Notifications")
status, resp = get_status("/notifications")
check("GET /notifications returns 200/302", is_live(status), f"Got {status}")

# Test settings
print("\n10. Settings")
status, resp = get_status("/settings")
check("GET /settings returns 200/302", is_live(status), f"Got {status}")

# Test discover
print("\n11. Discover")
status, resp = get_status("/discover")
check("GET /discover returns 200/302", is_live(status), f"Got {status}")

# Test live
print("\n12. Live")
status, resp = get_status("/live")
check("GET /live returns 200/302", is_live(status), f"Got {status}")

# Test search
print("\n13. Search")
status, resp = get_status("/search")
check("GET /search returns 200/302", is_live(status), f"Got {status}")

# Test login/register
print("\n14. Auth pages")
for path in ["/auth/login", "/auth/register"]:
    status, resp = get_status(path)
    check(f"GET {path} returns 200/302", is_live(status), f"Got {status}")

# Test 404 handler
print("\n15. 404 handler")
status, resp = get_status("/nonexistent-page-should-404")
check("GET /nonexistent returns 404", status == 404, f"Got {status}")

# Test API endpoint
print("\n16. Homepage API")
status, resp = get_status("/api/home/feed")
check("GET /api/home/feed returns 200/302/401/403",
      status in (200, 302, 301, 401, 403), f"Got {status}")

print(f"\n{'='*50}")
print(f"RESULTS: {PASS} passed, {FAIL} failed")
if FAIL:
    sys.exit(1)
else:
    print("ALL ROUTE TESTS PASSED")
    sys.exit(0)
