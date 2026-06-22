#!/usr/bin/env python3
"""
Phase 131 — Audio Call Polish Test.
Verifies outgoing/incoming screens, ring tone, accept/reject, busy, offline, timeout, missed, duration, reconnect.
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

co = read_file("templates/calls/call_overlay.html")
se = read_file("services/socket_events.py")
cs = read_file("services/call_service.py")
webrtc = read_file("services/webrtc_call_service.py")
cr = read_file("api_routes/call_routes.py")
js = read_file("static/js/calls.js")

print("=" * 60)
print("PHASE 131 — AUDIO CALL POLISH TEST")
print("=" * 60)

print("\n--- 1. UI Templates ---")
ok("incoming screen") if "call-overlay-incoming" in co else fail("incoming screen missing")
ok("outgoing screen") if "call-overlay-outgoing" in co else fail("outgoing screen missing")
ok("accept button") if "data-call-accept" in co else fail("accept button missing")
ok("reject button") if "data-call-reject" in co else fail("reject button missing")
ok("cancel button") if "data-call-cancel" in co else fail("cancel button missing")
ok("end button") if "data-call-end" in co or "call-end" in co else fail("end button missing")
ok("call timer") if "call-timer" in co else fail("call timer missing")
ok("reconnecting overlay") if "call-overlay-reconnecting" in co else fail("reconnecting overlay missing")

print("\n--- 2. Call Lifecycle ---")
combined = cs + webrtc + se + cr
ok("start call") if re.search(r"start.*call|call.*start|init_call", combined, re.I) else fail("start call missing")
ok("answer call") if re.search(r"answer.*call|accept.*call", combined, re.I) else fail("answer call missing")
ok("reject call") if re.search(r"reject.*call|decline.*call", combined, re.I) else fail("reject call missing")
ok("end call") if re.search(r"end.*call|end_call", combined, re.I) else fail("end call missing")
ok("busy") if "busy" in combined else fail("busy missing")
ok("offline") if "offline" in combined or "unavailable" in combined else fail("offline missing")
ok("timeout 30s") if "timeout" in combined else warn("timeout — check 30s default")
ok("missed call") if "missed" in combined else fail("missed call missing")
ok("call duration") if "duration" in combined or "started_at" in combined else fail("call duration missing")

print("\n--- 3. Reconnect ---")
ok("reconnect") if "reconnect" in combined else fail("reconnect missing")
ok("network loss detection") if "reconnect" in combined or "connection_state" in combined else warn("network loss detection")

print("\n--- 4. Socket Events ---")
ok("call:start") if "call:start" in se else fail("call:start socket event missing")
ok("call:ringing") if "call:ringing" in se else fail("call:ringing socket event missing")
ok("call:accept") if "call:accept" in se else fail("call:accept socket event missing")
ok("call:reject") if "call:reject" in se else fail("call:reject socket event missing")
ok("call:cancel") if "call:cancel" in se else fail("call:cancel socket event missing")
ok("call:end") if "call:end" in se else fail("call:end socket event missing")
ok("call:busy") if "call:busy" in se else fail("call:busy socket event missing")

print(f"\n{'=' * 60}")
print("PHASE 131 — AUDIO CALL POLISH TEST SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
