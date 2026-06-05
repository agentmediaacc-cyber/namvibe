import os
import sys
import unittest
from flask import session

class LaunchReadinessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Disable rate limits for tests
        os.environ["CHAIN_DISABLE_RATE_LIMITS"] = "1"
        from app import create_app
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def test_healthz(self):
        res = self.client.get("/healthz")
        self.assertEqual(res.status_code, 200)

    def test_health_endpoints(self):
        for path in ["/health/db", "/health/supabase", "/health/redis", "/health/realtime"]:
            res = self.client.get(path)
            self.assertIn(res.status_code, [200, 503]) # 503 is okay if service down but endpoint exists

    def test_public_routes_200(self):
        routes = ["/", "/discover/", "/live/", "/reels/", "/feed/"]
        for r in routes:
            res = self.client.get(r)
            self.assertEqual(res.status_code, 200, f"Route {r} failed")

    def test_protected_routes_redirect(self):
        routes = ["/messages/", "/wallet/", "/notifications/", "/profile/", "/verification/"]
        for r in routes:
            res = self.client.get(r)
            self.assertEqual(res.status_code, 302, f"Route {r} should redirect")
            self.assertIn("/auth/login", res.location)

    def test_auth_pages_200(self):
        for r in ["/auth/login", "/auth/register"]:
            res = self.client.get(r)
            self.assertEqual(res.status_code, 200)

    def test_static_assets(self):
        res = self.client.get("/static/css/chain_theme.css")
        self.assertEqual(res.status_code, 200)

if __name__ == "__main__":
    print("[launch] Running readiness suite...")
    unittest.main()
