#!/usr/bin/env python3
import os
import sys
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"

from app import app
from services.ai.config import get_ai_config


def check(name, condition, detail=""):
    prefix = "PASS" if condition else "FAIL"
    print(prefix, name + (f" :: {detail}" if detail else ""))
    return 0 if condition else 1


def session_login(client):
    with client.session_transaction() as session:
        session["auth_user_id"] = "auth-1"
        session["profile_id"] = "profile-1"
        session["profile_data"] = {"id": "profile-1", "username": "tester"}


def read(path):
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as handle:
        return handle.read()


failures = 0
client = app.test_client()
session_login(client)

with patch("api_routes.homepage_api.toggle_like", return_value={"success": True, "liked": True, "count": 2}), \
     patch("api_routes.homepage_api.track_interaction_safe") as track_like:
    resp = client.post("/api/home/post/post-1/like", headers={"X-CSRFToken": "test"})
    failures += check("successful like records like", resp.status_code == 200 and track_like.call_count == 1)
    if track_like.call_args:
        failures += check("like action name", track_like.call_args.args[3] == "like")

with patch("api_routes.homepage_api.toggle_like", return_value={"success": True, "liked": False, "count": 1}), \
     patch("api_routes.homepage_api.track_interaction_safe") as track_unlike:
    resp = client.post("/api/home/post/post-1/like", headers={"X-CSRFToken": "test"})
    failures += check("successful unlike records unlike", resp.status_code == 200 and track_unlike.call_count == 1)
    if track_unlike.call_args:
        failures += check("unlike action name", track_unlike.call_args.args[3] == "unlike")

with patch("api_routes.homepage_api.toggle_like", return_value={"success": False}), \
     patch("api_routes.homepage_api.track_interaction_safe") as track_failed_like:
    resp = client.post("/api/home/post/post-1/like", headers={"X-CSRFToken": "test"})
    failures += check("failed like does not record interaction", resp.status_code >= 400 and track_failed_like.call_count == 0)

with patch("api_routes.social_routes.get_current_profile", return_value={"id": "profile-1"}), \
     patch("api_routes.social_routes.invalidate_profile_cache"), \
     patch("services.social_relationship_service.relationship_summary", return_value={"state": "none"}), \
     patch("services.social_relationship_service.follow", return_value={"ok": True, "state": "following"}), \
     patch("api_routes.social_routes.track_interaction_safe") as track_follow:
    resp = client.post("/social/follow/profile-2", headers={"X-CSRFToken": "test"})
    failures += check("follow records correct action", resp.status_code == 200 and track_follow.call_count == 1)
    if track_follow.call_args:
        failures += check("follow action name", track_follow.call_args.args[3] == "follow")

with patch("api_routes.social_routes.get_current_profile", return_value={"id": "profile-1"}), \
     patch("api_routes.social_routes.invalidate_profile_cache"), \
     patch("services.social_relationship_service.relationship_summary", return_value={"state": "following"}), \
     patch("services.social_relationship_service.unfollow", return_value={"ok": True, "state": "none"}), \
     patch("api_routes.social_routes.track_interaction_safe") as track_unfollow:
    resp = client.post("/social/follow/profile-2", headers={"X-CSRFToken": "test"})
    failures += check("unfollow records correct action", resp.status_code == 200 and track_unfollow.call_count == 1)
    if track_unfollow.call_args:
        failures += check("unfollow action name", track_unfollow.call_args.args[3] == "unfollow")

with patch("api_routes.friend_routes.get_current_profile", return_value={"id": "profile-1"}), \
     patch("api_routes.friend_routes.send_friend_request", return_value={"success": True, "request_id": "req-1"}), \
     patch("api_routes.friend_routes.track_interaction_safe") as track_friend_request:
    resp = client.post("/api/friends/request/profile-2", json={}, headers={"X-CSRFToken": "test"})
    failures += check("friend request records correctly", resp.status_code == 200 and track_friend_request.call_count == 1)
    if track_friend_request.call_args:
        failures += check("friend request action name", track_friend_request.call_args.args[3] == "friend_request")

with patch("api_routes.friend_routes.get_current_profile", return_value={"id": "profile-1"}), \
     patch("api_routes.friend_routes.accept_friend_request", return_value={"success": True, "sender_profile_id": "profile-2"}), \
     patch("api_routes.friend_routes.track_interaction_safe") as track_friend_accept:
    resp = client.post("/api/friends/accept/req-1", json={}, headers={"X-CSRFToken": "test"})
    failures += check("friend accept records correctly", resp.status_code == 200 and track_friend_accept.call_count == 1)
    if track_friend_accept.call_args:
        failures += check("friend accept action name", track_friend_accept.call_args.args[3] == "friend_accept")

with patch("api_routes.block_routes.get_current_profile", return_value={"id": "profile-1"}), \
     patch("api_routes.block_routes.block_user", return_value={"ok": True}), \
     patch("api_routes.block_routes.track_interaction_safe") as track_block:
    resp = client.post("/api/blocked/profile-2", headers={"X-CSRFToken": "test"})
    failures += check("block records block", resp.status_code == 200 and track_block.call_count == 1)
    if track_block.call_args:
        failures += check("block action name", track_block.call_args.args[3] == "block")

