import os
import unittest
from flask import Flask, session
from services.auth_service import handle_oauth_callback
from unittest.mock import MagicMock, patch

class TestOAuthIntentFlow(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'test'
        self.ctx = self.app.test_request_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    @patch('services.auth_service.get_supabase')
    @patch('services.auth_service._find_profile_for_user')
    def test_oauth_login_mode_no_account(self, mock_find, mock_supabase):
        print("\n[test] Testing OAuth callback in 'login' mode with no existing account...")
        
        # Mock Supabase callback success
        mock_auth_res = MagicMock()
        mock_auth_res.user = MagicMock(id="test-user-id", email="new@example.com")
        mock_auth_res.session = MagicMock()
        mock_supabase.return_value.auth.exchange_code_for_session.return_value = mock_auth_res
        
        # Mock no existing profile
        mock_find.return_value = None
        
        ok, result = handle_oauth_callback("google", {"code": "test-code"}, mode="login")
        
        self.assertFalse(ok)
        self.assertEqual(result, "OAUTH_SIGNUP_REQUIRED")
        print("Success: OAuth login mode correctly refused unknown account.")

    @patch('services.auth_service.get_supabase')
    @patch('services.auth_service.sync_oauth_profile')
    @patch('services.auth_service.store_auth_session')
    def test_oauth_signup_mode_creates_account(self, mock_store, mock_sync, mock_supabase):
        print("\n[test] Testing OAuth callback in 'signup' mode...")
        
        # Mock Supabase callback success
        mock_auth_res = MagicMock()
        mock_auth_res.user = MagicMock(id="test-user-id", email="new@example.com")
        mock_auth_res.session = MagicMock()
        mock_supabase.return_value.auth.exchange_code_for_session.return_value = mock_auth_res
        
        # Mock sync_oauth_profile success
        mock_sync.return_value = {"id": "new-profile-id", "username": "newuser", "profile_completed": False, "date_of_birth": "1990-01-01"}
        
        ok, result = handle_oauth_callback("google", {"code": "test-code"}, mode="signup")
        
        self.assertTrue(ok)
        self.assertEqual(result, "/profile/onboarding")
        print("Success: OAuth signup mode allowed new account creation.")

if __name__ == "__main__":
    unittest.main()
