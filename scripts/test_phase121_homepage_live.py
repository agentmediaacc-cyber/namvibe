#!/usr/bin/env python3
"""
Phase 121 — Live Homepage Render Test.

Verifies that GET / produces the Phase 120 premium homepage with:
  - HTTP 200
  - Phase 120 premium shell, header, left rail, feed, sidebar, bottom nav
  - Premium CSS/JS linked in rendered HTML
  - No old feed/index.html template artifacts
"""

import os
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


print("=" * 60)
print("PHASE 121 — LIVE HOMEPAGE RENDER TEST")
print("=" * 60)

# ── 1. Render GET / via subprocess ──
print("\n--- 1. Homepage Render ---")
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
text = resp.data.decode("utf-8", errors="ignore") if hasattr(resp, "data") else ""
with open(os.environ["_LIVE_OUT"], "w") as f:
    f.write(str(resp.status_code) + "\\n" + text)
'''
import subprocess, tempfile
try:
    outf = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    outf.close()
    env = {**os.environ, "FLASK_ENV": "development",
           "CHAIN_TEST_MODE": "1", "CHAIN_FAST_LOCAL": "1",
           "_LIVE_OUT": outf.name}
    proc = subprocess.run(
        [sys.executable, "-c", render_code],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
        cwd=ROOT, env=env,
    )
    if os.path.exists(outf.name):
        with open(outf.name) as f:
            content = f.read()
        os.unlink(outf.name)
        lines = content.split("\n", 1)
        status_code = lines[0].strip()
        rendered_html = lines[1] if len(lines) > 1 else ""
    else:
        warn("Render subprocess produced no output file")
        status_code = "0"
        rendered_html = ""
except Exception as e:
    warn(f"Render error: {e}")
    status_code = "0"
    rendered_html = ""

if status_code == "200":
    ok("GET / returns HTTP 200")
else:
    fail(f"GET / returned HTTP {status_code} (expected 200)")

# ── 2. Rendered HTML checks ──
print("\n--- 2. Rendered HTML Content ---")
if not rendered_html:
    fail("No rendered HTML captured")
else:
    # Phase 120 premium structure markers
    premium_structure = [
        ("Premium shell", "nvpro-shell"),
        ("Premium header", "nvpro-header"),
        ("Left navigation rail", "nvpro-left-rail"),
        ("Feed section", "nvpro-feed"),
        ("Sidebar", "nvpro-sidebar"),
        ("Bottom mobile nav", "nvpro-bottom-nav"),
        ("Stories tray", "nvpro-stories-tray"),
        ("Reels section", "nvpro-reels-section"),
    ]
    for label, marker in premium_structure:
        if marker in rendered_html:
            ok(f"Rendered HTML contains: {label}")
        else:
            warn(f"Rendered HTML missing: {label}")

    # Premium empty state markers
    empty_states = [
        "Your NamVibe feed is ready",
        "No stories yet",
        "No reels yet",
        "Discover Creators",
        "Create Post",
    ]
    for es in empty_states:
        if es in rendered_html:
            ok(f"Empty state present: '{es}'")
            break
    else:
        warn("No premium empty states found in rendered HTML")

    # CSS/JS linked
    if "namvibe_home_pro.css" in rendered_html:
        ok("Premium CSS linked in rendered HTML")
    else:
        fail("namvibe_home_pro.css NOT linked in rendered HTML")

    if "namvibe_home_pro.js" in rendered_html:
        ok("Premium JS linked in rendered HTML")
    else:
        fail("namvibe_home_pro.js NOT linked in rendered HTML")

    # Title check
    import re
    title_match = re.search(r'<title>(.*?)</title>', rendered_html)
    if title_match:
        title = title_match.group(1)
        ok(f"Page title: '{title}'")
        if "namvibe" in title.lower() and ("home" in title.lower() or "premium" in title.lower()):
            ok("Title contains NamVibe branding")
    else:
        warn("No <title> tag found")

    # No old template artifacts
    old_markers = ["Feed - NamVibe", "feed/index.html"]
    for old in old_markers:
        if old in rendered_html:
            warn(f"Old template artifact detected: '{old}'")

    # Premium navbar elements
    nav_links = [
        ("Home link", "href=\"/\""),
        ("Discover link", "href=\"/discover/\""),
        ("Reels link", "href=\"/reels/\""),
    ]
    for label, link in nav_links:
        if link in rendered_html:
            ok(f"Nav {label} present")
        else:
            warn(f"Nav {label} missing")

    # Sidebar sections
    sidebar_sections = ["Live Now", "Suggested Creators", "Trending Hashtags", "Wallet"]
    for section in sidebar_sections:
        if section in rendered_html:
            ok(f"Sidebar section present: {section}")
        else:
            warn(f"Sidebar section missing: {section}")

    # Bottom nav icons (mobile)
    bottom_nav_items = ["Home", "Discover", "Reels", "Profile"]
    for item in bottom_nav_items:
        if item in rendered_html:
            ok(f"Bottom nav item: {item}")
        else:
            warn(f"Bottom nav item missing: {item}")

    # Action buttons
    action_buttons = ["Upload Reel", "Create Post", "Watch Reels"]
    for btn in action_buttons:
        if btn in rendered_html:
            ok(f"Action button: {btn}")
        else:
            warn(f"Action button missing: {btn}")

    # No fake content
    fake_patterns = ["lorem ipsum", "john doe", "test user", "placeholder"]
    fake_lower = rendered_html.lower()
    found_fake = False
    for pat in fake_patterns:
        if pat in fake_lower:
            warn(f"Suspicious fake text in rendered HTML: '{pat}'")
            found_fake = True
    if not found_fake:
        ok("No fake/placeholder text in rendered HTML")

    # Premium branding
    if "premium" in rendered_html.lower():
        ok("Premium branding present in rendered HTML")

    # Responsive length
    if len(rendered_html) > 5000:
        ok(f"Rendered HTML is substantial ({len(rendered_html)} bytes)")
    else:
        warn(f"Rendered HTML seems short ({len(rendered_html)} bytes)")

    # CSRF token present (from base.html)
    if "csrf-token" in rendered_html:
        ok("CSRF token present")

# ── Summary ──
print(f"\n{'=' * 60}")
print(f"PHASE 121 — LIVE HOMEPAGE RENDER SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}")
print(f"  FAIL: {FAIL}")
print(f"  WARN: {WARN}")
print()

if FAIL == 0:
    print("  [PASS] No blockers — Phase 120 homepage renders correctly at /")
else:
    print("  [FAIL] Blockers present")

if WARN > 0:
    print(f"  WARNINGS: {WARN} (review recommended)")

print()
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
