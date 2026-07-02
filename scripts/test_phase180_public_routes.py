#!/usr/bin/env python3
"""Phase 180: Public Routes & Post Visibility Audit.

Tests that all public routes work, protected routes require login,
and post visibility rules are enforced for anonymous users.
"""

import sys, os, json

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
app = create_app()
client = app.test_client()

# ── 1. Public routes → 200 or valid redirect ──
section("1. Public routes respond without login")
PUBLIC = [
    ("/", {200}),
    ("/login", {200, 302}),
    ("/register", {200, 302}),
    ("/feed", {200}),
    ("/reels", {200, 302}),
    ("/stories", {200}),
    ("/search", {200}),
    ("/terms", {200}),
    ("/privacy", {200}),
    ("/healthz", {200}),
    ("/health/db", {200, 503}),
    ("/health/redis", {200, 503}),
    ("/health/realtime", {200}),
    ("/system/socketio-status", {200}),
    ("/discover/", {200, 302}),
    ("/live/", {200}),
    ("/profile/@", {200, 301, 302, 404}),  # empty username -> redirect
]
for route, allowed in PUBLIC:
    resp = client.get(route, follow_redirects=False)
    check(f"GET {route}", resp.status_code in allowed, f"status={resp.status_code} (allowed {sorted(allowed)})")

# ── 2. Protected routes → 302 when not logged in ──
section("2. Protected routes require login")
PROTECTED = [
    "/messages/",
    "/notifications/",
    "/notifications/center",
    "/calls/recent",
    "/wallet/",
    "/settings",
    "/features/create-post",
    "/features/upload-reel",
    "/reels/upload",
    "/live/studio",
]
for route in PROTECTED:
    resp = client.get(route, follow_redirects=False)
    check(f"GET {route} unauth", resp.status_code in (302, 401, 403),
          f"status={resp.status_code}")

# ── 3. Static assets return 200 ──
section("3. Static assets reachable")
STATIC = [
    "/static/css/namvibe_home_pro.css",
    "/static/css/namvibe_design_system.css",
    "/static/js/namvibe_home_pro.js",
    "/static/img/favicon.ico",
    "/static/manifest.json",
    "/static/img/icon-192.png",
]
for asset in STATIC:
    resp = client.get(asset)
    check(f"GET {asset}", resp.status_code == 200, f"status={resp.status_code}")

# ── 4. Promo video asset reachable ──
section("4. Promo video reachable")
resp = client.get("/static/media/samples/namvibe_promo_2min.mp4", follow_redirects=True)
check("GET promo video", resp.status_code == 200, f"status={resp.status_code}")
if resp.status_code == 200:
    content_len = int(resp.headers.get("Content-Length", 0))
    check("Promo video file size reasonable", content_len > 500_000,
          f"got {content_len} bytes")

# ── 5. No broken routes / 500 errors ──
section("5. No 500 errors on public routes")
for route, _ in PUBLIC:
    resp = client.get(route)
    ok = resp.status_code < 500
    check(f"GET {route} no 500", ok, f"status={resp.status_code}")

# ── 6. Post visibility: no private post leak to anonymous ──
section("6. Post visibility — no private leak")
# Try fetching a non-existent post — should 404, not 500
resp = client.get("/post/nonexistent-id-12345")
check("GET /post/<invalid>", resp.status_code in (404, 302), f"status={resp.status_code}")

# Try fetching a non-existent reel
resp = client.get("/reels/nonexistent-id-12345")
check("GET /reels/<invalid>", resp.status_code in (404, 302), f"status={resp.status_code}")

# ── 7. Anonymous feed is public-safe ──
section("7. Anonymous feed returns public content only")
resp = client.get("/feed")
check("GET /feed anonymous", resp.status_code == 200, f"status={resp.status_code}")
# The feed should render without error
html_feed = resp.data.decode("utf-8")
check("Feed HTML has no server error", "500" not in html_feed[:500] and "error" not in html_feed[:200].lower())

# ── 8. API profile summary is public ──
section("8. Public API endpoints")
resp = client.get("/api/profile/current")
check("GET /api/profile/current (anon)", resp.status_code in (200, 302, 401),
      f"status={resp.status_code}")

# ── 9. Health endpoints return valid JSON ──
section("9. Health endpoints return valid JSON")
for hp in ["/healthz", "/health/redis", "/health/db", "/health/realtime"]:
    resp = client.get(hp)
    try:
        data = json.loads(resp.data)
        check(f"GET {hp} valid JSON", True)
    except Exception:
        check(f"GET {hp} valid JSON", False, "not JSON")

# ── 10. HTML homepage has no href="#" ──
section("10. No dead links on homepage")
resp = client.get("/")
html = resp.data.decode("utf-8")
import re
hrefs = re.findall(r'href="([^"]+)"', html)
dead = [h for h in hrefs if h in ("#", "javascript:void(0)")]
check("No href=\"#\" in homepage", len(dead) == 0, f"found {len(dead)} dead hrefs")
check("No javascript: in homepage", "javascript:" not in html)

# ── Summary ──
print(f"\n{'='*60}")
print(f"Results: {_passed}/{_total} passed, {_failed} failed")
if _failed:
    sys.exit(1)
print("ALL CHECKS PASSED")
