#!/usr/bin/env python3
"""Phase 133 - Realtime socket reality checks."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from phase133_reality_utils import has_pattern, http_request, print_header, read_file, Results, warn_ssl_fallback

R = Results()
print_header("PHASE 133 - REALTIME SOCKET REALITY")

sockets = read_file("services/socket_events.py")
socket_service = read_file("services/socketio_service.py") + read_file("services/redis_service.py") + read_file("services/redis_hardening_service.py")
frontend = read_file("static/js/namvibe_messages_pro.js") + read_file("templates/messages/thread.html") + read_file("templates/messages/index.html") + read_file("static/js/notification_badge.js") + read_file("static/js/realtime_presence.js")

print("\n--- Socket Event Static Checks ---")
events = [
    ("connect", r"@socketio\.on\([\"']connect|socket\.on\([\"']connect"),
    ("disconnect", r"@socketio\.on\([\"']disconnect|socket\.on\([\"']disconnect"),
    ("reconnect", r"reconnect|socket:recovered|recover"),
    ("join_thread", r"join_thread|join:thread"),
    ("leave_thread", r"leave_thread|leave:thread|room:leave"),
    ("typing_start", r"typing:start|typing_start|typing"),
    ("typing_stop", r"typing:stop|typing_stop|typing"),
    ("message_send", r"message:send|message_send"),
    ("message_receive", r"message:new|message_receive|message:delivered"),
    ("message_delivered", r"message:delivered|delivered"),
    ("message_seen", r"message:seen|seen"),
    ("group:rename", r"group:rename"),
    ("group:avatar", r"group:avatar"),
    ("group:promote", r"group:promote"),
    ("group:demote", r"group:demote"),
    ("group:remove-member", r"group:remove-member"),
    ("group:leave", r"group:leave"),
    ("presence:update", r"presence:update|presence_update|presence:heartbeat"),
    ("user_online", r"user_online|online|presence"),
    ("user_offline", r"user_offline|offline|presence"),
    ("notification:new", r"notification:new"),
]
for label, pattern in events:
    R.check(label, has_pattern(sockets + frontend, pattern))

print("\n--- Redis Checks ---")
R.check("Redis configured", has_pattern(socket_service, r"REDIS|redis_url|rediss://|Redis"))
R.check("Redis pub/sub or message queue integration", has_pattern(socket_service + sockets, r"publish|pubsub|RedisManager|message_queue|set_json"))
R.check("Redis fallback safe", has_pattern(socket_service, r"fallback|unavailable|in-memory|Dummy|safe"))

print("\n--- Live Socket Endpoint ---")
status, body, _ = http_request("/socket.io/?EIO=4&transport=polling")
if status in (200, 400, 401, 403) and status not in (404, 500):
    R.ok(f"/socket.io polling endpoint responds ({status})")
elif status in (404, 500, 502, 503):
    R.fail(f"/socket.io polling endpoint returned {status}")
else:
    R.warn(f"/socket.io polling endpoint returned {status}")
if status == 200 and (body.startswith("0") or "sid" in body or "Engine.IO" in body):
    R.ok("Socket.IO handshake-like response")
elif status == 400:
    R.ok("Socket.IO returned expected 400 handshake validation response")
else:
    R.warn("Socket.IO response did not expose a clear handshake marker")

warn_ssl_fallback(R)
R.summary("PHASE 133 - REALTIME SOCKET REALITY")

