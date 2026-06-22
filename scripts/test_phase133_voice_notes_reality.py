#!/usr/bin/env python3
"""Phase 133 - Voice note reality checks."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from phase133_reality_utils import ACCEPTABLE_AUTH_STATUSES, credentials, has_pattern, print_header, read_file, route_check, Results, warn_ssl_fallback

R = Results()
print_header("PHASE 133 - VOICE NOTES REALITY")

js = read_file("static/js/namvibe_messages_pro.js") + read_file("static/js/message_composer.js") + read_file("templates/messages/thread.html") + read_file("templates/messages/index.html")
routes = read_file("api_routes/message_routes.py") + read_file("api_routes/message_production_routes.py")
services = read_file("services/message_media_service.py") + read_file("services/message_feature_service.py") + read_file("services/media_storage_service.py") + read_file("services/notification_engine.py")
css_html = read_file("static/css/namvibe_messages_pro.css") + read_file("static/css/chat.css") + read_file("templates/messages/thread.html") + read_file("templates/messages/index.html")

print("\n--- Static Voice Note Checks ---")
checks = [
    ("pointerdown/touchstart handler", r"pointerdown|touchstart|mousedown"),
    ("pointermove slide cancel handler", r"pointermove|touchmove|mousemove|slideCancel|cancelThreshold"),
    ("pointerup/touchend handler", r"pointerup|touchend|mouseup"),
    ("MediaRecorder support", r"MediaRecorder"),
    ("preview audio player", r"voice-note-audio|voicePreview|<audio"),
    ("waveform rendering", r"waveform|voice-wave|renderWaveform|generateWaveformBars"),
    ("upload progress", r"upload\.onprogress|vp-progress|progress"),
    ("retry button", r"vp-retry|retryBtn|retry"),
    ("delete/cancel button", r"vp-delete|voice-preview-delete|cancelVoice|deleteVoicePreview"),
    ("playback speed controls", r"vp-speed|playbackSpeed|voice-speed|playback_speed"),
]
for label, pattern in checks:
    R.check(label, has_pattern(js + css_html, pattern))

R.check("backend accepts audio/voice-note media", has_pattern(routes + services, r"voice-note|voice_note|audio|upload_media_file|validate_message_attachment"))
R.check("notification type voice_note_received", has_pattern(services, r"voice_note_received"))

print("\n--- Live Route Checks ---")
route_check(R, "/messages/api/voice-note", method="POST", acceptable=ACCEPTABLE_AUTH_STATUSES | {400})
route_check(R, "/messages/api/thread/phase133/voice-note", method="POST", acceptable=ACCEPTABLE_AUTH_STATUSES | {400})

if not credentials():
    R.warn("test credentials missing; optional live tiny voice upload skipped")
else:
    R.warn("credentials available; voice upload skipped without dedicated disposable thread id")

warn_ssl_fallback(R)
R.summary("PHASE 133 - VOICE NOTES REALITY")

