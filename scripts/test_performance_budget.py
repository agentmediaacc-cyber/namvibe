import time
import unittest
from unittest.mock import patch, MagicMock
import os
from services.homepage_service import build_homepage_payload
from app import create_app

class TestPerformanceBudget(unittest.TestCase):
    def setUp(self):
        # Mocking time-consuming app initialization and prewarm
        with patch.dict(os.environ, {"CHAIN_DISABLE_RATE_LIMITS": "1"}), \
             patch("app.prime_neon_runtime"), \
             patch("app.prime_live_rooms_public_cache"), \
             patch("app.init_scheduler"):
            self.app = create_app()
        self.client = self.app.test_client()

    def test_homepage_budget(self):
        print("\n[test] Verifying Homepage performance budget...")
        with self.app.app_context():
            # Force fallback by mocking Neon internal _run to be slow (2s sleep)
            # This verifies the HARD wall-clock timeout in neon_service.fast_query
            def slow_run(*a, **k):
                time.sleep(2)
                return []

            mock_schemas = {t: ["id", "created_at"] for t in [
                "chain_profiles", "chain_posts", "chain_stories", 
                "chain_status_posts", "chain_reels", "chain_live_rooms"
            ]}
            mock_schemas["chain_profiles"].extend(["username", "display_name", "is_creator", "dating_mode_enabled"])
            mock_schemas["chain_reels"].extend(["video_url", "profile_id"])

            with patch("services.homepage_service.get_pool_status", return_value={"recent_success": True, "pool_ready": True, "circuit_open": False}), \
                 patch("services.homepage_service.get_tables_columns", return_value=mock_schemas), \
                 patch("services.homepage_service.get_cached_table_columns", return_value=None), \
                 patch("services.neon_service._run", side_effect=slow_run):
                
                start = time.perf_counter()
                payload = build_homepage_payload()
                elapsed_fallback = (time.perf_counter() - start) * 1000
                print(f"  Fallback build (simulated 2s Neon delay): {elapsed_fallback:.1f}ms")
                
                # Either we caught the first timeout (partial_fallback)
                # or the circuit opened and we exited early (neon: unavailable)
                has_fallback_issue = any(i in payload.get("issues", []) for i in ["partial_fallback", "neon: unavailable"])
                self.assertTrue(has_fallback_issue, f"Expected fallback issue in {payload.get('issues')}")
                self.assertLess(elapsed_fallback, 800, "Homepage fallback must be under 800ms")

            # Warm build (cached)
            from engines.cache_engine import set_cache, cache_key
            set_cache(cache_key("chain_homepage_v3", "public"), {"mock": "data", "issues": [], "stats": {}}, ttl=30)
            
            start = time.perf_counter()
            build_homepage_payload()
            elapsed_warm = (time.perf_counter() - start) * 1000
            print(f"  Warm build (cached): {elapsed_warm:.1f}ms")
            self.assertLess(elapsed_warm, 80, "Warm homepage build must be under 80ms")

    def test_healthz_speed(self):
        print("\n[test] Verifying /healthz speed...")
        start = time.perf_counter()
        res = self.client.get("/healthz")
        elapsed = (time.perf_counter() - start) * 1000
        print(f"  /healthz: {elapsed:.1f}ms")
        self.assertEqual(res.status_code, 200)
        self.assertLess(elapsed, 50, "/healthz must be under 50ms")

if __name__ == "__main__":
    unittest.main()
