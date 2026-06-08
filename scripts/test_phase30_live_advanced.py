#!/usr/bin/env python3
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / "venv" / "bin" / "python3"
if VENV_PY.exists() and Path(sys.executable).resolve() != VENV_PY.resolve():
    os.execv(str(VENV_PY), [str(VENV_PY), *sys.argv])
sys.path.insert(0, str(ROOT))
os.environ["FLASK_TESTING"] = "1"

from services import live_feature_service as l  # noqa: E402


def main():
    host = str(uuid.uuid4())
    viewer = str(uuid.uuid4())
    room = l.start_live(host, "Phase 30 live", "Host")["room"]
    room_id = room["id"]
    assert l.join_live(room_id, viewer)["viewer_count"] == 1
    assert l.comment_live(room_id, viewer, "hello")["ok"]
    guest = l.request_guest(room_id, viewer, "join me")
    assert guest["ok"]
    assert l.update_guest_request(guest["guest_request"]["id"], "accepted")["ok"]
    poll = l.create_poll(room_id, host, "Question?", ["A", "B"])
    assert poll["ok"]
    assert l.vote_poll(poll["poll"]["id"], viewer, "A")["ok"]
    assert l.create_battle(room_id, host_profile_id=host, challenger_profile_id=viewer)["ok"]
    assert l.moderation_action(room_id, host, "mute", viewer, "test")["ok"]
    assert l.save_replay(room_id, host, "local://replay.m3u8", 60)["ok"]
    assert l.create_clip(room_id, viewer, "local://clip.mp4", 5, 10, "Clip")["ok"]
    assert l.add_shopping_item(room_id, host, "Product", 25, "https://example.com/product")["ok"]
    assert l.upsert_leaderboard(room_id, viewer, 100, 1)["ok"]
    assert l.save_stream_settings(room_id, host, webrtc_enabled=True, rtmp_enabled=False, turn_required=True)["ok"]
    assert l.end_live(room_id, host)["ok"]
    print("phase30 live advanced: ok")


if __name__ == "__main__":
    main()
