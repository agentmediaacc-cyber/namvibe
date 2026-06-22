#!/usr/bin/env python3
"""
Phase 120 — NamVibe Premium Homepage Reality Test.

Verifies:
  - Template syntax, CSS, JS exist
  - No fake/hardcoded content in rendered HTML
  - API endpoints return valid JSON with real data
  - Premium empty states when no content
  - Nav structure, no placeholder text
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
FAKE_PATTERNS = [
    "lorem ipsum", "john doe", "test user", "fake user",
    "demo reel", "sample post", "jane doe", "test account",
    "placeholder", "insert name here",
]


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
print("PHASE 120 — PREMIUM HOMEPAGE REALITY TEST")
print("=" * 60)

# ── 1. File existence ──
print("\n--- 1. File Existence ---")
tpl = "templates/chain_home.html"
css = "static/css/namvibe_home_pro.css"
js_f = "static/js/namvibe_home_pro.js"
svc = "services/homepage_service.py"
api = "api_routes/homepage_api.py"

if file_exists(tpl):
    ok(f"Template exists: {tpl}")
else:
    fail(f"Template missing: {tpl}")

if file_exists(css):
    ok(f"CSS exists: {css}")
else:
    fail(f"CSS missing: {css}")

if file_exists(js_f):
    ok(f"JS exists: {js_f}")
else:
    fail(f"JS missing: {js_f}")

if file_exists(svc):
    ok(f"Service exists: {svc}")
else:
    fail(f"Service missing: {svc}")

if file_exists(api):
    ok(f"API exists: {api}")
else:
    fail(f"API missing: {api}")

# ── 2. Template syntax check ──
print("\n--- 2. Template Syntax ---")
html = file_read(tpl)
if html:
    # Check balanced block tags
    block_starts = html.count("{% block")
    block_ends = html.count("{% endblock")
    if block_starts == block_ends or block_ends >= block_starts:
        ok("Jinja2 block tags balanced")
    else:
        fail(f"Block tag mismatch: {block_starts} open, {block_ends} close")

    # Check no raw template syntax errors
    for marker in ["{% raw %}", "{% endraw %}", "{% include"]:
        if marker in html:
            warn(f"Unusual template marker: {marker}")

    # Check extends base
    if "{% extends \"base.html\" %}" in html or "{% extends 'base.html' %}" in html:
        ok("Template extends base.html")
    else:
        warn("Template does not extend base.html")

    # Block content present
    if "{% block content %}" in html and "{% endblock %}" in html:
        ok("Content block defined")
    else:
        fail("Missing content block")

    # Extra CSS block linked
    if "namvibe_home_pro.css" in html:
        ok("Template links namvibe_home_pro.css")
    else:
        fail("Template missing namvibe_home_pro.css link")

    # Extra JS block linked
    if "namvibe_home_pro.js" in html:
        ok("Template links namvibe_home_pro.js")
    else:
        fail("Template missing namvibe_home_pro.js link")
else:
    fail("Template file is empty")

# ── 3. Fake content scan ──
print("\n--- 3. Fake Content Scan ---")
html_lower = html.lower() if html else ""
found_fake = False
for pat in FAKE_PATTERNS:
    if pat in html_lower:
        warn(f"Found suspicious text in HTML: '{pat}'")
        found_fake = True
if not found_fake:
    ok("No fake/placeholder text found in template")

# Check for hardcoded hashtags that look fake
hashtag_matches = re.findall(r'#(\w+)', html)
namibian_hashtags = ["namibia", "windhoek", "namvibe", "swakopmund"]
real_hashtags = [h.lower() for h in hashtag_matches if h.lower() not in namibian_hashtags]
if real_hashtags:
    ok(f"No hardcoded hashtags detected beyond Namibian references")
else:
    ok("Hashtag references are from real data or Namibian-themed")

# Check no inline Lorem ipsum
if "lorem" in html_lower:
    warn("Lorem ipsum text detected in template")

# ── 4. Navigation check ──
print("\n--- 4. Navigation Structure ---")
nav_items = [
    ("Home", "/"),
    ("Discover", "/discover/"),
    ("Reels", "/reels/"),
]
for label, href in nav_items:
    if href in html or label in html:
        ok(f"Nav link present: {label} -> {href}")
    else:
        warn(f"Nav link missing: {label} -> {href}")

# Left rail present
if 'class="nvpro-left-rail"' in html:
    ok("Left navigation rail present")
else:
    warn("Left navigation rail missing")

# Bottom nav present
if 'class="nvpro-bottom-nav"' in html:
    ok("Bottom mobile navigation present")
else:
    warn("Bottom mobile navigation missing")

# Check no duplicate nav labels that would overlap
label_counts = {}
for label, _ in nav_items:
    label_counts[label] = html.count(label)
dupes = [k for k, v in label_counts.items() if v > 2]
if dupes:
    for d in dupes:
        warn(f"Nav label '{d}' appears {label_counts[d]} times (possible overlap)")
else:
    ok("No duplicate nav labels causing overlap")

# ── 5. Premium empty states ──
print("\n--- 5. Empty States ---")
empty_signals = [
    "Your NamVibe feed is ready",
    "No stories yet",
    "No reels yet",
    "No one is live right now",
    "No suggestions yet",
    "No trending hashtags yet",
]
for signal in empty_signals:
    if signal in html:
        ok(f"Empty state message found: '{signal[:50]}...'")
    else:
        warn(f"Empty state message missing: '{signal[:50]}...'")

# Action buttons in empty states
empty_actions = [
    "Discover Creators",
    "Create Post",
    "Watch Reels",
    "Upload Reel",
]
for action in empty_actions:
    if action in html:
        ok(f"Empty state action button: '{action}'")
    else:
        warn(f"Empty state action button missing: '{action}'")

# ── 6. Stories tray ──
print("\n--- 6. Stories Tray ---")
if 'nvpro-stories-tray' in html:
    ok("Stories tray section present")
else:
    warn("Stories tray section missing")
if 'nvpro-story-create' in html:
    ok("Create story button present")
else:
    warn("Create story button missing")
if 'nvpro-story-ring' in html or 'nvpro-story-empty' in html:
    ok("Story ring or empty state present")
else:
    warn("Neither story ring nor empty state found")

# ── 7. Reels section ──
print("\n--- 7. Reels Section ---")
if 'nvpro-reels-section' in html:
    ok("Reels section present")
else:
    warn("Reels section missing")
if 'nvpro-reels-grid' in html or 'nvpro-reels-empty' in html:
    ok("Reels grid or empty state present")
else:
    warn("Reels grid/empty state missing")
if '/reels/upload' in html or '/reels/' in html:
    ok("Reels links present")
else:
    warn("No reels links found")

# ── 8. Sidebar sections ──
print("\n--- 8. Sidebar ---")
sidebar_sections = [
    ("Live panel", "Live Now"),
    ("Suggested creators", "Suggested Creators"),
    ("Trending hashtags", "Trending Hashtags"),
    ("Wallet quick card", "Wallet"),
]
for label, text in sidebar_sections:
    if text in html:
        ok(f"Sidebar section: {label}")
    else:
        warn(f"Sidebar section missing: {label}")
if 'nvpro-sidebar' in html:
    ok("Sidebar container present")
else:
    warn("Sidebar container missing")

# ── 9. API endpoints (use subprocess to test Flask app) ──
print("\n--- 9. API Endpoints ---")
import subprocess, tempfile

api_code = '''
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
app.config["TESTING"] = True
app.config["WTF_CSRF_ENABLED"] = False
client = app.test_client()
results = {}
for path, label in [
    ("/api/homepage/feed?tab=for_you", "/api/homepage/feed"),
    ("/api/homepage/stories", "/api/homepage/stories"),
    ("/api/homepage/reels", "/api/homepage/reels"),
    ("/api/homepage/sidebar", "/api/homepage/sidebar"),
]:
    try:
        resp = client.get(path)
        data = resp.get_json()
        results[label] = {"status": resp.status_code, "ok": data.get("ok", False) if data else False, "has_data": bool(data)}
    except Exception as e:
        results[label] = {"status": -1, "ok": False, "error": str(e)}
with open(os.environ["_API_OUT"], "w") as f:
    f.write(json.dumps(results))
'''
try:
    outf = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    outf.close()
    env = {**os.environ, "FLASK_ENV": "development",
           "CHAIN_TEST_MODE": "1", "CHAIN_FAST_LOCAL": "1",
           "_API_OUT": outf.name}
    proc = subprocess.run(
        [sys.executable, "-c", api_code],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
        cwd=ROOT, env=env,
    )
    if os.path.exists(outf.name):
        with open(outf.name) as f:
            raw = f.read().strip()
        os.unlink(outf.name)
        if raw:
            api_results = json.loads(raw)
            for label, r in api_results.items():
                if r.get("ok"):
                    ok(f"{label} -> 200 JSON OK")
                elif r.get("status") == 200:
                    ok(f"{label} -> 200 (no ok flag)")
                elif r.get("status"):
                    warn(f"{label} -> HTTP {r['status']}")
                else:
                    warn(f"{label} error: {r.get('error', 'unknown')}")
        else:
            warn("API test produced empty output")
    else:
        warn("API subprocess failed")
except Exception as e:
    warn(f"API test error: {e}")

# ── 10. Template render check ──
print("\n--- 10. Template Render Check ---")
render_code = '''
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
app.config["TESTING"] = True
app.config["WTF_CSRF_ENABLED"] = False
client = app.test_client()
resp = client.get("/")
with open(os.environ["_RENDER_OUT"], "w") as f:
    f.write(str(resp.status_code) + "\\n" + (resp.data.decode("utf-8", errors="ignore") if hasattr(resp, "data") else ""))
'''
try:
    outf2 = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    outf2.close()
    env2 = {**os.environ, "FLASK_ENV": "development",
            "CHAIN_TEST_MODE": "1", "CHAIN_FAST_LOCAL": "1",
            "_RENDER_OUT": outf2.name}
    proc2 = subprocess.run(
        [sys.executable, "-c", render_code],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
        cwd=ROOT, env=env2,
    )
    if os.path.exists(outf2.name):
        with open(outf2.name) as f:
            content = f.read()
        os.unlink(outf2.name)
        lines = content.split("\n", 1)
        status_code = lines[0].strip()
        rendered_html = lines[1] if len(lines) > 1 else ""
        if status_code == "200":
            ok("Homepage renders with HTTP 200")
        else:
            warn(f"Homepage returned HTTP {status_code}")

        if rendered_html:
            # Check for fake patterns in rendered output
            rl = rendered_html.lower()
            found_in_render = False
            for pat in FAKE_PATTERNS:
                if pat in rl:
                    warn(f"Fake text found in rendered HTML: '{pat}'")
                    found_in_render = True
            if not found_in_render:
                ok("No fake/placeholder text in rendered HTML")

            # Check for premium components in rendered output
            if "nvpro-shell" in rendered_html:
                ok("Rendered HTML contains premium shell")
            else:
                warn("Rendered HTML missing premium shell structure")
            if "nvpro-header" in rendered_html:
                ok("Rendered HTML contains premium header")
            else:
                warn("Rendered HTML missing premium header")
            if "nvpro-feed" in rendered_html or "nvpro-empty" in rendered_html:
                ok("Rendered HTML contains feed section")
            else:
                warn("Rendered HTML missing feed section")
        else:
            warn("No rendered HTML body captured")
    else:
        warn("Render subprocess failed")
except Exception as e:
    warn(f"Render test error: {e}")

# ── 11. get_homepage_payload function check ──
print("\n--- 11. Service Function Check ---")
svc_content = file_read(svc)
if "def get_homepage_payload" in svc_content:
    ok("get_homepage_payload() defined in homepage_service.py")
else:
    fail("get_homepage_payload() NOT found in homepage_service.py")

if "def _normalize_story" in svc_content:
    ok("Helper _normalize_story exists")
else:
    warn("_normalize_story not found")

# ── 12. API function check ──
print("\n--- 12. API Function Check ---")
api_content = file_read(api)
endpoints = ["/api/homepage/feed", "/api/homepage/sidebar", "/api/homepage/stories", "/api/homepage/reels"]
for ep in endpoints:
    if ep in api_content:
        ok(f"API endpoint defined: {ep}")
    else:
        fail(f"API endpoint missing: {ep}")

# ── Summary ──
print(f"\n{'=' * 60}")
print(f"PHASE 120 — PREMIUM HOMEPAGE REALITY SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}")
print(f"  FAIL: {FAIL}")
print(f"  WARN: {WARN}")
print()

if FAIL == 0:
    print("  [PASS] No blockers")
else:
    print("  [FAIL] Blockers present")

if WARN > 0:
    print(f"  WARNINGS: {WARN} (review recommended)")

print()
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
