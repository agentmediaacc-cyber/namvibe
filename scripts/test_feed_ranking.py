import time
import unittest
from unittest.mock import patch

from app import create_app
from engines.cache_engine import delete_cache
from services import feed_engine


class TestFeedRanking(unittest.TestCase):
    def setUp(self):
        self.app = create_app()

    def test_weighted_ranking_prefers_live_verified_reel(self):
        rows = [
            {
                "type": "post",
                "id": "post-1",
                "profile_id": "profile-1",
                "title": "Older post",
                "created_at": "2026-05-24T08:00:00+00:00",
                "likes_count": 5,
                "comments_count": 1,
                "shares_count": 0,
                "views_count": 20,
                "is_live": False,
                "is_reel": False,
                "moderation_status": "clean",
                "username": "plain",
                "full_name": "Plain",
                "avatar_url": None,
                "is_verified": False,
                "is_premium": False,
                "is_creator": False,
                "author_region": "windhoek",
                "viewer_region": "windhoek",
                "follows_author": False,
                "author_live_viewers": 0,
            },
            {
                "type": "reel",
                "id": "reel-1",
                "profile_id": "profile-2",
                "title": "Fresh reel",
                "created_at": "2026-05-25T09:45:00+00:00",
                "likes_count": 40,
                "comments_count": 10,
                "shares_count": 8,
                "views_count": 400,
                "is_live": False,
                "is_reel": True,
                "moderation_status": "clean",
                "username": "creator",
                "full_name": "Creator",
                "avatar_url": None,
                "is_verified": True,
                "is_premium": True,
                "is_creator": True,
                "author_region": "windhoek",
                "viewer_region": "windhoek",
                "follows_author": True,
                "author_live_viewers": 20,
            },
            {
                "type": "live_room",
                "id": "live-1",
                "profile_id": "profile-3",
                "title": "Live now",
                "created_at": "2026-05-25T09:50:00+00:00",
                "likes_count": 0,
                "comments_count": 0,
                "shares_count": 0,
                "views_count": 180,
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
                "author_live_viewers": 180,
            },
        ]
        with self.app.test_request_context("/feed/"):
            with patch("services.feed_engine.fast_query", return_value=rows), \
                 patch("services.feed_engine.cache_get", return_value=None), \
                 patch("services.feed_engine.cache_set"):
                ranked = feed_engine.build_feed(profile_id="viewer-1", limit=3)
        self.assertEqual(len(ranked), 3)
        self.assertIn(ranked[0]["type"], {"reel", "live_room"})
        self.assertGreaterEqual(ranked[0]["rank_score"], ranked[1]["rank_score"])
        self.assertGreaterEqual(ranked[1]["rank_score"], ranked[2]["rank_score"])

    def test_feed_dedupe_and_fast_fallback(self):
        delete_cache("feed:explore:anon:5")

        def slow_run(*args, **kwargs):
            time.sleep(1.5)
            return []

        with self.app.test_request_context("/feed/"):
            with patch("services.neon_service._run", side_effect=slow_run):
                start = time.perf_counter()
                payload = feed_engine.build_feed(limit=5)
                elapsed_ms = (time.perf_counter() - start) * 1000
                warm_start = time.perf_counter()
                warm_payload = feed_engine.build_feed(limit=5)
                warm_elapsed_ms = (time.perf_counter() - warm_start) * 1000

        self.assertEqual(payload, [])
        self.assertEqual(warm_payload, [])
        self.assertLess(elapsed_ms, 700, "feed fallback should stay under 700ms")
        self.assertLess(warm_elapsed_ms, 100, "warm feed path should stay under 100ms")
        print(f"feed fallback result: {elapsed_ms:.1f}ms")
        print(f"feed warm result: {warm_elapsed_ms:.1f}ms")

    def test_blocked_muted_filter_clause_exists(self):
        clause = feed_engine._viewer_exclusion_clause("viewer-1")
        self.assertIn("chain_blocks", clause)
        self.assertIn("chain_mutes", clause)


if __name__ == "__main__":
    unittest.main(verbosity=2)
