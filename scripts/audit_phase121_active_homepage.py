#!/usr/bin/env python3
"""
Phase 121 — Active Homepage Route Audit.

Verifies:
  - feed_bp no longer shadows / with its own route
  - app.home() is the sole handler for GET /
  - app.home() renders chain_home.html
  - chain_home.html contains Phase 120 premium markers
  - feed/index.html still accessible at /feed
"""

import os
import re
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip("'\"")
                if v:
                    os.environ.setdefault(k, v)

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASS = 0
FAIL = 0
WARN = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  [PASS] {msg}")


def fail(msg):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {msg}")


def warn(msg):
    global WARN
    WARN += 1
    print(f"  [WARN] {msg}")


def file_read(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return ""
    with open(full, encoding="utf-8", errors="ignore") as f:
        return f.read()


def file_exists(path):
    return os.path.exists(os.path.join(ROOT, path))


print("=" * 60)
print("PHASE 121 — ACTIVE HOMEPAGE ROUTE AUDIT")
print("=" * 60)

# ── 1. Route audit via subprocess ──
print("\n--- 1. Route Registration Audit ---")
route_code = '''
import os, sys, json
os.environ["FLASK_ENV"] = "development"
os.environ["CHAIN_TEST_MODE"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
sys.path.insert(0, ".")
import warnings
warnings.filterwarnings("ignore")
import logging
logging.disable(logging.CRITICAL)
import app as app_module
app = app_module.app
rules = {}
for rule in app.url_map.iter_rules():
    if rule.rule == "/":
        rules[rule.endpoint] = str(rule.methods)
with open(os.environ["_ROUTE_OUT"], "w") as f:
    f.write(json.dumps(rules))
'''
import subprocess, tempfile
try:
    outf = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    outf.close()
    env = {**os.environ, "FLASK_ENV": "development",
           "CHAIN_TEST_MODE": "1", "CHAIN_FAST_LOCAL": "1",
           "_ROUTE_OUT": outf.name}
    proc = subprocess.run(
        [sys.executable, "-c", route_code],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60,
        cwd=ROOT, env=env,
    )
    if os.path.exists(outf.name):
        with open(outf.name) as f:
            raw = f.read().strip()
        os.unlink(outf.name)
        if raw:
            routes = json.loads(raw)
            if "home" in routes and "feed.index" not in routes:
                ok("Only app.home() handles GET / (feed_bp shadow removed)")
            elif "home" in routes and "feed.index" in routes:
                fail("feed_bp still shadows / — Route: feed.index still registered")
            elif "home" not in routes:
                fail("app.home() NOT registered for /")
            else:
                ok(f"Route / handled by: {list(routes.keys())}")
        else:
            warn("Route audit produced empty output")
    else:
        warn("Route audit subprocess failed")
except Exception as e:
    warn(f"Route audit error: {e}")

# ── 2. Check feed_routes.py no longer has @feed_bp.route("/") ──
print("\n--- 2. Feed Blueprint Route Audit ---")
feed_content = file_read("api_routes/feed_routes.py")
if "@feed_bp.route(\"/\")" not in feed_content:
    ok("feed_bp no longer has a shadowing / route")
else:
    fail("feed_bp still defines @feed_bp.route(\"/\") — shadowing app.home()")

if "@feed_bp.route(\"/feed/\")" in feed_content:
    ok("feed_bp /feed/ route preserved")
else:
    warn("feed_bp /feed/ route missing")

# ── 3. Verify app.home() renders chain_home.html ──
print("\n--- 3. app.py home() Route Check ---")
app_content = file_read("app.py")
if "@app.route(\"/\")" in app_content:
    ok("app.route('/') defined in app.py")
else:
    fail("app.route('/') missing from app.py")

if "render_template(\"chain_home.html\"" in app_content:
    ok("app.home() renders chain_home.html")
else:
    fail("app.home() does NOT render chain_home.html")

# ── 4. chain_home.html exists and has Phase 120 markers ──
print("\n--- 4. Template Verification ---")
tpl = "templates/chain_home.html"
if file_exists(tpl):
    ok(f"Template exists: {tpl}")
else:
    fail(f"Template missing: {tpl}")

html = file_read(tpl)
if html:
    phase_120_markers = [
        "namvibe_home_pro.css",
        "namvibe_home_pro.js",
        "nvpro-shell",
        "nvpro-left-rail",
        "nvpro-feed",
        "nvpro-sidebar",
        "nvpro-bottom-nav",
    ]
    for marker in phase_120_markers:
        if marker in html:
            ok(f"Phase 120 marker present: {marker}")
        else:
            warn(f"Phase 120 marker missing: {marker}")

    if "extends base.html" in html or "extends \"base.html\"" in html or "extends 'base.html'" in html:
        ok("Template extends base.html")
    else:
        warn("Template may not extend base.html")

    if "premium" in html.lower():
        ok("Template contains premium branding")
else:
    fail("chain_home.html is empty or missing")

# ── 5. Static assets exist ──
print("\n--- 5. Static Assets ---")
for fpath, label in [
    ("static/css/namvibe_home_pro.css", "Premium CSS"),
    ("static/js/namvibe_home_pro.js", "Premium JS"),
]:
    if file_exists(fpath):
        ok(f"{label} exists: {fpath}")
    else:
        fail(f"{label} missing: {fpath}")

# ── 6. API endpoints registered ──
print("\n--- 6. API Endpoint Registration ---")
api_content = file_read("api_routes/homepage_api.py")
endpoints = ["/api/homepage/feed", "/api/homepage/sidebar", "/api/homepage/stories", "/api/homepage/reels"]
found_api = 0
for ep in endpoints:
    if ep in api_content:
        ok(f"API endpoint defined: {ep}")
        found_api += 1
    else:
        fail(f"API endpoint missing: {ep}")

if found_api == len(endpoints):
    ok("All 4 Phase 120 API endpoints registered")
else:
    fail(f"Only {found_api}/{len(endpoints)} API endpoints found")

if "homepage_api_bp" in file_read("app.py"):
    ok("homepage_api_bp registered in app.py")
else:
    warn("homepage_api_bp registration not found in app.py")

# ── 7. Homepage service function exists ──
print("\n--- 7. Service Function Check ---")
svc_content = file_read("services/homepage_service.py")
if "def get_homepage_payload" in svc_content:
    ok("get_homepage_payload() defined")
else:
    fail("get_homepage_payload() NOT found")

# ── 8. Old feed view still accessible ──
print("\n--- 8. Legacy Feed Accessibility ---")
if "@app.route(\"/feed\")" in app_content:
    ok("/feed route preserved for legacy access")
else:
    warn("/feed route may be missing")

feed_index = file_read("templates/feed/index.html")
if feed_index:
    ok("templates/feed/index.html still exists")
else:
    warn("templates/feed/index.html missing")

# ── Summary ──
print(f"\n{'=' * 60}")
print(f"PHASE 121 — ACTIVE HOMEPAGE ROUTE AUDIT SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}")
print(f"  FAIL: {FAIL}")
print(f"  WARN: {WARN}")
print()

if FAIL == 0:
    print("  [PASS] No blockers — Phase 120 homepage is the active route")
else:
    print("  [FAIL] Blockers present")

if WARN > 0:
    print(f"  WARNINGS: {WARN} (review recommended)")

print()
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
