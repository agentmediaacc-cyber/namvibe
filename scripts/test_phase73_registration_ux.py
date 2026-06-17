"""
Phase 73 — Finish New Registration Form UX.

Asserts:
- /auth/register returns 200
- no old stepper text
- Full Name, Email, Username, Phone, Country Origin, Date of Birth,
  Gender, Password, Confirm Password, Terms, Create Account button all exist
- country-list datalist with world countries (Namibia, South Africa, Angola, US, China)
- form method POST
- csrf_token exists
- Create Account button visible and not hidden
- POST with missing date_of_birth shows DOB required error
- POST with valid date_of_birth does not fail because DOB missing
- CSS contains input[type="date"] readability rules
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
os.environ["SECRET_KEY"] = "test-secret-key-for-phase73"

from app import create_app


class Phase73RegistrationUXTest:
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

    def _extract_csrf(self, html):
        m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
        return m.group(1) if m else None

    def test_01_page_returns_200(self):
        print("\n[Test 1] GET /auth/register returns 200")
        resp = self.client.get("/auth/register")
        self.check("status 200", resp.status_code == 200, f"got {resp.status_code}")
        return resp

    def test_02_no_old_wizard(self):
        print("\n[Test 2] No old stepper/wizard text present")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        forbidden = [
            "Step 1 of 7", "Your account starts here",
            "chain-register-progress-text", "chain-auth-step-label",
            "data-step=", "chain-register-stepper", "step-dot",
        ]
        for phrase in forbidden:
            self.check(f"no '{phrase}'", phrase not in html,
                       f"Found forbidden: {phrase}")
        return html

    def test_03_required_fields_exist(self):
        print("\n[Test 3] All required form fields present")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        fields = {
            "full_name": "name=\"full_name\"",
            "email": "name=\"email\"",
            "username": "name=\"username\"",
            "phone": "name=\"phone\"",
            "country_origin": "name=\"country_origin\"",
            "date_of_birth": "name=\"date_of_birth\"",
            "gender": "name=\"gender\"",
            "password": "name=\"password\"",
            "confirm_password": "name=\"confirm_password\"",
            "terms": "name=\"terms\"",
        }
        for label, pattern in fields.items():
            self.check(f"field '{label}' exists",
                       bool(re.search(pattern, html)),
                       f"Missing field: {label}")
        return html

    def test_04_datalist_exists(self):
        print("\n[Test 4] Country datalist exists with world countries")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        self.check("country-list datalist",
                   bool(re.search(r'<datalist\s+id="country-list"', html)),
                   "Missing country-list datalist")
        self.check("list='country-list' on input",
                   bool(re.search(r'list="country-list"', html)),
                   "Missing list attribute on country input")
        self.check("Namibia in datalist",
                   bool(re.search(r'Namibia', html)),
                   "Namibia not in datalist")
        self.check("South Africa in datalist",
                   bool(re.search(r'South Africa', html)),
                   "South Africa not in datalist")
        self.check("Angola in datalist",
                   bool(re.search(r'Angola', html)),
                   "Angola not in datalist")
        self.check("United States in datalist",
                   bool(re.search(r'United States', html)),
                   "United States not in datalist")
        self.check("China in datalist",
                   bool(re.search(r'China', html)),
                   "China not in datalist")

    def test_05_button_visible(self):
        print("\n[Test 5] Create Account button exists and is not hidden")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        btn_pattern = r'<button[^>]*class="register-btn[^"]*"[^>]*>Create Account</button>'
        self.check("Create Account button",
                   bool(re.search(btn_pattern, html)),
                   "Create Account button missing")
        # Also check CSS does not hide it
        css_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "css", "chain_auth.css"
        )
        with open(css_path) as f:
            css = f.read()
        has_hidden = bool(re.search(r'#register_submit\s*\{\s*display:\s*none', css))
        self.check("button not hidden by CSS", not has_hidden,
                   "register_submit still has display:none in CSS")

    def test_06_form_method(self):
        print("\n[Test 6] Form method POST and CSRF token")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        self.check("form method=POST",
                   bool(re.search(r'<form[^>]*method="POST"', html)),
                   "Form method is not POST")
        self.check("csrf_token present",
                   bool(re.search(r'name="csrf_token"', html)),
                   "Missing csrf_token input")
        # Also check meta csrf-token from base.html
        self.check("meta csrf-token",
                   bool(re.search(r'<meta\s+name="csrf-token"', html)),
                   "Missing meta csrf-token")

    def test_07_post_missing_dob(self):
        print("\n[Test 7] POST with missing date_of_birth shows DOB required error")
        get_resp = self.client.get("/auth/register")
        html = get_resp.data.decode("utf-8")
        csrf_token = self._extract_csrf(html)
        if not csrf_token:
            self.check("csrf extracted", False, "Could not extract CSRF")
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
            # date_of_birth deliberately omitted
        })
        body = resp.data.decode("utf-8")
        self.check("returns 200 with error", resp.status_code == 200,
                   f"Expected 200, got {resp.status_code}")
        self.check("DOB required error shown",
                   "Date of birth is required" in body,
                   "Missing 'Date of birth is required' validation error")

    def test_08_post_with_valid_dob(self):
        print("\n[Test 8] POST with valid date_of_birth does not fail because DOB missing")
        get_resp = self.client.get("/auth/register")
        html = get_resp.data.decode("utf-8")
        csrf_token = self._extract_csrf(html)
        if not csrf_token:
            self.check("csrf extracted", False, "Could not extract CSRF")
            return

        resp = self.client.post("/auth/register", data={
            "csrf_token": csrf_token,
            "full_name": "Test Adult User",
            "email": "testadult@example.com",
            "username": "testadult",
            "phone": "+264811234568",
            "country_origin": "Namibia",
            "date_of_birth": "2000-01-15",
            "gender": "male",
            "password": "TestPass123!",
            "confirm_password": "TestPass123!",
            "terms": "on",
            "human_confirmed": "on",
            "profile_type": "member",
            "signup_method": "email",
        })
        # Should NOT say "Date of birth is required" as a validation error
        body = resp.data.decode("utf-8")
        body_lower = body.lower()
        # Check for the specific validation error message
        dob_error_message = "Date of birth is required" in body
        # The field label always contains 'date of birth' + 'req *' so don't match on that
        # Instead check for the specific error message pattern shown by auth_routes.py
        has_dob_validation_error = dob_error_message
        underage = "18 and older" in body_lower or "only available" in body_lower
        self.check("not DOB validation error", not has_dob_validation_error,
                   f"Got 'Date of birth is required' error even with valid DOB")
        self.check("acceptable response (200 or 302)",
                   resp.status_code in (200, 302),
                   f"Got status {resp.status_code}")

    def test_09_css_date_input_rules(self):
        print("\n[Test 9] CSS contains input[type='date'] readability rules")
        css_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "css", "chain_auth.css"
        )
        with open(css_path) as f:
            css = f.read()
        self.check("input[type='date'] rule",
                   "input[type=\"date\"]" in css or "input[type='date']" in css,
                   "Missing input[type=date] CSS rule")
        self.check("date input white background",
                   "background: #ffffff" in css,
                   "Missing white background for date input")
        self.check("date input color-scheme light",
                   "color-scheme: light" in css,
                   "Missing color-scheme light for date input")
        self.check("calendar picker indicator style",
                   "calendar-picker-indicator" in css,
                   "Missing calendar picker indicator CSS")

    def test_10_no_removed_fields(self):
        print("\n[Test 10] Removed long fields not present")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        removed = [
            "current_country", "region", "town",
            "agreement_true_details", "agreement_identity_use",
            "agreement_username_privacy", "agreement_standards",
            "agreement_no_abuse",
        ]
        for field in removed:
            pattern = r'name="' + re.escape(field) + r'"'
            self.check(f"removed '{field}' absent",
                       not bool(re.search(pattern, html)),
                       f"Field still present: {field}")

    def test_11_oauth_buttons(self):
        print("\n[Test 11] OAuth buttons present")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        self.check("Google OAuth link",
                   bool(re.search(r'/auth/google', html)),
                   "Missing Google OAuth link")
        self.check("Facebook OAuth link",
                   bool(re.search(r'/auth/facebook', html)),
                   "Missing Facebook OAuth link")

    def test_12_post_without_csrf_fails(self):
        print("\n[Test 12] POST without CSRF returns CSRF error")
        resp = self.client.post("/auth/register", data={
            "full_name": "Hacker",
            "email": "hacker@evil.com",
        })
        self.check("CSRF error",
                   resp.status_code == 400 or b"csrf" in resp.data.lower(),
                   f"Expected CSRF error, got {resp.status_code}")

    def test_13_auth_page_class(self):
        print("\n[Test 13] auth-page class present")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        self.check("auth-page class",
                   "auth-page" in html,
                   "Missing auth-page class")

    def test_14_versioned_assets(self):
        print("\n[Test 14] Versioned CSS and JS assets")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        self.check("chain_auth.css?v=phase73",
                   'chain_auth.css?v=phase73' in html,
                   "Missing versioned CSS")
        self.check("chain_register.js?v=phase73",
                   'chain_register.js?v=phase73' in html,
                   "Missing versioned register JS")
        self.check("chain_locations.js?v=phase73",
                   'chain_locations.js?v=phase73' in html,
                   "Missing versioned locations JS")

    def run_all(self):
        print("=" * 60)
        print("Phase 73 — Finish New Registration Form UX")
        print("=" * 60)

        self.test_01_page_returns_200()
        self.test_02_no_old_wizard()
        self.test_03_required_fields_exist()
        self.test_04_datalist_exists()
        self.test_05_button_visible()
        self.test_06_form_method()
        self.test_07_post_missing_dob()
        self.test_08_post_with_valid_dob()
        self.test_09_css_date_input_rules()
        self.test_10_no_removed_fields()
        self.test_11_oauth_buttons()
        self.test_12_post_without_csrf_fails()
        self.test_13_auth_page_class()
        self.test_14_versioned_assets()

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
    success = Phase73RegistrationUXTest().run_all()
    sys.exit(0 if success else 1)
