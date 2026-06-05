import io
import os
import time
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from app import create_app, schedule_delayed_homepage_prewarm
from services import redis_service


class TestLocalRunPolish(unittest.TestCase):
    def setUp(self):
        os.environ["FLASK_ENV"] = "testing"
        self.app = create_app()
        self.client = self.app.test_client()

    def test_chain_disable_prewarm_disables_thread(self):
        os.environ["CHAIN_DISABLE_PREWARM"] = "1"
        with patch("app.threading.Thread") as mock_thread:
            started = schedule_delayed_homepage_prewarm(self.app, debug=True)
        self.assertFalse(started)
        mock_thread.assert_not_called()
        print("prewarm control result: disabled by CHAIN_DISABLE_PREWARM=1")

    def test_discover_under_1000ms_when_neon_slow(self):
        def slow_run(*args, **kwargs):
            time.sleep(1.5)
            return []

        with patch("services.neon_service._run", side_effect=slow_run), \
             patch("services.discovery_service.is_circuit_open", return_value=False):
            start = time.perf_counter()
            response = self.client.get("/discover/")
            elapsed_ms = (time.perf_counter() - start) * 1000

        self.assertEqual(response.status_code, 200)
        self.assertLess(elapsed_ms, 1000, "/discover/ must stay under 1000ms when Neon is slow")
        print(f"discover speed result: {elapsed_ms:.1f}ms")

    def test_redis_missing_does_not_crash_and_warning_is_throttled(self):
        redis_service._REDIS_CLIENT = None
        redis_service._LOG_THROTTLE.clear()

        with patch("services.redis_service.redis.from_url", side_effect=RuntimeError("redis missing")):
            capture = io.StringIO()
            with redirect_stdout(capture):
                first = redis_service.get_redis()
                second = redis_service.get_redis()
                third = redis_service.log_redis_warning("redis_limiter_fallback", "[limiter] Redis unavailable, using in-memory storage")
                fourth = redis_service.log_redis_warning("redis_limiter_fallback", "[limiter] Redis unavailable, using in-memory storage")

        output = capture.getvalue()
        self.assertIsNone(first)
        self.assertIsNone(second)
        self.assertTrue(third)
        self.assertFalse(fourth)
        self.assertEqual(output.count("[redis_service] Redis unavailable"), 1)
        self.assertIn("[limiter] Redis unavailable, using in-memory storage", output)
        self.assertEqual(output.count("[limiter] Redis unavailable, using in-memory storage"), 1)
        print("redis warning throttle result: ok (logged once per 60s)")

    def test_healthz_under_100ms(self):
        start = time.perf_counter()
        response = self.client.get("/healthz")
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertEqual(response.status_code, 200)
        self.assertLess(elapsed_ms, 100, "/healthz must stay under 100ms")
        print(f"/healthz result: {elapsed_ms:.1f}ms")


if __name__ == "__main__":
    unittest.main(verbosity=2)
