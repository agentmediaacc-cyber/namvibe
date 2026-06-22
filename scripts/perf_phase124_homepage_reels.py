#!/usr/bin/env python3
"""
Phase 124 — Homepage & Reels Performance Verification.

Requests / and /reels/ three times each, reports average/max latency.
Warns if homepage >1200ms or reels >1200ms.
"""

import os
import sys
import time
import urllib.request
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0

BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://localhost:5050")
TIMEOUT = 30
SAMPLES = 3
HOMEPAGE_WARN_MS = 1200
REELS_WARN_MS = 1200


def fetch(url, label):
    latencies = []
    for i in range(SAMPLES):
        started = time.perf_counter()
        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "Phase124-Perf/1.0")
            resp = urllib.request.urlopen(req, timeout=TIMEOUT)
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            latencies.append(latency_ms)
            print(f"  [{label}] attempt {i+1}: {latency_ms:>8.1f}ms  (HTTP {resp.status})")
        except Exception as e:
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            print(f"  [{label}] attempt {i+1}: {latency_ms:>8.1f}ms  ERROR: {str(e)[:60]}")
    return latencies


print("=" * 60)
print("PHASE 124 — PERFORMANCE VERIFICATION")
print(f"BASE: {BASE_URL}")
print("=" * 60)

# Homepage
print("\n--- Homepage (/) ---")
home_latencies = fetch(BASE_URL + "/", "home")
home_avg = sum(home_latencies) / max(len(home_latencies), 1)
home_max = max(home_latencies) if home_latencies else 0
print(f"  Homepage: avg={home_avg:.1f}ms  max={home_max:.1f}ms")

# Reels
print("\n--- Reels (/reels/) ---")
reels_latencies = fetch(BASE_URL + "/reels/", "reels")
reels_avg = sum(reels_latencies) / max(len(reels_latencies), 1)
reels_max = max(reels_latencies) if reels_latencies else 0
print(f"  Reels:    avg={reels_avg:.1f}ms  max={reels_max:.1f}ms")

# Report
print(f"\n{'=' * 60}")
print("PERFORMANCE REPORT")
print(f"{'=' * 60}")

issues = []

if home_max > HOMEPAGE_WARN_MS:
    msg = f"WARN: Homepage max latency {home_max:.0f}ms exceeds {HOMEPAGE_WARN_MS}ms threshold"
    print(f"  [WARN] {msg}")
    issues.append(msg)
else:
    print(f"  [PASS] Homepage max {home_max:.0f}ms < {HOMEPAGE_WARN_MS}ms threshold")
    PASS += 1

if reels_max > REELS_WARN_MS:
    msg = f"WARN: Reels max latency {reels_max:.0f}ms exceeds {REELS_WARN_MS}ms threshold"
    print(f"  [WARN] {msg}")
    issues.append(msg)
else:
    print(f"  [PASS] Reels max {reels_max:.0f}ms < {REELS_WARN_MS}ms threshold")
    PASS += 1

print(f"  PASS: {PASS}")
print(f"  WARN: {len(issues)}")
if issues:
    for i in issues:
        print(f"    - {i}")

print(f"\n  overall: {'OK' if len(issues) == 0 else 'CHECK_WARNINGS'}")
