import sys
import os
from unittest.mock import MagicMock, patch

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.auth_service import register_chain_user

def test_registration_truth():
    print("Testing Registration Truthfulness...")
    
    # Mock data
    email = "test_truth@example.com"
    password = "password123"
    username = "testtruth"
    full_name = "Test Truth"
    extra = {
        "phone": "+1234567890",
        "date_of_birth": "1990-01-01",
        "terms_accepted": True
    }

    with patch("services.auth_service.get_supabase") as mock_supabase_client, \
         patch("services.auth_service.get_supabase_admin") as mock_admin_client, \
         patch("services.auth_service.safe_select") as mock_select, \
         patch("services.auth_service._supabase_auth_email_exists") as mock_exists, \
         patch("services.auth_service._profile_exists_by_username") as mock_user_exists:
        
        # Setup common mocks
        mock_select.return_value = []
        mock_exists.return_value = False
        mock_user_exists.return_value = False
        
        auth_mock = MagicMock()
        mock_supabase_client.return_value.auth = auth_mock
        
        # Case 1: Supabase returns no user
        auth_mock.sign_up.return_value = MagicMock(user=None, session=None)
        mock_admin_client.return_value.auth.admin.list_users.return_value = [] # Fallback also fails
        
        ok, result = register_chain_user(email, password, username, full_name, extra)
        assert ok is False
        assert "Registration could not be completed" in result
        print("[OK] Blocked registration when Supabase returns no user")

        # Case 2: Supabase returns user but no ID
        user_no_id = MagicMock(id=None, email=email)
        auth_mock.sign_up.return_value = MagicMock(user=user_no_id, session=None)
        
        ok, result = register_chain_user(email, password, username, full_name, extra)
        assert ok is False
        print("[OK] Blocked registration when user has no ID")

        # Case 3: Email mismatch
        user_wrong_email = MagicMock(id="123", email="wrong@example.com")
        auth_mock.sign_up.return_value = MagicMock(user=user_wrong_email, session=None)
        
        ok, result = register_chain_user(email, password, username, full_name, extra)
        assert ok is False
        assert "verification mismatch" in result
        print("[OK] Blocked registration on email mismatch")

        # Case 4: Real user success
        real_user = MagicMock(id="123", email=email)
        auth_mock.sign_up.return_value = MagicMock(user=real_user, session=None)
        
        # Mock profile sync
        with patch("services.auth_service.sync_oauth_profile") as mock_sync:
            mock_sync.return_value = {"id": "prof_123"}
            with patch("services.profile_service._neon_update_profile") as mock_update:
                ok, result = register_chain_user(email, password, username, full_name, extra)
                assert ok is True
                assert "Account created" in result
                print("[OK] Success with real user ID")

        # Case 5: Fallback success (signup returns empty, but admin lookup finds user)
        auth_mock.sign_up.return_value = MagicMock(user=None, session=None)
        mock_admin_client.return_value.auth.admin.list_users.return_value = [real_user]
        
        with patch("services.auth_service.sync_oauth_profile") as mock_sync:
            mock_sync.return_value = {"id": "prof_123"}
            with patch("services.profile_service._neon_update_profile") as mock_update:
                ok, result = register_chain_user(email, password, username, full_name, extra)
                assert ok is True
                print("[OK] Success via admin fallback")

    print("\nRegistration Truthfulness Tests Passed!")

if __name__ == "__main__":
    try:
        test_registration_truth()
    except Exception as e:
        print(f"Tests failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
