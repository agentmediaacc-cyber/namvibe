#!/usr/bin/env python3
"""
Phase 126 — Live Deploy Static Audit (requests-based).
Checks https://namvibe.com for correct routes, assets, version marker, and console safety.
"""

import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASS = 0; FAIL = 0; WARN = 0

BASE = "https://namvibe.com"
HEADERS = {"User-Agent": "Mozilla/5.0 NamVibeAudit/phase127"}
TIMEOUT = 20


def ok(m): global PASS; PASS += 1; print(f"  [PASS] {m}")
def fail(m): global FAIL; FAIL += 1; print(f"  [FAIL] {m}")
def warn(m): global WARN; WARN += 1; print(f"  [WARN] {m}")


def http_get(url, allow_redirects=True):
    try:
        import requests
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=allow_redirects, verify=True)
        return r.status_code, r.text, r.url
    except requests.exceptions.ConnectionError as e:
        return -1, f"ConnectionError: {e}", url
    except requests.exceptions.Timeout as e:
        return -1, f"Timeout: {e}", url
    except requests.exceptions.RequestException as e:
        return -1, f"RequestException: {e}", url
    except Exception as e:
        return -1, str(e), url


def file_read(path):
    f = os.path.join(ROOT, path)
    if not os.path.exists(f): return ""
    with open(f, encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def file_exists(path):
    return os.path.exists(os.path.join(ROOT, path))


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
ok(f"/discover/ returns {s}") if s in (200, 301, 302) else fail(f"/discover/ returned {s}")

# ── 4. /stories/ ──
print("\n--- 4. /stories/ ---")
s, _, _ = http_get(BASE + "/stories/")
ok(f"/stories/ returns {s}") if s in (200, 301, 302) else fail(f"/stories/ returned {s}")

# ── 5. /live/ ──
print("\n--- 5. /live/ ---")
s, _, _ = http_get(BASE + "/live/")
ok(f"/live/ returns {s}") if s in (200, 301, 302) else fail(f"/live/ returned {s}")

# ── 6. /wallet/ ──
print("\n--- 6. /wallet/ ---")
s, _, _ = http_get(BASE + "/wallet/")
ok(f"/wallet/ returns {s} (auth redirect expected)") if s in (200, 301, 302) else fail(f"/wallet/ returned {s}")

# ── 7. /profile/ ──
print("\n--- 7. /profile/ ---")
s, _, _ = http_get(BASE + "/profile/")
if s == 302:
    ok("/profile/ redirects to login (expected)")
else:
    fail(f"/profile/ returned {s} (expected 302)")

# ── 8. www redirect ──
print("\n--- 8. www Redirect ---")
s, _, _ = http_get("https://www.namvibe.com/", allow_redirects=False)
if s in (301, 302):
    ok(f"www.namvibe.com redirects ({s})")
else:
    fail(f"www.namvibe.com returned {s} (expected 301/302)")

# ── 9. Build version marker ──
print("\n--- 9. Build Version Marker ---")
if 'namvibe-build' in body:
    ok("Homepage contains namvibe-build marker")
else:
    fail("Build marker missing from homepage")
# Check for the hidden marker too
if 'data-namvibe-build="phase127"' in body:
    ok("Hidden marker data-namvibe-build=phase127 present")
else:
    warn("Hidden build marker may be missing — check deployment")

# ── 10. CSS/JS asset references ──
print("\n--- 10. CSS/JS Asset References ---")
refs_ok = True
for ref in ['namvibe_home_pro.css', 'namvibe_home_pro.js']:
    if ref in body:
        ok(f"Homepage references {ref}")
    else:
        fail(f"{ref} not referenced")
        refs_ok = False

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
fa_in_body = "font-awesome" in body.lower() or "fontawesome" in body.lower()
if not fa_in_body:
    ok("No FontAwesome dependency in homepage")
elif 'href="https://cdn.*fontawesome' in body:
    warn("FontAwesome CDN loaded")
else:
    ok("FontAwesome mention only (not loaded)")

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
s, b, _ = http_get(BASE + "/this-page-does-not-exist-audit-127")
if "NamVibe" in b or "Page not found" in b or "404" in b:
    ok("Custom 404 page works")
else:
    fail("Custom 404 missing branding")

# ── 17. /games/ redirect ──
print("\n--- 17. /games/ Redirect ---")
s, _, final = http_get(BASE + "/games/")
if s in (200, 301, 302) or "/discover" in final:
    ok(f"/games/ returns {s} (expected redirect to /discover/)")
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
print(f"\n  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
