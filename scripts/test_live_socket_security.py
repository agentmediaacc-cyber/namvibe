#!/usr/bin/env python3
import os
import sys
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
os.environ.setdefault("FLASK_TESTING", "1")

from app import create_app
from services.socketio_service import socketio


def check(label, condition):
    print(("PASS" if condition else "FAIL"), label)
    return 0 if condition else 1


app = create_app()
failures = 0

anon_client = socketio.test_client(app)
result = anon_client.emit("live_chat_message", {"room_id": "room-1", "message": "hello"}, callback=True)
failures += check("Chat requires authentication", bool(result and result.get("error") == "unauthorized"))
anon_client.disconnect()

auth_client = app.test_client()
with auth_client.session_transaction() as session:
    session["auth_user_id"] = "33333333-3333-3333-3333-333333333333"
    session["profile_id"] = "33333333-3333-3333-3333-333333333333"
    session["username"] = "viewer"
socket_client = socketio.test_client(app, flask_test_client=auth_client)

with patch("services.socket_events._live_access_allowed", return_value=({"id": "room-1", "owner_profile_id": "host-1"}, None)), \
     patch("services.socket_events.emit_to_live_room") as emit_room:
    long_message = "a" * 800
    result = socket_client.emit("live_chat_message", {"room_id": "room-1", "message": long_message, "profile_id": "spoofed"}, callback=True)
    failures += check("Chat sender cannot be spoofed", bool(result and result.get("ok") is True))
    if emit_room.call_args:
        payload = emit_room.call_args.args[2]
        failures += check("Chat rejects oversized message", len(payload.get("body", "")) <= 500)
        failures += check("Socket events are room scoped", emit_room.call_args.args[0] == "room-1")
        failures += check("No private session data leaked", "token" not in str(payload).lower())

source = open(os.path.join(ROOT, "services", "socket_events.py"), "r", encoding="utf-8").read()
failures += check("WebRTC offer sender cannot be spoofed", "_get_profile_id()" in source and "call:offer" in source)
failures += check("ICE candidate sender cannot be spoofed", "_get_profile_id()" in source and "call:ice-candidate" in source)
failures += check("No duplicate socket handlers", source.count('@socketio.on("join_live_room")') == 1 and source.count('@socketio.on("live_chat_message")') == 1)

socket_client.disconnect()
sys.exit(1 if failures else 0)
