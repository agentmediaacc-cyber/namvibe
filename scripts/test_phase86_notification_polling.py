"""Verify notification badge polling interval and guards."""

import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0

def check(name, condition):
    global PASS, FAIL
    if condition:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name}")
        FAIL += 1

print("Phase 86: Notification Polling")

js_path = "static/js/namvibe_global_badges.js"
with open(js_path) as f:
    js = f.read()

check("POLL_INTERVAL is 60000ms", "POLL_INTERVAL = 60000" in js)
check("POLL_INTERVAL not 20000ms", "POLL_INTERVAL = 20000" not in js)
check("timerGuard exists", "timerGuard" in js)
check("timerGuard prevents multiple timers", "if (timerGuard) return;" in js)
check("refreshBadge function exists", "function refreshBadge" in js)
check("socket.on notification:new uses refreshBadge", js.count("refreshBadge()") >= 3)
check("one socket manager (io() called once)", js.count("io()") == 1 or js.count("NamVibeSocket") > 0)

print(f"\nPhase 86 Notification Polling: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
