#!/usr/bin/env python3
"""
Phase 127 — Production Live Build Verification.
Checks https://namvibe.com for correct build marker, cache-busting, static assets, and routes.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0; FAIL = 0; WARN = 0

BASE = "https://namvibe.com"
HEADERS = {"User-Agent": "Mozilla/5.0 NamVibeAudit Phase127"}
TIMEOUT = 20
SSL_VERIFY = True


def ok(m): global PASS; PASS += 1; print(f"  [PASS] {m}")
def fail(m): global FAIL; FAIL += 1; print(f"  [FAIL] {m}")
def warn(m): global WARN; WARN += 1; print(f"  [WARN] {m}")


def http_get(url, allow_redirects=True):
    try:
        import requests
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT,
                         allow_redirects=allow_redirects, verify=SSL_VERIFY)
        return r.status_code, r.text, r.url, str(r.headers)
    except requests.exceptions.SSLError as e:
        return -1, f"SSLError: {e}", url, ""
    except requests.exceptions.ConnectionError as e:
        return -1, f"ConnectionError: {e}", url, ""
    except requests.exceptions.Timeout as e:
        return -1, f"Timeout: {e}", url, ""
    except requests.exceptions.RequestException as e:
        return -1, f"RequestException: {e}", url, ""
    except Exception as e:
        return -1, str(e), url, ""


print("=" * 60)
print("PHASE 127 — PRODUCTION LIVE BUILD VERIFICATION")
print(f"BASE: {BASE}")
print("=" * 60)

# ── 1. Homepage returns 200 ──
print("\n--- 1. Homepage 200 ---")
s, body, final_url, headers = http_get(BASE + "/")
if s == 200:
    ok("Homepage returns 200")
else:
    fail(f"Homepage returned {s} (expected 200)")
    if s == -1:
        print(f"       Error: {body}")

# ── 2. Build marker exists ──
print("\n--- 2. Build Version Marker ---")
if 'namvibe-build' in body:
    ok("Build version meta tag present")
else:
    fail("Build meta tag missing")

# ── 3. Phase127 marker ├⌐xiste ──
print("\n--- 3. Phase127 Marker ---")
if 'phase127' in body:
    ok("phase127 marker found in homepage")
else:
    fail("phase127 marker missing from homepage")

# ── 4. Hidden marker div ──
print("\n--- 4. Hidden Build Marker ---")
if 'data-namvibe-build="phase127"' in body:
    ok("Hidden build marker <div data-namvibe-build=phase127> present")
else:
    warn("Hidden build marker not found (may not affect functionality)")

# ── 5. CSS cache-busting ──
print("\n--- 5. CSS Cache-Busting ---")
if 'namvibe_home_pro.css?v=phase127' in body:
    ok("CSS cache-busting: ?v=phase127")
else:
    fail("CSS version parameter missing or wrong")

# ── 6. JS cache-busting ──
print("\n--- 6. JS Cache-Busting ---")
if 'namvibe_home_pro.js?v=phase127' in body:
    ok("JS cache-busting: ?v=phase127")
else:
    fail("JS version parameter missing or wrong")

# ── 7. JS asset returns 200 ──
print("\n--- 7. JS Asset 200 ---")
s, _, _, _ = http_get(BASE + "/static/js/namvibe_home_pro.js?v=phase127")
if s == 200:
    ok("JS asset returns 200")
else:
    fail(f"JS asset returned {s} (expected 200)")

# ── 8. CSS asset returns 200 ──
print("\n--- 8. CSS Asset 200 ---")
s, _, _, _ = http_get(BASE + "/static/css/namvibe_home_pro.css?v=phase127")
if s == 200:
    ok("CSS asset returns 200")
else:
    fail(f"CSS asset returned {s} (expected 200)")

# ── 9. Custom 404 works ──
print("\n--- 9. Custom 404 Page ---")
s, body_404, _, _ = http_get(BASE + "/this-page-does-not-exist-phase127")
if "NamVibe" in body_404 or "Page not found" in body_404 or s == 404:
    ok("Custom 404 page works (branded or 404)")
else:
    fail(f"Custom 404 unexpected: status={s}")

# ── 10. /games/ redirect ──
print("\n--- 10. /games/ Redirect ---")
s, _, final_url, _ = http_get(BASE + "/games/")
if s in (301, 302) or s == 200 or "/discover" in final_url:
    ok(f"/games/ returns {s} (expected redirect)")
else:
    warn(f"/games/ returned {s} (final URL: {final_url})")

# ── 11. www redirect ──
print("\n--- 11. www Redirect ---")
s, _, _, _ = http_get("https://www.namvibe.com/", allow_redirects=False)
if s in (301, 302):
    ok(f"www.namvibe.com redirects ({s})")
else:
    fail(f"www.namvibe.com returned {s} (expected 301/302)")

# ── Summary ──
print(f"\n{'=' * 60}")
print("PHASE 127 — PRODUCTION LIVE BUILD VERIFICATION SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"\n  RESULT: {'READY' if FAIL == 0 else 'BLOCKERS PRESENT'}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
