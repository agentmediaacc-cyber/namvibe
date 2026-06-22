#!/usr/bin/env python3
"""
Phase 131 — Voice Note UX Test.
Verifies press-hold, slide cancel, upload progress, playback speed, waveform.
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

js = read_file("static/js/namvibe_messages_pro.js")
css = read_file("static/css/namvibe_messages_pro.css")
chat_css = read_file("static/css/chat.css")
mfs = read_file("services/message_feature_service.py")
se = read_file("services/socket_events.py")
ne = read_file("services/notification_engine.py")

print("=" * 60)
print("PHASE 131 — VOICE NOTE UX TEST")
print("=" * 60)

print("\n--- 1. Recording UX ---")
ok("wireVoice function") if "function wireVoice" in js else fail("wireVoice function missing")
ok("press and hold") if "mousedown" in js and "touchstart" in js else fail("press and hold not wired")
ok("slide to cancel") if "cancelVoiceRecording" in js or "slideCancel" in js.lower() else warn("slide to cancel")
ok("recording overlay") if "showVoiceOverlay" in js else fail("recording overlay missing")
ok("recording timer") if "vo-timer" in js or "_voiceTimer" in js else fail("recording timer missing")

print("\n--- 2. Preview Panel ---")
ok("voice preview") if "showVoicePreview" in js else fail("showVoicePreview missing")
ok("play/pause") if "vp-play" in js or "isPlaying" in js else fail("play/pause missing")
ok("delete") if "vp-delete" in js else fail("delete button missing")
ok("send") if "vp-send" in js or "voice-preview-send" in js else fail("send button missing")
ok("duration display") if "vp-duration" in js else fail("duration display missing")

print("\n--- 3. Upload Progress ---")
ok("upload progress bar") if "vp-progress" in js or "upload.onprogress" in js else fail("upload progress missing")
ok("cancel upload") if "vp-cancel" in js or "uploadCancelled" in js else fail("cancel upload missing")
ok("retry upload") if "vp-retry" in js or "retryBtn" in js else fail("retry upload missing")

print("\n--- 4. Playback Speed ---")
ok("playback speed") if "vp-speed" in js or "playbackSpeed" in js else fail("playback speed missing")

print("\n--- 5. Waveform ---")
ok("waveform generation") if "generateWaveformBars" in js or "renderWaveform" in js else fail("waveform generation missing")
ok("waveform CSS") if "voice-wave" in css or "waveform" in css else warn("waveform CSS")

print("\n--- 6. Backend Support ---")
ok("voice note service") if "save_voice_note" in mfs else fail("save_voice_note missing")
ok("playback state") if "save_voice_playback_state" in mfs else fail("playback state missing")
ok("voice_note_received notification") if "voice_note_received" in ne else warn("voice_note_received notification type")

print(f"\n{'=' * 60}")
print("PHASE 131 — VOICE NOTE UX TEST SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
