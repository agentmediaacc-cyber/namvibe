#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from flask import Flask
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.reels_service import build_viewer_reels_feed_cache_key, get_reel_feed


def main() -> int:
    viewer_id = "010e54de-c11e-4f5f-9f98-4d674d721d59"
    cache_key = build_viewer_reels_feed_cache_key(
        content_version=7,
        limit=5,
        cursor=None,
        viewer_id=viewer_id,
    )
    assert "viewer:010e54de-c11e-4f5f-9f98-4d674d721d59" in cache_key
    assert "csrf" not in cache_key.lower()
    assert "session" not in cache_key.lower()

    cached_payload = {"items": [{"id": "reel-1"}], "next_cursor": None, "has_more": False}
    with patch("services.redis_service.redis_manager") as redis_manager, \
         patch("services.reels_service.fast_query", side_effect=AssertionError("cache hit should skip DB")):
        redis_manager.get_json_result.return_value = {"shared": True, "value": cached_payload, "backend": "redis"}
        payload = get_reel_feed(limit=5, viewer_id=viewer_id)
        assert payload == cached_payload

    app = Flask(__name__)
    app.secret_key = "test"
    with app.test_request_context("/reels/api/reels/feed?limit=5"):
        from flask import session

        session["profile_id"] = viewer_id
        session["auth_user_id"] = "auth-1"
        with patch("api_routes.reels_routes.get_current_profile", side_effect=AssertionError("route should not load full profile")), \
             patch("services.reels_service.get_reel_feed", return_value=cached_payload) as feed_mock:
            from api_routes.reels_routes import api_reels_feed
            response = api_reels_feed()
            assert response.status_code == 200
            assert response.get_json()["items"] == cached_payload["items"]
            assert feed_mock.call_count == 1
            assert feed_mock.call_args.kwargs["viewer_id"] == viewer_id

    print("TEST_OK reel feed performance contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
