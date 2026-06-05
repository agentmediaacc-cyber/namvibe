import os
import unittest
from flask import Flask, session
from services.auth_service import sync_oauth_profile
from unittest.mock import MagicMock, patch

class TestProfileBootstrapResilience(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'test'
        self.ctx = self.app.test_request_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    @patch('services.auth_service.ensure_neon_profile')
    @patch('services.auth_service._find_profile_for_user')
    def test_sync_profile_neon_down(self, mock_find, mock_ensure):
        print("\n[test] Testing sync_oauth_profile resilience when Neon is completely down...")
        
        # Mock finding no existing profile (or just let it return None)
        mock_find.return_value = None
        
        # Mock Neon failure
        mock_ensure.return_value = (False, "Neon chain_profiles table is unavailable.")
        
        user = MagicMock()
        user.id = "test-user-id"
        user.email = "test@example.com"
        user.user_metadata = {"full_name": "Test User"}
        
        profile = sync_oauth_profile(user, "password")
        
        self.assertIsNotNone(profile)
        self.assertTrue(profile.get("setup_warning"))
        self.assertEqual(profile.get("email"), "test@example.com")
        self.assertEqual(profile.get("username"), "test") # default from email if metadata empty? wait.
        # email split is used if metadata name fails. "test@example.com" -> "test"
        
        print("Success: sync_oauth_profile returned a best-effort profile despite Neon failure.")

if __name__ == "__main__":
    unittest.main()
