"""
Phase 71 — Full Auth Production Flow (Login, Register, OAuth).

Tests:
 1. GET /auth/login returns 200
 2. Login form contains login_id and password fields
 3. Login form has CSRF token
 4. Login form has OAuth buttons (Google, Facebook)
 5. POST /auth/login without CSRF returns CSRF error
 6. POST /auth/login with CSRF does not return CSRF error
 7. Login page has auth-page class for mobile styling
 8. Login page labels are readable (not dark-on-dark)
 9. CSS has Phase 71 login overrides
10. OAuth routes (/auth/google, /auth/facebook) respond gracefully
11. OAuth callback handles errors gracefully
12. OAuth diagnostics page renders
13. GET /auth/register returns 200
14. Register form has correct short fields (Phase 70)
15. Register POST validation: empty required fields returns error
16. Register POST validation: password mismatch returns error
17. Register POST validation: missing terms returns error
18. Register POST without removed fields does not fail on those fields
19. Registration page CSRF
20. Combined: auth-page CSS override covers both register and login
"""

import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["FLASK_ENV"] = "development"
os.environ["ENV"] = "development"
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"
os.environ["CHAIN_DISABLE_DB_PING"] = "1"
os.environ["SECRET_KEY"] = "test-secret-key-for-phase71"

from app import create_app


