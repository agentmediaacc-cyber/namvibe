#!/usr/bin/env python3
"""
Phase 124 — Lightweight Browser-Style Route Smoke Test.

Requests critical app routes and reports status/latency.
Does not fail on auth redirects.
"""

import os
import sys
import time
import urllib.request
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0
WARN = 0

BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://localhost:5050")
TIMEOUT = 15

ROUTES = [
    ("/", "Homepage"),
    ("/reels/", "Reels"),
    ("/discover/", "Discover"),
    ("/stories/", "Stories"),
    ("/live/", "Live"),
    ("/wallet/", "Wallet"),
    ("/profile/", "Profile"),
    ("/inbox/", "Inbox"),
]

print("=" * 60)
print("PHASE 124 — ROUTE SMOKE TEST")
print(f"BASE: {BASE_URL}")
print("=" * 60)

for path, label in ROUTES:
    url = BASE_URL + path
    started = time.perf_counter()
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "Phase124-Smoke/1.0")
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        status = resp.status
        if status == 200:
            print(f"  [PASS] {label:20s} {path:20s} {status}   {latency_ms:>8.1f}ms")
            PASS += 1
        elif 300 <= status < 400:
            print(f"  [WARN] {label:20s} {path:20s} {status}   {latency_ms:>8.1f}ms  (redirect OK)")
            WARN += 1
        else:
            print(f"  [FAIL] {label:20s} {path:20s} {status}   {latency_ms:>8.1f}ms")
            FAIL += 1
    except urllib.error.HTTPError as e:
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        if e.code in (302, 301, 303, 307, 308):
            print(f"  [WARN] {label:20s} {path:20s} {e.code}   {latency_ms:>8.1f}ms  (auth redirect OK)")
            WARN += 1
        else:
            print(f"  [FAIL] {label:20s} {path:20s} {e.code}   {latency_ms:>8.1f}ms  {str(e)[:60]}")
            FAIL += 1
    except urllib.error.URLError as e:
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        print(f"  [FAIL] {label:20s} {path:20s} ERR    {latency_ms:>8.1f}ms  {str(e)[:60]}")
        FAIL += 1
    except Exception as e:
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        print(f"  [FAIL] {label:20s} {path:20s} ERR    {latency_ms:>8.1f}ms  {str(e)[:60]}")
        FAIL += 1

print(f"\n{'=' * 60}")
print(f"RESULTS:  PASS={PASS}  FAIL={FAIL}  WARN={WARN}")
print(f"{'=' * 60}")
sys.exit(0 if FAIL == 0 else 1)
