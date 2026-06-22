#!/usr/bin/env python3
"""
Phase 131 — Messaging UI Full Audit.
Audits group management, voice notes, mobile chat, call routes, audio/video calls, PiP, notifications, performance.
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
def find_pattern(text, pattern):
    return bool(re.search(pattern, text, re.IGNORECASE))

mts = read_file("services/message_thread_service.py")
se = read_file("services/socket_events.py")
ne = read_file("services/notification_engine.py")
ns = read_file("services/notification_service.py")
ps = read_file("services/push_notification_service.py")
js = read_file("static/js/namvibe_messages_pro.js")
calls_js = read_file("static/js/calls.js")
calls_pro_js = read_file("static/js/namvibe_calls_pro.js")
co = read_file("templates/calls/call_overlay.html")
css_chat = read_file("static/css/chat.css")
css_msg = read_file("static/css/namvibe_messages_pro.css")
cr = read_file("api_routes/call_routes.py")
webrtc = read_file("services/webrtc_call_service.py")
cs = read_file("services/call_service.py")
mfs = read_file("services/message_feature_service.py")
badge_js = read_file("static/js/notification_badge.js")
app_py = read_file("app.py")

print("=" * 60)
print("PHASE 131 — MESSAGING UI FULL AUDIT")
print("=" * 60)

# ── SECTION 1: Group Management ──
print("\n" + "=" * 60)
print("SECTION 1 — GROUP MANAGEMENT")
print("=" * 60)
ok("rename_group") if "def rename_group" in mts else fail("rename_group function missing")
ok("update_group_avatar") if "def update_group_avatar" in mts else fail("update_group_avatar missing")
ok("promote_admin") if "def promote_admin" in mts else fail("promote_admin missing")
ok("demote_admin") if "def demote_admin" in mts else fail("demote_admin missing")
ok("remove admin check") if "not_admin" in mts else fail("admin check in remove_group_member missing")
ok("group:rename socket") if "group:rename" in se else fail("group:rename socket missing")
ok("group:name-updated socket") if "group:name-updated" in se else fail("group:name-updated socket missing")
ok("group:avatar socket") if "group:avatar" in se else fail("group:avatar socket missing")
ok("group:avatar-updated socket") if "group:avatar-updated" in se else fail("group:avatar-updated socket missing")
ok("group:promote socket") if "group:promote" in se else fail("group:promote socket missing")
ok("group:admin-promoted socket") if "group:admin-promoted" in se else fail("group:admin-promoted socket missing")
ok("group:demote socket") if "group:demote" in se else fail("group:demote socket missing")
ok("group:admin-demoted socket") if "group:admin-demoted" in se else fail("group:admin-demoted socket missing")
ok("group:remove-member socket") if "group:remove-member" in se else fail("group:remove-member socket missing")
ok("group:member-removed socket") if "group:member-removed" in se else fail("group:member-removed socket missing")
ok("group:leave socket") if "group:leave" in se else fail("group:leave socket missing")
ok("group:member-left socket") if "group:member-left" in se else fail("group:member-left socket missing")
ok("group_update notification") if "group_update" in ne else fail("group_update notification missing")
ok("admin_promoted notification") if "admin_promoted" in ne else fail("admin_promoted notification missing")
ok("admin_demoted notification") if "admin_demoted" in ne else fail("admin_demoted notification missing")
ok("member_removed notification") if "member_removed" in ne else fail("member_removed notification missing")

# ── SECTION 2: Voice Notes ──
print("\n" + "=" * 60)
print("SECTION 2 — VOICE NOTES")
print("=" * 60)
ok("wireVoice function") if "function wireVoice" in js else fail("wireVoice missing")
ok("press and hold recording") if "mousedown" in js and "touchstart" in js else fail("press and hold missing")
ok("slide to cancel") if "cancelVoiceRecording" in js else fail("slide to cancel missing")
ok("recording overlay") if "showVoiceOverlay" in js else fail("recording overlay missing")
ok("recording timer") if "_voiceTimer" in js else fail("recording timer missing")
ok("voice preview") if "showVoicePreview" in js else fail("voice preview missing")
ok("play/pause") if "vp-play" in js else fail("play/pause missing")
ok("delete button") if "vp-delete" in js else fail("delete button missing")
ok("send button") if "vp-send" in js else fail("send button missing")
ok("duration display") if "vp-duration" in js else fail("duration display missing")
ok("upload progress") if "upload.onprogress" in js else fail("upload progress missing")
ok("cancel upload") if "vp-cancel" in js else fail("cancel upload missing")
ok("retry upload") if "vp-retry" in js else fail("retry upload missing")
ok("playback speed") if "vp-speed" in js else fail("playback speed missing")
ok("waveform generation") if "generateWaveformBars" in js else fail("waveform generation missing")
ok("waveform render") if "renderWaveform" in js else fail("waveform render missing")
ok("voice note service") if "save_voice_note" in mfs else fail("save_voice_note missing")
ok("playback state") if "save_voice_playback_state" in mfs else fail("playback state missing")

# ── SECTION 3: Mobile Chat ──
print("\n" + "=" * 60)
print("SECTION 3 — MOBILE CHAT")
print("=" * 60)
ok("bubble styles") if ".msg" in css_chat or ".message-bubble" in css_chat else fail("bubble styles missing")
ok("max-width constraint") if "max-width" in css_chat else fail("max-width constraint missing")
ok("word break") if "word-break" in css_chat or "overflow-wrap" in css_chat else fail("word break missing")
ok("safe area") if "safe-area" in css_chat or "env(safe-area" in css_chat else warn("safe area padding")
ok("44px tap targets") if "44px" in css_chat else warn("44px tap targets")
ok("sticky composer") if "sticky" in css_chat and "bottom" in css_chat else warn("sticky composer")
ok("composer exists") if "chat-composer" in css_chat else fail("composer missing")
ok("typing indicator") if "typing-indicator" in css_chat or "typing" in js else fail("typing indicator missing")
ok("voice note button") if "mic-btn" in js else fail("voice note button missing")
ok("attach button") if "attach" in js.lower() or "attachment" in css_chat else warn("attach button")
ok("emoji picker") if "emoji" in js.lower() else warn("emoji picker")
ok("draft autosave") if "draft" in js.lower() and "save" in js.lower() else warn("draft autosave")

# ── SECTION 4: Call Routes ──
print("\n" + "=" * 60)
print("SECTION 4 — CALL ROUTES")
print("=" * 60)
ok("api_calls_bp blueprint") if "api_calls_bp" in cr else fail("api_calls_bp missing")
ok("api_calls_bp registered") if "api_calls_bp" in app_py else fail("api_calls_bp not registered")
api_calls_sec = cr[cr.find("api_calls_bp = Blueprint"):]
if not api_calls_sec: api_calls_sec = ""
std_routes = ["/start", "/answer", "/<call_id>/answer",
              "/<call_id>/reject", "/<call_id>/cancel", "/<call_id>/end",
              "/history", "/missed", "/group", "/active",
              "/ice-servers", "/diagnostics", "/<call_id>/mute",
              "/<call_id>/camera", "/<call_id>/speaker",
              "/<call_id>/invite", "/<call_id>/leave",
              "/<call_id>/reconnect", "/safety/check"]
for route in std_routes:
    pattern = route.replace("<call_id>", "[^/]+").replace("/", "\\/")
    ok(f"std route: /api/calls{route}") if re.search(pattern, api_calls_sec) else warn(f"std route missing: /api/calls{route}")

# ── SECTION 5: Audio Calls ──
print("\n" + "=" * 60)
print("SECTION 5 — AUDIO CALLS")
print("=" * 60)
combined_audio = cs + webrtc + se + cr
ok("incoming overlay") if "call-overlay-incoming" in co else fail("incoming overlay missing")
ok("outgoing overlay") if "call-overlay-outgoing" in co else fail("outgoing overlay missing")
ok("accept button") if "data-call-accept" in co else fail("accept button missing")
ok("reject button") if "data-call-reject" in co else fail("reject button missing")
ok("cancel button") if "data-call-cancel" in co else fail("cancel button missing")
ok("end button") if "data-call-end" in co else fail("end button missing")
ok("call timer") if "call-timer" in co else fail("call timer missing")
ok("reconnecting overlay") if "call-overlay-reconnecting" in co else fail("reconnecting overlay missing")
ok("start call") if find_pattern(combined_audio, "start.*call|init_call") else fail("start call missing")
ok("answer call") if find_pattern(combined_audio, "answer.*call|accept.*call") else fail("answer call missing")
ok("reject call") if find_pattern(combined_audio, "reject|decline") else fail("reject call missing")
ok("end call") if "end_call" in combined_audio else fail("end call missing")
ok("busy") if "busy" in combined_audio else fail("busy missing")
ok("offline") if "offline" in combined_audio else fail("offline missing")
ok("timeout") if "timeout" in combined_audio else warn("timeout")
ok("missed call") if "missed" in combined_audio else fail("missed call missing")
ok("duration") if "duration" in combined_audio else fail("duration missing")
ok("reconnect") if "reconnect" in combined_audio else fail("reconnect missing")

# ── SECTION 6: Video Calls ──
print("\n" + "=" * 60)
print("SECTION 6 — VIDEO CALLS")
print("=" * 60)
combined_video = co + se + webrtc + cr + calls_js
ok("camera toggle") if "call-camera-btn" in co or "camera" in co else fail("camera toggle missing")
ok("mic mute") if "call-mute-btn" in co else fail("mic mute missing")
ok("speaker") if "call-speaker-btn" in co else fail("speaker missing")
ok("switch camera") if "call-switch-camera" in co else fail("switch camera missing")
ok("local video") if "call-local-video" in co else fail("local video missing")
ok("remote video") if "call-remote-video" in co else fail("remote video missing")
ok("call:mute socket") if "call:mute" in se else fail("call:mute socket missing")
ok("call:camera-toggle socket") if "call:camera-toggle" in se else fail("call:camera-toggle socket missing")
ok("call:speaker-toggle socket") if "call:speaker-toggle" in se else fail("call:speaker-toggle socket missing")
ok("call:media-state socket") if "call:media-state" in se else fail("call:media-state socket missing")

# ── SECTION 7: PiP ──
print("\n" + "=" * 60)
print("SECTION 7 — PICTURE-IN-PICTURE")
print("=" * 60)
all_js = js + calls_js + calls_pro_js + read_file("static/js/webrtc_calls.js")
ok("pictureInPicture API") if "pictureInPicture" in all_js else warn("pictureInPicture API")
ok("requestPictureInPicture") if "requestPictureInPicture" in all_js else warn("requestPictureInPicture")
ok("minimized fallback") if "minimized" in all_js or "minimize" in all_js else warn("minimized fallback")

# ── SECTION 8: Notifications ──
print("\n" + "=" * 60)
print("SECTION 8 — NOTIFICATIONS")
print("=" * 60)
all_notif = ne + ns + ps + se
ok("incoming_call") if "incoming_call" in all_notif else fail("incoming_call notification missing")
ok("missed_call") if "missed_call" in all_notif else fail("missed_call notification missing")
ok("group_update") if "group_update" in ne else warn("group_update notification type")
ok("admin_promoted") if "admin_promoted" in ne else warn("admin_promoted notification type")
ok("admin_demoted") if "admin_demoted" in ne else warn("admin_demoted notification type")
ok("member_removed") if "member_removed" in ne else warn("member_removed notification type")
ok("voice_note_received") if "voice_note_received" in all_notif else warn("voice_note_received notification type")
ok("notification:new socket") if "notification:new" in se else fail("notification:new missing")
ok("notification:read socket") if "notification:read" in se else fail("notification:read missing")
ok("badge JS") if badge_js else fail("notification_badge.js missing")
ok("badge count logic") if "badge" in badge_js or "count" in badge_js else fail("badge count logic missing")

# ── SUMMARY ──
print(f"\n{'=' * 60}")
print("PHASE 131 — MESSAGING UI FULL AUDIT SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
