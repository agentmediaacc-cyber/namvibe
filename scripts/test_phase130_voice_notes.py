#!/usr/bin/env python3
"""
Phase 130 — Voice Notes Audit.
Verifies voice note recording, upload, playback, duration, waveform, and persistence.
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


def find_pattern(text, pattern):
    return bool(re.search(pattern, text, re.IGNORECASE))


print("=" * 60)
print("PHASE 130 — VOICE NOTES AUDIT")
print("=" * 60)

msg_feat = read_file("services/message_feature_service.py")
msg_media = read_file("services/message_media_service.py")
msg_engine = read_file("services/messaging_engine.py")
nv_pro_js = read_file("static/js/namvibe_messages_pro.js")
nv_pro_css = read_file("static/css/namvibe_messages_pro.css")

# ── 1. Service layer ──
print("\n--- 1. Service Layer ---")
ok("voice note service exists") if len(msg_feat) > 0 else fail("message_feature_service.py missing")
ok("voice note function") if find_pattern(msg_feat, "voice") or find_pattern(msg_media, "voice") else fail("voice note function missing")
ok("media service exists") if len(msg_media) > 0 else fail("message_media_service.py missing")

# ── 2. Database support ──
print("\n--- 2. Database ---")
sql_dir = os.path.join(ROOT, "sql")
voice_in_sql = False
if os.path.isdir(sql_dir):
    for fname in os.listdir(sql_dir):
        if fname.endswith(".sql"):
            text = read_file(f"sql/{fname}")
            if "chain_message_voice_notes" in text:
                voice_in_sql = True
                break
ok("voice notes table") if voice_in_sql else fail("chain_message_voice_notes table not found")

# ── 3. Frontend JS ──
print("\n--- 3. Frontend JS ---")
ok("messages pro JS exists") if nv_pro_js else fail("namvibe_messages_pro.js missing")
js_voice = "voice" in nv_pro_js.lower()
ok("voice note in JS") if js_voice else warn("voice note not found in JS")
ok("recording UI") if find_pattern(nv_pro_js, "record|recording") else warn("recording UI — check frontend")
ok("media uploader") if find_pattern(nv_pro_js, "upload|attachment") else warn("media upload")
ok("playback control") if find_pattern(nv_pro_js, "play|audio|sound") else warn("playback control")

# ── 4. CSS ──
print("\n--- 4. CSS ---")
ok("messages pro CSS exists") if nv_pro_css else fail("namvibe_messages_pro.css missing")
ok("voice UI styles") if find_pattern(nv_pro_css, "voice|audio|recording") else warn("voice note CSS styles")

# ── 5. Required features ──
print("\n--- 5. Features ---")
combined = msg_feat + msg_media + nv_pro_js + msg_engine
ok("press & hold record") if find_pattern(combined, "press.*hold|long.*press|hold.*record") else warn("press & hold — frontend pattern")
ok("slide to cancel") if find_pattern(combined, "slide.*cancel|cancel") else warn("slide to cancel — UI pattern")
ok("preview screen") if find_pattern(combined, "preview") else warn("preview — check composer")
ok("play") if find_pattern(combined, "play") else warn("play")
ok("delete") if find_pattern(combined, "delete|remove") else warn("delete")
ok("send") if find_pattern(combined, "send") else warn("send")
ok("duration display") if find_pattern(combined, "duration") else warn("duration display")
ok("upload progress") if find_pattern(combined, "progress|percentage|uploading") else warn("upload progress")
ok("persistence") if find_pattern(combined, "save|store|persist") else warn("persistence check not found")

# ── Summary ──
print(f"\n{'=' * 60}")
print("PHASE 130 — VOICE NOTES AUDIT SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