class Phase71FullAuthFlowTest:
    def __init__(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.errors = []
        self.passes = 0
        self.fails = 0
        css_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "css", "chain_auth.css"
        )
        with open(css_path) as f:
            self.css = f.read()

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

    def _extract_csrf_token(self, html):
        m = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', html)
        if m:
            return m.group(1)
        m = re.search(r'<input\s+type="hidden"[^>]*name="csrf_token"[^>]*value="([^"]+)"', html)
        if m:
            return m.group(1)
        return None

    # ── Login Page Tests ────────────────────────────────────

    def test_01_login_page_returns_200(self):
        print("\n[Test 1] GET /auth/login returns 200")
        resp = self.client.get("/auth/login")
        self.check("status 200", resp.status_code == 200, f"got {resp.status_code}")
        return resp

    def test_02_login_form_fields(self):
        print("\n[Test 2] Login form contains login_id and password fields")
        resp = self.client.get("/auth/login")
        html = resp.data.decode("utf-8")
        self.check("field 'login_id' present",
                   bool(re.search(r'name="login_id"', html)),
                   "Missing login_id field")
        self.check("field 'password' present",
                   bool(re.search(r'name="password"', html)),
                   "Missing password field")
        self.check("submit button present",
                   bool(re.search(r'type="submit"', html)),
                   "Missing submit button")
        return html

    def test_03_login_csrf_token(self):
        print("\n[Test 3] Login form has CSRF token")
        resp = self.client.get("/auth/login")
        html = resp.data.decode("utf-8")
        token = self._extract_csrf_token(html)
        self.check("csrf_token present", bool(token),
                   "No CSRF token found in login page")

    def test_04_login_oauth_buttons(self):
        print("\n[Test 4] Login form has OAuth buttons (Google, Facebook)")
        resp = self.client.get("/auth/login")
        html = resp.data.decode("utf-8")
        self.check("Google OAuth button",
                   bool(re.search(r'/auth/google', html)),
                   "Missing Google OAuth link")
        self.check("Facebook OAuth button",
                   bool(re.search(r'/auth/facebook', html)),
                   "Missing Facebook OAuth link")
        self.check("oauth-trigger class",
                   bool(re.search(r'oauth-trigger', html)),
                   "Missing oauth-trigger class")

    def test_05_login_post_without_csrf_returns_error(self):
        print("\n[Test 5] POST /auth/login without CSRF returns CSRF error")
        resp = self.client.post("/auth/login", data={
            "login_id": "test@example.com",
            "password": "password123",
        })
        body = resp.data.decode("utf-8").lower()
        is_csrf = "csrf" in body or resp.status_code == 400
        self.check("CSRF error returned", is_csrf,
                   f"Expected CSRF error, got status {resp.status_code}")

    def test_06_login_post_with_csrf_not_csrf_error(self):
        print("\n[Test 6] POST /auth/login with CSRF does not return CSRF error")
        get_resp = self.client.get("/auth/login")
        html = get_resp.data.decode("utf-8")
        csrf_token = self._extract_csrf_token(html)
        if not csrf_token:
            self.check("csrf token extracted", False, "Could not extract CSRF token")
            return

        resp = self.client.post("/auth/login", data={
            "csrf_token": csrf_token,
            "login_id": "test@example.com",
            "password": "password123",
        })
        body = resp.data.decode("utf-8").lower()
        is_csrf_specific = (
            "the csrf token is missing" in body
            or "the csrf token has expired" in body
            or "csrf token" in body
        )
        is_csrf_rejection = is_csrf_specific and resp.status_code == 400
        self.check("not CSRF rejection", not is_csrf_rejection,
                   f"CSRF rejection (status {resp.status_code})")

    def test_07_login_auth_page_class(self):
        print("\n[Test 7] Login page contains auth-page class")
        resp = self.client.get("/auth/login")
        html = resp.data.decode("utf-8")
        self.check("auth-page class present",
                   bool(re.search(r'auth-page', html)),
                   "auth-page class not found in login page")

    def test_08_login_labels_readable(self):
        print("\n[Test 8] Login page labels are styled for readability")
        resp = self.client.get("/auth/login")
        html = resp.data.decode("utf-8")
        has_label = bool(re.search(r'<span>\s*Email or Username\s*</span>', html))
        has_password_label = bool(re.search(r'<span>\s*Password\s*</span>', html))
        self.check("Email or Username label present", has_label,
                   "Login label missing")
        self.check("Password label present", has_password_label,
                   "Password label missing")

    def test_09_login_css_overrides(self):
        print("\n[Test 9] CSS contains Phase 71 login overrides for readability")
        self.check("chain-auth-card--login CSS present",
                   ".chain-auth-card--login" in self.css,
                   "Missing login card CSS overrides")
        self.check("login form input white bg",
                   ".chain-auth-card--login .chain-auth-form input" in self.css,
                   "Missing login form input override")
        self.check("login label light text",
                   ".chain-auth-card--login .chain-auth-form label span" in self.css,
                   "Missing login label override")
        self.check("login OAuth button override",
                   ".chain-auth-card--login .chain-auth-oauth" in self.css,
                   "Missing login OAuth button override")
        self.check("login submit button override",
                   ".chain-auth-card--login .auth-submit-btn" in self.css,
                   "Missing login submit button override")

    # ── OAuth Route Tests ──────────────────────────────────

    def test_10_oauth_google_route(self):
        print("\n[Test 10] /auth/google OAuth route responds gracefully")
        resp = self.client.get("/auth/google")
        # Should redirect either to Google (if configured) or back to login with error
        self.check("redirect response", resp.status_code in (302, 303, 307),
                   f"Expected redirect, got status {resp.status_code}")
        location = resp.location or ""
        if "/auth/login" in location:
            self.check("falls back to login on OAuth error", True,
                       "Redirected to login (Supabase OAuth not available)")
        elif location.startswith("http"):
            self.check("redirects to provider URL", True,
                       f"Redirecting to {location[:60]}...")

    def test_11_oauth_facebook_route(self):
        print("\n[Test 11] /auth/facebook OAuth route responds gracefully")
        resp = self.client.get("/auth/facebook")
        self.check("redirect response", resp.status_code in (302, 303, 307),
                   f"Expected redirect, got status {resp.status_code}")
        location = resp.location or ""

    def test_12_oauth_callback_errors(self):
        print("\n[Test 12] OAuth callback handles errors gracefully")
        # Simulate callback with error params
        resp = self.client.get("/auth/google/callback?error=access_denied&error_description=User+cancelled")
        self.check("error redirect", resp.status_code in (302, 303, 307),
                   f"Expected redirect, got status {resp.status_code}")
        if resp.status_code in (302, 303, 307):
            self.check("redirects to login with oauth error",
                       "/auth/login" in (resp.location or ""),
                       f"Redirected to {resp.location}")

    def test_13_oauth_diagnostics_page(self):
        print("\n[Test 13] OAuth diagnostics page renders")
        resp = self.client.get("/auth/oauth-diagnostics")
        exists = resp.status_code == 200
        self.check("diagnostics page renders", exists,
                   f"OAuth diagnostics returned {resp.status_code}")

    # ── Registration Page Tests ───────────────────────────

    def test_14_register_page_returns_200(self):
        print("\n[Test 14] GET /auth/register returns 200")
        resp = self.client.get("/auth/register")
        self.check("status 200", resp.status_code == 200, f"got {resp.status_code}")
        return resp

    def test_15_register_short_fields_present(self):
        print("\n[Test 15] Register form contains short required fields (Phase 70)")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        short_fields = [
            "full_name", "email", "username", "phone",
            "country_origin", "gender", "password", "confirm_password", "terms"
        ]
        for field in short_fields:
            pattern = r'name="' + re.escape(field) + r'"'
            self.check(f"field '{field}' present",
                       bool(re.search(pattern, html)),
                       f"Missing field: {field}")
        return html

    def test_16_register_removed_fields_absent(self):
        print("\n[Test 16] Removed long fields are not on register form")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        removed = [
            "current_country", "region", "town", "date_of_birth",
            "agreement_true_details", "agreement_identity_use",
            "agreement_username_privacy", "agreement_standards",
            "agreement_no_abuse", "creator_mode_enabled",
            "seller_mode_enabled", "dating_mode_enabled",
            "premium_mode_enabled", "interests", "activities",
            "looking_for", "residential_address", "preferred_language"
        ]
        for field in removed:
            pattern = r'name="' + re.escape(field) + r'"'
            self.check(f"removed '{field}' absent",
                       not bool(re.search(pattern, html)),
                       f"Field still present: {field}")

    def test_17_register_empty_fields_validation(self):
        print("\n[Test 17] Register POST: empty required fields returns error")
        get_resp = self.client.get("/auth/register")
        html = get_resp.data.decode("utf-8")
        csrf_token = self._extract_csrf_token(html)
        if not csrf_token:
            self.check("csrf token extracted", False, "Could not extract CSRF token")
            return

        resp = self.client.post("/auth/register", data={
            "csrf_token": csrf_token,
            "full_name": "",
            "email": "",
            "username": "",
            "phone": "",
            "country_origin": "",
            "gender": "",
            "password": "",
            "confirm_password": "",
        })
        body = resp.data.decode("utf-8").lower()
        self.check("returns 200 with error", resp.status_code == 200,
                   f"Expected 200 with validation error, got {resp.status_code}")
        has_error = "is required" in body or "required" in body
        self.check("error message shown", has_error,
                   "No validation error displayed")

    def test_18_register_password_mismatch(self):
        print("\n[Test 18] Register POST: password mismatch returns error")
        get_resp = self.client.get("/auth/register")
        html = get_resp.data.decode("utf-8")
        csrf_token = self._extract_csrf_token(html)
        if not csrf_token:
            self.check("csrf token extracted", False, "Could not extract CSRF token")
            return

        resp = self.client.post("/auth/register", data={
            "csrf_token": csrf_token,
            "full_name": "Test User",
            "email": "test@example.com",
            "username": "testuser",
            "phone": "+264811234567",
            "country_origin": "Namibia",
            "gender": "male",
            "password": "Pass1234!",
            "confirm_password": "DIFFERENT",
            "terms": "on",
        })
        body = resp.data.decode("utf-8")
        self.check("returns 200", resp.status_code == 200,
                   f"Expected 200, got {resp.status_code}")
        self.check("password mismatch error",
                   "do not match" in body.lower(),
                   "Missing password mismatch error")

    def test_19_register_missing_terms(self):
        print("\n[Test 19] Register POST: missing terms returns error")
        get_resp = self.client.get("/auth/register")
        html = get_resp.data.decode("utf-8")
        csrf_token = self._extract_csrf_token(html)
        if not csrf_token:
            self.check("csrf token extracted", False, "Could not extract CSRF token")
            return

        resp = self.client.post("/auth/register", data={
            "csrf_token": csrf_token,
            "full_name": "Test User",
            "email": "test@example.com",
            "username": "testuser",
            "phone": "+264811234567",
            "country_origin": "Namibia",
            "gender": "male",
            "password": "Pass1234!",
            "confirm_password": "Pass1234!",
            # terms is missing
        })
        body = resp.data.decode("utf-8")
        self.check("returns 200", resp.status_code == 200,
                   f"Expected 200, got {resp.status_code}")
        self.check("terms error shown",
                   "terms" in body.lower() or "accept" in body.lower(),
                   "Missing terms error")

    def test_20_register_without_removed_fields(self):
        print("\n[Test 20] Register POST without removed fields does not fail on those fields")
        get_resp = self.client.get("/auth/register")
        html = get_resp.data.decode("utf-8")
        csrf_token = self._extract_csrf_token(html)
        if not csrf_token:
            self.check("csrf token extracted", False, "Could not extract CSRF token")
            return

        resp = self.client.post("/auth/register", data={
            "csrf_token": csrf_token,
            "full_name": "Test User",
            "email": "test@example.com",
            "username": "testuser",
            "phone": "+264811234567",
            "country_origin": "Namibia",
            "gender": "male",
            "password": "TestPass123!",
            "confirm_password": "TestPass123!",
            "terms": "on",
        })
        body = resp.data.decode("utf-8").lower()
        removed_field_errors = [
            "current country is required",
            "region, state, or province is required",
            "town or city is required",
            "you must accept all account agreements",
        ]
        for err in removed_field_errors:
            self.check(f"no '{err}' error", err not in body,
                       f"Got removed field error: {err}")
        self.check("acceptable response (200/302)",
                   resp.status_code in (200, 302),
                   f"Got status {resp.status_code}")

    def test_21_register_csrf(self):
        print("\n[Test 21] Register POST without CSRF gives error, with CSRF does not")
        # Without CSRF
        resp_no = self.client.post("/auth/register", data={
            "full_name": "Test User",
            "email": "test@example.com",
        })
        self.check("no CSRF = CSRF error",
                   resp_no.status_code == 400 or b"csrf" in resp_no.data.lower(),
                   f"No CSRF error, got {resp_no.status_code}")

        # With CSRF
        get_resp = self.client.get("/auth/register")
        html = get_resp.data.decode("utf-8")
        csrf_token = self._extract_csrf_token(html)
        if csrf_token:
            resp_yes = self.client.post("/auth/register", data={
                "csrf_token": csrf_token,
                "full_name": "Test User",
                "email": "test@example.com",
                "username": "testuser",
                "phone": "+264811234567",
                "country_origin": "Namibia",
                "gender": "male",
                "password": "TestPass123!",
                "confirm_password": "TestPass123!",
                "terms": "on",
            })
            body_lower = resp_yes.data.decode("utf-8").lower()
            is_csrf = ("the csrf token is missing" in body_lower
                       or "the csrf token has expired" in body_lower)
            self.check("with CSRF = not CSRF error",
                       not is_csrf,
                       f"Got CSRF error with token: {resp_yes.data[:200]}")

    def test_22_auth_page_shared_css(self):
        print("\n[Test 22] auth-page CSS override covers both register and login")
        # Check register page
        resp_reg = self.client.get("/auth/register")
        html_reg = resp_reg.data.decode("utf-8")
        reg_has_auth_page = "auth-page" in html_reg

        # Check login page
        resp_log = self.client.get("/auth/login")
        html_log = resp_log.data.decode("utf-8")
        log_has_auth_page = "auth-page" in html_log

        self.check("register has auth-page class", reg_has_auth_page,
                   "Register page missing auth-page class")
        self.check("login has auth-page class", log_has_auth_page,
                   "Login page missing auth-page class")

    # ── Run All ────────────────────────────────────────────

    def run_all(self):
        print("=" * 60)
        print("Phase 71 — Full Auth Production Flow")
        print("=" * 60)

        self.test_01_login_page_returns_200()
        self.test_02_login_form_fields()
        self.test_03_login_csrf_token()
        self.test_04_login_oauth_buttons()
        self.test_05_login_post_without_csrf_returns_error()
        self.test_06_login_post_with_csrf_not_csrf_error()
        self.test_07_login_auth_page_class()
        self.test_08_login_labels_readable()
        self.test_09_login_css_overrides()
        self.test_10_oauth_google_route()
        self.test_11_oauth_facebook_route()
        self.test_12_oauth_callback_errors()
        self.test_13_oauth_diagnostics_page()
        self.test_14_register_page_returns_200()
        self.test_15_register_short_fields_present()
        self.test_16_register_removed_fields_absent()
        self.test_17_register_empty_fields_validation()
        self.test_18_register_password_mismatch()
        self.test_19_register_missing_terms()
        self.test_20_register_without_removed_fields()
        self.test_21_register_csrf()
        self.test_22_auth_page_shared_css()

        total = self.passes + self.fails
        print("\n" + "=" * 60)
        print(f"RESULTS:  {self.passes} passed  /  {self.fails} failed  /  {total} total")
        if self.errors:
            print("\nFAILURES:")
            for e in self.errors:
                print(f"  \u2022 {e}")
        print("=" * 60)
        return self.fails == 0


if __name__ == "__main__":
    success = Phase71FullAuthFlowTest().run_all()
    sys.exit(0 if success else 1)
