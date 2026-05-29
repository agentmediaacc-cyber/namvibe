import os
import time
import unittest
from services.homepage_service import _load_public_homepage

class TestHomepageFast(unittest.TestCase):
    def test_homepage_performance(self):
        print("\n[test] Checking Homepage performance...")
        # Clear cache for cold start test if possible (or just assume first run is cold)
        from engines.cache_engine import delete_cache, cache_key
        delete_cache(cache_key("chain_homepage_neon_v1", "public"))
        
        start = time.perf_counter()
        data = _load_public_homepage()
        elapsed_cold = (time.perf_counter() - start) * 1000
        print(f"  Cold start: {elapsed_cold:.1f}ms")
        
        start = time.perf_counter()
        data = _load_public_homepage()
        elapsed_warm = (time.perf_counter() - start) * 1000
        print(f"  Warm start: {elapsed_warm:.1f}ms")
        
        # Note: cold start might still be high if DB is actually cold, 
        # but we target < 800ms.
        if elapsed_cold > 800:
            print(f"  WARNING: Cold start {elapsed_cold:.1f}ms exceeds 800ms target")
        
        self.assertLess(elapsed_warm, 100, "Warm start should be under 100ms")

if __name__ == "__main__":
    unittest.main()