with patch("api_routes.messaging_routes._profile_id", return_value="profile-1"), \
     patch("api_routes.messaging_routes.can_access_thread", return_value=True), \
     patch("api_routes.messaging_routes._blocked", return_value=False), \
     patch("services.messaging_engine.send_message", return_value={"success": True, "id": "msg-1"}), \
     patch("api_routes.messaging_routes.fast_query", return_value=[{"profile_id": "profile-2"}]), \
     patch("api_routes.messaging_routes.track_interaction_safe") as track_message:
    resp = client.post("/api/messages/send", json={"thread_id": "thread-1", "body": "private message body", "profile_id": "spoofed"}, headers={"X-CSRFToken": "test"})
    failures += check("successful message records metadata only", resp.status_code == 200 and track_message.call_count == 1)
    if track_message.call_args:
        kwargs = track_message.call_args.kwargs
        metadata = kwargs.get("metadata", {})
        failures += check("message never includes text", "body" not in str(metadata).lower() and "private message body" not in str(metadata))
        failures += check("client profile_id spoofing impossible", track_message.call_args.args[0] == "profile-1")

with patch("api_routes.call_routes.get_current_profile", return_value={"id": "profile-1"}), \
     patch("api_routes.call_routes._are_friends", return_value=True, create=True), \
     patch("services.friendship_service.are_friends", return_value=True), \
     patch("api_routes.call_routes.w_create_call", return_value={"ok": True, "call": {"id": "call-1"}}), \
     patch("api_routes.call_routes.track_interaction_safe") as track_call:
    resp = client.post("/calls/api/start", json={"receiver_id": "profile-2", "call_type": "audio"}, headers={"X-CSRFToken": "test"})
    failures += check("successful call records call", resp.status_code == 200 and track_call.call_count == 1)
    if track_call.call_args:
        failures += check("call action name", track_call.call_args.args[3] == "call")

with patch("api_routes.reels_routes.track_interaction_safe") as track_reel_complete, \
     patch("api_routes.reels_routes.get_current_profile", return_value={"id": "profile-1"}), \
     patch("api_routes.reels_routes.track_reel_watch", return_value=None):
    resp = client.post("/reels/api/reels/reel-1/watch-v2", json={"watch_ms": 5, "completion_percent": 50}, headers={"X-CSRFToken": "test"})
    failures += check("reel incomplete does not record complete", resp.status_code == 200 and not any(call.args[3] == "complete" for call in track_reel_complete.call_args_list))

with patch("api_routes.reels_routes.track_interaction_safe") as track_reel_complete, \
     patch("api_routes.reels_routes.get_current_profile", return_value={"id": "profile-1"}), \
     patch("api_routes.reels_routes.track_reel_watch", return_value=None):
    resp = client.post("/reels/api/reels/reel-1/watch-v2", json={"watch_ms": 9, "completion_percent": 95}, headers={"X-CSRFToken": "test"})
    failures += check("reel complete recorded at threshold", resp.status_code == 200 and any(call.args[3] == "complete" for call in track_reel_complete.call_args_list))

with patch("api_routes.homepage_api.toggle_like", return_value={"success": True, "liked": True, "count": 1}), \
     patch("api_routes.homepage_api.track_interaction_safe", return_value=False):
    resp = client.post("/api/home/post/post-2/like", headers={"X-CSRFToken": "test"})
    failures += check("tracking failure does not break real action", resp.status_code == 200)

changed_sources = {
    "api_routes/homepage_api.py": read("api_routes/homepage_api.py"),
    "api_routes/reels_routes.py": read("api_routes/reels_routes.py"),
    "api_routes/social_routes.py": read("api_routes/social_routes.py"),
    "api_routes/friend_routes.py": read("api_routes/friend_routes.py"),
    "api_routes/block_routes.py": read("api_routes/block_routes.py"),
    "api_routes/messaging_routes.py": read("api_routes/messaging_routes.py"),
    "api_routes/message_routes.py": read("api_routes/message_routes.py"),
    "api_routes/message_production_routes.py": read("api_routes/message_production_routes.py"),
    "api_routes/call_routes.py": read("api_routes/call_routes.py"),
}

sensitive_tokens = ["message body", "body=", "password", "token", "wallet", "phone", "email", "latitude", "longitude"]
metadata_sensitive = True
for path, source in changed_sources.items():
    if "track_interaction_safe(" not in source:
        continue
    snippets = [line.strip().lower() for line in source.splitlines() if "track_interaction_safe(" in line or "metadata=" in line]
    if any(token in " ".join(snippets) for token in sensitive_tokens):
        metadata_sensitive = False
        break
failures += check("sensitive values are not passed in metadata", metadata_sensitive)

no_duplicate_routes = (
    read("api_routes/homepage_api.py").count('track_interaction_safe(profile["id"], "post", post_id, action_type') <= 1 and
    read("api_routes/friend_routes.py").count('track_interaction_safe(current["id"], "profile", profile_id, "friend_request"') == 1 and
    read("api_routes/block_routes.py").count('track_interaction_safe(profile["id"], "profile", profile_id, "block"') == 1
)
failures += check("no duplicate tracking calls in inspected routes", no_duplicate_routes)

cfg = get_ai_config()
failures += check("recommendations remain disabled", cfg.recommendations_enabled is False)
failures += check("external AI remains disabled", cfg.external_calls_enabled is False)

sys.exit(1 if failures else 0)
