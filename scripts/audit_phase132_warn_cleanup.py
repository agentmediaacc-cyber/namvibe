#!/usr/bin/env python3
"""
Phase 132 - Final WARN cleanup audit.
"""

import os
import re
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
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


def run_script(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        fail(f"{path} missing")
        return ""
    result = subprocess.run([sys.executable, full], cwd=ROOT, capture_output=True, text=True, timeout=60)
    output = result.stdout + result.stderr
    if "[FAIL]" in output or result.returncode != 0:
        fail(f"{path} reports FAIL")
    else:
        ok(f"{path} passes without FAIL")
    return output


thread = read_file("templates/messages/thread.html")
css = read_file("static/css/namvibe_messages_pro.css") + read_file("templates/messages/thread.html")
js = read_file("static/js/namvibe_messages_pro.js")
cr = read_file("api_routes/call_routes.py")
notifications = read_file("services/notification_engine.py") + read_file("services/notification_service.py") + read_file("services/socket_events.py")

print("=" * 60)
print("PHASE 132 - WARN CLEANUP AUDIT")
print("=" * 60)

ok("scroll-to-bottom template exists") if "nv-scroll-bottom" in thread and "Scroll to latest messages" in thread else fail("scroll-to-bottom template missing")
ok("scroll-to-bottom CSS exists") if ".nv-scroll-bottom" in css and "44px" in css and "safe-area" in css else fail("scroll-to-bottom CSS missing")
ok("scroll-to-bottom JS exists") if "wireScrollToBottom" in js and "nv-scroll-bottom" in js and "MutationObserver" in js else fail("scroll-to-bottom JS missing")
ok("legacy call wrappers exist") if cr.count("Phase 132 legacy compatibility wrapper") >= 7 else fail("legacy call wrappers missing")

for route in ["/start", "/answer", "/reject", "/cancel", "/end", "/history", "/missed", "/group", "/active", "/ice-servers", "/diagnostics", "/mute", "/camera", "/speaker", "/invite", "/leave", "/reconnect", "/safety/check"]:
    if f'@api_calls_bp.route("{route}"' in cr:
        ok(f"modern call route {route}")
    else:
        fail(f"modern call route {route} missing")

for script in [
    "scripts/test_phase132_pip_detection.py",
    "scripts/test_phase132_voice_note_reality.py",
    "scripts/test_phase132_mobile_chat_reality.py",
    "scripts/test_phase132_call_route_compat.py",
]:
    run_script(script)

ok("live browser reality script exists") if os.path.exists(os.path.join(ROOT, "scripts/test_phase132_live_browser_reality.py")) else fail("live browser reality script missing")
ok("call route compatibility script exists") if os.path.exists(os.path.join(ROOT, "scripts/test_phase132_call_route_compat.py")) else fail("call route compatibility script missing")
tracked_text = js + css + cr + notifications
ok("Phase 131 WARN tracked") if all(term in tracked_text for term in ["nv-scroll-bottom", "Phase 132 legacy compatibility wrapper", "requestPictureInPicture", "voice_note_received"]) else warn("some Phase 131 WARN tracking markers absent")

print(f"\n{'=' * 60}")
print("PHASE 132 - WARN CLEANUP AUDIT SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
