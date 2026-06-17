"""
Phase 70 — Short APK Registration + Dark Inputs Fix.

Tests:
1. GET /auth/register returns 200
2. Register form contains only the short required fields
3. Removed long fields are not required
4. CSS contains color-scheme: light
5. CSS contains -webkit-text-fill-color
6. CSS contains white input background
7. Form has csrf_token
8. Form method is POST
9. POST without CSRF gives CSRF error
10. POST with CSRF does not give CSRF error
11. POST with missing removed fields does not fail because those fields are missing
12. Registration page contains auth-page class
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
os.environ["SECRET_KEY"] = "test-secret-key-for-phase70"

from app import create_app


class Phase70ShortRegistrationTest:
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

    def _extract_csrf_token(self, html):
        m = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', html)
        if m:
            return m.group(1)
        m = re.search(r'<input\s+type="hidden"[^>]*name="csrf_token"[^>]*value="([^"]+)"', html)
        if m:
            return m.group(1)
        m = re.search(r'<input\s+[^>]*name="csrf_token"[^>]*value="([^"]+)"', html)
        if m:
            return m.group(1)
        return None

    def test_01_get_register_returns_200(self):
        print("\n[Test 1] GET /auth/register returns 200")
        resp = self.client.get("/auth/register")
        self.check("status 200", resp.status_code == 200, f"got {resp.status_code}")
        return resp

    def test_02_short_required_fields_present(self):
        print("\n[Test 2] Register form contains only short required fields")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")

        short_fields = ["full_name", "email", "username", "phone", "country_origin", "gender", "password", "confirm_password", "terms"]
        for field in short_fields:
            pattern = r'name="' + re.escape(field) + r'"'
            self.check(f"field '{field}' present", bool(re.search(pattern, html)),
                        f"Missing field: {field}")

        return html

    def test_03_removed_fields_not_required(self):
        print("\n[Test 3] Removed long fields are not required")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")

        removed = ["current_country", "region", "town", "date_of_birth",
                    "agreement_true_details", "agreement_identity_use",
                    "agreement_username_privacy", "agreement_standards",
                    "agreement_no_abuse", "creator_mode_enabled",
                    "seller_mode_enabled", "dating_mode_enabled",
                    "premium_mode_enabled", "interests", "activities",
                    "looking_for", "residential_address", "preferred_language"]
        for field in removed:
            pattern = r'name="' + re.escape(field) + r'"'
            self.check(f"removed field '{field}' absent", not bool(re.search(pattern, html)),
                        f"Field still present: {field}")

        # Hidden fields that are allowed (profile_type, signup_method, human_confirmed)
        allowed_hidden = ["profile_type", "signup_method", "human_confirmed", "phone_code"]
        for field in allowed_hidden:
            pattern = r'name="' + re.escape(field) + r'"'
            self.check(f"allowed hidden field '{field}' present",
                        bool(re.search(pattern, html)),
                        f"Missing allowed field: {field}")

    def test_04_css_color_scheme_light(self):
        print("\n[Test 4] CSS contains color-scheme: light")
        css_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "static", "css", "chain_auth.css")
        with open(css_path) as f:
            css = f.read()
        self.check("color-scheme: light", "color-scheme: light" in css,
                    "color-scheme: light not found in chain_auth.css")

    def test_05_css_webkit_text_fill_color(self):
        print("\n[Test 5] CSS contains -webkit-text-fill-color")
        css_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "static", "css", "chain_auth.css")
        with open(css_path) as f:
            css = f.read()
        count = css.count("-webkit-text-fill-color")
        self.check("-webkit-text-fill-color present", count >= 2,
                    f"Only found {count} occurrences, expected >= 2")

    def test_06_css_white_input_background(self):
        print("\n[Test 6] CSS contains white input background")
        css_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "static", "css", "chain_auth.css")
        with open(css_path) as f:
            css = f.read()
        # Check for the Phase 70 section which has the strongest overrides
        has_phase70_bg = 'background: #ffffff !important' in css or 'background-color: #ffffff !important' in css
        self.check("white background override", has_phase70_bg,
                    "No background: #ffffff !important found in chain_auth.css")

    def test_07_form_has_csrf_token(self):
        print("\n[Test 7] Form has csrf_token")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        has_meta = bool(re.search(r'<meta\s+name="csrf-token"\s+content="[^"]+"', html))
        has_input = bool(re.search(r'<input[^>]*name="csrf_token"[^>]*value="[^"]+"', html))
        self.check("meta csrf-token", has_meta, "meta csrf-token not found")
        self.check("csrf_token input", has_input, "csrf_token input not found")

    def test_08_form_method_post(self):
        print("\n[Test 8] Form method is POST")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        has_post = bool(re.search(r'<form[^>]*method="POST"', html))
        self.check("form method=POST", has_post, "No form with method=POST")

    def test_09_post_without_csrf_returns_csrf_error(self):
        print("\n[Test 9] POST without CSRF gives CSRF error")
        resp = self.client.post("/auth/register", data={
            "full_name": "Test User",
            "email": "test@example.com",
            "username": "testuser",
            "phone": "+264811234567",
            "country_origin": "Namibia",
            "gender": "male",
            "password": "TestPass123!",
            "confirm_password": "TestPass123!",
        })
        is_csrf = b"CSRF" in resp.data or b"csrf" in resp.data.lower()
        self.check("CSRF error returned", is_csrf or resp.status_code == 400,
                    f"Expected CSRF error, got status {resp.status_code}: {resp.data[:200]}")

    def test_10_post_with_csrf_not_csrf_error(self):
        print("\n[Test 10] POST with CSRF does not give CSRF error")
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
            "human_confirmed": "on",
            "profile_type": "member",
            "signup_method": "email",
        })

        body_text = resp.data.decode("utf-8")
        body_lower = body_text.lower()

        is_csrf_specific = (
            "the csrf token is missing" in body_lower
            or "the csrf token has expired" in body_lower
            or "csrf token" in body_lower
        )
        is_csrf_rejection = is_csrf_specific and resp.status_code == 400

        self.check("not CSRF rejection", not is_csrf_rejection,
                    f"CSRF rejection (status {resp.status_code}): {body_text[:200]}")

        if resp.status_code == 302:
            self.check("redirected (registration attempt)", True,
                        f"Location: {resp.location}")
        elif resp.status_code == 200:
            self.check("form returned (non-CSRF error)", True,
                        "Validation/user error shown")
        else:
            self.check(f"status {resp.status_code} (non-CSRF)", not is_csrf_rejection,
                        body_text[:200])

    def test_11_post_without_removed_fields_succeeds_or_validation(self):
        print("\n[Test 11] POST with missing removed fields does not fail because fields are missing")
        get_resp = self.client.get("/auth/register")
        html = get_resp.data.decode("utf-8")
        csrf_token = self._extract_csrf_token(html)

        if not csrf_token:
            self.check("csrf token extracted", False, "Could not extract CSRF token")
            return

        # POST without any removed fields (current_country, region, town, etc.)
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

        body_text = resp.data.decode("utf-8")
        body_lower = body_text.lower()

        # Should NOT say "current country is required" or "region is required" etc
        removed_field_errors = [
            "current country is required",
            "region, state, or province is required",
            "town or city is required",
            "you must accept all account agreements",
        ]
        for err in removed_field_errors:
            self.check(f"no '{err}' error", err not in body_lower,
                        f"Got removed field error: {err}")

        # Acceptable responses (not field-missing errors for removed fields)
        acceptable = resp.status_code in (200, 302)
        self.check("response acceptable (200/302)", acceptable,
                    f"Got status {resp.status_code}")

    def test_12_auth_page_class_present(self):
        print("\n[Test 12] Registration page contains auth-page class")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        self.check("auth-page class in HTML", "auth-page" in html,
                    "auth-page class not found")

    def run_all(self):
        print("=" * 60)
        print("Phase 70 — Short APK Registration + Dark Inputs Fix")
        print("=" * 60)

        resp = self.test_01_get_register_returns_200()
        if resp and resp.status_code == 200:
            self.test_02_short_required_fields_present()
            self.test_03_removed_fields_not_required()
        else:
            self.check("skipped tests 2-3 (depends on 1)", False,
                        "Skipped because GET /auth/register did not return 200")

        self.test_04_css_color_scheme_light()
        self.test_05_css_webkit_text_fill_color()
        self.test_06_css_white_input_background()
        self.test_07_form_has_csrf_token()
        self.test_08_form_method_post()
        self.test_09_post_without_csrf_returns_csrf_error()
        self.test_10_post_with_csrf_not_csrf_error()
        self.test_11_post_without_removed_fields_succeeds_or_validation()
        self.test_12_auth_page_class_present()

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
    success = Phase70ShortRegistrationTest().run_all()
    sys.exit(0 if success else 1)
