import io
import time
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from app import create_app
from engines.cache_engine import delete_cache
from services import feed_engine, recommendation_service


class TestScalingReadiness(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def test_no_route_500_and_websocket_init_safe(self):
        routes = ["/", "/discover/", "/feed/", "/reels/", "/healthz"]
        for path in routes:
            response = self.client.get(path)
            self.assertLess(response.status_code, 500, f"{path} returned {response.status_code}")

    def test_feed_cache_and_duplicate_query_dedupe(self):
        feed_engine.cache_set("feed:explore:anon:5", None, ttl=0)
        calls = {"count": 0}

        def fake_fast_query(*args, **kwargs):
            calls["count"] += 1
            return [
                {
                    "type": "reel",
                    "id": "reel-1",
                    "profile_id": "profile-1",
                    "title": "Reel",
                    "created_at": "2026-05-25T10:00:00+00:00",
                    "likes_count": 10,
                    "comments_count": 5,
                    "shares_count": 1,
                    "views_count": 100,
                    "is_live": False,
                    "is_reel": True,
                    "moderation_status": "clean",
                    "username": "creator",
                    "full_name": "Creator",
                    "avatar_url": None,
                    "is_verified": True,
                    "is_premium": True,
                    "is_creator": True,
                    "author_region": "Windhoek",
                    "viewer_region": "Windhoek",
                    "follows_author": False,
                    "author_live_viewers": 0,
                }
            ]

        with self.app.test_request_context("/feed/"):
            with patch("services.feed_engine.fast_query", side_effect=fake_fast_query):
                first = feed_engine.build_feed(limit=5)
                second = feed_engine.build_feed(limit=5)
        self.assertEqual(calls["count"], 1)
        self.assertEqual(first, second)
        self.assertTrue(first and "rank_score" in first[0])

    def test_recommendation_fallback_and_warm_cache(self):
        with patch("services.recommendation_service.is_circuit_open", return_value=True):
            start = time.perf_counter()
            payload = recommendation_service.get_recommended_profiles(None, limit=5)
            elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertEqual(payload, [])
        self.assertLess(elapsed_ms, 100)

        warm_payload = [{"id": "p1", "recommendation_score": 10}]
        with patch("services.recommendation_service.cache_get", return_value=warm_payload):
            start = time.perf_counter()
            cached = recommendation_service.get_recommended_profiles(None, limit=5)
            elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertEqual(cached, warm_payload)
        self.assertLess(elapsed_ms, 100)

    def test_no_repeated_slow_logs(self):
        delete_cache("slow_log_healthz_/healthz")
        capture = io.StringIO()
        with redirect_stdout(capture):
            with patch("app.time.perf_counter", side_effect=[0.0, 1.0, 0.0, 1.0]):
                self.client.get("/healthz")
                self.client.get("/healthz")
        output = capture.getvalue()
        self.assertEqual(output.count("\"event\": \"slow_request\""), 1)

    def test_realtime_and_worker_imports(self):
        import services.socketio_service as socketio_service
        import services.socket_events as socket_events
        import scripts.chain_worker as chain_worker

        self.assertTrue(hasattr(socketio_service, "socketio"))
        self.assertTrue(hasattr(socket_events, "handle_connect"))
        self.assertTrue(chain_worker is not None)

    def test_no_public_admin_link_on_home(self):
        response = self.client.get("/")
        self.assertLess(response.status_code, 500)
        self.assertNotIn("/admin", response.get_data(as_text=True).lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
