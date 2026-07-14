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


PAYLOAD = {
    "feed_items": [
        {
            "id": "reel-public-1",
            "type": "reel",
            "caption": "Public NamVibe reel",
            "body": "Public NamVibe reel",
            "privacy": "public",
            "profile_id": "creator-1",
            "username": "publiccreator",
            "display_name": "Public Creator",
            "video_url": "https://cdn.example.com/reel.mp4",
            "thumbnail_url": "https://cdn.example.com/reel.jpg",
        }
    ],
    "posts": [
        {
            "id": "post-public-1",
            "type": "post",
            "caption": "Public NamVibe post",
            "body": "Public NamVibe post",
            "privacy": "public",
            "profile_id": "creator-1",
            "username": "publiccreator",
            "display_name": "Public Creator",
        }
    ],
    "reels": [
        {
            "id": "reel-public-1",
            "type": "reel",
            "caption": "Public NamVibe reel",
            "body": "Public NamVibe reel",
            "privacy": "public",
            "profile_id": "creator-1",
            "username": "publiccreator",
            "display_name": "Public Creator",
            "video_url": "https://cdn.example.com/reel.mp4",
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


def test_homepage_cached_public_content_renders(client):
    with patch("app.get_full", return_value=dict(PAYLOAD)), patch("api_routes.homepage_api._build_homepage_contract", side_effect=RuntimeError("should not be used")), patch("services.homepage_service.get_homepage_data", side_effect=RuntimeError("should not be used")):
        response = client.get("/")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "reel-public-1" in html
    assert "data-post-id=\"reel-public-1\"" in html
    assert "<video" in html


if __name__ == "__main__":
    with app.test_client() as client:
        test_homepage_cached_public_content_renders(client)
    print("OK")
