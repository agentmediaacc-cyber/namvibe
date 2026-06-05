import unittest
from unittest.mock import patch

from app import create_app
from services import feed_engine


class TestFeedBatching(unittest.TestCase):
    def setUp(self):
        self.app = create_app()

    def test_feed_uses_single_batched_query_path(self):
        rows = [{
            "type": "live_room",
            "id": "live-1",
            "profile_id": "host-1",
            "title": "Live",
            "created_at": "2026-05-25T10:00:00+00:00",
            "likes_count": 0,
            "comments_count": 0,
            "shares_count": 0,
            "views_count": 50,
            "is_live": True,
            "is_reel": False,
            "moderation_status": "clean",
            "username": "host",
            "full_name": "Host",
            "avatar_url": None,
            "is_verified": True,
            "is_premium": False,
            "is_creator": True,
            "author_region": "windhoek",
            "viewer_region": "windhoek",
            "follows_author": False,
            "author_live_viewers": 50,
        }]
        with self.app.test_request_context("/feed/"):
            with patch("services.feed_engine.fast_query", return_value=rows) as mock_fast, \
                 patch("services.feed_engine.cache_get", return_value=None), \
                 patch("services.feed_engine.cache_set"):
                payload = feed_engine.build_feed(profile_id="viewer", limit=10)
        self.assertEqual(len(payload), 1)
        self.assertEqual(mock_fast.call_count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
