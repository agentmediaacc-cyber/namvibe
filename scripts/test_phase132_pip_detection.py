#!/usr/bin/env python3
"""
Phase 132 - Picture-in-Picture detection cleanup.
Detects the real PiP implementation across messaging and call assets.
"""

import os
import re

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


assets = {
    "messages_js": read_file("static/js/namvibe_messages_pro.js"),
    "calls_js": read_file("static/js/calls.js"),
    "calls_pro_js": read_file("static/js/namvibe_calls_pro.js"),
    "webrtc_js": read_file("static/js/webrtc_calls.js"),
    "call_overlay": read_file("templates/calls/call_overlay.html"),
    "calls_css": read_file("static/css/calls.css"),
    "messages_css": read_file("static/css/namvibe_messages_pro.css"),
}
all_text = "\n".join(assets.values())

print("=" * 60)
print("PHASE 132 - PICTURE-IN-PICTURE DETECTION")
print("=" * 60)

checks = [
    ("wirePiP function", r"function\s+wirePiP", False),
    ("requestPictureInPicture", r"requestPictureInPicture", False),
    ("document.pictureInPictureElement", r"document\.pictureInPictureElement", False),
    ("exitPictureInPicture", r"exitPictureInPicture", False),
    ("nv-call-minimized fallback class", r"nv-call-minimized", False),
    ("restoreCall function", r"function\s+restoreCall|restoreCall", False),
    ("minimizeCall function", r"function\s+minimizeCall|minimizeCall", False),
    ("floating/minimized fallback", r"floating|minimized|minimizeCall", False),
    ("PiP button hook", r"pip-btn|data-pip-btn|data-minimize-call", True),
]

for label, pattern, soft in checks:
    found = re.search(pattern, all_text, re.IGNORECASE) is not None
    if found:
        ok(label)
    elif soft:
        warn(label)
    else:
        fail(f"{label} missing")

print(f"\n{'=' * 60}")
print("PHASE 132 - PICTURE-IN-PICTURE DETECTION SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")

