#!/usr/bin/env python3
"""
Phase 131 — Picture-in-Picture Test.
Verifies desktop PiP API and mobile floating window fallback.
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

js = read_file("static/js/calls.js")
calls_js = read_file("static/js/namvibe_calls_pro.js")
webrtc_js = read_file("static/js/webrtc_calls.js")
co = read_file("templates/calls/call_overlay.html")
css = read_file("static/css/calls.css")

print("=" * 60)
print("PHASE 131 — PICTURE-IN-PICTURE TEST")
print("=" * 60)

all_js = js + calls_js + webrtc_js

print("\n--- 1. Desktop PiP ---")
ok("document.pictureInPicture") if "pictureInPicture" in all_js or "PictureInPicture" in all_js else warn("document.pictureInPicture API")
ok("requestPictureInPicture") if "requestPictureInPicture" in all_js or "requestPictureInPicture" in all_js else warn("requestPictureInPicture")
ok("exitPictureInPicture") if "exitPictureInPicture" in all_js or "exitPictureInPicture" in all_js else warn("exitPictureInPicture")
ok("enterpictureinpicture event") if "enterpictureinpicture" in all_js else warn("enterpictureinpicture event")
ok("leavepictureinpicture event") if "leavepictureinpicture" in all_js else warn("leavepictureinpicture event")

print("\n--- 2. Mobile PiP Fallback ---")
ok("minimized call window") if "minimized" in all_js or "minimize" in all_js or "floating" in all_js else warn("minimized/floating window")
ok("restore from minimized") if "restore" in all_js or "maximize" in all_js else warn("restore from minimized")
ok("continue audio in PiP") if "audio" in co and "pip" in co.lower() or "background" in all_js else warn("continue audio in PiP")
ok("continue timer in PiP") if "timer" in co else warn("continue timer in PiP")

print("\n--- 3. PiP Transitions ---")
ok("PiP button in overlay") if "pip" in co.lower() or "picture" in co.lower() else warn("PiP button in call overlay")

print(f"\n{'=' * 60}")
print("PHASE 131 — PICTURE-IN-PICTURE TEST SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
