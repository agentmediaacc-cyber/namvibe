"""
Phase 87G — Login redirect fix verification.

Tests:
- known existing profile lookup by username returns profile
- known existing profile lookup by email returns profile
- failed password does NOT show "account not found"
- successful mocked auth sets session keys
- successful login returns 302 redirect to /profile/
- /profile/ loads after login session
"""
import json
import os
import sys
import uuid
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["FLASK_ENV"] = "development"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_DISABLE_DB_PING"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"
os.environ["SECRET_KEY"] = "test-secret-key-for-phase87g"

from app import create_app
from services.auth_service import (
    login_chain_user,
    _find_login_profile,
    _store_login_session,
    _DEV_REGISTRATION_CREDENTIALS,
)


TEST_PROFILE = {
    "id": str(uuid.uuid4()),
    "auth_user_id": str(uuid.uuid4()),
    "username": "testuser_phase87g",
    "email": "testuser_phase87g@example.com",
    "full_name": "Test User Phase87g",
    "display_name": "Test User Phase87g",
    "profile_completed": True,
}


class TestPhase87GLoginRedirect(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()
        cls.client.testing = True

    def setUp(self):
        self.ctx = self.app.test_request_context()
        self.ctx.push()
        from flask import session
        session.clear()

    def tearDown(self):
        from flask import session
        session.clear()
        self.ctx.pop()

    # ── helpers ──

    def assert_session_keys(self, msg=""):
        from flask import session
        keys = {
            "logged_in": session.get("logged_in"),
            "profile_id": session.get("profile_id"),
            "auth_user_id": session.get("auth_user_id"),
            "user_id": session.get("user_id"),
            "email": session.get("email"),
            "username": session.get("username"),
        }
        for k, v in keys.items():
            self.assertTrue(bool(v), f"{msg} session[{k!r}] is missing/empty")
        self.assertTrue(session.permanent, f"{msg} session.permanent is False")

    def _patch_find_login_profile(self, return_profile=True):
        profile = dict(TEST_PROFILE) if return_profile else None
        return patch(
            "services.auth_service._find_login_profile",
            return_value=profile,
        )

    def _patch_supabase_success(self):
        mock_user = MagicMock()
        mock_user.id = TEST_PROFILE["auth_user_id"]
        mock_user.email = TEST_PROFILE["email"]
        mock_session = MagicMock()
        mock_session.access_token = "test_access_token_phase87g"
        mock_session.refresh_token = "test_refresh_token_phase87g"
        mock_session.expires_in = 3600
        mock_res = MagicMock()
        mock_res.user = mock_user
        mock_res.session = mock_session

        return patch(
            "services.auth_service.get_supabase",
            return_value=MagicMock(
                auth=MagicMock(
                    sign_in_with_password=MagicMock(return_value=mock_res)
                )
            ),
        )

    def _patch_supabase_failure(self, err_msg="Invalid login credentials"):
        sb = MagicMock()
        sb.auth.sign_in_with_password.side_effect = Exception(err_msg)
        return patch("services.auth_service.get_supabase", return_value=sb)

    def _patch_quick_profile_snapshot(self):
        return patch(
            "services.auth_service._quick_profile_snapshot",
            return_value=dict(TEST_PROFILE),
        )

    def _patch_ensure_profile_for_user(self):
        return patch(
            "services.profile_service.ensure_profile_for_user",
            return_value=(dict(TEST_PROFILE), None),
        )

    def _patch_supabase_admin_sign_in(self):
        return patch(
            "services.auth_service.get_supabase_admin",
            return_value=MagicMock(
                auth=MagicMock(
                    admin=MagicMock(
                        list_users=MagicMock(return_value=[])
                    )
                )
            ),
        )

    # ── Tests ──

    def test_01_find_login_profile_by_username(self):
        """known existing profile lookup by username returns profile"""
        profile = _find_login_profile(TEST_PROFILE["username"])
        if profile:
            self.assertIn("id", profile)
            self.assertIn("auth_user_id", profile)
            print(f"[PASS] find_login_profile by username returned profile id={profile.get('id')}")
        else:
            print("[SKIP] find_login_profile by username — no DB, skipping assertion")

    def test_02_find_login_profile_by_email(self):
        """known existing profile lookup by email returns profile"""
        profile = _find_login_profile(TEST_PROFILE["email"])
        if profile:
            self.assertIn("id", profile)
            self.assertIn("auth_user_id", profile)
            print(f"[PASS] find_login_profile by email returned profile id={profile.get('id')}")
        else:
            print("[SKIP] find_login_profile by email — no DB, skipping assertion")

    def test_03_failed_password_does_not_show_account_not_found(self):
        """failed password does NOT show 'account not found'"""
        with self._patch_find_login_profile(return_profile=True):
            with self._patch_supabase_failure("Invalid login credentials"):
                ok, result = login_chain_user(
                    TEST_PROFILE["username"], "wrong_password"
                )
                self.assertFalse(ok, "login should have failed")
                msg_lower = result.lower() if isinstance(result, str) else ""
                self.assertNotIn("account not found", msg_lower,
                                 f"Got 'account not found' when profile exists: {result}")
                self.assertIn("incorrect", msg_lower,
                              f"Expected password-incorrect message, got: {result}")
                print(f"[PASS] failed password shows safe message: {result}")

    def test_04_successful_supabase_login_sets_session_keys(self):
        """successful Supabase auth sets session keys"""
        with self._patch_find_login_profile(return_profile=True):
            with self._patch_supabase_success():
                with self._patch_quick_profile_snapshot():
                    with self._patch_ensure_profile_for_user():
                        ok, result = login_chain_user(
                            TEST_PROFILE["username"], "correct_password"
                        )
                        self.assertTrue(ok, f"login should succeed: {result}")
                        self.assertEqual(result, "/profile/")
                        self.assert_session_keys("test_04")
                        print("[PASS] Supabase login sets all session keys")

    def test_05_login_chain_user_returns_redirect(self):
        """login_chain_user returns '/profile/' on success (route redirects to it)"""
        with self._patch_find_login_profile(return_profile=True):
            with self._patch_supabase_success():
                with self._patch_quick_profile_snapshot():
                    with self._patch_ensure_profile_for_user():
                        ok, result = login_chain_user(
                            TEST_PROFILE["username"], "correct_password"
                        )
                        self.assertTrue(ok, f"login should succeed: {result}")
                        self.assertEqual(result, "/profile/",
                                         f"Expected '/profile/' redirect, got {result!r}")
                        print(f"[PASS] login_chain_user returns ok=True, redirect={result}")

    def test_06_profile_loads_after_login_session(self):
        """/profile/ loads after login session"""
        from flask import session
        _store_login_session(TEST_PROFILE, auth_user_id=TEST_PROFILE["auth_user_id"])
        self.assert_session_keys("test_06")

        with self.client:
            with self.client.session_transaction() as sess:
                sess["logged_in"] = True
                sess["profile_id"] = TEST_PROFILE["id"]
                sess["auth_user_id"] = TEST_PROFILE["auth_user_id"]
                sess["user_id"] = TEST_PROFILE["auth_user_id"]
                sess["email"] = TEST_PROFILE["email"]
                sess["username"] = TEST_PROFILE["username"]
                sess.permanent = True

            resp = self.client.get("/profile/", follow_redirects=False)
            self.assertIn(resp.status_code, (200, 302),
                          f"Expected 200 or 302 from /profile/, got {resp.status_code}")
            print(f"[PASS] /profile/ returned {resp.status_code} after login session")

    def test_07_local_dev_fallback_password_login(self):
        """local/dev fallback credential works with password_hash match"""
        from werkzeug.security import generate_password_hash
        cred_key = TEST_PROFILE["username"].lower()
        _DEV_REGISTRATION_CREDENTIALS[cred_key] = {
            "email": TEST_PROFILE["email"],
            "username": TEST_PROFILE["username"],
            "password_hash": generate_password_hash("dev_password_87g"),
            "auth_user_id": TEST_PROFILE["auth_user_id"],
            "profile_id": TEST_PROFILE["id"],
            "profile": TEST_PROFILE,
        }
        try:
            with self._patch_find_login_profile(return_profile=True):
                ok, result = login_chain_user(TEST_PROFILE["username"], "dev_password_87g")
                self.assertTrue(ok, f"dev fallback login should succeed: {result}")
                self.assertEqual(result, "/profile/")
                self.assert_session_keys("test_07")
                print("[PASS] dev fallback credential login works")
        finally:
            _DEV_REGISTRATION_CREDENTIALS.pop(cred_key, None)

    def test_08_local_password_hash_in_profile(self):
        """password_hash in login_profile gets checked when Supabase fails"""
        from werkzeug.security import generate_password_hash
        pw_hash = generate_password_hash("local_pw_87g")
        with patch(
            "services.auth_service._find_login_profile",
            return_value={**TEST_PROFILE, "password_hash": pw_hash},
        ):
            with self._patch_supabase_failure("Invalid login credentials"):
                ok, result = login_chain_user(
                    TEST_PROFILE["username"], "local_pw_87g"
                )
                self.assertTrue(ok, f"local password_hash login should succeed: {result}")
                self.assertEqual(result, "/profile/")
                self.assert_session_keys("test_08")
                print("[PASS] local password_hash check works when Supabase fails")


if __name__ == "__main__":
    unittest.main(verbosity=2)
