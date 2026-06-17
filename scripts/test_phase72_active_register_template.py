"""
Phase 72B — Hard Replace Active Register Template.

Asserts:
- /auth/register does NOT contain old wizard text
- /auth/register contains short form fields
- /auth/register contains csrf_token
- /auth/register contains Google/Facebook OAuth links
- /auth/register uses versioned CSS/JS
- /auth/register form action points to register_post
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
os.environ["SECRET_KEY"] = "test-secret-key-for-phase72b"

from app import create_app


class Phase72ActiveRegisterTemplateTest:
    def __init__(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.errors = []
        self.passes = 0
        self.fails = 0

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

    def test_01_no_old_wizard_text(self):
        print("\n[Test 1] /auth/register does NOT contain old wizard text")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        forbidden = [
            "Step 1 of 7",
            "Your account starts here",
            "chain-register-progress-text",
            "chain-auth-step-label",
            "data-step=",
            "chain-register-stepper",
            "step-dot",
        ]
        for phrase in forbidden:
            self.check(f"no '{phrase}'", phrase not in html,
                       f"Found forbidden text: {phrase}")

    def test_02_short_fields_present(self):
        print("\n[Test 2] /auth/register contains short form fields")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        fields = [
            "full_name", "email", "username", "phone",
            "country_origin", "gender", "password", "confirm_password", "terms"
        ]
        for field in fields:
            pattern = r'name="' + re.escape(field) + r'"'
            self.check(f"field '{field}' present",
                       bool(re.search(pattern, html)),
                       f"Missing field: {field}")

    def test_03_csrf_token(self):
        print("\n[Test 3] /auth/register contains csrf_token")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        has_meta = bool(re.search(r'<meta\s+name="csrf-token"\s+content="[^"]+"', html))
        has_input = bool(re.search(r'name="csrf_token"', html))
        self.check("meta csrf-token tag", has_meta, "Missing meta csrf-token")
        self.check("csrf_token hidden input", has_input, "Missing csrf_token input")

    def test_04_oauth_links(self):
        print("\n[Test 4] /auth/register contains Google and Facebook OAuth links")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        self.check("Continue with Google link",
                   bool(re.search(r'/auth/google', html)),
                   "Missing Google OAuth link")
        self.check("Continue with Facebook link",
                   bool(re.search(r'/auth/facebook', html)),
                   "Missing Facebook OAuth link")
        self.check("oauth-trigger class",
                   bool(re.search(r'oauth-trigger', html)),
                   "Missing oauth-trigger class")

    def test_05_versioned_assets(self):
        print("\n[Test 5] /auth/register uses versioned CSS and JS")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        self.check("chain_auth.css?v=phase72b",
                   'chain_auth.css?v=phase72b' in html,
                   "Missing versioned CSS link")
        self.check("chain_register.js?v=phase72b",
                   'chain_register.js?v=phase72b' in html,
                   "Missing versioned JS link")
        self.check("chain_locations.js?v=phase72b",
                   'chain_locations.js?v=phase72b' in html,
                   "Missing versioned locations JS link")

    def test_06_form_action(self):
        print("\n[Test 6] /auth/register form action points to register_post")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        has_action = bool(re.search(
            r'<form[^>]*action="[^"]*/auth/register[^"]*"',
            html
        ))
        self.check("form action=/auth/register", has_action,
                   "Form missing action attribute pointing to /auth/register")

    def test_07_no_removed_fields(self):
        print("\n[Test 7] /auth/register does NOT contain removed long fields")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        removed = [
            "current_country", "region", "town", "date_of_birth",
            "agreement_true_details", "agreement_identity_use",
            "agreement_username_privacy", "agreement_standards",
            "agreement_no_abuse", "creator_mode_enabled",
            "seller_mode_enabled", "dating_mode_enabled",
            "premium_mode_enabled", "interests", "activities",
            "looking_for", "residential_address", "preferred_language",
        ]
        for field in removed:
            pattern = r'name="' + re.escape(field) + r'"'
            self.check(f"removed '{field}' absent",
                       not bool(re.search(pattern, html)),
                       f"Field still present: {field}")

    def test_08_auth_page_class(self):
        print("\n[Test 8] /auth/register has auth-page class")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        self.check("auth-page class",
                   "auth-page" in html,
                   "Missing auth-page class")

    def test_09_register_post_without_csrf_fails(self):
        print("\n[Test 9] POST /auth/register without CSRF returns CSRF error")
        resp = self.client.post("/auth/register", data={
            "full_name": "Test User",
            "email": "test@example.com",
        })
        body_lower = resp.data.decode("utf-8").lower()
        is_csrf = resp.status_code == 400 or "csrf" in body_lower
        self.check("CSRF rejection", is_csrf,
                   f"Expected CSRF error, got {resp.status_code}")

    def test_10_register_post_with_csrf_no_csrf_error(self):
        print("\n[Test 10] POST /auth/register with CSRF does not get CSRF rejection")
        get_resp = self.client.get("/auth/register")
        html = get_resp.data.decode("utf-8")
        m = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', html)
        if not m:
            self.check("csrf token extracted", False, "Could not extract CSRF token")
            return
        csrf_token = m.group(1)

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
        is_csrf_specific = (
            "the csrf token is missing" in body
            or "the csrf token has expired" in body
            or "csrf token" in body
        )
        is_csrf_rejection = is_csrf_specific and resp.status_code == 400
        self.check("not CSRF rejection", not is_csrf_rejection,
                   f"Got CSRF rejection: {resp.data[:200]}")

    def test_11_register_post_missing_terms(self):
        print("\n[Test 11] POST /auth/register missing terms shows error")
        get_resp = self.client.get("/auth/register")
        html = get_resp.data.decode("utf-8")
        m = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', html)
        if not m:
            self.check("csrf token extracted", False, "Could not extract CSRF token")
            return
        csrf_token = m.group(1)

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
        })
        self.check("returns 200 with error", resp.status_code == 200,
                   f"Expected 200, got {resp.status_code}")
        self.check("terms error shown",
                   "terms" in resp.data.decode("utf-8").lower(),
                   "Missing terms error message")

    def test_12_register_post_password_mismatch(self):
        print("\n[Test 12] POST /auth/register password mismatch shows error")
        get_resp = self.client.get("/auth/register")
        html = get_resp.data.decode("utf-8")
        m = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', html)
        if not m:
            self.check("csrf token extracted", False, "Could not extract CSRF token")
            return
        csrf_token = m.group(1)

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
        self.check("returns 200", resp.status_code == 200,
                   f"Expected 200, got {resp.status_code}")
        self.check("password mismatch error",
                   "do not match" in resp.data.decode("utf-8").lower(),
                   "Missing password mismatch error")

    def test_13_css_phase72_overrides(self):
        print("\n[Test 13] chain_auth.css has Phase 72 register OAuth button overrides")
        css_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "css", "chain_auth.css"
        )
        with open(css_path) as f:
            css = f.read()
        self.check("register-card .chain-auth-oauth",
                   ".register-card .chain-auth-oauth" in css,
                   "Missing register OAuth button CSS")

    def run_all(self):
        print("=" * 60)
        print("Phase 72B — Active Register Template")
        print("=" * 60)

        self.test_01_no_old_wizard_text()
        self.test_02_short_fields_present()
        self.test_03_csrf_token()
        self.test_04_oauth_links()
        self.test_05_versioned_assets()
        self.test_06_form_action()
        self.test_07_no_removed_fields()
        self.test_08_auth_page_class()
        self.test_09_register_post_without_csrf_fails()
        self.test_10_register_post_with_csrf_no_csrf_error()
        self.test_11_register_post_missing_terms()
        self.test_12_register_post_password_mismatch()
        self.test_13_css_phase72_overrides()

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
    success = Phase72ActiveRegisterTemplateTest().run_all()
    sys.exit(0 if success else 1)
