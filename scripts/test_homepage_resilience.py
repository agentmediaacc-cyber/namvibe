import unittest
import time
from unittest.mock import patch, MagicMock
from services.homepage_service import build_homepage_payload
from app import create_app

class TestHomepageResilience(unittest.TestCase):
    def setUp(self):
        # Mocking time-consuming app initialization
        with patch("app.prime_neon_runtime"), \
             patch("app.prime_live_rooms_public_cache"), \
             patch("app.init_scheduler"), \
             patch("threading.Thread"):
            self.app = create_app()
        
        # Clear schema cache to force lookup
        import services.homepage_service
        services.homepage_service._SCHEMA_CACHE = {}
        from engines.cache_engine import set_cache, cache_key
        # Ensure we don't hit real cache
        set_cache(cache_key("chain_homepage_v3", "public"), None)

    def test_reels_missing_video_url(self):
        print("\n[test] Verifying Homepage resilience when video_url is missing...")
        
        # Mock schema lookup to return reels WITHOUT video_url
        mock_schemas = {
            "chain_profiles": ["id", "username", "display_name"],
            "chain_posts": ["id", "caption"],
            "chain_stories": ["id", "caption"],
            "chain_status_posts": ["id", "caption"],
            "chain_reels": ["id", "profile_id", "caption"], # NO video_url
            "chain_live_rooms": ["id", "title"]
        }
        
        with patch("services.homepage_service.get_pool_status", return_value={"recent_success": True, "pool_ready": True}), \
             patch("services.homepage_service.get_tables_columns", return_value=mock_schemas), \
             patch("services.homepage_service.get_cached_table_columns", return_value=None), \
             patch("services.homepage_service.fast_query", return_value=[]), \
             patch("services.homepage_service.get_cache", return_value=None), \
             patch("services.homepage_service.set_cache"):
            
            with self.app.app_context():
                start = time.perf_counter()
                payload = build_homepage_payload()
                elapsed = (time.perf_counter() - start) * 1000
                
                print(f"  Build time with missing column: {elapsed:.1f}ms")
                self.assertLess(elapsed, 1000, "Homepage build should be fast even with schema issues")
                
                # Verify reels are still returned (if any in DB) but we didn't crash
                self.assertEqual(payload.get("reels"), [])
                
                print("  Resilience check PASSED")

    def test_schema_lookup_failure(self):
        print("\n[test] Verifying Homepage resilience when schema lookup fails completely...")
        
        with patch("services.homepage_service.get_pool_status", return_value={"recent_success": True, "pool_ready": True}), \
             patch("services.homepage_service.get_tables_columns", side_effect=Exception("DB Timeout")), \
             patch("services.homepage_service.get_cached_table_columns", return_value=None), \
             patch("services.homepage_service.fast_query", return_value=[]), \
             patch("services.homepage_service.get_cache", return_value=None), \
             patch("services.homepage_service.set_cache"):
            
            with self.app.app_context():
                start = time.perf_counter()
                payload = build_homepage_payload()
                elapsed = (time.perf_counter() - start) * 1000
                
                print(f"  Build time with failed lookup: {elapsed:.1f}ms")
                self.assertLess(elapsed, 1000)
                
                # Reels should be empty if schema lookup failed
                self.assertEqual(len(payload.get("reels", [])), 0)
                # Check issues list for reels mismatch
                issues = payload.get("issues", [])
                self.assertTrue(any("reels: schema_mismatch" in i for i in issues), f"Expected 'reels: schema_mismatch' in {issues}")
                
                print("  Lookup failure check PASSED")

if __name__ == "__main__":
    unittest.main()
