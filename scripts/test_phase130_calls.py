#!/usr/bin/env python3
"""
Phase 130 — Audio & Video Call Audit.
Verifies call lifecycle, signaling, database, history, and WebRTC infrastructure.
"""

import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASS = 0; FAIL = 0; WARN = 0


def ok(m): global PASS; PASS += 1; print(f"  [PASS] {m}")
def fail(m): global FAIL; FAIL += 1; print(f"  [FAIL] {m}")
def warn(m): global WARN; WARN += 1; print(f"  [WARN] {m}")


def read_file(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full): return ""
    with open(full, encoding="utf-8", errors="ignore") as f:
        return f.read()


def file_exists(path):
    return os.path.exists(os.path.join(ROOT, path))


print("=" * 60)
print("PHASE 130 — CALLS AUDIT")
print("=" * 60)

call_r = read_file("api_routes/call_routes.py")
grp_r = read_file("api_routes/group_call_routes.py")
webrtc = read_file("services/webrtc_call_service.py")
turn = read_file("services/webrtc_turn_service.py")
call_svc = read_file("services/call_service.py")
call_hist = read_file("services/call_history_service.py")
call_life = read_file("services/call_lifecycle_service.py")
call_perm = read_file("services/call_permission_service.py")
call_feat = read_file("services/call_feature_service.py")
callkit = read_file("services/callkit_service.py")
grp_svc = read_file("services/group_call_service.py")
se = read_file("services/socket_events.py")
calls_js = read_file("static/js/calls.js")
calls_pro_js = read_file("static/js/namvibe_calls_pro.js")
webrtc_js = read_file("static/js/webrtc_calls.js")
grp_js = read_file("static/js/group_calls.js")

# ── 1. Route files ──
print("\n--- 1. Route Files ---")
for f in ["api_routes/call_routes.py", "api_routes/group_call_routes.py"]:
    ok(f"{f} exists") if file_exists(f) else fail(f"{f} missing")

# ── 2. Service files ──
print("\n--- 2. Service Files ---")
svcs = ["services/call_service.py", "services/webrtc_call_service.py",
        "services/webrtc_turn_service.py", "services/call_history_service.py",
        "services/call_lifecycle_service.py", "services/call_permission_service.py",
        "services/call_feature_service.py", "services/callkit_service.py",
        "services/group_call_service.py"]
for s in svcs:
    ok(f"{s} exists") if file_exists(s) else fail(f"{s} missing")

# ── 3. Call lifecycle ──
print("\n--- 3. Call Lifecycle ---")
combined = call_r + webrtc + call_svc + call_life + se
ok("start call") if "start" in combined.lower() and "call" in combined.lower() else fail("start call missing")
ok("incoming call") if "incoming" in combined.lower() or "ringing" in combined.lower() else fail("incoming call missing")
ok("accept") if "accept" in combined.lower() else fail("accept missing")
ok("reject") if "reject" in combined.lower() else fail("reject missing")
ok("cancel") if "cancel" in combined.lower() else fail("cancel missing")
ok("end") if "'end'" in combined or "'call:end'" in combined or "end_call" in combined else fail("end missing")
ok("busy") if "busy" in combined.lower() else fail("busy missing")
ok("timeout") if "timeout" in combined.lower() else fail("timeout missing")
ok("missed call") if "missed" in combined.lower() else fail("missed call missing")

# ── 4. WebRTC signaling ──
print("\n--- 4. WebRTC Signaling ---")
ok("SDP offer") if "offer" in webrtc.lower() or "call:offer" in se else fail("SDP offer missing")
ok("SDP answer") if "answer" in webrtc.lower() or "call:answer" in se else fail("SDP answer missing")
ok("ICE candidates") if ("ice" in (webrtc + se).lower() and "candidate" in (webrtc + se).lower()) else fail("ICE candidates missing")
ok("TURN servers") if "turn" in turn.lower() or "stun" in turn.lower() else fail("TURN servers missing")
ok("reconnect") if "reconnect" in combined.lower() else fail("reconnect missing")

# ── 5. Call history ──
print("\n--- 5. Call History ---")
ok("history API") if "history" in call_r.lower() + call_hist.lower() else fail("history API missing")
ok("call logs") if "log" in call_hist.lower() or "chain_call_logs" in call_hist else fail("call logs missing")
ok("call duration") if "duration" in combined.lower() or "started_at" in combined.lower() else fail("call duration missing")
ok("missed count") if "missed" in call_r.lower() and "count" in call_r.lower() else fail("missed count API missing")

# ── 6. Video features ──
print("\n--- 6. Video Features ---")
ok("camera toggle") if "camera" in webrtc.lower() + se.lower() else fail("camera toggle missing")
ok("mic mute") if "mute" in webrtc.lower() + se.lower() else fail("mic mute missing")
ok("switch camera") if "switch" in combined.lower() and "camera" in combined.lower() else fail("switch camera missing")
ok("speaker") if "speaker" in combined.lower() else fail("speaker toggle missing")
ok("picture-in-picture") if "picture" in combined.lower() or "pip" in combined.lower() else warn("picture-in-picture")

# ── 7. Group calls ──
print("\n--- 7. Group Calls ---")
ok("group call routes") if grp_r else fail("group call routes missing")
ok("group call service") if grp_svc else fail("group call service missing")
ok("group-call:create") if "group-call:create" in se else fail("group-call:create missing")
ok("group-call:join") if "group-call:join" in se else fail("group-call:join missing")
ok("group-call:leave") if "group-call:leave" in se else fail("group-call:leave missing")
ok("group call DB tables") if "chain_group_calls" in read_file("sql/phase44_group_calls.sql") else fail("group call DB tables missing")

# ── 8. Frontend JS ──
print("\n--- 8. Frontend JS ---")
for j in ["static/js/calls.js", "static/js/namvibe_calls_pro.js",
          "static/js/webrtc_calls.js", "static/js/group_calls.js"]:
    ok(f"{j} exists") if file_exists(j) else fail(f"{j} missing")

# ── 9. Templates ──
print("\n--- 9. Templates ---")
for t in ["templates/calls/call_overlay.html", "templates/calls/group_call.html"]:
    ok(f"{t} exists") if file_exists(t) else fail(f"{t} missing")

# ── 10. Database tables ──
print("\n--- 10. Database Tables ---")
sql_all = ""
sql_dir = os.path.join(ROOT, "sql")
if os.path.isdir(sql_dir):
    for f in os.listdir(sql_dir):
        if f.endswith(".sql"):
            sql_all += read_file(f"sql/{f}")
for tbl in ["chain_calls", "chain_call_logs", "chain_call_participants",
            "chain_group_calls", "chain_group_call_participants",
            "chain_call_notifications", "chain_call_quality_events",
            "chain_call_sessions", "chain_call_events"]:
    if tbl in sql_all:
        ok(f"table: {tbl}")
    else:
        warn(f"table: {tbl} not found in SQL")

# ── Summary ──
print(f"\n{'=' * 60}")
print("PHASE 130 — CALLS AUDIT SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
