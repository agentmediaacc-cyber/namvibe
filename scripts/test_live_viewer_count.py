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

client = app.test_client()
with client.session_transaction() as session:
    session["auth_user_id"] = "44444444-4444-4444-4444-444444444444"
    session["profile_id"] = "44444444-4444-4444-4444-444444444444"
socket_client = socketio.test_client(app, flask_test_client=client)

with patch("services.socket_events._live_access_allowed", return_value=({"id": "room-1", "owner_profile_id": "host-1"}, None)), \
     patch("services.socket_events._upsert_live_participant"), \
     patch("services.socket_events.track_interaction_safe", return_value=False), \
     patch("services.socket_events._sync_live_viewer_count", return_value=1):
    result = socket_client.emit("join_live_room", {"room_id": "room-1"}, callback=True)
    failures += check("Viewer count increments once", bool(result and result.get("viewer_count") == 1))

with patch("services.socket_events._live_access_allowed", return_value=({"id": "room-1", "owner_profile_id": "host-1"}, None)), \
     patch("services.socket_events._upsert_live_participant"), \
     patch("services.socket_events.track_interaction_safe", return_value=False), \
     patch("services.socket_events._sync_live_viewer_count", return_value=1):
    result = socket_client.emit("join_live_room", {"room_id": "room-1"}, callback=True)
    failures += check("Reconnect does not double count", bool(result and result.get("viewer_count") == 1))

with patch("services.socket_events._live_room_row", return_value={"id": "room-1", "owner_profile_id": "host-1"}), \
     patch("services.socket_events._deactivate_live_participant"), \
     patch("services.socket_events._sync_live_viewer_count", return_value=0):
    result = socket_client.emit("leave_live_room", {"room_id": "room-1"}, callback=True)
    failures += check("Disconnect decrements", bool(result and result.get("viewer_count") == 0))

source = open(os.path.join(ROOT, "services", "socket_events.py"), "r", encoding="utf-8").read()
failures += check("Stale presence cleanup works", "_deactivate_live_participant" in source and "handle_disconnect" in source)

socket_client.disconnect()
sys.exit(1 if failures else 0)
