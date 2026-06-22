#!/usr/bin/env python3
"""
Phase 132 - Voice note final reality checks.
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


js = read_file("static/js/namvibe_messages_pro.js") + read_file("static/js/message_composer.js")
html = read_file("templates/messages/thread.html") + read_file("templates/messages/inbox.html")
css = read_file("static/css/namvibe_messages_pro.css") + read_file("static/css/chat.css")
notifications = read_file("services/notification_engine.py") + read_file("services/notification_service.py") + read_file("services/socket_events.py")
all_text = js + html + css + notifications

print("=" * 60)
print("PHASE 132 - VOICE NOTE REALITY")
print("=" * 60)

checks = [
    ("press-hold handlers", r"mousedown|pointerdown|touchstart", False),
    ("pointerdown/touchstart", r"pointerdown|touchstart", False),
    ("pointerup/touchend", r"pointerup|touchend|mouseup", False),
    ("cancel gesture", r"cancelVoiceRecording|slideCancel|data-voice-control=\"cancel\"|voice-cancel", False),
    ("upload progress", r"upload\.onprogress|vp-progress|progress", False),
    ("preview player", r"voice-note-audio|showVoicePreview|<audio", False),
    ("retry upload", r"vp-retry|retryBtn|retry upload", False),
    ("waveform", r"waveform|voice-wave|generateWaveformBars|renderWaveform", False),
    ("playback speed", r"vp-speed|playbackSpeed|playback_speed", False),
    ("voice note received notification", r"voice_note_received", False),
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
print("PHASE 132 - VOICE NOTE REALITY SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")

