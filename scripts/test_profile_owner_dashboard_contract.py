#!/usr/bin/env python3
"""Contract tests for the owner profile dashboard path."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

from flask import session as flask_session

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")

from app import app
from api_routes.profile_routes import _render_profile_index, my_profile
from services.profile_dashboard_service import build_profile_dashboard


def check(name: str, condition: bool, detail: str = "") -> None:
    print(("PASS" if condition else "FAIL"), name)
    if not condition:
        raise AssertionError(detail or name)


def _profile() -> dict:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "auth_user_id": "11111111-1111-1111-1111-111111111111",
        "username": "owneruser",
        "display_name": "Owner User",
        "full_name": "Owner User",
        "bio": "Owner bio",
        "is_verified": True,
        "verified": True,
        "profile_theme": "Dark Premium",
        "posts_count": 1,
        "reels_count": 1,
    }


def _dashboard_payload() -> dict:
    return {
        "profile": _profile(),
        "stats": {"posts": 1, "reels": 1, "stories": 1, "followers": 2, "following": 3, "friends": 4, "likes": 5, "views": 6},
        "content": {
            "posts": {"items": [{"id": "p1", "caption": "Post"}]},
            "reels": ({"id": "r1", "video_url": "/v.mp4"},),
            "stories": {"results": [{"id": "s1"}]},
            "friends": {"items": [{"username": "friend", "display_name": "Friend"}]},
            "gallery": {"items": []},
            "gallery_preview": {"data": [{"id": "g1"}]},
            "photos": {"rows": []},
            "videos": {"items": [{"id": "v1"}]},
            "saved": {"items": [{"id": "saved1"}]},
            "saved_items": {"results": [{"id": "saved2"}]},
            "tagged": {"items": [{"id": "tag1"}]},
            "albums": {"items": [{"id": "alb1"}]},
            "favorites": {"items": [{"id": "fav1"}]},
            "rooms": {"items": [{"id": "room1"}]},
        },
        "wallet": {},
        "creator": {},
        "marketplace": {},
        "dating": {},
        "achievements": {"items": [{"label": "A"}]},
        "calls": {},
        "live": {},
        "ai": {},
        "portfolio": {},
        "reputation": {},
        "completion": {},
        "permissions": {},
        "presence": {"status": "online"},
        "actions": [],
        "activity": {"items": [{"activity_label": "Owner act", "activity_type": "post"}]},
        "mutual_friends": {"count": 1, "items": [{"username": "friend", "display_name": "Friend"}]},
        "profile_strength": {"score": 88},
        "recently_active_friends": ({"username": "recent", "display_name": "Recent"},),
        "public_stats": {},
        "level": {},
        "story_highlights": ["Travel"],
        "pinned": {"posts": [], "reels": [], "products": []},
        "contact": {},
        "theme_options": [],
        "super_tabs": [],
        "collections": {"items": [{"id": "col1", "title": "Collection"}]},
        "visitors": {"items": [{"username": "visitor", "display_name": "Visitor"}]},
        "timeline": {"items": [{"id": "t1", "event_label": "Timeline"}]},
        "education": {"items": [{"id": "e1"}]},
        "works": {"items": [{"id": "w1"}]},
        "skills": {"items": [{"id": "s1"}]},
        "badges": {"items": [{"id": "b1"}]},
        "favorites_music": {"items": [{"id": "m1"}]},
        "favorites_games": {"items": [{"id": "g1"}]},
    }


def main() -> None:
    profile = _profile()
    payload = _dashboard_payload()

    captured = {}

    def fake_render(template_name, **context):
        captured.clear()
        captured["template"] = template_name
        captured["context"] = context
        return "profile ok"

    # Service-layer contract: malformed collection-like payloads are normalized safely without live DB access.
    with patch("services.profile_dashboard_service.table_exists", return_value=False), \
         patch("services.profile_dashboard_service.safe_select", return_value=[]), \
         patch("services.profile_dashboard_service.safe_count", return_value=0):
        service_bundle = build_profile_dashboard(profile=profile, viewer=dict(profile), bundle=payload)

    check("service normalized pinned posts", isinstance(service_bundle["pinned"]["posts"], list), type(service_bundle["pinned"]["posts"]))
    check("service normalized pinned reels", isinstance(service_bundle["pinned"]["reels"], list), type(service_bundle["pinned"]["reels"]))
    check("service normalized activity", isinstance(service_bundle["activity"], list), type(service_bundle["activity"]))
    check("service normalized recently active friends", isinstance(service_bundle["recently_active_friends"], list), type(service_bundle["recently_active_friends"]))

    # Route renderer contract: malformed bundle values are normalized safely.
    with app.test_request_context("/profile/", method="GET"), patch("api_routes.profile_routes.get_profile_bundle", return_value=payload), patch("api_routes.profile_routes.build_profile_dashboard", return_value=payload), patch("api_routes.profile_routes.render_template", side_effect=fake_render):
        response = _render_profile_index(profile, viewer=dict(profile), bundle=payload, action_policy={"can_chat": False})

    rendered = captured["context"]
    check("owner dashboard renderer returns html", response[1] == 200, response[1])
    check("owner dashboard renderer uses profile template", captured["template"] == "profile/index.html", captured.get("template"))
    check("posts normalized to list", isinstance(rendered["content"]["posts"], list), type(rendered["content"]["posts"]))
    check("reels normalized to list", isinstance(rendered["content"]["reels"], list), type(rendered["content"]["reels"]))
    check("stories normalized to list", isinstance(rendered["content"]["stories"], list), type(rendered["content"]["stories"]))
    check("friends normalized to list", isinstance(rendered["content"]["friends"], list), type(rendered["content"]["friends"]))
    check("gallery normalized to list", isinstance(rendered["content"]["gallery"], list), type(rendered["content"]["gallery"]))
    check("activity normalized to list", isinstance(rendered["activity"], list), type(rendered["activity"]))
    check("collections normalized to list", isinstance(rendered["collections"], list), type(rendered["collections"]))
    check("visitors normalized to list", isinstance(rendered["visitors"], list), type(rendered["visitors"]))
    check("recently active friends normalized to list", isinstance(rendered["recently_active_friends"], list), type(rendered["recently_active_friends"]))
    check("pinned posts normalized to list", isinstance(rendered["pinned"]["posts"], list), type(rendered["pinned"]["posts"]))
    check("pinned reels normalized to list", isinstance(rendered["pinned"]["reels"], list), type(rendered["pinned"]["reels"]))

    # Route-level owner detection: logged-in self should still use the owner path.
    with app.test_request_context("/profile/", method="GET"):
        flask_session["profile_id"] = profile["id"]
        flask_session["auth_user_id"] = profile["id"]
        flask_session["user_id"] = profile["id"]
        flask_session["username"] = profile["username"]
        flask_session["age_verified"] = True
        flask_session["age_check_required"] = False

        with patch("app.get_current_profile", return_value=dict(profile)), \
         patch("services.profile_service.get_current_profile", return_value=dict(profile)), \
         patch("services.notification_engine.unread_count", return_value=0), \
         patch("services.wallet_engine.ensure_wallet", return_value={"coin_balance": 0}), \
         patch("api_routes.profile_routes.get_current_profile", return_value=dict(profile)), \
         patch("api_routes.profile_routes.verify_profile_age", return_value=(True, None)), \
         patch("api_routes.profile_routes.is_profile_complete", return_value=True), \
         patch("api_routes.profile_routes.get_profile_bundle", return_value={"profile": dict(profile), "content": {"posts": [], "reels": [], "stories": [], "rooms": []}, "stats": {}}), \
         patch("api_routes.profile_routes.build_profile_dashboard", return_value=payload), \
         patch("api_routes.profile_routes.get_my_notifications", return_value=([], [], 0)), \
         patch("api_routes.profile_routes.render_template", return_value="profile ok"):
            resp = my_profile()
    check("owner route returns 200 with logged-in owner", resp[1] == 200 if isinstance(resp, tuple) else getattr(resp, "status_code", None) == 200, resp)

    print("TEST_OK owner profile dashboard contract")


if __name__ == "__main__":
    main()
