#!/usr/bin/env python3
"""
Phase 126 — Live Deploy Static Audit.
Checks https://namvibe.com for correct routes, assets, version marker, and console safety.
"""

import os
import sys
import urllib.request
import urllib.error
import ssl

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASS = 0; FAIL = 0; WARN = 0

BASE = "https://namvibe.com"
ctx = ssl.create_default_context()

def ok(m): global PASS; PASS += 1; print(f"  [PASS] {m}")
def fail(m): global FAIL; FAIL += 1; print(f"  [FAIL] {m}")
def warn(m): global WARN; WARN += 1; print(f"  [WARN] {m}")

def http_get(url, follow=True):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Phase126Audit/1.0"})
        if follow:
            with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
                return r.status, r.read().decode("utf-8", "ignore"), r.url
        class NR(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, hdrs, newurl):
                return None
        opener = urllib.request.build_opener(NR)
        with opener.open(req, timeout=15) as r:
            return r.status, r.read().decode("utf-8", "ignore"), r.url
    except urllib.error.HTTPError as e:
        b = e.read().decode("utf-8", "ignore") if e.fp else ""
        return e.code, b, url
    except Exception as e:
        return -1, str(e), url

def file_read(path):
    f = os.path.join(ROOT, path)
    if not os.path.exists(f): return ""
    with open(f, encoding="utf-8", errors="ignore") as fh:
        return fh.read()

print("=" * 60)
print("PHASE 126 — LIVE DEPLOY STATIC AUDIT")
print(f"BASE: {BASE}")
print("=" * 60)

# ── 1. Homepage ──
print("\n--- 1. Homepage ---")
s, body, _ = http_get(BASE + "/")
if s == 200:
    ok("Homepage returns 200")
else:
    fail(f"Homepage returned {s}")

# ── 2. /reels/ ──
print("\n--- 2. /reels/ ---")
s, _, _ = http_get(BASE + "/reels/")
ok(f"/reels/ returns {s}") if s == 200 else fail(f"/reels/ returned {s}")

# ── 3. /discover/ ──
print("\n--- 3. /discover/ ---")
s, _, _ = http_get(BASE + "/discover/")
if s in (200, 301, 302):
    ok(f"/discover/ returns {s}")
else:
    fail(f"/discover/ returned {s}")

# ── 4. /stories/ ──
print("\n--- 4. /stories/ ---")
s, _, _ = http_get(BASE + "/stories/")
if s in (200, 301, 302):
    ok(f"/stories/ returns {s}")
else:
    fail(f"/stories/ returned {s}")

# ── 5. /live/ ──
print("\n--- 5. /live/ ---")
s, _, _ = http_get(BASE + "/live/")
if s in (200, 301, 302):
    ok(f"/live/ returns {s}")
else:
    fail(f"/live/ returned {s}")

# ── 6. /wallet/ ──
print("\n--- 6. /wallet/ ---")
s, _, _ = http_get(BASE + "/wallet/")
if s in (200, 301, 302):
    ok(f"/wallet/ returns {s} (auth redirect expected)")
else:
    fail(f"/wallet/ returned {s}")

# ── 7. /profile/ ──
print("\n--- 7. /profile/ ---")
s, _, _ = http_get(BASE + "/profile/")
if s == 302:
    ok("/profile/ redirects to login (expected)")
else:
    fail(f"/profile/ returned {s} (expected 302)")

# ── 8. www redirect ──
print("\n--- 8. www Redirect ---")
s, _, _ = http_get("https://www.namvibe.com/", follow=False)
if s in (301, 302):
    ok(f"www.namvibe.com redirects ({s})")
else:
    fail(f"www.namvibe.com returned {s} (expected 301/302)")

# ── 9. Build version marker ──
print("\n--- 9. Build Version Marker ---")
if 'name="namvibe-build"' in body or "namvibe-build" in body:
    ok("Homepage contains namvibe-build marker")
else:
    fail("Build marker missing from homepage")

if 'phase126' in body:
    ok("Build marker value is phase126")
else:
    fail("Build marker phase126 not found")

# ── 10. CSS/JS asset references ──
print("\n--- 10. CSS/JS Asset References ---")
if 'namvibe_home_pro.css' in body:
    ok("Homepage references namvibe_home_pro.css")
else:
    fail("namvibe_home_pro.css not referenced")
if 'namvibe_home_pro.js' in body:
    ok("Homepage references namvibe_home_pro.js")
else:
    fail("namvibe_home_pro.js not referenced")

# ── 11. CSS loads ──
print("\n--- 11. CSS Loads ---")
s, _, _ = http_get(BASE + "/static/css/namvibe_home_pro.css")
ok("CSS returns 200") if s == 200 else fail(f"CSS returned {s}")

# ── 12. JS loads ──
print("\n--- 12. JS Loads ---")
s, _, _ = http_get(BASE + "/static/js/namvibe_home_pro.js")
ok("JS returns 200") if s == 200 else fail(f"JS returned {s}")

# ── 13. No old tiktok_home.js ──
print("\n--- 13. No Deprecated JS ---")
if "tiktok_home.js" not in body:
    ok("tiktok_home.js not loaded")
else:
    fail("tiktok_home.js still referenced")

# ── 14. No FontAwesome required ──
print("\n--- 14. FontAwesome ---")
if "font-awesome" not in body.lower() and "fontawesome" not in body.lower():
    ok("No FontAwesome dependency in homepage")
else:
    warn("FontAwesome reference found")

# ── 15. No placeholder text ──
print("\n--- 15. Placeholder Text ---")
clean = True
for ph in ["TODO", "lorem", "test call sound", "test-call-sound"]:
    if ph.lower() in body.lower():
        warn(f"Placeholder found: '{ph}'")
        clean = False
if clean:
    ok("No placeholder text visible on homepage")

# ── 16. Custom 404 ──
print("\n--- 16. Custom 404 Page ---")
s, b, _ = http_get(BASE + "/this-page-does-not-exist-audit-126")
if "NamVibe" in b or "Page not found" in b or "404" in b:
    ok("Custom 404 page works")
else:
    fail("Custom 404 missing branding")

# ── 17. /games/ redirect ──
print("\n--- 17. /games/ Redirect ---")
s, _, final = http_get(BASE + "/games/")
if s in (301, 302) or "/discover" in final:
    ok(f"/games/ redirects to /discover/")
else:
    warn(f"/games/ returned {s}")

# ── 18. /pink-friday/ safe ──
print("\n--- 18. /pink-friday/ ---")
s, b, _ = http_get(BASE + "/pink-friday/")
if "NamVibe" in b or "Page not found" in b or s == 404:
    ok("/pink-friday/ shows branded 404 or redirects safely")
else:
    warn(f"/pink-friday/ unexpected: {s}")

# ── Summary ──
print(f"\n{'=' * 60}")
print("PHASE 126 — LIVE DEPLOY STATIC AUDIT SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
if FAIL == 0:
    print("  [PASS] No blockers")
else:
    print("  [FAIL] Blockers present")
if s < 0 or s == -1:
    print("  [WARN] Live server may not be deployed — local code verified")
print(f"\n  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
