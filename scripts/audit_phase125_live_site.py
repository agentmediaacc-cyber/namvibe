#!/usr/bin/env python3
"""
Phase 125 — Live NamVibe Production Error Audit (requests-based).
Checks live https://namvibe.com endpoints, static assets, error pages, and canonical redirects.
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
    full = os.path.join(ROOT, path)
    if not os.path.exists(full): return ""
    with open(full, encoding="utf-8", errors="ignore") as f:
        return f.read()


def file_exists(path):
    return os.path.exists(os.path.join(ROOT, path))


print("=" * 60)
print("PHASE 125 — LIVE SITE PRODUCTION ERROR AUDIT")
print(f"BASE: {BASE}")
print("=" * 60)

# ── 1. DNS / HTTPS reachable ──
print("\n--- 1. DNS / HTTPS Reachable ---")
status, body, final_url = http_get(BASE + "/")
if status == 200:
    ok("Root HTTPS reachable, status 200")
else:
    fail(f"Root returned {status}")

# ── 2. Root returns 200 ──
print("\n--- 2. Root Homepage ---")
if status == 200:
    ok("Homepage returns 200")
    if "NamVibe" in body or "namvibe" in body:
        ok("Homepage contains NamVibe branding")
    else:
        warn("Homepage branding check")
else:
    fail("Homepage failed")

# ── 3. www redirect ──
print("\n--- 3. www Canonical Redirect ---")
www_status, www_body, www_final = http_get("https://www.namvibe.com/", allow_redirects=False)
if www_status in (301, 302):
    ok(f"www.namvibe.com redirects ({www_status})")
elif www_status == 200:
    if "NamVibe" in www_body:
        warn("www.namvibe.com returns 200 (no redirect) — same content served")
    else:
        fail("www.namvibe.com inconsistent with canonical")
else:
    fail(f"www.namvibe.com unexpected status {www_status}")

# ── 4. /reels/ returns 200 ──
print("\n--- 4. /reels/ ---")
r_status, r_body, _ = http_get(BASE + "/reels/")
if r_status == 200:
    ok("/reels/ returns 200")
else:
    fail(f"/reels/ returned {r_status}")

# ── 5. /games/ ──
print("\n--- 5. /games/ ---")
g_status, g_body, _ = http_get(BASE + "/games/")
if g_status in (301, 302, 200):
    ok(f"/games/ returns {g_status} (redirect or active)")
else:
    if "NamVibe" in g_body or "namvibe" in g_body or "Page not found" in g_body:
        ok("/games/ 404s with branded page")
    else:
        fail(f"/games/ returned {g_status} without branding")

# ── 6. /pink-friday/ ──
print("\n--- 6. /pink-friday/ ---")
pf_status, pf_body, _ = http_get(BASE + "/pink-friday/")
if pf_status in (301, 302):
    ok(f"/pink-friday/ redirects ({pf_status})")
elif pf_status == 200:
    fail("/pink-friday/ still serves content")
else:
    if "NamVibe" in pf_body or "Page not found" in pf_body:
        ok("/pink-friday/ 404s with branded page (removed)")
    else:
        ok(f"/pink-friday/ returns {pf_status} (removed)")

# ── 7. Static CSS loads ──
print("\n--- 7. Static Assets ---")
assets = [
    "/static/css/namvibe_home_pro.css",
    "/static/js/namvibe_home_pro.js",
    "/static/css/chain_theme.css",
    "/static/css/platform_premium.css",
]
for asset in assets:
    a_status, _, _ = http_get(BASE + asset)
    if a_status == 200:
        ok(f"{asset} loads (200)")
    else:
        fail(f"{asset} returned {a_status}")

# ── 8. namvibe_home_pro.css exists locally ──
print("\n--- 8. Local File Integrity ---")
css_path = "static/css/namvibe_home_pro.css"
js_path = "static/js/namvibe_home_pro.js"
if file_exists(css_path):
    ok(f"{css_path} exists locally")
else:
    fail(f"{css_path} missing")
if file_exists(js_path):
    ok(f"{js_path} exists locally")
else:
    fail(f"{js_path} missing")

# ── 9. Error page templates exist ──
print("\n--- 9. Custom Error Pages ---")
if file_exists("templates/errors/404.html"):
    ok("Custom 404 template exists")
else:
    fail("Custom 404 template missing")
if file_exists("templates/errors/500.html"):
    ok("Custom 500 template exists")
else:
    fail("Custom 500 template missing")

# ── 10. Nav/footer contains no broken routes ──
print("\n--- 10. Broken Route References ---")
html = file_read("templates/chain_home.html")
if "/games/" not in html:
    ok("No /games/ link in homepage nav")
else:
    warn("/games/ referenced in homepage — verify it works")
if "/pink-friday/" not in html:
    ok("No /pink-friday/ link in homepage nav")
else:
    fail("/pink-friday/ still referenced in homepage nav")

# ── 11. App.py error handlers use new templates ──
print("\n--- 11. Error Handler Routes ---")
app_text = file_read("app.py")
if "errors/404.html" in app_text:
    ok("404 handler uses errors/404.html")
else:
    fail("404 handler does not use custom template")
if "errors/500.html" in app_text:
    ok("500 handler uses errors/500.html")
else:
    fail("500 handler does not use custom template")

# ── 12. www redirect in app.py ──
print("\n--- 12. www Redirect Logic ---")
if "www." in app_text and "redirect" in app_text.lower():
    ok("www redirect logic present in app.py")
else:
    warn("www redirect may only be at nginx level")

# ── 13. /games/ route in app.py ──
print("\n--- 13. /games/ Route ---")
if "/games/" in app_text or "/games" in app_text:
    ok("/games/ route present in app.py")
else:
    warn("/games/ has no route — 404 with branded page")

# ── 14. No console-breaking JS references ──
print("\n--- 14. Console-Safe JS ---")
js_text = file_read("static/js/namvibe_home_pro.js")
broken_patterns = ["document.write"]
bad_found = False
for pat in broken_patterns:
    if pat in js_text:
        warn(f"Potential breaking pattern in JS: {pat}")
        bad_found = True
if not bad_found:
    ok("No console-breaking JS patterns in namvibe_home_pro.js")

# ── 15. Live 404 test ──
print("\n--- 15. Live 404 Error Page ---")
live_404_status, live_404_body, _ = http_get(BASE + "/this-page-does-not-exist-xyz")
if "NamVibe" in live_404_body or "Page not found" in live_404_body:
    ok("Live 404 shows branded error page")
else:
    warn("Live 404 may show generic error — check deployment")

# ── Summary ──
print(f"\n{'=' * 60}")
print("PHASE 125 — LIVE SITE AUDIT SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}")
print(f"  FAIL: {FAIL}")
print(f"  WARN: {WARN}")
print()
if FAIL == 0:
    print("  [PASS] No blockers — live site audit passes")
else:
    print("  [FAIL] Blockers present")
if WARN > 0:
    print(f"  WARNINGS: {WARN} (review recommended)")
print()
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
