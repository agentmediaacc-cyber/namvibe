import os
import unittest
from flask import Flask, session
from services.auth_service import register_chain_user, _age_from_date
from unittest.mock import MagicMock, patch

class TestAuthRegistrationFlow(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'test'
        self.ctx = self.app.test_request_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_age_validation(self):
        print("\n[test] Checking age validation...")
        from datetime import datetime, timedelta, timezone
        dob_17 = (datetime.now(timezone.utc) - timedelta(days=17*365 + 10)).date().isoformat()
        age_17 = _age_from_date(dob_17)
        self.assertLess(age_17, 18)
        
        dob_19 = (datetime.now(timezone.utc) - timedelta(days=19*365 + 10)).date().isoformat()
        age_19 = _age_from_date(dob_19)
        self.assertGreaterEqual(age_19, 18)

    @patch('services.auth_service.get_supabase')
    @patch('services.auth_service.safe_select')
    @patch('services.auth_service._supabase_auth_email_exists')
    @patch('services.auth_service.sync_oauth_profile')
    def test_registration_with_email_confirmation(self, mock_sync, mock_exists_auth, mock_select, mock_supabase):
        print("\n[test] Testing registration with email confirmation (no session returned)...")
        
        mock_select.return_value = []
        mock_exists_auth.return_value = False
        mock_sync.return_value = {"id": "test-profile-id", "username": "testuser"}
        
        # Mock Supabase response with user but NO session
        mock_auth_res = MagicMock()
        mock_auth_res.user = MagicMock(id="test-user-id", email="test@example.com")
        mock_auth_res.session = None
        mock_supabase.return_value.auth.sign_up.return_value = mock_auth_res
        
        ok, msg = register_chain_user(
            email="test@example.com",
            password="Password123!",
            username="testuser",
            full_name="Test User",
            extra={
                "terms_accepted": True,
                "human_confirmed": True,
                "date_of_birth": "1990-01-01",
                "phone": "+1234567890"
            }
        )
        
        self.assertTrue(ok)
        self.assertIn("check your email to confirm", msg.lower())
        print("Success: Registration correctly identified email confirmation requirement.")

    @patch('services.auth_service.get_supabase')
    @patch('services.auth_service.safe_select')
    @patch('services.auth_service._supabase_auth_email_exists')
    @patch('services.auth_service.sync_oauth_profile')
    @patch('services.auth_service.store_auth_session')
    def test_registration_immediate_login(self, mock_store, mock_sync, mock_exists_auth, mock_select, mock_supabase):
        print("\n[test] Testing registration with immediate login (session returned)...")
        
        mock_select.return_value = []
        mock_exists_auth.return_value = False
        mock_sync.return_value = {"id": "test-profile-id", "username": "testuser", "profile_completed": False}
        
        # Mock Supabase response WITH session
        mock_auth_res = MagicMock()
        mock_auth_res.user = MagicMock(id="test-user-id", email="new@example.com")
        mock_auth_res.session = MagicMock(access_token="test-token")
        mock_supabase.return_value.auth.sign_up.return_value = mock_auth_res
        
        ok, result = register_chain_user(
            email="new@example.com",
            password="Password123!",
            username="newuser",
            full_name="New User",
            extra={
                "terms_accepted": True,
                "human_confirmed": True,
                "date_of_birth": "1990-01-01",
                "phone": "+1987654321"
            }
        )
        
        self.assertTrue(ok)
        self.assertEqual(result, "/profile/onboarding")
        mock_store.assert_called_once()
        print("Success: Registration correctly handled immediate login.")

    @patch('services.auth_service.get_supabase')
    @patch('services.auth_service.safe_select')
    def test_registration_email_exists(self, mock_select, mock_supabase):
        print("\n[test] Testing registration with existing email...")
        
        # Mock side_effect to distinguish queries
        def select_side_effect(table, filters=None, **kwargs):
            if filters and filters.get("normalized_email") == "existing@example.com":
                return [{"id": "existing-id"}]
            return []
        
        mock_select.side_effect = select_side_effect
        
        ok, msg = register_chain_user(
            email="existing@example.com",
            password="Password123!",
            username="testuser",
            full_name="Test User",
            extra={
                "terms_accepted": True,
                "human_confirmed": True,
                "date_of_birth": "1990-01-01",
                "phone": "+1234567890"
            }
        )
        
        self.assertFalse(ok)
        self.assertEqual(msg, "EMAIL_EXISTS")
        print("Success: Registration correctly returned EMAIL_EXISTS error.")

if __name__ == "__main__":
    unittest.main()
