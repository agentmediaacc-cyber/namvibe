import os
import sys
from unittest.mock import patch

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app


FULL_CACHE = {
    "feed_items": [
        {
            "id": "full-cache-reel",
            "type": "reel",
            "caption": "Full cache reel",
            "body": "Full cache reel",
            "privacy": "public",
            "profile_id": "creator-full",
            "username": "fullcachecreator",
            "display_name": "Full Cache Creator",
            "video_url": "https://cdn.example.com/full-cache-reel.mp4",
            "thumbnail_url": "https://cdn.example.com/full-cache-reel.jpg",
        }
    ],
    "posts": [
        {
            "id": "full-cache-post",
            "type": "post",
            "caption": "Full cache post",
            "body": "Full cache post",
            "privacy": "public",
            "profile_id": "creator-full",
            "username": "fullcachecreator",
            "display_name": "Full Cache Creator",
        }
    ],
    "reels": [
        {
            "id": "full-cache-reel",
            "type": "reel",
            "caption": "Full cache reel",
            "body": "Full cache reel",
            "privacy": "public",
            "profile_id": "creator-full",
            "username": "fullcachecreator",
            "display_name": "Full Cache Creator",
            "video_url": "https://cdn.example.com/full-cache-reel.mp4",
            "thumbnail_url": "https://cdn.example.com/full-cache-reel.jpg",
        }
    ],
    "stories": [],
    "live_rooms": [],
    "suggested_creators": [],
    "suggested_people": [],
    "trending_hashtags": [],
    "friend_activity": [],
    "online_users": [],
    "counts": {},
    "timings": {},
    "homepage_degraded": False,
}

STALE_CACHE = {
    "feed_items": [
        {
            "id": "stale-cache-reel",
            "type": "reel",
            "caption": "Stale cache reel",
            "body": "Stale cache reel",
            "privacy": "public",
            "profile_id": "creator-stale",
            "username": "stalecachecreator",
            "display_name": "Stale Cache Creator",
            "video_url": "https://cdn.example.com/stale-cache-reel.mp4",
            "thumbnail_url": "https://cdn.example.com/stale-cache-reel.jpg",
        }
    ],
    "posts": [],
    "reels": [],
    "stories": [],
    "live_rooms": [],
    "suggested_creators": [],
    "suggested_people": [],
    "trending_hashtags": [],
    "friend_activity": [],
    "online_users": [],
    "counts": {},
    "timings": {},
    "homepage_degraded": False,
}

PAYLOAD_CACHE = {
    "feed_items": [
        {
            "id": "payload-cache-reel",
            "type": "reel",
            "caption": "Payload cache reel",
            "body": "Payload cache reel",
            "privacy": "public",
            "profile_id": "creator-payload",
            "username": "payloadcachecreator",
            "display_name": "Payload Cache Creator",
            "video_url": "https://cdn.example.com/payload-cache-reel.mp4",
            "thumbnail_url": "https://cdn.example.com/payload-cache-reel.jpg",
        }
    ],
    "posts": [],
    "reels": [],
    "stories": [],
    "live_rooms": [],
    "suggested_creators": [],
    "suggested_people": [],
    "trending_hashtags": [],
    "friend_activity": [],
    "online_users": [],
    "counts": {},
    "timings": {},
    "homepage_degraded": False,
}

BUILDER_PAYLOAD = {
    "feed_items": [
        {
            "id": "builder-reel",
            "type": "reel",
            "caption": "Builder reel",
            "body": "Builder reel",
            "privacy": "public",
            "profile_id": "creator-builder",
            "username": "buildercreator",
            "display_name": "Builder Creator",
            "video_url": "https://cdn.example.com/builder-reel.mp4",
            "thumbnail_url": "https://cdn.example.com/builder-reel.jpg",
        }
    ],
    "posts": [],
    "reels": [],
    "stories": [],
    "live_rooms": [],
    "suggested_creators": [],
    "suggested_people": [],
    "trending_hashtags": [],
    "friend_activity": [],
    "online_users": [],
    "counts": {},
    "timings": {},
    "homepage_degraded": False,
}


def test_homepage_cached_public_content_renders(client):
    with patch("app.get_full_with_stale", return_value=(dict(FULL_CACHE), False)), patch("api_routes.homepage_api._build_homepage_contract", side_effect=RuntimeError("should not be used")), patch("services.homepage_service.get_homepage_data", side_effect=RuntimeError("should not be used")):
        response = client.get("/")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "full-cache-reel" in html
    assert "data-post-id=\"full-cache-reel\"" in html
    assert "<video" in html


def test_empty_cached_homepage_refreshes_from_live_data(client):
    with patch("app.get_full_with_stale", return_value=(dict(STALE_CACHE), True)), patch("app._app_test_mode", return_value=False), patch("app.wait_for_homepage_refresh", return_value=False), patch("api_routes.homepage_api._build_homepage_contract", return_value=dict(BUILDER_PAYLOAD)), patch("services.homepage_service.get_homepage_data", side_effect=RuntimeError("should not be used")):
        response = client.get("/")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "stale-cache-reel" in html
    assert "<video" in html


def test_malformed_full_cache_falls_back_to_payload(client):
    with patch("app.get_full_with_stale", return_value=(None, False)), patch("app._app_test_mode", return_value=False), patch("services.homepage_service.get_homepage_data", return_value=dict(PAYLOAD_CACHE)), patch("api_routes.homepage_api._build_homepage_contract", side_effect=RuntimeError("should not be used")):
        response = client.get("/")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "payload-cache-reel" in html
    assert "<video" in html


if __name__ == "__main__":
    with app.test_client() as client:
        test_homepage_cached_public_content_renders(client)
        test_empty_cached_homepage_refreshes_from_live_data(client)
    print("OK")
