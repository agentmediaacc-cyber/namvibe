import os
import time
import unittest
from services.neon_service import get_neon_health, get_pool_status, prime_neon_runtime
from services.media_storage_service import get_storage_health

class TestConnectionStability(unittest.TestCase):
    def test_neon_health_caching(self):
        print("\n[test] Checking Neon health caching...")
        start = time.perf_counter()
        h1 = get_neon_health()
        t1 = (time.perf_counter() - start) * 1000
        print(f"  First call: {t1:.1f}ms (connected: {h1.get('connected')})")
        
        start = time.perf_counter()
        h2 = get_neon_health()
        t2 = (time.perf_counter() - start) * 1000
        print(f"  Second call (cached): {t2:.1f}ms")
        
        self.assertLess(t2, 5, "Cached health check should be near-instant")
        self.assertEqual(h1.get("connected"), h2.get("connected"))

    def test_neon_pool_status(self):
        print("\n[test] Checking Neon pool status...")
        status = get_pool_status()
        print(f"  Pool ready: {status.get('pool_ready')}")
        print(f"  Ever connected: {status.get('ever_connected')}")
        self.assertTrue(status.get("configured"), "DATABASE_URL must be configured")

    def test_storage_health_caching(self):
        print("\n[test] Checking Storage health caching...")
        start = time.perf_counter()
        h1 = get_storage_health()
        t1 = (time.perf_counter() - start) * 1000
        print(f"  First call: {t1:.1f}ms (connected: {h1.get('connected')})")
        
        start = time.perf_counter()
        h2 = get_storage_health()
        t2 = (time.perf_counter() - start) * 1000
        print(f"  Second call (cached): {t2:.1f}ms")
        
        self.assertLess(t2, 5, "Cached storage health should be near-instant")

    def test_neon_prewarm(self):
        print("\n[test] Checking Neon prewarm...")
        prime_neon_runtime()
        status = get_pool_status()
        self.assertTrue(status.get("pool_ready"), "Pool should be ready after prewarm")

if __name__ == "__main__":
    unittest.main()
