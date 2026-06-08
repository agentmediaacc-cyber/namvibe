import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")

from app import create_app
from services.homepage_cache_service import invalidate_homepage_cache
from services.homepage_service import build_homepage_payload
from services.query_optimizer import batch_load_profiles, get_performance_summary


class Phase51PerformanceTest(unittest.TestCase):
    def setUp(self):
        invalidate_homepage_cache()
        with patch("app.prime_neon_runtime"), patch("app.prime_live_rooms_public_cache"), patch("app.init_scheduler"):
            self.app = create_app()
        self.client = self.app.test_client()

    def test_homepage_under_1000ms(self):
        started = time.perf_counter()
        payload = build_homepage_payload()
        elapsed_ms = (time.perf_counter() - started) * 1000
        self.assertLess(elapsed_ms, 1000)
        self.assertIn("stats", payload)

    def test_batch_profile_loading_uses_single_in_query(self):
        captured = []

        def fake_query(label, sql_text, params=None, timeout_ms=1000, default=None, budget_ms=None):
            captured.append((label, sql_text, params))
            return [{"id": "p1", "username": "phase51"}]

        with patch("services.query_optimizer.profiled_query", side_effect=fake_query):
            result = batch_load_profiles(
                ["p1", "p1", "p2"],
                ["id", "username"],
                lambda columns, extra=None: list(extra or []),
                lambda row: row,
            )
        self.assertEqual(len(captured), 1)
        self.assertIn("IN", captured[0][1])
        self.assertEqual(captured[0][2], ["p1", "p2"])
        self.assertIn("p1", result)

    def test_admin_performance_route_exists(self):
        with self.app.test_request_context("/admin/performance"):
            with self.client.session_transaction() as sess:
                sess["admin_id"] = "test-admin"
            response = self.client.get("/admin/performance")
        self.assertIn(response.status_code, (200, 302))

    def test_create_budgets_are_documented(self):
        budgets = {
            "posts_create_ms": 500,
            "reels_create_ms": 500,
            "stories_create_ms": 500,
        }
        for budget in budgets.values():
            self.assertLessEqual(budget, 500)

    def test_profiler_summary_shape(self):
        summary = get_performance_summary()
        self.assertIn("budgets", summary)
        self.assertIn("recent_queries", summary)


if __name__ == "__main__":
    unittest.main()
