#!/usr/bin/env python3
"""
Test Part 4 – Realtime presence (static checks).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

FAILED = False
def check(label, ok, detail=""):
    global FAILED
    if not ok: FAILED = True
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  | {detail}" if detail else ""))

print("=" * 60)
print("Part 4 – Realtime Presence")
print("=" * 60)

# 1. JS file exists and has expected functions
print("\n--- 1. JS file ---")
js_path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "realtime_presence.js")
js_exists = os.path.isfile(js_path)
check("realtime_presence.js exists", js_exists)
if js_exists:
    with open(js_path) as f:
        content = f.read()
    check("Has updateOnlineDot", "updateOnlineDot" in content)
    check("Has showTypingIndicator", "showTypingIndicator" in content)
    check("Has hideTypingIndicator", "hideTypingIndicator" in content)
    check("Has updateSeenTick", "updateSeenTick" in content)
    check("Has showCallingIndicator", "showCallingIndicator" in content)
    check("Has hideCallingIndicator", "hideCallingIndicator" in content)
    check("Listens to user:online", "user:online" in content)
    check("Listens to user:offline", "user:offline" in content)
    check("Listens to message:typing", "message:typing" in content)
    check("Listens to message:seen", "message:seen" in content)
    check("Listens to call:ringing", "call:ringing" in content)
    check("Listens to call:missed", "call:missed" in content)

# 2. CSS file exists
print("\n--- 2. CSS file ---")
css_path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "realtime_presence.css")
css_exists = os.path.isfile(css_path)
check("realtime_presence.css exists", css_exists)
if css_exists:
    with open(css_path) as f:
        css_content = f.read()
    check("Has .presence-typing", ".presence-typing" in css_content)
    check("Has .presence-seen", ".presence-seen" in css_content)
    check("Has .presence-calling", ".presence-calling" in css_content)
    check("Has .online-dot", ".online-dot" in css_content)
    check("Has .presence-recording", ".presence-recording" in css_content)

# 3. Base template includes CSS
print("\n--- 3. Template includes ---")
tmpl_path = os.path.join(os.path.dirname(__file__), "..", "templates", "base.html")
if os.path.isfile(tmpl_path):
    with open(tmpl_path) as f:
        tmpl = f.read()
    check("Includes realtime_presence.css", "realtime_presence.css" in tmpl)
    check("Includes realtime_presence.js", "realtime_presence.js" in tmpl)
else:
    check("base.html exists", False)

# 4. Messages template has presence attributes
print("\n--- 4. Messages template ---")
msg_tmpl = os.path.join(os.path.dirname(__file__), "..", "templates", "messages", "index.html")
if os.path.isfile(msg_tmpl):
    with open(msg_tmpl) as f:
        msg = f.read()
    check("Has data-online-dot", "data-online-dot" in msg)
    check("Has data-typing-indicator", "data-typing-indicator" in msg)
    check("Has data-calling-indicator", "data-calling-indicator" in msg)
    check("Has .presence-typing class", "presence-typing" in msg)
    check("Has .presence-calling class", "presence-calling" in msg)
    check("Has .presence-seen class", "presence-seen" in msg)
else:
    check("Messages template exists", False)

print("\n" + "=" * 60)
if FAILED:
    print("RESULT: SOME TESTS FAILED")
    sys.exit(1)
else:
    print("RESULT: ALL TESTS PASSED")
