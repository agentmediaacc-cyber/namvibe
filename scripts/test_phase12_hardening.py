import unittest
from app import create_app
from services.media_provider import get_storage_provider
from services.push_notification_engine import send_push_notification

class TestPhase12Hardening(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_media_provider_abstraction(self):
        provider = get_storage_provider()
        self.assertIsNotNone(provider)
        url = provider.get_url("test-bucket", "test-path")
        self.assertTrue(url.startswith("http"))
        print(f"Media provider URL generation: {url} - OK")

    def test_observability_registration(self):
        # Check if observability hooks are registered
        self.assertTrue(any(f.__name__ == 'before_req' for f in self.app.before_request_funcs.get(None, [])))
        self.assertTrue(any(f.__name__ == 'after_req' for f in self.app.after_request_funcs.get(None, [])))
        print("Observability middleware - OK")

    def test_mobile_api_v1_expanded(self):
        client = self.app.test_client()
        # Test existence of new endpoints (they will return 401 but they should exist)
        endpoints = ['/api/mobile/v1/reels', '/api/mobile/v1/stories', '/api/mobile/v1/messages', '/api/mobile/v1/wallet', '/api/mobile/v1/dating/discover']
        for ep in endpoints:
            resp = client.get(ep)
            self.assertEqual(resp.status_code, 401)
            print(f"Mobile API {ep} registration - OK")

if __name__ == '__main__':
    unittest.main()
