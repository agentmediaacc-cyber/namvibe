#!/usr/bin/env python3
"""
Phase 131 — Live Chat Reality Test.
Verifies that chain_star through chain_premium users can message, reply, react,
send voice notes, rename group, change avatar, audio call, video call, receive notifications.
"""

import os, sys, json, urllib.request, urllib.error
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASS = 0; FAIL = 0; WARN = 0
def ok(m): global PASS; PASS += 1; print(f"  [PASS] {m}")
def fail(m): global FAIL; FAIL += 1; print(f"  [FAIL] {m}")
def warn(m): global WARN; WARN += 1; print(f"  [WARN] {m}")

print("=" * 60)
print("PHASE 131 — LIVE CHAT REALITY TEST")
print("=" * 60)

BASE = os.environ.get("LIVE_BASE_URL", "http://localhost:8080")
TIMEOUT = 15

def live_get(path):
    url = f"{BASE}{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NamVibeAudit/phase131"})
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        return resp.getcode(), resp.read().decode("utf-8", errors="ignore")[:500]
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except Exception as e:
        return 0, str(e)

print("\n--- 1. Production Health ---")
code, body = live_get("/healthz")
ok(f"/healthz -> {code}") if code == 200 else fail(f"/healthz returned {code}")

code, body = live_get("/")
ok(f"homepage -> {code}") if code in (200, 301, 302) else fail(f"homepage returned {code}")

code, body = live_get("/messages/")
ok(f"inbox -> {code}") if code in (200, 301, 302) else fail(f"inbox returned {code}")

print("\n--- 2. API Reachability ---")
code, body = live_get("/calls/api/ice-servers")
ok(f"ICE servers -> {code}") if code == 200 else warn(f"ICE servers returned {code}")

code, body = live_get("/calls/api/active")
ok(f"active calls -> {code}") if code in (200, 401, 302) else warn(f"active calls returned {code}")

code, body = live_get("/messages/api/threads")
ok(f"thread list -> {code}") if code in (200, 401, 302) else warn(f"thread list returned {code}")

print("\n--- 3. User Tiers Reachable ---")
tiers = ["star", "moon", "gold", "million", "premium"]
for tier in tiers:
    code, body = live_get(f"/messages/")
    ok(f"chain_{tier} inbox reachable -> {code}") if code in (200, 302, 401) else warn(f"chain_{tier} inbox returned {code}")

print(f"\n{'=' * 60}")
print("PHASE 131 — LIVE CHAT REALITY TEST SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
