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


BASE_PAYLOAD = {
    "success": True,
    "homepage_degraded": False,
    "posts": [
        {
            "id": "post-public-1",
            "type": "post",
            "title": "",
            "caption": "Public post from Namibia #namvibe",
            "body": "Public post from Namibia #namvibe",
            "media_url": "https://cdn.example.com/post.jpg",
            "video_url": "",
            "image_url": "https://cdn.example.com/post.jpg",
            "creator_id": "creator-1",
            "creator_name": "Public Creator",
            "creator_username": "publiccreator",
            "creator_avatar": "https://cdn.example.com/avatar.jpg",
            "created_at": "2026-07-09T08:00:00+00:00",
            "privacy": "public",
            "stats": {"likes": 3, "comments": 1, "shares": 0, "views": 12},
            "display_name": "Public Creator",
            "username": "publiccreator",
            "avatar_url": "https://cdn.example.com/avatar.jpg",
            "profile_id": "creator-1",
            "likes_count": 3,
            "comments_count": 1,
            "shares_count": 0,
            "views_count": 12,
            "created_label": "1h ago",
        }
    ],
    "feed_items": [],
    "feed_for_you": [],
    "reels": [
        {
            "id": "reel-public-1",
            "type": "reel",
            "title": "",
            "caption": "Public reel #reels",
            "body": "Public reel #reels",
            "media_url": "https://cdn.example.com/reel.mp4",
            "video_url": "https://cdn.example.com/reel.mp4",
            "image_url": "https://cdn.example.com/reel.jpg",
            "creator_id": "creator-1",
            "creator_name": "Public Creator",
            "creator_username": "publiccreator",
            "creator_avatar": "https://cdn.example.com/avatar.jpg",
            "created_at": "2026-07-09T08:00:00+00:00",
            "privacy": "public",
            "stats": {"likes": 5, "comments": 2, "shares": 1, "views": 20},
            "display_name": "Public Creator",
            "username": "publiccreator",
            "avatar_url": "https://cdn.example.com/avatar.jpg",
            "profile_id": "creator-1",
            "likes_count": 5,
            "comments_count": 2,
            "shares_count": 1,
            "views_count": 20,
            "created_label": "1h ago",
        }
    ],
    "stories": [
        {
            "id": "story-public-1",
            "type": "story",
            "title": "",
            "caption": "Public story #story",
            "body": "Public story #story",
            "media_url": "https://cdn.example.com/story.jpg",
            "video_url": "",
            "image_url": "https://cdn.example.com/story.jpg",
            "creator_id": "creator-1",
            "creator_name": "Public Creator",
            "creator_username": "publiccreator",
            "creator_avatar": "https://cdn.example.com/avatar.jpg",
            "created_at": "2026-07-09T08:00:00+00:00",
            "privacy": "public",
            "stats": {"likes": 0, "comments": 0, "shares": 0, "views": 9},
            "display_name": "Public Creator",
            "username": "publiccreator",
            "avatar_url": "https://cdn.example.com/avatar.jpg",
            "profile_id": "creator-1",
            "views_count": 9,
            "created_label": "1h ago",
        }
    ],
    "live_rooms": [
        {
            "id": "live-1",
            "type": "live_room",
            "title": "Live with Public Creator",
            "media_url": "https://cdn.example.com/live.jpg",
            "video_url": "",
            "image_url": "https://cdn.example.com/live.jpg",
            "creator_id": "creator-1",
            "creator_name": "Public Creator",
            "creator_username": "publiccreator",
            "creator_avatar": "https://cdn.example.com/avatar.jpg",
            "created_at": "2026-07-09T08:00:00+00:00",
            "privacy": "public",
            "stats": {"likes": 0, "comments": 0, "shares": 0, "views": 7},
            "viewer_count": 7,
            "watch_url": "/live/live-1",
        }
    ],
    "suggested_creators": [
        {
            "id": "creator-1",
            "type": "profile",
            "creator_name": "Public Creator",
            "creator_username": "publiccreator",
            "creator_avatar": "https://cdn.example.com/avatar.jpg",
            "display_name": "Public Creator",
            "username": "publiccreator",
            "avatar_url": "https://cdn.example.com/avatar.jpg",
            "followers_count": 42,
            "privacy": "public",
            "stats": {"likes": 0, "comments": 0, "shares": 0, "views": 0},
        }
    ],
    "suggested_people": [],
    "trending_hashtags": [{"tag": "namvibe", "hashtag": "namvibe", "count": 2, "posts_count": 2}],
    "online_users": [{"id": "creator-1", "username": "publiccreator", "display_name": "Public Creator", "avatar_url": "https://cdn.example.com/avatar.jpg"}],
    "counts": {"live_now": 1, "unread_messages": 0, "coins": 0},
    "friend_activity": [],
    "empty_states": {"feed": False, "stories": False, "reels": False, "live": False, "suggested": False, "hashtags": False},
}


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def _patch_homepage_contract(payload, widget_payload):
    return (
        patch("app.get_full", return_value=None),
        patch("api_routes.homepage_api._HOMEPAGE_CACHE", {"payload": None, "expires_at": 0}),
        patch("api_routes.homepage_api._build_homepage_contract", return_value=payload),
        patch("api_routes.homepage_api._get_homepage_widgets", return_value=widget_payload),
    )


