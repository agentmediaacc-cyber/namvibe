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


def check(label, condition, detail=""):
    print(("PASS" if condition else "FAIL"), label + (f" :: {detail}" if detail else ""))
    return 0 if condition else 1


def login(client, profile_id="11111111-1111-1111-1111-111111111111"):
    with client.session_transaction() as session:
        session["auth_user_id"] = profile_id
        session["profile_id"] = profile_id
        session["profile_data"] = {"id": profile_id, "username": "alpha"}


app = create_app()
failures = 0

with app.test_client() as client:
    resp = client.get("/live")
    failures += check("Live Hub returns 200", resp.status_code == 200)
    failures += check("Empty Live Hub contains no fake room", "Demo" not in resp.get_data(as_text=True))

    resp = client.post("/api/live/start", json={"title": "Test Live"})
    failures += check("Authentication required to create room", resp.status_code == 401)

    login(client)
    with patch("api_routes.live_routes._active_room_for_host", return_value=None), \
         patch("api_routes.live_routes._create_room_row", return_value="room-1"), \
         patch("api_routes.live_routes._finalize_room_start"), \
         patch("api_routes.live_routes.livekit_configured", return_value=False), \
         patch("api_routes.live_routes.track_interaction_safe", return_value=False):
        resp = client.post("/api/live/start", json={"title": "Real Stream", "status": "live"})
        body = resp.get_json()
        failures += check("Host can create one room", resp.status_code == 200 and body["room_id"] == "room-1")

    with patch("api_routes.live_routes._active_room_for_host", return_value={"id": "room-1", "status": "live"}):
        resp = client.post("/api/live/start", json={"title": "Real Stream", "status": "live"})
        body = resp.get_json()
        failures += check("Duplicate active host room is prevented or reused safely", body.get("reused") is True and body.get("room_id") == "room-1")

    with patch("api_routes.live_routes._fetch_room", return_value={"id": "room-1", "owner_profile_id": "other"}):
        resp = client.post("/api/live/room-1/end", json={})
        failures += check("Viewer cannot end stream", resp.status_code == 403)

    with patch("api_routes.live_routes._fetch_room", return_value={"id": "room-1", "owner_profile_id": "11111111-1111-1111-1111-111111111111"}), \
         patch("api_routes.live_routes._columns", return_value={"status", "is_live", "ended_at", "viewer_count"}), \
         patch("api_routes.live_routes.execute"), \
         patch("api_routes.live_routes.table_exists", return_value=False):
        resp = client.post("/api/live/room-1/end", json={})
        failures += check("Host can end stream", resp.status_code == 200 and resp.get_json().get("ok") is True)

viewer_client = app.test_client()
login(viewer_client, "22222222-2222-2222-2222-222222222222")
socket_client = socketio.test_client(app, flask_test_client=viewer_client)
with patch("services.socket_events._live_access_allowed", return_value=({"id": "room-1", "owner_profile_id": "11111111-1111-1111-1111-111111111111"}, None)), \
     patch("services.socket_events._sync_live_viewer_count", return_value=1), \
     patch("services.socket_events._upsert_live_participant"), \
     patch("services.socket_events.track_interaction_safe", return_value=False):
    result = socket_client.emit("join_live_room", {"room_id": "room-1"}, callback=True)
    failures += check("Viewer can join active room", bool(result and result.get("joined") is True))

with patch("services.socket_events._live_access_allowed", return_value=({"id": "room-1"}, "stream_ended")):
    result = socket_client.emit("join_live_room", {"room_id": "room-1"}, callback=True)
    failures += check("Viewer cannot join ended room", bool(result and result.get("error") == "stream_ended"))

socket_client.disconnect()
sys.exit(1 if failures else 0)
