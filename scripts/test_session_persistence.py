import os
import time
import unittest
from flask import Flask, session
from services.session_service import (
    store_auth_session, 
    clear_auth_session, 
    is_logged_in, 
    refresh_supabase_session_if_needed,
    K_USER_ID, K_ACCESS_TOKEN, K_REFRESH_TOKEN, K_EXPIRES_AT
)
from unittest.mock import MagicMock, patch

class TestSessionPersistence(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'test'
        self.ctx = self.app.test_request_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_store_and_clear_session(self):
        print("\n[test] Testing store and clear session...")
        
        user = MagicMock(id="test-user-id", email="test@example.com")
        auth_session = MagicMock(access_token="access", refresh_token="refresh", expires_in=3600)
        profile = {"id": "p1", "username": "user1"}
        
        store_auth_session(auth_session, user, profile, provider="password")
        
        self.assertTrue(is_logged_in())
        self.assertEqual(session.get(K_USER_ID), "test-user-id")
        self.assertEqual(session.get(K_ACCESS_TOKEN), "access")
        
        clear_auth_session()
        
        self.assertFalse(is_logged_in())
        self.assertIsNone(session.get(K_USER_ID))
        self.assertIsNone(session.get(K_ACCESS_TOKEN))
        print("Success: Store and clear session working.")

    @patch('services.session_service.get_supabase')
    def test_refresh_session_success(self, mock_supabase):
        print("\n[test] Testing refresh session success...")
        
        session[K_REFRESH_TOKEN] = "old-refresh"
        
        # Mock Supabase refresh success
        mock_auth_res = MagicMock()
        mock_auth_res.user = MagicMock(id="test-user-id", email="test@example.com")
        mock_auth_res.session = MagicMock(access_token="new-access", refresh_token="new-refresh", expires_in=3600)
        mock_supabase.return_value.auth.refresh_session.return_value = mock_auth_res
        
        ok = refresh_supabase_session_if_needed()
        
        self.assertTrue(ok)
        self.assertEqual(session.get(K_ACCESS_TOKEN), "new-access")
        self.assertEqual(session.get(K_REFRESH_TOKEN), "new-refresh")
        print("Success: Session refresh working.")

    @patch('services.session_service.get_supabase')
    def test_refresh_session_failure_clears_session(self, mock_supabase):
        print("\n[test] Testing refresh session failure clears session...")
        
        session[K_USER_ID] = "some-user"
        session[K_REFRESH_TOKEN] = "bad-refresh"
        
        # Mock Supabase refresh failure
        mock_supabase.return_value.auth.refresh_session.side_effect = Exception("Invalid refresh token")
        
        ok = refresh_supabase_session_if_needed()
        
        self.assertFalse(ok)
        self.assertFalse(is_logged_in())
        self.assertIsNone(session.get(K_USER_ID))
        print("Success: Session cleared on refresh failure.")

if __name__ == "__main__":
    unittest.main()