def test_api_contract(client):
    with patch("api_routes.homepage_api._build_homepage_contract", return_value=dict(BASE_PAYLOAD)):
        response = client.get("/api/homepage/feed")
    data = response.get_json()
    assert_true(response.status_code == 200, "homepage API should return 200")
    for key in ("success", "posts", "reels", "stories", "live_rooms", "suggested_creators", "trending_hashtags", "online_users", "counts"):
        assert_true(key in data, f"missing API key: {key}")
    assert_true(data["success"] is True, "success should be true")
    assert_true(data["posts"][0]["privacy"] == "public", "public post should remain visible")
    assert_true("Private" not in str(data), "private content should not leak into payload")


def test_rendered_homepage(client):
    payload = dict(BASE_PAYLOAD)
    payload["feed_items"] = list(payload["posts"])
    payload["feed_for_you"] = list(payload["posts"])
    widget_payload = {
        "ok": True,
        "suggested_creators": list(payload["suggested_creators"]),
        "suggested_people": list(payload["suggested_creators"]),
        "trending_hashtags": list(payload["trending_hashtags"]),
        "live_rooms": list(payload["live_rooms"]),
        "online_users": list(payload["online_users"]),
        "counts": dict(payload["counts"]),
        "timings": {},
    }
    with _patch_homepage_contract(payload, widget_payload)[0], \
         _patch_homepage_contract(payload, widget_payload)[1], \
         _patch_homepage_contract(payload, widget_payload)[2], \
         _patch_homepage_contract(payload, widget_payload)[3]:
        response = client.get("/")
    html = response.get_data(as_text=True)
    forbidden = [
        "debug_test",
        "UI Test",
        "Tester",
        "Test photo caption",
        "Real JPEG upload test",
        "Promo - UI Test",
        "Connection lost",
        "fake",
        "demo",
        "placeholder",
        "Beta Feedback",
        "Special homepage",
        "mock",
        "developer",
    ]
    for term in forbidden:
        assert_true(term.lower() not in html.lower(), f"forbidden public term leaked: {term}")
    assert_true("Public post from Namibia" in html, "public posts should render")


def test_empty_sections_hidden(client):
    payload = dict(BASE_PAYLOAD)
    payload["suggested_creators"] = []
    payload["suggested_people"] = []
    payload["trending_hashtags"] = []
    payload["empty_states"] = dict(payload["empty_states"], suggested=True, hashtags=True)
    payload["feed_items"] = list(payload["posts"])
    widget_payload = {
        "ok": True,
        "suggested_creators": [],
        "suggested_people": [],
        "trending_hashtags": [],
        "live_rooms": list(payload["live_rooms"]),
        "online_users": list(payload["online_users"]),
        "counts": dict(payload["counts"]),
        "timings": {},
    }
    with _patch_homepage_contract(payload, widget_payload)[0], \
         _patch_homepage_contract(payload, widget_payload)[1], \
         _patch_homepage_contract(payload, widget_payload)[2], \
         _patch_homepage_contract(payload, widget_payload)[3]:
        response = client.get("/")
    html = response.get_data(as_text=True)
    assert_true('id="nv-home-suggestions-section" hidden' in html, "empty suggestions section should stay hidden")
    assert_true('id="nv-home-hashtags-section" hidden' in html, "empty hashtags section should stay hidden")


def test_real_suggestions_render(client):
    payload = dict(BASE_PAYLOAD)
    payload["feed_items"] = list(payload["posts"])
    payload["empty_states"] = dict(payload["empty_states"], suggested=False, hashtags=False)
    widget_payload = {
        "ok": True,
        "suggested_creators": list(payload["suggested_creators"]),
        "suggested_people": list(payload["suggested_creators"]),
        "trending_hashtags": list(payload["trending_hashtags"]),
        "live_rooms": list(payload["live_rooms"]),
        "online_users": list(payload["online_users"]),
        "counts": dict(payload["counts"]),
        "timings": {},
    }
    with _patch_homepage_contract(payload, widget_payload)[0], \
         _patch_homepage_contract(payload, widget_payload)[1], \
         _patch_homepage_contract(payload, widget_payload)[2], \
         _patch_homepage_contract(payload, widget_payload)[3]:
        response = client.get("/")
    html = response.get_data(as_text=True)
    assert_true('id="nv-home-suggestions-section" hidden' not in html, "real suggestions section should render normally")
    assert_true("Public Creator" in html, "real suggestions should be present in rendered HTML")


if __name__ == "__main__":
    with app.test_client() as client:
        test_api_contract(client)
        test_rendered_homepage(client)
        test_empty_sections_hidden(client)
        test_real_suggestions_render(client)
    print("homepage production reality: ok")
