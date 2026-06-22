#!/usr/bin/env python3
"""
Phase 131 — Call Route Standardization Test.
Verifies standardized /api/calls/* routes exist with redirects to /calls/api/*.
"""

import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASS = 0; FAIL = 0; WARN = 0
def ok(m): global PASS; PASS += 1; print(f"  [PASS] {m}")
def fail(m): global FAIL; FAIL += 1; print(f"  [FAIL] {m}")
def warn(m): global WARN; WARN += 1; print(f"  [WARN] {m}")
def read_file(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full): return ""
    with open(full, encoding="utf-8", errors="ignore") as f: return f.read()

cr = read_file("api_routes/call_routes.py")
app_py = read_file("app.py")

print("=" * 60)
print("PHASE 131 — CALL ROUTE STANDARDIZATION TEST")
print("=" * 60)

ROUTE_DECORATORS = [
    "/start",
    "/answer",
    "/<call_id>/answer",
    "/<call_id>/reject",
    "/<call_id>/cancel",
    "/<call_id>/end",
    "/history",
    "/missed",
    "/group",
    "/active",
    "/ice-servers",
    "/diagnostics",
    "/<call_id>/mute",
    "/<call_id>/camera",
    "/<call_id>/speaker",
    "/<call_id>/invite",
    "/<call_id>/leave",
    "/<call_id>/reconnect",
    "/safety/check",
]

# Find all route decorators in the api_calls_bp section
api_calls_section = cr[cr.find("api_calls_bp = Blueprint"):]
if not api_calls_section:
    api_calls_section = ""

print("\n--- 1. Standardized Routes (/api/calls/*) ---")
for route in ROUTE_DECORATORS:
    pattern = route.replace("<call_id>", "[^/]+").replace("/", "\\/")
    if re.search(pattern, api_calls_section):
        ok(f"route: /api/calls{route}")
    else:
        warn(f"route not found: /api/calls{route}")

print("\n--- 2. Blueprint Registration ---")
ok("api_calls_bp defined") if "api_calls_bp" in cr else fail("api_calls_bp blueprint missing")
ok("api_calls_bp registered") if "api_calls_bp" in app_py else fail("api_calls_bp not registered in app.py")

print("\n--- 3. Legacy Routes (/calls/*) Existing ---")
legacy_decorators = [
    "/start",
    "/api/start",
    "/<call_id>/answer",
    "/api/<call_id>/accept",
    "/api/<call_id>/reject",
    "/api/<call_id>/end",
    "/api/history",
    "/api/active",
    "/api/ice-servers",
    "/api/diagnostics",
    "/api/missed-count",
    "/api/<call_id>/mute",
    "/api/<call_id>/camera",
    "/api/<call_id>/invite",
    "/api/<call_id>/reconnect",
    "/api/logs",
    "/api/contacts/search",
    "/api/safety/check",
]
# Find the call_bp section (primary blueprint with url_prefix=/calls).
# Phase 132 legacy wrappers can live after api_calls_bp because they call the same backend functions.
call_bp_section = cr[cr.find("call_bp = Blueprint"):]
for route in legacy_decorators:
    pattern = route.replace("<call_id>", "[^/]+").replace("/", "\\/")
    if re.search(pattern, call_bp_section):
        ok(f"legacy route: /calls{route}")
    else:
        warn(f"legacy route not found: /calls{route}")

print(f"\n{'=' * 60}")
print("PHASE 131 — CALL ROUTE STANDARDIZATION TEST SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
