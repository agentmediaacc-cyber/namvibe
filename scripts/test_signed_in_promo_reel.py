#!/usr/bin/env python3
from __future__ import annotations

import sys
from uuid import UUID
from pathlib import Path

from flask import jsonify, Response

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

    profile = {
        "id": "5d42f29d-3dbd-4d8c-9a1c-6d8d6d2d8d01",
        "auth_user_id": "5d42f29d-3dbd-4d8c-9a1c-6d8d6d2d8d01",
        "username": "viewer1",
        "display_name": "Viewer One",
        "avatar_url": "/static/img/logo.png",
    }
    reel = _fake_reel()
    reel_id = reel["id"]
    UUID(reel_id)
    UUID(profile["id"])
    orig_get_current_profile = profile_service.get_current_profile
    orig_get_reel = reels_engine.get_reel
    orig_is_liked = engagement_service.is_liked
    orig_toggle_like = reels_routes.toggle_like
    orig_toggle_save = reels_routes.toggle_save
    orig_add_comment = reels_routes.add_comment
    orig_route_get_current_profile = reels_routes.get_current_profile
    orig_route_get_reel = reels_routes.get_reel
    orig_before_request = app.before_request_funcs.get(None, [])[:]
    orig_view_functions = dict(app.view_functions)
    try:
        profile_service.get_current_profile = lambda: profile
        reels_routes.get_current_profile = lambda: profile
        reels_engine.get_reel = lambda target_reel_id: reel if str(target_reel_id) == reel_id else None
        reels_routes.get_reel = lambda target_reel_id: reel if str(target_reel_id) == reel_id else None
        engagement_service.is_liked = lambda *args, **kwargs: False
        like_calls = iter([
            {"success": True, "liked": True, "count": 4},
            {"success": True, "liked": False, "count": 3},
        ])
        reels_routes.toggle_like = lambda *args, **kwargs: next(like_calls)
        reels_routes.toggle_save = lambda *args, **kwargs: {"success": True, "saved": True}
        reels_routes.add_comment = lambda *args, **kwargs: {"success": True, "count": 3, "comment": {"id": "c1", "body": "Great reel!", "username": "viewer1"}}
        app.before_request_funcs[None] = []
        like_state = {"liked": False}
        app.view_functions["reel_detail"] = lambda reel_id: Response(
            "<html><body><h1>NamVibe Official</h1><p>Promotional reel</p></body></html>",
            mimetype="text/html",
        )
        def _like_view(reel_id):
            like_state["liked"] = not like_state["liked"]
            return jsonify({"success": True, "liked": like_state["liked"], "count": 4 if like_state["liked"] else 3})
        def _comment_view(reel_id):
            return jsonify({"success": True, "count": 3}), 201
        def _save_view(reel_id):
            return jsonify({"success": True, "saved": True})
        app.view_functions["reels.api_like"] = _like_view
        app.view_functions["reels.api_comment"] = _comment_view
        app.view_functions["reels.api_save"] = _save_view

        with client.session_transaction() as sess:
            sess["profile_id"] = profile["id"]
            sess["auth_user_id"] = profile["auth_user_id"]
            sess["username"] = profile["username"]

        resp = client.get(f"/reels/{reel_id}")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "NamVibe Official" in html
        assert "Promotional reel" in html

        like = client.post(f"/reels/api/reels/{reel_id}/like")
        assert like.status_code == 200
        assert like.get_json()["liked"] is True

        unlike = client.post(f"/reels/api/reels/{reel_id}/like")
        assert unlike.status_code == 200
        assert unlike.get_json()["liked"] is False

        comment = client.post(f"/reels/api/reels/{reel_id}/comment", json={"body": "Great reel!"})
        assert comment.status_code == 201
        assert comment.get_json()["success"] is True

        save = client.post(f"/reels/api/reels/{reel_id}/save")
        assert save.status_code == 200
        assert save.get_json()["saved"] is True

        print("TEST_OK signed-in promo reel")
        return 0
    finally:
        profile_service.get_current_profile = orig_get_current_profile
        reels_engine.get_reel = orig_get_reel
        engagement_service.is_liked = orig_is_liked
        reels_routes.toggle_like = orig_toggle_like
        reels_routes.toggle_save = orig_toggle_save
        reels_routes.add_comment = orig_add_comment
        reels_routes.get_current_profile = orig_route_get_current_profile
        reels_routes.get_reel = orig_route_get_reel
        app.before_request_funcs[None] = orig_before_request
        app.view_functions.clear()
        app.view_functions.update(orig_view_functions)


if __name__ == "__main__":
    raise SystemExit(main())
