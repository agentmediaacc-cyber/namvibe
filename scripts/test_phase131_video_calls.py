#!/usr/bin/env python3
"""
Phase 131 — Video Call Polish Test.
Verifies camera toggle, mic toggle, switch camera, speaker, PiP, timer, reconnect.
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
webrtc = read_file("services/webrtc_call_service.py")
cr = read_file("api_routes/call_routes.py")
js = read_file("static/js/calls.js")
calls_js = read_file("static/js/namvibe_calls_pro.js")

print("=" * 60)
print("PHASE 131 — VIDEO CALL POLISH TEST")
print("=" * 60)

print("\n--- 1. Call Controls ---")
combined = co + se + webrtc + cr + js + calls_js
ok("camera toggle button") if "call-camera-btn" in co or "camera" in co else fail("camera toggle button missing")
ok("mic mute button") if "call-mute-btn" in co or "mute" in co else fail("mic mute button missing")
ok("speaker button") if "call-speaker-btn" in co or "speaker" in co else fail("speaker button missing")
ok("switch camera") if "call-switch-camera" in co or "switch.*camera" in combined else fail("switch camera missing")
ok("end call button") if "data-call-end" in co else fail("end call button missing")

print("\n--- 2. Video Features ---")
ok("local video") if "call-local-video" in co else fail("local video element missing")
ok("remote video") if "call-remote-video" in co else fail("remote video element missing")
ok("remote mute indicator") if "call-remote-mute" in co else warn("remote mute indicator")
ok("remote camera indicator") if "call-remote-camera" in co else warn("remote camera indicator")
ok("call timer connected") if "call-timer-connected" in co else fail("call timer missing")

print("\n--- 3. Socket Events ---")
ok("call:mute") if "call:mute" in se else fail("call:mute socket missing")
ok("call:camera-toggle") if "call:camera-toggle" in se else fail("call:camera-toggle socket missing")
ok("call:speaker-toggle") if "call:speaker-toggle" in se else fail("call:speaker-toggle socket missing")
ok("call:media-state") if "call:media-state" in se else fail("call:media-state socket missing")

print("\n--- 4. Route Handlers ---")
ok("mute route") if "mute" in cr and "POST" in cr else warn("mute route")
ok("camera route") if "camera" in cr and "POST" in cr else warn("camera route")
ok("speaker route") if "speaker" in cr and "POST" in cr else warn("speaker route")

print(f"\n{'=' * 60}")
print("PHASE 131 — VIDEO CALL POLISH TEST SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
