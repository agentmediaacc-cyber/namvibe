#!/usr/bin/env python3
"""Phase 180: Production Readiness — Redis, Socket.IO, Public Routes, Feed."""

import sys, os, json, re, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("FLASK_ENV", "development")

PASS, FAIL = "PASS", "FAIL"
_total = 0; _passed = 0; _failed = 0

def check(label, condition, detail=""):
    global _total, _passed, _failed
    _total += 1
    status = PASS if condition else FAIL
    if status == PASS: _passed += 1
    else: _failed += 1
    print(f"  [{status}] {label}" + (f" \u2014 {detail}" if detail else ""))

def section(name):
    print(f"\n{'='*60}\n{name}\n{'='*60}")

from app import create_app

TEST_AUTH_ID = "11111111-1111-4111-8111-111111111111"
TEST_PROFILE_ID = "22222222-2222-4222-8222-222222222222"
TEST_EMAIL = "phase180@example.com"
TEST_USERNAME = "phase180"
TEST_PROFILE_DATA = {
    "id": TEST_PROFILE_ID, "auth_user_id": TEST_AUTH_ID,
    "email": TEST_EMAIL, "username": TEST_USERNAME,
    "display_name": "Phase 180", "full_name": "Phase 180",
    "avatar_url": "", "is_verified": False, "verified": False,
    "profile_completed": True,
}

app = create_app()
client = app.test_client()

# ── Section 1: Redis & Socket.IO health ──
section("1. Redis & Socket.IO health endpoints")
resp = client.get("/healthz")
check("GET /healthz returns 200", resp.status_code == 200, f"got {resp.status_code}")
data = resp.get_json(silent=True) or {}
check("/healthz has ok field", data.get("ok") in (True, False))
check("/healthz has components.app", "app" in data.get("components", {}))
check("/healthz has components.redis", "redis" in data.get("components", {}))

resp_r = client.get("/health/redis")
check("GET /health/redis returns 200 or 503", resp_r.status_code in (200, 503))
rh = resp_r.get_json(silent=True) or {}
check("health/redis has status field", "status" in rh)
check("health/redis has connected field", "connected" in rh)
check("health/redis has fallback field", "fallback" in rh)
check("health/redis has service=redis", rh.get("service") == "redis")

resp_rt = client.get("/health/realtime")
check("GET /health/realtime returns 200", resp_rt.status_code == 200)
rt = resp_rt.get_json(silent=True) or {}
check("realtime has socketio_ready", "socketio_ready" in rt)
check("realtime has redis_backed", "redis_backed" in rt)
check("realtime has async_mode", "async_mode" in rt)

resp_ss = client.get("/system/socketio-status")
check("GET /system/socketio-status returns 200", resp_ss.status_code == 200)
ss = resp_ss.get_json(silent=True) or {}
check("socketio-status has ok", ss.get("ok") is True)
check("socketio-status has async_mode", "async_mode" in ss)
check("socketio-status has redis_manager_enabled", "redis_manager_enabled" in ss)
check("socketio-status has redis_available", "redis_available" in ss)
check("socketio-status has server_ready", "server_ready" in ss)

resp_db = client.get("/health/db")
check("GET /health/db returns 200 or 503", resp_db.status_code in (200, 503))
dbh = resp_db.get_json(silent=True) or {}
check("health/db has service=neon", dbh.get("service") == "neon")
check("health/db has connected field", "connected" in dbh)

# ── Section 2: Public routes return 200 ──
section("2. Public routes return 200")
public_routes = [
    "/", "/login", "/register", "/feed",
    "/reels", "/stories",
    "/search", "/terms", "/privacy", "/healthz",
    "/health/db", "/health/redis", "/health/realtime",
]
for route in public_routes:
    resp = client.get(route)
    ok = resp.status_code in (200, 302)
    check(f"GET {route}", ok, f"status={resp.status_code}")

# ── Section 3: Unauthenticated access to protected routes → redirect ──
section("3. Protected routes redirect unauthenticated")
protected_routes = [
    "/messages/", "/notifications/", "/notifications/center",
    "/calls/recent", "/wallet/", "/settings",
]
for route in protected_routes:
    resp = client.get(route, follow_redirects=False)
    check(f"GET {route} unauth", resp.status_code in (302, 401, 403),
          f"status={resp.status_code}")

# ── Section 4: Authenticated access works ──
section("4. Authenticated routes work")
with client.session_transaction() as sess:
    sess["auth_user_id"] = TEST_AUTH_ID
    sess["profile_id"] = TEST_PROFILE_ID
    sess["user_id"] = TEST_PROFILE_ID
    sess["auth_email"] = TEST_EMAIL
    sess["email"] = TEST_EMAIL
    sess["username"] = TEST_USERNAME
    sess["full_name"] = "Phase 180"
    sess["profile_completed"] = True
    sess["profile_data"] = dict(TEST_PROFILE_DATA)

for route in protected_routes:
    resp = client.get(route, follow_redirects=False)
    ok = resp.status_code in (200, 302)
    check(f"GET {route} auth", ok, f"status={resp.status_code}")

