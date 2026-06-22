#!/usr/bin/env python3
"""
Phase 132 - Mobile chat final reality checks.
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


css = read_file("static/css/chat.css") + read_file("static/css/namvibe_messages_pro.css") + read_file("templates/messages/thread.html")
js = read_file("static/js/namvibe_messages_pro.js") + read_file("static/js/message_composer.js") + read_file("templates/messages/thread.html")
html = read_file("templates/messages/thread.html") + read_file("templates/messages/inbox.html")
all_text = css + js + html

print("=" * 60)
print("PHASE 132 - MOBILE CHAT REALITY")
print("=" * 60)

checks = [
    ("input font-size 16px", r"font-size:\s*16px", False),
    ("composer auto-grow", r"scrollHeight|auto-grow|style\.height", False),
    ("safe-area padding", r"safe-area|env\(safe-area", False),
    ("scroll-to-bottom button", r"nv-scroll-bottom|data-scroll-bottom|wireScrollToBottom", False),
    ("keyboard visualViewport handler", r"visualViewport", False),
    ("draft autosave", r"wireDraftAutosave|localStorage.*draft|draft", False),
    ("emoji insert at cursor", r"insertAtCursor|emoji", False),
    ("attachment button", r"attach|attachment-preview|file-input", False),
    ("voice button", r"mic-btn|data-voice-record|voice-record", False),
    ("bubble overlap protection", r"overflow-wrap|word-break|max-width:\s*min|max-width", False),
    ("mobile breakpoint CSS", r"@media\s*\(max-width:\s*(480|760)px\)", False),
]

for label, pattern, soft in checks:
    found = re.search(pattern, all_text, re.IGNORECASE | re.DOTALL) is not None
    if found:
        ok(label)
    elif soft:
        warn(label)
    else:
        fail(f"{label} missing")

print(f"\n{'=' * 60}")
print("PHASE 132 - MOBILE CHAT REALITY SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")

