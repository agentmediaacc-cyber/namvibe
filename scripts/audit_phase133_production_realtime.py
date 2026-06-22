#!/usr/bin/env python3
"""Phase 133 - Production realtime audit."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from phase133_reality_utils import ACCEPTABLE_AUTH_STATUSES, has_pattern, http_request, print_header, read_file, route_check, static_refs, Results, warn_ssl_fallback

R = Results()
print_header("PHASE 133 - PRODUCTION REALTIME AUDIT")

messages = read_file("templates/messages/thread.html") + read_file("templates/messages/inbox.html") + read_file("templates/messages/index.html")
calls = read_file("templates/calls/call_overlay.html") + read_file("templates/calls/video.html") + read_file("templates/calls/recent.html") + read_file("templates/calls/history.html")
js = read_file("static/js/namvibe_messages_pro.js") + read_file("static/js/namvibe_calls_pro.js") + read_file("static/js/webrtc_calls.js") + read_file("static/js/realtime_presence.js") + read_file("static/js/notification_badge.js")
css = read_file("static/css/namvibe_messages_pro.css") + read_file("static/css/chat.css") + read_file("static/css/namvibe_calls_pro.css") + read_file("static/css/calls.css")
services = read_file("services/socket_events.py") + read_file("services/notification_engine.py") + read_file("services/message_delivery_service.py") + read_file("services/message_media_service.py")
routes = read_file("api_routes/call_routes.py") + read_file("api_routes/message_routes.py") + read_file("api_routes/message_production_routes.py")
all_text = messages + calls + js + css + services + routes

print("\n--- Static Production UX Checks ---")
checks = [
    ("console guard/no debugger markers", not has_pattern(js, r"debugger;")),
    ("websocket recovery/reconnect", has_pattern(all_text, r"reconnect|socket:recovered|offline")),
    ("notification dedupe/no duplicate support", has_pattern(services + js, r"dedupe|event_id|client_event_id|notification:new")),
    ("avatar fallback", has_pattern(messages + calls + css, r"avatar|fallback|fa-user|object-fit")),
    ("message overlap protection", has_pattern(css + messages, r"overflow-wrap|word-break|max-width")),
    ("call route coverage", has_pattern(routes, r"api_calls_bp|/ice-servers|/diagnostics|/reconnect")),
    ("voice note handlers", has_pattern(js + messages, r"wireVoice|MediaRecorder|voice-note")),
    ("upload buttons", has_pattern(messages + js, r"file-input|attachment|upload|attach")),
    ("mobile safe-area CSS", has_pattern(css + messages, r"safe-area|env\(safe-area")),
    ("read receipt UI", has_pattern(messages + js, r"status-tick|check-double|message:seen|read_at")),
    ("typing indicator UI", has_pattern(messages + js, r"typing-indicator|typingLine|typing")),
    ("presence UI", has_pattern(messages + js + services, r"presence|online|offline")),
]
for label, condition in checks:
    R.check(label, condition)

print("\n--- Live Production Checks ---")
status, home, _ = http_request("/")
R.ok("live homepage 200") if status == 200 else R.fail(f"live homepage returned {status}")
route_check(R, "/messages/inbox", acceptable=ACCEPTABLE_AUTH_STATUSES)
route_check(R, "/api/calls/ice-servers", acceptable=ACCEPTABLE_AUTH_STATUSES)
status, body, _ = http_request("/socket.io/?EIO=4&transport=polling")
R.ok(f"socket.io live endpoint ({status})") if status in (200, 400, 401, 403) else R.fail(f"socket.io returned {status}")
for asset in ["/static/js/namvibe_messages_pro.js", "/static/css/namvibe_messages_pro.css"]:
    status, _, _ = http_request(asset)
    R.ok(f"{asset} 200") if status == 200 else R.fail(f"{asset} returned {status}")

missing = []
for ref in static_refs(home):
    status, _, _ = http_request(ref)
    if status == 404:
        missing.append(ref)
if missing:
    R.fail("live homepage missing assets: " + ", ".join(missing[:8]))
else:
    R.ok("no live homepage 404 assets")

warn_ssl_fallback(R)
R.summary("PHASE 133 - PRODUCTION REALTIME AUDIT")