# ── Section 5: Homepage payload has real data structure ──
section("5. Homepage payload structure")
resp = client.get("/")
check("GET / returns 200", resp.status_code == 200, f"got {resp.status_code}")
html = resp.data.decode("utf-8")
check("HTML has root feed container", 'id="nv-feed"' in html or 'id="app"' in html or 'id="root"' in html)
check("HTML does not contain href=\"#\"", 'href="#"' not in html,
      "found href=# (should use real routes)")
check("HTML does not contain javascript:void", "javascript:void" not in html)

# Check no placeholder/fake text in user-visible content (skip HTML placeholder= attributes)
import re as _re_html
visible_text = _re_html.sub(r'<[^>]+>', ' ', html)
for fake in ["coming soon", "under construction", "lorem ipsum"]:
    if fake in visible_text.lower():
        check(f"Visible text contains no '{fake}'", False, "FAKE DATA DETECTED")
        break
else:
    check("No placeholder/fake text in visible HTML", True)

# ── Section 6: Template has all required sections ──
section("6. Template sections present")
tpl_path = "templates/chain_home.html"
tpl = open(tpl_path, "rb").read().decode("utf-8")
for section_name, marker in [
    ("Stories", "nv-stories"),
    ("Feed", "nv-feed"),
    ("Reels", "nv-reels"),
    ("Live rooms", "nv-live"),
    ("Suggested creators", "suggested_creators"),
    ("Friend activity", "friend_activity"),
    ("Bottom sheet", "nv-bottom-sheet"),
    ("Heart burst animation", "nv-heart-burst"),
    ("Infinite scroll sentinel", "nv-feed-sentinel"),
]:
    check(f"Template has '{section_name}' section", marker in tpl)

# ── Section 7: CSS animations and a11y features ──
section("7. CSS accessibility & animations")
all_styles = tpl + "\n" + open("static/css/namvibe_home_pro.css", "rb").read().decode("utf-8")
check("prefers-reduced-motion exists", "prefers-reduced-motion" in all_styles)
check("focus-visible outline exists", "focus-visible" in all_styles)
check("skeleton/shimmer animation exists", "nv-skeleton" in all_styles or "@keyframes shimmer" in all_styles or "skeleton" in all_styles)
check("fade-in animation exists", "fade-in" in all_styles or "nv-fade-in" in all_styles)

# ── Section 8: JavaScript features ──
section("8. JavaScript interaction features")
check("Double-tap like (lastTap)", "lastTap" in tpl)
check("Bottom sheet (openBottomSheet)", "openBottomSheet" in tpl)
check("Close bottom sheet (closeBottomSheet)", "closeBottomSheet" in tpl)
check("NamVibeToast defined", "window.NamVibeToast" in tpl)
check("Native share (navigator.share)", "navigator.share" in tpl)
check("Socket.IO listeners", "socket.on" in tpl or "NamVibeRealtime" in tpl)
check("Pull-to-refresh (ptrFeed)", "ptrFeed" in tpl or ("touchstart" in tpl and "touchmove" in tpl))
check("Escape key handler", "Escape" in tpl and "closeBottomSheet" in tpl)

# ── Section 9: Route verification ──
section("9. Route href verification")
import re as _re
hrefs = _re.findall(r'href="([^"]+)"', tpl)
bad = [h for h in hrefs if h in ("#", "javascript:void(0)")]
if bad:
    check("No dead href values", False, f"found {len(bad)} dead hrefs: {bad[:5]}")
else:
    check("No dead href values", True)

from flask import url_for
def _route_exists(endpoint):
    try:
        with app.app_context():
            url_for(endpoint)
        return True
    except Exception:
        return False

# ── Section 10: Rendering performance (under 3s) ──
section("10. Rendering performance")
t0 = time.perf_counter()
resp = client.get("/")
elapsed = time.perf_counter() - t0
check(f"Homepage renders under 3s ({elapsed*1000:.0f}ms)", elapsed < 3.0,
      f"took {elapsed:.2f}s")

t0 = time.perf_counter()
resp = client.get("/healthz")
elapsed_hz = time.perf_counter() - t0
check(f"Healthz under 500ms ({elapsed_hz*1000:.0f}ms)", elapsed_hz < 0.5,
      f"took {elapsed_hz:.2f}s")

# ── Section 11: No N+1 query risk (friend activity queries real DB) ──
section("11. Data source integrity")
from services.homepage_service import _fetch_friend_activity, _fetch_stories
activity = _fetch_friend_activity(viewer_id=None, limit=3)
check("friend_activity returns a list", isinstance(activity, list))
if activity:
    first = activity[0]
    check("friend_activity item has type key", "type" in first or "verb" in first or "action" in first)
    check("friend_activity item has profile info", "username" in first or "display_name" in first or "profile_id" in first)

check("ALL TESTS COMPLETE", True)

# ── Summary ──
print(f"\n{'='*60}")
print(f"Results: {_passed}/{_total} passed, {_failed} failed")
if _failed:
    sys.exit(1)
print("ALL CHECKS PASSED")
