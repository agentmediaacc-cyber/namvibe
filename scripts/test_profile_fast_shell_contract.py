#!/usr/bin/env python3
import os
import sys
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")

from app import app


def check(name, condition, detail=""):
    print(("PASS" if condition else "FAIL"), name)
    if not condition:
        raise AssertionError(detail or name)


def main():
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
        "content": {"posts": [{"id": "post-1", "caption": "Public post"}], "reels": [{"id": "reel-1", "thumbnail_url": "https://cdn.example.com/r.jpg"}], "rooms": []},
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
        raise AssertionError("premium profile data should not be loaded for public visitors")

    with patch("api_routes.profile_routes.get_profile_by_username", return_value=profile), \
         patch("api_routes.profile_routes.get_current_profile", return_value=None), \
         patch("api_routes.profile_routes.record_profile_view", return_value=True), \
         patch("api_routes.profile_routes.emit_activity", return_value=True), \
         patch("api_routes.profile_routes.track_interaction_safe", return_value=True), \
         patch("api_routes.profile_routes.get_profile_bundle", return_value=bundle), \
         patch("services.social_action_policy.get_action_policy", return_value={"primary_action": "follow", "can_chat": False, "can_call": False}), \
         patch("services.social_action_policy.can_view_profile", return_value={"can_view_full_profile": True}), \
         patch("services.profile_premium_service.get_achievements", side_effect=fail_if_called), \
         patch("services.profile_premium_service.get_badges", side_effect=fail_if_called), \
         patch("services.profile_premium_service.get_collections", side_effect=fail_if_called), \
         patch("services.profile_premium_service.get_timeline", side_effect=fail_if_called), \
         patch("services.profile_premium_service.get_education", side_effect=fail_if_called), \
         patch("services.profile_premium_service.get_work_experience", side_effect=fail_if_called), \
         patch("services.profile_premium_service.get_skills", side_effect=fail_if_called), \
         patch("services.profile_premium_service.get_visitors", side_effect=fail_if_called), \
         patch("services.profile_premium_service.get_activity_log", side_effect=fail_if_called), \
         patch("services.profile_premium_service.get_favorites_by_type", side_effect=fail_if_called):
        response = client.get("/profile/@publiccreator")

    html = response.get_data(as_text=True)
    check("public profile returned", response.status_code == 200, response.status_code)
    check("real public content rendered", "Public post" in html or "Public Creator" in html, html[:500])
    check("no premium sections rendered", "education" not in html.lower() or "premium profile data" not in html.lower(), html[:500])
    print("OK")


if __name__ == "__main__":
    main()
