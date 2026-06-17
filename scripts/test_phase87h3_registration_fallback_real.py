"""
Phase 87H3 — Stop Supabase From Blocking Local Registration.

Tests:
- monkeypatch Supabase invalid email => moon@gmail.com registers and returns /profile/
- monkeypatch Supabase rate limit => moon2@gmail.com registers and returns /profile/
- session keys exist after fallback registration
- password_hash saved in profile
- login works using fallback password
- moongmail.com (no @) fails before fallback
- optional phone/country/DOB/gender never block
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
os.environ["SECRET_KEY"] = "test-secret-key-phase87h3"

from app import create_app
from services.auth_service import (
    register_chain_user,
    login_chain_user,
    _find_login_profile,
    _DEV_REGISTRATION_CREDENTIALS,
)


TEST_EMAIL = "moon@gmail.com"
TEST_EMAIL2 = "moon2@gmail.com"
TEST_PASSWORD = "TestPass123!"
TEST_USERNAME = "moontest_87h3"
TEST_FULL_NAME = "Moon Test 87h3"

TEST_PROFILE = {
    "id": str(uuid.uuid4()),
    "auth_user_id": str(uuid.uuid4()),
    "username": TEST_USERNAME,
    "email": TEST_EMAIL,
    "full_name": TEST_FULL_NAME,
    "display_name": TEST_FULL_NAME,
    "profile_completed": False,
    "email_verified": False,
    "password_hash": None,  # will be set per-test
}


class TestPhase87H3RegistrationFallback(unittest.TestCase):

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
        _DEV_REGISTRATION_CREDENTIALS.clear()

    def tearDown(self):
        from flask import session
        session.clear()
        _DEV_REGISTRATION_CREDENTIALS.clear()
        self.ctx.pop()

    # ── Helpers ──

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

    def _mock_ensure_profile(self, profile=None):
        """Mock ensure_profile_for_user to return a profile without DB."""
        if profile is None:
            profile = dict(TEST_PROFILE)
            profile["id"] = str(uuid.uuid4())
            profile["auth_user_id"] = str(uuid.uuid4())
        from werkzeug.security import generate_password_hash
        profile["password_hash"] = generate_password_hash(TEST_PASSWORD)
        return patch(
            "services.profile_service.ensure_profile_for_user",
            return_value=(dict(profile), None),
        )

    def _mock_bootstrap_and_local_dev(self, profile=None):
        """Mock _bootstrap_registration_profile and _build_local_dev_profile to return a profile without DB."""
        if profile is None:
            profile = dict(TEST_PROFILE)
            profile["id"] = str(uuid.uuid4())
            profile["auth_user_id"] = str(uuid.uuid4())
        from werkzeug.security import generate_password_hash
        profile["password_hash"] = generate_password_hash(TEST_PASSWORD)
        return (
            patch(
                "services.auth_service._bootstrap_registration_profile",
                return_value=(dict(profile), None),
            ),
            patch(
                "services.auth_service._build_local_dev_profile",
                return_value=dict(profile),
            ),
        )

    def _patch_supabase_signup_error(self, err_msg="Email address \"moon@gmail.com\" is invalid"):
        sb = MagicMock()
        sb.auth.sign_up.side_effect = Exception(err_msg)
        return patch("services.auth_service.get_supabase", return_value=sb)

    def _patch_supabase_signup_rate_limited(self):
        sb = MagicMock()
        sb.auth.sign_up.side_effect = Exception("Email rate limit exceeded")
        return patch("services.auth_service.get_supabase", return_value=sb)

    def _patch_supabase_signup_network_error(self):
        sb = MagicMock()
        sb.auth.sign_up.side_effect = Exception("Failed to establish a new connection")
        return patch("services.auth_service.get_supabase", return_value=sb)

    def _patch_email_valid_format(self, return_value=True):
        return patch(
            "services.auth_service._email_valid_format",
            return_value=return_value,
        )

    # ── Tests ──

    def test_01_supabase_invalid_email_fallback(self):
        """Supabase rejects moon@gmail.com as invalid → fallback succeeds"""
        p1, p2 = self._mock_bootstrap_and_local_dev()
        with self._patch_supabase_signup_error():
            with p1, p2:
                result = register_chain_user(
                    TEST_EMAIL, TEST_PASSWORD, TEST_USERNAME, TEST_FULL_NAME,
                    extra={"terms_accepted": True},
                )
                self.assertTrue(result.get("ok"), f"Expected ok=True, got: {result}")
                self.assertEqual(result.get("redirect_to"), "/profile/",
                                 f"Expected /profile/, got: {result.get('redirect_to')}")
                self.assertTrue(result.get("dev_fallback"), "Expected dev_fallback=True")
                self.assert_session_keys("test_01")
                print(f"[PASS] test_01: moon@gmail.com fallback registration succeeded")

    def test_02_supabase_rate_limit_fallback(self):
        """Supabase rate limit → fallback succeeds"""
        p1, p2 = self._mock_bootstrap_and_local_dev()
        with self._patch_supabase_signup_rate_limited():
            with p1, p2:
                result = register_chain_user(
                    TEST_EMAIL2, TEST_PASSWORD, "moontest_87h3_2", "Moon Test 2",
                    extra={"terms_accepted": True},
                )
                self.assertTrue(result.get("ok"), f"Expected ok=True, got: {result}")
                self.assertEqual(result.get("redirect_to"), "/profile/")
                self.assert_session_keys("test_02")
                print(f"[PASS] test_02: rate limit fallback registration succeeded")

    def test_03_session_keys_set_after_fallback(self):
        """Session keys are set after fallback registration"""
        with self._patch_supabase_signup_error():
            p1, p2 = self._mock_bootstrap_and_local_dev()
            with p1, p2:
                result = register_chain_user(
                    TEST_EMAIL, TEST_PASSWORD, TEST_USERNAME, TEST_FULL_NAME,
                    extra={"terms_accepted": True},
                )
                self.assertTrue(result.get("ok"))
                self.assert_session_keys("test_03")
                from flask import session
                self.assertTrue(session.get("logged_in"), "session.logged_in should be True")
                print("[PASS] test_03: session keys set correctly")

    def test_04_login_works_after_fallback(self):
        """Login works using fallback password after fallback registration"""
        from werkzeug.security import generate_password_hash
        profile = {
            "id": str(uuid.uuid4()),
            "auth_user_id": str(uuid.uuid4()),
            "username": TEST_USERNAME,
            "email": TEST_EMAIL,
            "full_name": TEST_FULL_NAME,
            "display_name": TEST_FULL_NAME,
            "profile_completed": False,
            "password_hash": generate_password_hash(TEST_PASSWORD),
        }

        with self._patch_supabase_signup_error():
            p1, p2 = self._mock_bootstrap_and_local_dev(profile)
            with p1, p2:
                result = register_chain_user(
                    TEST_EMAIL, TEST_PASSWORD, TEST_USERNAME, TEST_FULL_NAME,
                    extra={"terms_accepted": True},
                )
                self.assertTrue(result.get("ok"))

        # Now try logging in with the same credentials
        with patch(
            "services.auth_service._find_login_profile",
            return_value=dict(profile),
        ):
            with patch(
                "services.auth_service._quick_profile_snapshot",
                return_value=dict(profile),
            ):
                ok, login_result = login_chain_user(TEST_USERNAME, TEST_PASSWORD)
                self.assertTrue(ok, f"Login after fallback should succeed: {login_result}")
                self.assertEqual(login_result, "/profile/")
                print(f"[PASS] test_04: login works after fallback registration")

    def test_05_moongmail_com_fails_before_fallback(self):
        """moongmail.com (no @) fails before fallback is attempted"""
        with self._patch_supabase_signup_error():
            result = register_chain_user(
                "moongmail.com", TEST_PASSWORD, "moongmail_user", "Moon Gmail User",
                extra={"terms_accepted": True},
            )
            self.assertFalse(result.get("ok"), f"Expected ok=False, got: {result}")
            self.assertIn("valid email", (result.get("error") or "").lower(),
                          f"Expected 'valid email' error, got: {result.get('error')}")
            print(f"[PASS] test_05: moongmail.com correctly rejected: {result.get('error')}")

    def test_06_optional_fields_never_block(self):
        """Optional phone/country/DOB/gender fields never block registration"""
        with self._patch_supabase_signup_error():
            p1, p2 = self._mock_bootstrap_and_local_dev()
            with p1, p2:
                result = register_chain_user(
                    "moon_optional@test.com", TEST_PASSWORD, "moon_optional", "Moon Optional",
                    extra={
                        "terms_accepted": True,
                        "phone": "+1234567890",
                        "country_origin": "US",
                        "date_of_birth": "2000-01-01",
                        "gender": "male",
                    },
                )
                self.assertTrue(result.get("ok"), f"Optional fields blocked registration: {result}")
                print("[PASS] test_06: optional fields did not block registration")

    def test_07_supabase_network_error_fallback(self):
        """Supabase network error → fallback succeeds"""
        p1, p2 = self._mock_bootstrap_and_local_dev()
        with self._patch_supabase_signup_network_error():
            with p1, p2:
                result = register_chain_user(
                    "moon_network@test.com", TEST_PASSWORD, "moon_network", "Moon Network",
                    extra={"terms_accepted": True},
                )
                self.assertTrue(result.get("ok"), f"Expected ok=True, got: {result}")
                self.assertEqual(result.get("redirect_to"), "/profile/")
                self.assert_session_keys("test_07")
                print("[PASS] test_07: network error fallback succeeded")

    def test_08_fallback_logged_in_session_after_register(self):
        """register_chain_user returns ok=True and session has logged_in=True"""
        with self._patch_supabase_signup_error():
            p1, p2 = self._mock_bootstrap_and_local_dev()
            with p1, p2:
                result = register_chain_user(
                    TEST_EMAIL, TEST_PASSWORD, TEST_USERNAME, TEST_FULL_NAME,
                    extra={"terms_accepted": True},
                )
                self.assertTrue(result.get("ok"))
                from flask import session
                self.assertTrue(session.get("logged_in"))
                self.assertEqual(session.get("email"), TEST_EMAIL)
                self.assertEqual(session.get("username"), TEST_USERNAME)
                print("[PASS] test_08: session correctly set after fallback registration")

    def test_09_password_hash_stored_in_dev_credential(self):
        """password_hash is stored in dev registration credential after fallback"""
        with self._patch_supabase_signup_error():
            p1, p2 = self._mock_bootstrap_and_local_dev()
            with p1, p2:
                result = register_chain_user(
                    TEST_EMAIL, TEST_PASSWORD, TEST_USERNAME, TEST_FULL_NAME,
                    extra={"terms_accepted": True},
                )
                self.assertTrue(result.get("ok"))
                # Check in-memory dev credentials
                cred_key = TEST_EMAIL.lower()
                cred = _DEV_REGISTRATION_CREDENTIALS.get(cred_key)
                self.assertIsNotNone(cred, f"No dev credential found for {TEST_EMAIL}")
                self.assertIn("password_hash", cred, "password_hash missing from dev credential")
                from werkzeug.security import check_password_hash
                self.assertTrue(
                    check_password_hash(cred["password_hash"], TEST_PASSWORD),
                    "password_hash does not match TEST_PASSWORD",
                )
                print("[PASS] test_09: password_hash stored in dev credential")


if __name__ == "__main__":
    unittest.main(verbosity=2)
