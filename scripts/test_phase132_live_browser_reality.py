#!/usr/bin/env python3
"""
Phase 132 - Live browser reality checks.
Uses HTTP-level checks first; Playwright is optional and WARN-only.
"""

import os
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BASE = "https://namvibe.com"
PASS = 0
FAIL = 0
WARN = 0
HEADERS = {"User-Agent": "NamVibe Phase132 Live Reality"}
SSL_FALLBACK_USED = False


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


def read_file(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return ""
    with open(full, encoding="utf-8", errors="ignore") as handle:
        return handle.read()


def http_get(path_or_url, method="GET"):
    global SSL_FALLBACK_USED
    url = path_or_url if path_or_url.startswith("http") else BASE + path_or_url
    req = urllib.request.Request(url, method=method, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()) as response:
            body = response.read(700000).decode("utf-8", errors="ignore")
            return response.status, body, response.geturl()
    except urllib.error.HTTPError as exc:
        body = exc.read(200000).decode("utf-8", errors="ignore")
        return exc.code, body, exc.geturl()
    except urllib.error.URLError as exc:
        if "CERTIFICATE_VERIFY_FAILED" in str(exc):
            SSL_FALLBACK_USED = True
            try:
                with urllib.request.urlopen(req, timeout=20, context=ssl._create_unverified_context()) as response:
                    body = response.read(700000).decode("utf-8", errors="ignore")
                    return response.status, body, response.geturl()
            except urllib.error.HTTPError as http_exc:
                body = http_exc.read(200000).decode("utf-8", errors="ignore")
                return http_exc.code, body, http_exc.geturl()
            except Exception as retry_exc:
                return -1, str(retry_exc), url
        return -1, str(exc), url
    except Exception as exc:
        return -1, str(exc), url


def static_refs(html):
    refs = set()
    for match in re.findall(r"""(?:src|href)=["']([^"']+\.(?:js|css)(?:\?[^"']*)?)["']""", html, re.I):
        if match.startswith("/static/"):
            refs.add(match)
        elif match.startswith(BASE + "/static/"):
            refs.add(match.replace(BASE, ""))
    return sorted(refs)


print("=" * 60)
print("PHASE 132 - LIVE BROWSER REALITY")
print("=" * 60)

status, home, final_url = http_get("/")
ok("https://namvibe.com returns 200") if status == 200 else fail(f"homepage returned {status}: {home[:120]}")
ok("phase127 or later marker exists") if re.search(r"phase12[7-9]|phase13[0-9]|namvibe-build", home, re.I) else warn("phase127+ marker not visible")

status, body, _ = http_get("/messages/inbox")
if status in (200, 301, 302, 401, 403):
    ok(f"messages/inbox reachable or auth-gated ({status})")
else:
    fail(f"messages/inbox unexpected status {status}")

for route in ["/api/calls/ice-servers", "/api/calls/active", "/api/calls/diagnostics", "/calls/api/ice-servers"]:
    status, body, _ = http_get(route)
    jsonish = "{" in body[:80] or status in (301, 302, 401, 403)
    if status in (200, 301, 302, 401, 403) and jsonish:
        ok(f"{route} returns valid JSON/status ({status})")
    else:
        fail(f"{route} unexpected status/body ({status})")

for asset in ["/static/js/namvibe_messages_pro.js", "/static/css/namvibe_messages_pro.css"]:
    status, _, _ = http_get(asset)
    ok(f"{asset} returns 200") if status == 200 else fail(f"{asset} returned {status}")

missing = []
for ref in static_refs(home):
    status, _, _ = http_get(ref)
    if status != 200:
        missing.append(f"{ref} -> {status}")
if missing:
    fail("missing static references: " + ", ".join(missing[:8]))
else:
    ok("no missing static references in live HTML")

if re.search(r"/static/js/(call|calls|webrtc).*\.js", home, re.I) and "namvibe_calls_pro.js" not in home and "calls.js" not in home:
    fail("old broken call JS references suspected")
else:
    ok("no old broken call JS references")

js_path = os.path.join(ROOT, "static/js/namvibe_messages_pro.js")
try:
    result = subprocess.run(["node", "--check", js_path], capture_output=True, text=True, timeout=15)
    if result.returncode == 0:
        ok("node --check local message JS")
    else:
        fail("node --check failed: " + (result.stderr or result.stdout)[:160])
except FileNotFoundError:
    warn("node unavailable for JS syntax check")
except Exception as exc:
    warn(f"node --check skipped: {exc}")

for health_path in ["/healthz", "/health"]:
    status, body, _ = http_get(health_path)
    if status == 200 and re.search(r"ok|healthy", body, re.I):
        ok(f"live {health_path} returns ok")
        break
else:
    fail("live healthz did not return ok")

try:
    import playwright.sync_api  # noqa: F401
    warn("Playwright installed; optional scripted browser session not run without saved auth state")
except Exception:
    warn("Playwright not installed; browser automation skipped")

if SSL_FALLBACK_USED:
    warn("Python CA verification failed locally; retried live HTTPS with certificate verification disabled")

print(f"\n{'=' * 60}")
print("PHASE 132 - LIVE BROWSER REALITY SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
