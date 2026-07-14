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
from services.ai.config import get_ai_config


def check(label, condition):
    print(("PASS" if condition else "FAIL"), label)
    return 0 if condition else 1


app = create_app()
failures = 0
client = app.test_client()
with client.session_transaction() as session:
    session["auth_user_id"] = "55555555-5555-5555-5555-555555555555"
    session["profile_id"] = "55555555-5555-5555-5555-555555555555"

with patch("api_routes.live_routes._active_room_for_host", return_value=None), \
     patch("api_routes.live_routes._create_room_row", return_value="room-fallback"), \
     patch("api_routes.live_routes._finalize_room_start"), \
     patch("api_routes.live_routes.livekit_configured", return_value=False), \
     patch("api_routes.live_routes.track_interaction_safe", return_value=False):
    resp = client.post("/api/live/start", json={"title": "Fallback Stream", "status": "live"})
    body = resp.get_json()
    failures += check("LiveKit missing config uses safe fallback", resp.status_code == 200 and body.get("provider") == "webrtc_fallback")

resp = client.get("/api/live/webrtc-config")
body = resp.get_json()
failures += check("TURN missing config does not crash", resp.status_code == 200 and "iceServers" in body)

with patch("api_routes.live_routes.livekit_configured", return_value=False):
    resp = client.post("/api/live/livekit-token", json={"room_id": "room-fallback", "role": "viewer"})
    failures += check("LiveKit token route safe when disabled", resp.status_code == 503)

source = open(os.path.join(ROOT, "services", "livekit_service.py"), "r", encoding="utf-8").read()
failures += check("LiveKit tokens never appear in logs", "to_jwt()" in source and "Token creation failed: {e}" not in source)

cfg = get_ai_config()
failures += check("Recommendations remain disabled", cfg.recommendations_enabled is False)
failures += check("External AI remains disabled", cfg.external_calls_enabled is False)

sys.exit(1 if failures else 0)
