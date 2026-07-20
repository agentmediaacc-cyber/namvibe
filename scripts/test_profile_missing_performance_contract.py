#!/usr/bin/env python3
"""Contract tests for fast-fail public profile lookup."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")

from app import app


def check(name: str, condition: bool, detail: str = "") -> None:
    print(("PASS" if condition else "FAIL"), name)
    if not condition:
        raise AssertionError(detail or name)


def main() -> None:
    client = app.test_client()
    profile = {
        "id": "33333333-3333-3333-3333-333333333333",
        "username": "publiccreator",
        "display_name": "Public Creator",
        "avatar_url": "https://cdn.example.com/avatar.jpg",
        "bio": "Public bio",
        "verified": True,
        "is_verified": True,
    }
    bundle = {
        "profile": dict(profile),
        "stats": {"posts": 1, "reels": 1, "stories": 0, "followers": 12, "following": 4, "friends": 0, "likes": 0, "views": 0},
        "content": {"posts": [{"id": "post-1", "caption": "Public post"}], "reels": [{"id": "reel-1", "thumbnail_url": "https://cdn.example.com/r.jpg"}], "stories": [], "rooms": []},
        "wallet": {},
        "creator_tools": {},
        "activity": [],
        "actions": [{"can_message": False}],
        "presence": {"state": "online"},
        "mutual_friends": {"count": 0, "items": []},
        "profile_strength": 55,
        "recently_active_friends": [],
    }

    def fail_if_called(*args, **kwargs):
        raise AssertionError("expensive hydration should not run for missing public profile")

    with patch("api_routes.profile_routes.get_public_profile_reference", return_value=None), \
         patch("api_routes.profile_routes.get_profile_by_id", side_effect=fail_if_called), \
         patch("api_routes.profile_routes.build_profile_dashboard", side_effect=fail_if_called), \
         patch("api_routes.profile_routes.get_current_profile", side_effect=fail_if_called), \
         patch("api_routes.profile_routes.get_profile_bundle", side_effect=fail_if_called), \
         patch("api_routes.profile_routes.get_profile_content", side_effect=fail_if_called), \
         patch("api_routes.profile_routes.get_profile_stats", side_effect=fail_if_called), \
         patch("api_routes.profile_routes.get_my_notifications", side_effect=fail_if_called), \
         patch("api_routes.profile_routes.get_wallet_snapshot", side_effect=fail_if_called), \
         patch("api_routes.profile_routes.get_friends", side_effect=fail_if_called), \
         patch("api_routes.profile_routes.get_followers_page", side_effect=fail_if_called), \
         patch("api_routes.profile_routes.get_following_page", side_effect=fail_if_called), \
         patch("api_routes.profile_routes.get_following_types", side_effect=fail_if_called), \
         patch("api_routes.profile_routes.get_friend_requests", side_effect=fail_if_called), \
         patch("api_routes.profile_routes.get_sent_friend_requests", side_effect=fail_if_called):
        response = client.get("/profile/@missinghandle")

    check("missing handle returns 404", response.status_code == 404, response.status_code)
    check("missing handle body is not blank", len(response.get_data()) > 0)
    check("missing handle uses lightweight 404 response", "NamVibe Not Found" in response.get_data(as_text=True) or "not found" in response.get_data(as_text=True).lower())

    with patch("api_routes.profile_routes.get_public_profile_reference", return_value=profile), \
         patch("api_routes.profile_routes.get_profile_by_id", side_effect=fail_if_called), \
         patch("api_routes.profile_routes.get_current_profile", return_value=None), \
         patch("api_routes.profile_routes.record_profile_view", return_value=True), \
         patch("api_routes.profile_routes.emit_activity", return_value=True), \
         patch("api_routes.profile_routes.track_interaction_safe", return_value=True), \
         patch("api_routes.profile_routes.get_profile_bundle", return_value=bundle), \
         patch("services.social_action_policy.get_action_policy", return_value={"primary_action": "follow", "can_chat": False, "can_call": False}), \
         patch("services.social_action_policy.can_view_profile", return_value={"can_view_full_profile": True}):
        response_ok = client.get("/profile/publiccreator")

    html = response_ok.get_data(as_text=True)
    check("public handle returns 200", response_ok.status_code == 200, response_ok.status_code)
    check("public handle renders content", "Public Creator" in html or "Public post" in html, html[:500])

    with patch("api_routes.profile_routes.get_public_profile_reference", return_value=profile), \
         patch("api_routes.profile_routes.get_profile_by_id", side_effect=fail_if_called), \
         patch("api_routes.profile_routes.get_current_profile", return_value=None), \
         patch("api_routes.profile_routes.record_profile_view", return_value=True), \
         patch("api_routes.profile_routes.emit_activity", return_value=True), \
         patch("api_routes.profile_routes.track_interaction_safe", return_value=True), \
         patch("api_routes.profile_routes.get_profile_bundle", return_value=bundle), \
         patch("services.social_action_policy.get_action_policy", return_value={"primary_action": "follow", "can_chat": False, "can_call": False}), \
         patch("services.social_action_policy.can_view_profile", return_value={"can_view_full_profile": True}):
        response_at = client.get("/profile/@publiccreator")

    check("at-handle route returns 200", response_at.status_code == 200, response_at.status_code)

    with patch("api_routes.profile_routes.get_public_profile_reference", side_effect=RuntimeError("db down")):
        response_fail = client.get("/profile/ghost")

    check("database failure degrades to 404", response_fail.status_code == 404, response_fail.status_code)
    check("database failure reports not found page", b"NamVibe Not Found" in response_fail.data or b"not found" in response_fail.data.lower())

    print("TEST_OK profile missing performance contract")


if __name__ == "__main__":
    main()
