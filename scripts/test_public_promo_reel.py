#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from uuid import UUID
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app


def _fake_reel() -> dict:
    return {
        "id": "9f2f6b59-70ec-5870-9595-eaab42c354c1",
        "profile_id": "db2080ad-549b-41ab-a103-fc6938cc4c57",
        "creator_id": "db2080ad-549b-41ab-a103-fc6938cc4c57",
        "username": "namvibe",
        "display_name": "NamVibe Official",
        "creator_username": "namvibe",
        "creator_url": "/profile/@namvibe",
        "avatar_url": "/static/img/logo.png",
        "thumbnail_url": "/static/uploads/reels/namvibe_promo/namvibe_promo_thumbnail.jpg",
        "video_url": "/static/uploads/reels/namvibe_promo/namvibe_promo_web.mp4",
        "caption": "Promotional reel",
        "likes_count": 3,
        "comments_count": 2,
    }


def main() -> int:
    client = app.test_client()
    from services import profile_service, engagement_service, reels_engine
    import api_routes.reels_routes as reels_routes

    orig_get_current_profile = profile_service.get_current_profile
    orig_get_reel = reels_engine.get_reel
    orig_is_liked = engagement_service.is_liked
    orig_route_get_current_profile = reels_routes.get_current_profile
    orig_route_get_reel = reels_routes.get_reel
    try:
        profile_service.get_current_profile = lambda: None
        reels_routes.get_current_profile = lambda: None
        reels_routes.get_reel = lambda reel_id: _fake_reel() if str(reel_id) == _fake_reel()["id"] else None
        reels_engine.get_reel = lambda reel_id: _fake_reel() if str(reel_id) == _fake_reel()["id"] else None
        engagement_service.is_liked = lambda *args, **kwargs: False

        reel_id = _fake_reel()["id"]
        UUID(reel_id)
        resp = client.get(f"/reels/{reel_id}")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "NamVibe Official" in html
        assert "Promotional reel" in html
        assert "/static/js/reel_auth_prompt.js" in html
        assert "rd-action-btn" in html

        like = client.post(f"/reels/api/reels/{reel_id}/like")
        assert like.status_code == 401
        like_json = like.get_json()
        assert like_json["error"] == "authentication_required"
        assert like_json["login_url"].startswith(f"/auth/login?next=/reels/{reel_id}")

        comment = client.post(f"/reels/api/reels/{reel_id}/comment", json={"body": "Hi"})
        assert comment.status_code == 401
        comment_json = comment.get_json()
        assert comment_json["error"] == "authentication_required"
        assert comment_json["login_url"].startswith(f"/auth/login?next=/reels/{reel_id}")

        save = client.post(f"/reels/api/reels/{reel_id}/save")
        assert save.status_code == 401

        print("TEST_OK public promo reel")
        return 0
    finally:
        profile_service.get_current_profile = orig_get_current_profile
        reels_engine.get_reel = orig_get_reel
        engagement_service.is_liked = orig_is_liked
        reels_routes.get_current_profile = orig_route_get_current_profile
        reels_routes.get_reel = orig_route_get_reel


if __name__ == "__main__":
    raise SystemExit(main())
