#!/usr/bin/env python3
"""Phase 133 - Calls reality checks."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from phase133_reality_utils import ACCEPTABLE_AUTH_STATUSES, has_pattern, print_header, read_file, route_check, Results, warn_ssl_fallback

R = Results()
print_header("PHASE 133 - CALLS REALITY")

routes = read_file("api_routes/call_routes.py")
services = read_file("services/webrtc_call_service.py") + read_file("services/call_service.py") + read_file("services/call_feature_service.py")
frontend = read_file("templates/calls/call_overlay.html") + read_file("templates/calls/video.html") + read_file("templates/calls/recent.html") + read_file("templates/calls/history.html") + read_file("static/js/namvibe_messages_pro.js") + read_file("static/js/namvibe_calls_pro.js") + read_file("static/js/webrtc_calls.js") + read_file("static/js/calls.js")
sockets = read_file("services/socket_events.py") + frontend

print("\n--- Backend Static Checks ---")
for label, pattern in [
    ("audio call", r"call_type.*audio|audio"),
    ("video call", r"call_type.*video|video"),
    ("missed call", r"missed"),
    ("busy call", r"busy"),
    ("reject", r"reject_call|/reject"),
    ("reconnect", r"reconnect|mark_call_reconnecting"),
    ("speaker", r"speaker"),
    ("camera toggle", r"camera"),
    ("mute", r"mute"),
]:
    R.check(label, has_pattern(routes + services, pattern))

print("\n--- Frontend Static Checks ---")
for label, pattern in [
    ("outgoing call screen", r"call-overlay-outgoing|outgoingOverlay|Calling"),
    ("incoming call screen", r"call-overlay-incoming|incomingOverlay|Incoming"),
    ("ringtone", r"ringtone|call-ringtone|Audio"),
    ("accept/reject", r"data-call-accept|call-accept|accept.*reject"),
    ("mute", r"call-mute|mute"),
    ("camera toggle", r"call-camera|cameraToggle"),
    ("speaker", r"call-speaker|speaker"),
    ("PiP button", r"pip-btn|data-pip-btn|Picture in picture"),
    ("reconnect indicator", r"reconnecting|call-overlay-reconnecting"),
    ("missed call UI", r"missed"),
    ("call history UI", r"history|call-log-card"),
]:
    R.check(label, has_pattern(frontend, pattern))

print("\n--- Realtime Event Checks ---")
for label, pattern in [
    ("call_offer/call:start", r"call_offer|call:start|call:ringing"),
    ("call_answer/call:accept", r"call_answer|call:answer|call:accept|call:answered"),
    ("call_reject/call:reject", r"call_reject|call:reject|call:rejected"),
    ("call_end/call:end", r"call_end|call:end|call:ended"),
    ("call_busy/call:busy", r"call_busy|call:busy"),
    ("ice_candidate", r"ice_candidate|ice-candidate|candidate"),
    ("reconnect", r"reconnect|call:reconnecting|call:reconnected"),
]:
    R.check(label, has_pattern(sockets, pattern))

print("\n--- Live Modern Call Routes ---")
modern = [
    ("/api/calls/start", "POST"), ("/api/calls/answer", "POST"), ("/api/calls/reject", "POST"),
    ("/api/calls/cancel", "POST"), ("/api/calls/end", "POST"), ("/api/calls/history", "GET"),
    ("/api/calls/missed", "GET"), ("/api/calls/group", "POST"), ("/api/calls/active", "GET"),
    ("/api/calls/ice-servers", "GET"), ("/api/calls/diagnostics", "GET"), ("/api/calls/mute", "POST"),
    ("/api/calls/camera", "POST"), ("/api/calls/speaker", "POST"), ("/api/calls/invite", "POST"),
    ("/api/calls/leave", "POST"), ("/api/calls/reconnect", "POST"), ("/api/calls/safety/check", "POST"),
]
for path, method in modern:
    route_check(R, path, method=method, data={"call_id": "phase133", "target_id": "phase133"} if method == "POST" else None, acceptable=ACCEPTABLE_AUTH_STATUSES | {400})

print("\n--- Live Legacy Call Routes ---")
for path, method in [
    ("/calls/api/diagnostics", "GET"), ("/calls/api/missed-count", "GET"), ("/calls/api/logs", "GET"),
    ("/calls/api/contacts/search?q=phase133", "GET"), ("/calls/api/safety/check", "POST"),
]:
    route_check(R, path, method=method, data={"target_id": "phase133"} if method == "POST" else None, acceptable=ACCEPTABLE_AUTH_STATUSES | {400})

warn_ssl_fallback(R)
R.summary("PHASE 133 - CALLS REALITY")

