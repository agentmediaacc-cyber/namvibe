import sys
import os
from unittest.mock import MagicMock, patch

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, session, url_for
from api_routes.profile_routes import profile_bp
from services.auth_service import login_chain_user

def test_login_chain_user_age_gate():
    print("\nTesting login_chain_user Age Gate...")
    
    app = Flask(__name__)
    app.secret_key = "test_secret"
    
    with app.test_request_context():
        # Case 1: Supabase success + Neon fail + no DOB -> True, /profile/age-check
        print("[Case 1] missing DOB -> redirect age-check")
        with patch("services.auth_service.get_supabase") as mock_supabase, \
             patch("services.auth_service._quick_profile_snapshot") as mock_snapshot, \
             patch("services.auth_service._schedule_profile_sync") as mock_schedule, \
             patch("services.auth_service.store_auth_session") as mock_store:
            
            auth_mock = MagicMock()
            user = MagicMock(id="u1", email="test@ex.com")
            user.user_metadata = {}
            user.identities = []
            auth_mock.sign_in_with_password.return_value = MagicMock(user=user, session=MagicMock())
            mock_supabase.return_value.auth = auth_mock
            
            # Profile with no DOB
            mock_snapshot.return_value = {"id": "p1", "username": "nodob", "date_of_birth": None}
            mock_schedule.return_value = None
            
            ok, result = login_chain_user("test@ex.com", "pass")
            assert ok is True
            assert result == "/profile/age-check"
            assert session.get("age_check_required") is True
            print("[OK] login_chain_user returned True, /profile/age-check")

        # Case 2: Supabase success + adult DOB in metadata -> True, /profile/
        print("[Case 2] adult DOB -> allow")
        with patch("services.auth_service.get_supabase") as mock_supabase, \
             patch("services.auth_service._quick_profile_snapshot") as mock_snapshot, \
             patch("services.auth_service._schedule_profile_sync") as mock_schedule, \
             patch("services.auth_service.store_auth_session") as mock_store, \
             patch("services.auth_service._is_profile_complete", return_value=True):
            
            auth_mock = MagicMock()
            user = MagicMock(id="u2", email="adult@ex.com")
            user.user_metadata = {}
            user.identities = []
            auth_mock.sign_in_with_password.return_value = MagicMock(user=user, session=MagicMock())
            mock_supabase.return_value.auth = auth_mock
            
            # Profile with adult DOB
            mock_snapshot.return_value = {"id": "p2", "username": "adult", "date_of_birth": "1990-01-01", "profile_completed": True}
            mock_schedule.return_value = None
            
            ok, result = login_chain_user("adult@ex.com", "pass")
            assert ok is True
            assert result == "/profile/"
            print("[OK] login_chain_user returned True, /profile/")

        # Case 3: Supabase success + under-18 DOB -> False, under-18 message
        print("[Case 3] under-18 DOB -> block")
        with patch("services.auth_service.get_supabase") as mock_supabase, \
             patch("services.auth_service._quick_profile_snapshot") as mock_snapshot, \
             patch("services.auth_service._schedule_profile_sync") as mock_schedule, \
             patch("services.auth_service.store_auth_session") as mock_store, \
             patch("services.auth_service.clear_auth_session") as mock_clear:
            
            auth_mock = MagicMock()
            user = MagicMock(id="u3", email="minor@ex.com")
            user.user_metadata = {}
            user.identities = []
            auth_mock.sign_in_with_password.return_value = MagicMock(user=user, session=MagicMock())
            mock_supabase.return_value.auth = auth_mock
            
            # Profile with minor DOB
            mock_snapshot.return_value = {"id": "p3", "username": "minor", "date_of_birth": "2015-01-01"}
            mock_schedule.return_value = None
            
            ok, result = login_chain_user("minor@ex.com", "pass")
            assert ok is False
            assert "18 and older" in result
            mock_clear.assert_called()
            print("[OK] login_chain_user returned False with error message")


def test_age_gate_login_routes():
    print("\nTesting Age Gate Login Flow (Routes)...")
    
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = "test_secret"
    app.register_blueprint(profile_bp)
    
    from datetime import datetime, timezone
    app.jinja_env.globals.update(now_utc=lambda: datetime.now(timezone.utc))

    with app.test_request_context():
        client = app.test_client()
        
        def set_session(user_id):
            with client.session_transaction() as sess:
                sess['auth_user_id'] = user_id
                sess['access_token'] = 'test-token'

        # Missing DOB redirect
        print("[Route] Missing DOB redirect")
        set_session("user_missing_dob")
        with patch("api_routes.profile_routes.get_current_profile") as mock_profile, \
             patch("api_routes.profile_routes.is_logged_in", return_value=True):
            mock_profile.return_value = {"id": "p1", "username": "nodob", "date_of_birth": None}
            res = client.get("/profile/")
            assert res.status_code == 302
            assert "/profile/age-check" in res.location
            print("[OK] Redirected to age-check")

if __name__ == "__main__":
    try:
        test_login_chain_user_age_gate()
        test_age_gate_login_routes()
        print("\nAll Age Gate Tests Passed!")
    except Exception as e:
        print(f"Tests failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
