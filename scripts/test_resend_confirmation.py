import os
import unittest
from flask import Flask
from services.auth_service import resend_confirmation_email
from unittest.mock import MagicMock, patch

class TestResendConfirmation(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'test'
        self.ctx = self.app.test_request_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    @patch('services.auth_service.get_supabase')
    def test_resend_confirmation_success(self, mock_supabase):
        print("\n[test] Testing resend_confirmation_email success...")
        
        # Mock Supabase success
        mock_supabase.return_value.auth.resend.return_value = {}
        
        ok, msg = resend_confirmation_email("test@example.com")
        self.assertTrue(ok)
        self.assertIn("sent", msg.lower())
        print("Success: Resend confirmation email link handled successfully.")

    @patch('services.auth_service.get_supabase')
    def test_resend_confirmation_failure_is_generic(self, mock_supabase):
        print("\n[test] Testing resend_confirmation_email failure returns generic success...")
        
        # Mock Supabase failure (e.g. user not found or rate limit)
        mock_supabase.return_value.auth.resend.side_effect = Exception("User not found")
        
        ok, msg = resend_confirmation_email("unknown@example.com")
        self.assertTrue(ok) # Should still return True for generic success
        self.assertIn("account exists", msg.lower())
        print("Success: Resend confirmation correctly returned generic message on failure.")

if __name__ == "__main__":
    unittest.main()
