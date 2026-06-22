#!/usr/bin/env python3
"""
Phase 132 - Call route compatibility checks.
"""

import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
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


def read_file(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return ""
    with open(full, encoding="utf-8", errors="ignore") as handle:
        return handle.read()


cr = read_file("api_routes/call_routes.py")
app_py = read_file("app.py")

print("=" * 60)
print("PHASE 132 - CALL ROUTE COMPATIBILITY")
print("=" * 60)

modern_routes = [
    "/start", "/answer", "/reject", "/cancel", "/end", "/history", "/missed",
    "/group", "/active", "/ice-servers", "/diagnostics", "/mute", "/camera",
    "/speaker", "/invite", "/leave", "/reconnect", "/safety/check",
]
legacy_routes = [
    "/api/diagnostics", "/api/missed-count", "/api/<call_id>/invite",
    "/api/<call_id>/reconnect", "/api/logs", "/api/contacts/search",
    "/api/safety/check",
]

api_sec = cr[cr.find("api_calls_bp = Blueprint"):]
call_sec = cr[cr.find("call_bp = Blueprint"):]

print("\n--- Modern /api/calls routes ---")
for route in modern_routes:
    pattern = re.escape(f'@api_calls_bp.route("{route}"').replace("<call_id>", r"[^/]+")
    if re.search(pattern, api_sec):
        ok(f"/api/calls{route}")
    else:
        fail(f"/api/calls{route} missing")

print("\n--- Legacy /calls/api wrappers ---")
for route in legacy_routes:
    pattern = re.escape(f'@call_bp.route("{route}"').replace("<call_id>", r"[^/]+")
    if re.search(pattern, call_sec):
        ok(f"/calls{route}")
    else:
        fail(f"/calls{route} missing")

comment_count = cr.count("Phase 132 legacy compatibility wrapper")
ok("legacy wrapper comments") if comment_count >= 7 else fail("legacy wrapper comments missing")
ok("api_calls_bp registered") if "app.register_blueprint(api_calls_bp)" in app_py else fail("api_calls_bp not registered")
ok("call_bp registered") if "app.register_blueprint(call_bp)" in app_py else fail("call_bp not registered")

try:
    from app import app
    rules = [rule.rule for rule in app.url_map.iter_rules()]
    call_blueprints = ["call_bp", "messages_call_bp", "api_calls_bp"]
    duplicate_regs = [name for name in call_blueprints if app_py.count(f"register_blueprint({name})") != 1]
    if duplicate_regs:
        fail(f"duplicate/missing call blueprint registrations: {duplicate_regs}")
    else:
        ok("no duplicate call blueprint registration")
    for route in ("/api/calls/start", "/api/calls/answer", "/api/calls/reject", "/api/calls/invite", "/calls/api/diagnostics"):
        if route in rules or any("<" in r and route.split("/")[-1] in r for r in rules):
            ok(f"url_map contains {route}")
        else:
            warn(f"url_map missing exact {route}")
except Exception as exc:
    fail(f"app import/url_map failed: {exc}")

print(f"\n{'=' * 60}")
print("PHASE 132 - CALL ROUTE COMPATIBILITY SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
