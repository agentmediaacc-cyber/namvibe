import unittest
import json
from app import create_app

class TestMobileAPIv1(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_api_envelope(self):
        res = self.client.get('/api/v1/feed/')
        data = res.get_json()
        self.assertIn('success', data)
        self.assertIn('data', data)
        self.assertIn('meta', data)

    def test_auth_unauthorized(self):
        res = self.client.get('/api/v1/notifications/')
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error']['code'], 'unauthorized')

    def test_public_reels(self):
        res = self.client.get('/api/v1/reels/')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

if __name__ == "__main__":
    unittest.main()
