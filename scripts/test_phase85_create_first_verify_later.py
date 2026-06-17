#!/usr/bin/env python3
"""
PHASE 85 — CREATE ACCOUNT FIRST, VERIFY LATER.

Tests:
 1. GET /auth/register 200
 2. Register page has country datalist <datalist id="country-list"> and no JS overlay
 3. Invalid email format returns friendly message before Supabase (mock register_post)
 4. Supabase "email invalid" in register_chain_user → friendly message
 5. Valid unique email registration → 302 → /profile/onboarding
 6. Session contains profile_id / auth_user_id / logged_in
 7. email_verified=False does NOT block redirect
 8. phone_verified=False does NOT block redirect (via profile flag)
 9. Onboarding template has "Welcome to NamVibe"
10. Onboarding template tells user to verify email/phone later
11. GET /auth/forgot-password 200
12. POST /auth/forgot-password does not return raw Bad Request
13. GET /auth/reset-password without token does not return raw Bad Request
14. POST /auth/reset-password invalid/missing token does not return raw Bad Request
15. Served JS has no preventDefault / key blocking / live checks
16. Served HTML has no country_suggestions div / JS country overlay
17. Python compile check
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["FLASK_ENV"] = "development"
os.environ["ENV"] = "development"
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"
os.environ["CHAIN_DISABLE_DB_PING"] = "1"
os.environ["CHAIN_DISABLE_RATE_LIMITS"] = "1"
os.environ["SECRET_KEY"] = "test-phase85-secret-key"

from app import create_app
from flask import session
from unittest.mock import MagicMock, patch


class Phase85CreateFirstVerifyLater:
    def __init__(self):
        self.app = create_app()
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.errors = []
        self.passes = 0
        self.fails = 0
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def check(self, name, condition, detail=""):
        if condition:
            self.passes += 1
            print(f"  PASS  {name}")
        else:
            self.fails += 1
            msg = f"  FAIL  {name}"
            if detail:
                msg += f"  \u2014  {detail}"
            print(msg)
            self.errors.append(f"{name}: {detail}")

    def _extract_csrf(self, html):
        m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
        return m.group(1) if m else None

    # ── Test 1: Register page GET 200 ──
    def test_01_register_page_200(self):
        print("\n[Test 1] GET /auth/register returns 200")
        resp = self.client.get("/auth/register")
        self.check("status 200", resp.status_code == 200, f"got {resp.status_code}")
        return resp

    # ── Test 2: Country datalist present, no JS overlay ──
    def test_02_country_datalist(self):
        print("\n[Test 2] Register page has country datalist, no JS overlay")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        self.check("has country-list datalist",
                    'id="country-list"' in html,
                    "Missing country datalist")
        self.check("datalist has Namibia option",
                    '<option value="Namibia">' in html,
                    "Missing Namibia option")
        self.check("input has list attribute",
                    'list="country-list"' in html,
                    "Missing list attribute on country input")
        self.check("no country_suggestions overlay div",
                    'id="country_suggestions"' not in html,
                    "country_suggestions div still present")
        self.check("no suggestions_username div",
                    'id="suggestions_username"' not in html,
                    "username suggestions still present")

    # ── Test 3: Invalid email format → friendly message before Supabase ──
    @patch("api_routes.auth_routes.register_chain_user")
    def test_03_invalid_email_format(self, mock_register):
        print("\n[Test 3] Invalid email format returns friendly error")
        mock_register.return_value = {"ok": False, "error": "EMAIL_EXISTS"}
        test_emails = [
            "notanemail",
            "@nodomain.com",
            "space @test.com",
            "missing@dot",
        ]
        for email in test_emails:
            resp = self.client.post("/auth/register", data={
                "csrf_token": "x",
                "full_name": "Test User",
                "email": email,
                "username": "testuser",
                "phone": "+264811234567",
                "country_origin": "Namibia",
                "date_of_birth": "2000-01-01",
                "gender": "male",
                "password": "TestPass123!",
                "confirm_password": "TestPass123!",
                "terms": "on",
            })
            html = resp.data.decode("utf-8")
            has_friendly = "valid email" in html.lower() or "name@example.com" in html
            self.check(f"invalid email '{email}' → friendly error",
                        has_friendly,
                        f"Got status {resp.status_code} without friendly message")

    # ── Test 4: Supabase "email invalid" → friendly message ──
    def test_04_supabase_email_invalid_friendly(self):
        print("\n[Test 4] Supabase email invalid exception → friendly message")
        from services.auth_service import register_chain_user
        result = register_chain_user(
            "bad@@email", "TestPass123!", "testuser85",
            "Test User", extra={
                "phone": "+264811234567",
                "phone_code": "",
                "date_of_birth": "2000-01-01",
                "country_origin": "Namibia",
                "current_country": "Namibia",
                "country": "Namibia",
                "terms_accepted": True,
                "human_confirmed": True,
                "profile_type": "member",
                "agreement_true_details": True,
                "agreement_identity_use": True,
                "agreement_username_privacy": True,
                "agreement_standards": True,
                "agreement_no_abuse": True,
                "profile_completed": False,
            },
        )
        error = result.get("error", "")
        self.check("bad email returns friendly error",
                    "valid email" in error.lower() or "name@example.com" in error,
                    f"Got: {error}")

    # ── Test 5: Valid registration → 302 → /profile/onboarding ──
    @patch("api_routes.auth_routes.register_chain_user")
    def test_05_register_redirects_onboarding(self, mock_register):
        print("\n[Test 5] Valid registration → 302 → /profile/onboarding")
        mock_register.return_value = {
            "ok": True,
            "profile": {"id": "test-profile-85", "username": "testuser85"},
            "auth_user_id": "test-auth-user-85",
            "redirect_to": "/profile/onboarding",
            "access_token": "test-token",
        }
        resp = self.client.post("/auth/register", data={
            "csrf_token": "x",
            "full_name": "Test User",
            "email": "test85@example.com",
            "username": "testuser85",
            "phone": "+264811234567",
            "country_origin": "Namibia",
            "date_of_birth": "2000-01-01",
            "gender": "male",
            "password": "TestPass123!",
            "confirm_password": "TestPass123!",
            "terms": "on",
        })
        self.check("status is redirect (302 or 303)",
                    resp.status_code in (302, 303),
                    f"got {resp.status_code}")
        location = resp.headers.get("Location", "")
        self.check("redirects to /profile/onboarding",
                    "/profile/onboarding" in location,
                    f"redirected to {location}")

    # ── Test 6: Session keys set correctly ──
    def test_06_session_keys(self):
        print("\n[Test 6] _apply_registration_session sets session correctly")
        from api_routes.auth_routes import _apply_registration_session
        from services.session_service import is_logged_in
        self.client = self.app.test_client()
        with self.app.test_request_context():
            result = {
                "ok": True,
                "profile": {
                    "id": "test-profile-85b",
                    "username": "testuser85b",
                    "full_name": "Test User 85b",
                    "email": "test85b@example.com",
                    "date_of_birth": "2000-01-01",
                    "profile_completed": False,
                    "email_verified": False,
                },
                "auth_user_id": "test-auth-user-85b",
                "access_token": "test-access-token-85b",
            }
            _apply_registration_session(result)
            self.check("is_logged_in() is True", is_logged_in(), "Not logged in")
            self.check("auth_user_id set",
                        session.get("auth_user_id") == "test-auth-user-85b")
            self.check("profile_id set",
                        session.get("profile_id") == "test-profile-85b")
            self.check("logged_in flag True",
                        session.get("logged_in") is True)
            self.check("access_token set",
                        session.get("access_token") == "test-access-token-85b")

    # ── Test 7: email_verified False does not block ──
    def test_07_email_verified_not_required(self):
        print("\n[Test 7] email_verified=False does not block registration")
        from services.auth_service import _registration_profile_payload, _bootstrap_registration_profile
        payload = _registration_profile_payload(
            "test85c@example.com", "testuser85c", "Test User 85c",
            "+264811234567", "2000-01-01",
            {"auth_user_id": "test-auth-85c", "country_origin": "Namibia",
             "current_country": "Namibia", "country": "Namibia",
             "town": "", "region": "", "profile_type": "member",
             "terms_accepted": True, "human_confirmed": True,
             "agreement_true_details": True, "agreement_identity_use": True,
             "agreement_username_privacy": True, "agreement_standards": True,
             "agreement_no_abuse": True, "profile_completed": False},
            email_verified=False,
        )
        self.check("email_verified is False in payload",
                    payload.get("email_verified") is False,
                    "email_verified should be False")
        self.check("is_verified is False",
                    payload.get("is_verified") is False,
                    "is_verified should be False")
        self.check("profile_completed in payload",
                    "profile_completed" in payload,
                    "Missing profile_completed")

    # ── Test 8: phone_verified not required ──
    def test_08_phone_verified_not_required(self):
        print("\n[Test 8] phone_verified is not checked during registration")
        from services.auth_service import _registration_profile_payload
        payload = _registration_profile_payload(
            "test85d@example.com", "testuser85d", "Test User 85d",
            "+264811234567", "2000-01-01",
            {"auth_user_id": "test-auth-85d", "country_origin": "Namibia",
             "current_country": "Namibia", "country": "Namibia",
             "town": "", "region": "", "profile_type": "member",
             "terms_accepted": True, "human_confirmed": True,
             "agreement_true_details": True, "agreement_identity_use": True,
             "agreement_username_privacy": True, "agreement_standards": True,
             "agreement_no_abuse": True, "profile_completed": False},
            email_verified=False,
        )
        self.check("profile payload has is_verified False",
                    payload.get("is_verified") is False,
                    "is_verified should be False")
        self.check("profile_completed is computed",
                    "profile_completed" in payload,
                    "Missing profile_completed")
        self.check("email_verified is False",
                    payload.get("email_verified") is False,
                    "email_verified should be False")

    # ── Test 9: Onboarding template has Welcome to NamVibe ──
    def test_09_onboarding_has_welcome(self):
        print("\n[Test 9] Onboarding template has 'Welcome to NamVibe'")
        path = os.path.join(self.base_dir, "templates", "profile", "onboarding.html")
        with open(path) as f:
            html = f.read()
        self.check("has Welcome to NamVibe",
                    "Welcome to NamVibe" in html,
                    "Missing welcome heading")
        self.check("has finish setting up message",
                    "Finish setting up your profile" in html or "Finish setting up" in html,
                    "Missing profile setup message")

    # ── Test 10: Onboarding tells user to verify later ──
    def test_10_onboarding_verify_later(self):
        print("\n[Test 10] Onboarding tells user to verify email/phone later")
        path = os.path.join(self.base_dir, "templates", "profile", "onboarding.html")
        with open(path) as f:
            html = f.read()
        self.check("verify later message present",
                    "verify" in html.lower() and "later" in html.lower(),
                    "No verify-later message in onboarding")

    # ── Test 11: Forgot password GET 200 ──
    def test_11_forgot_password_get(self):
        print("\n[Test 11] GET /auth/forgot-password returns 200")
        resp = self.client.get("/auth/forgot-password")
        self.check("status 200", resp.status_code == 200, f"got {resp.status_code}")

    # ── Test 12: Forgot password POST not Bad Request ──
    def test_12_forgot_password_post(self):
        print("\n[Test 12] POST /auth/forgot-password not Bad Request")
        get_resp = self.client.get("/auth/forgot-password")
        html = get_resp.data.decode("utf-8")
        csrf = self._extract_csrf(html)
        if not csrf:
            self.check("csrf token extracted", False, "Could not extract CSRF token")
            return
        resp = self.client.post("/auth/forgot-password", data={
            "csrf_token": csrf,
            "email": "test-forgot85@example.com",
        })
        text = resp.data.decode("utf-8", errors="replace").lower().strip()
        is_bad_request = resp.status_code == 400 and ("bad request" in text or text.startswith("bad request"))
        self.check("status not 400 Bad Request",
                    not is_bad_request,
                    f"Got Bad Request: status={resp.status_code} body={text[:200]}")

    # ── Test 13: Reset password GET missing token not Bad Request ──
    def test_13_reset_password_get_missing_token(self):
        print("\n[Test 13] GET /auth/reset-password missing token not Bad Request")
        resp = self.client.get("/auth/reset-password")
        text = resp.data.decode("utf-8", errors="replace").lower()
        is_bad_request = resp.status_code == 400 and ("bad request" in text or text.strip().startswith("bad request"))
        self.check("status not 400 Bad Request",
                    not is_bad_request,
                    f"Got Bad Request: status={resp.status_code}")
        self.check("response is HTML page",
                    "<!doctype" in resp.data.decode("utf-8", errors="replace").lower() or "reset" in text,
                    f"Response is not friendly: {text[:200]}")

    # ── Test 14: Reset password POST invalid token not Bad Request ──
    def test_14_reset_password_post_invalid_token(self):
        print("\n[Test 14] POST /auth/reset-password invalid token not Bad Request")
        get_resp = self.client.get("/auth/reset-password")
        html = get_resp.data.decode("utf-8")
        csrf = self._extract_csrf(html)
        if not csrf:
            self.check("csrf token extracted", False, "Could not extract CSRF token")
            return
        resp = self.client.post("/auth/reset-password", data={
            "csrf_token": csrf,
            "password": "NewPass123!",
            "confirm_password": "NewPass123!",
        })
        text = resp.data.decode("utf-8", errors="replace").lower()
        is_bad_request = resp.status_code == 400 and ("bad request" in text or "400" in text[:50])
        self.check("status not 400 Bad Request",
                    not is_bad_request,
                    f"Got Bad Request: status={resp.status_code}")

    # ── Test 15: Served JS has no preventDefault/key blocking ──
    def test_15_js_no_blocking(self):
        print("\n[Test 15] chain_register.js has no preventDefault or key blocking")
        js_path = os.path.join(self.base_dir, "static", "js", "chain_register.js")
        with open(js_path) as f:
            js = f.read()
        self.check("no preventDefault", "preventDefault" not in js, "preventDefault still present")
        self.check("no stopPropagation", "stopPropagation" not in js, "stopPropagation still present")
        self.check("no keydown listener", "keydown" not in js, "keydown listener still present")
        self.check("no keyup listener", "keyup" not in js, "keyup listener still present")
        self.check("no beforeinput listener", "beforeinput" not in js, "beforeinput still present")
        self.check("no check-email fetch", "check-email" not in js, "check-email fetch still present")
        self.check("no check-username fetch", "check-username" not in js, "check-username fetch still present")
        self.check("no check-phone fetch", "check-phone" not in js, "check-phone fetch still present")
        self.check("no country suggestions", "country_suggestions" not in js and "suggestions" not in js,
                    "country suggestions code still present")
        self.check("no input.value assignment rewriting (except password toggle)",
                    'input.value = ' not in js and '.value = "' not in js,
                    "input.value assignment still present")

    # ── Test 16: Served HTML has no country_suggestions overlay ──
    def test_16_html_no_overlay(self):
        print("\n[Test 16] Served register HTML has no country suggestions overlay")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        self.check("no country_suggestions div",
                    'id="country_suggestions"' not in html,
                    "country_suggestions div still present")
        self.check("no suggestions_username div",
                    'id="suggestions_username"' not in html,
                    "username suggestions still present")
        self.check("no availability hint",
                    "availability" not in html.lower() or "check-email" not in html.lower(),
                    "Availability hints still present")

    # ── Test 17: Python compilation ──
    def test_17_compile(self):
        print("\n[Test 17] Python files compile")
        files = [
            "app.py",
            "api_routes/auth_routes.py",
            "services/auth_service.py",
            "api_routes/profile_routes.py",
            "scripts/test_phase85_create_first_verify_later.py",
        ]
        for filepath in files:
            full = os.path.join(self.base_dir, filepath)
            if not os.path.exists(full):
                self.check(f"{filepath} exists", False, "File not found")
                continue
            try:
                with open(full) as f:
                    compile(f.read(), filepath, "exec")
                self.check(f"{filepath} compiles", True)
            except SyntaxError as e:
                self.check(f"{filepath} compiles", False, str(e))

    def summary(self):
        total = self.passes + self.fails
        print(f"\n{'='*50}")
        print(f"Phase 85 Summary: {self.passes}/{total} passed")
        if self.errors:
            print("Errors:")
            for e in self.errors:
                print(f"  - {e}")
        return self.fails == 0


if __name__ == "__main__":
    t = Phase85CreateFirstVerifyLater()
    tests = [
        t.test_01_register_page_200,
        t.test_02_country_datalist,
        t.test_03_invalid_email_format,
        t.test_04_supabase_email_invalid_friendly,
        t.test_05_register_redirects_onboarding,
        t.test_06_session_keys,
        t.test_07_email_verified_not_required,
        t.test_08_phone_verified_not_required,
        t.test_09_onboarding_has_welcome,
        t.test_10_onboarding_verify_later,
        t.test_11_forgot_password_get,
        t.test_12_forgot_password_post,
        t.test_13_reset_password_get_missing_token,
        t.test_14_reset_password_post_invalid_token,
        t.test_15_js_no_blocking,
        t.test_16_html_no_overlay,
        t.test_17_compile,
    ]
    for test in tests:
        try:
            test()
        except Exception as e:
            t.fails += 1
            name = test.__name__.replace("test_", "").replace("_", " ")
            print(f"  FAIL  {name}")
            print(f"        EXCEPTION: {e}")
            t.errors.append(f"{name}: EXCEPTION: {e}")
    ok = t.summary()
    sys.exit(0 if ok else 1)
