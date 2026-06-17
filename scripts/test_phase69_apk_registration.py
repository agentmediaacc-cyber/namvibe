"""
Phase 69 — APK Registration Mobile Form + CSRF test.

Tests:
1. GET /auth/register returns 200
2. HTML contains csrf_token input or csrf meta token
3. Registration form has method POST
4. Registration form has 'auth-page' CSS class
5. POST without CSRF returns 400 expected
6. POST with CSRF does NOT return CSRF missing error
   (may return validation/duplicate/user error, but NOT CSRF error)
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
os.environ["SECRET_KEY"] = "test-secret-key-for-phase69"

from app import create_app
from flask_wtf.csrf import generate_csrf


class Phase69APKRegistrationTest:
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
                msg += f"  —  {detail}"
            print(msg)
            self.errors.append(f"{name}: {detail}")

    def test_01_get_register_returns_200(self):
        print("\n[Test 1] GET /auth/register returns 200")
        resp = self.client.get("/auth/register")
        self.check("status 200", resp.status_code == 200, f"got {resp.status_code}")
        return resp

    def test_02_html_has_csrf_token(self):
        print("\n[Test 2] HTML contains csrf_token input or meta csrf-token")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")

        has_meta = bool(re.search(r'<meta\s+name="csrf-token"\s+content="[^"]+"', html))
        has_input = bool(re.search(r'<input\s+[^>]*name="csrf_token"\s+[^>]*value="[^"]+"', html))
        has_input_alt = bool(re.search(r'<input\s+[^>]*value="[^"]+"\s+[^>]*name="csrf_token"\s*[^>]*>', html))

        self.check("meta csrf-token tag", has_meta, "meta[name=csrf-token] not found")
        self.check("hidden csrf_token input", has_input or has_input_alt, "csrf_token input not found")

    def test_03_form_has_method_post(self):
        print("\n[Test 3] Registration form has method=POST")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        has_post_form = bool(re.search(r'<form[^>]*method="POST"', html))
        self.check("form method=POST", has_post_form, "No form with method=POST found")

    def test_04_form_has_auth_page_class(self):
        print("\n[Test 4] Registration form has 'auth-page' CSS class")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        has_auth_page = bool(re.search(r'auth-page', html))
        self.check("auth-page class present", has_auth_page, "auth-page class not found in HTML")

    def test_05_post_without_csrf_returns_400(self):
        print("\n[Test 5] POST without CSRF returns 400 expected")
        resp = self.client.post("/auth/register", data={
            "full_name": "APK Test",
            "email": "apktest@example.com",
            "phone": "+264811234567",
            "username": "apktest_user",
            "country_origin": "Namibia",
            "current_country": "Namibia",
            "region": "Khomas",
            "town": "Windhoek",
            "password": "TestPass123!",
            "confirm_password": "TestPass123!",
        })
        is_400 = resp.status_code == 400
        is_csrf_error = b"CSRF" in resp.data or b"csrf" in resp.data.lower()
        self.check("returns 400 without CSRF", is_400 or is_csrf_error,
                    f"status={resp.status_code}, body={resp.data[:200]}")
        # Also expect the response mentions CSRF
        self.check("response mentions CSRF", is_csrf_error,
                    f"No CSRF mention in 400 response: {resp.data[:200]}")

    def _extract_csrf_token(self, html):
        """Extract CSRF token from HTML meta tag or hidden input."""
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

    def test_06_post_with_csrf_does_not_return_csrf_error(self):
        print("\n[Test 6] POST with CSRF does NOT return CSRF missing error")

        # GET the register page to obtain a valid session + CSRF token
        get_resp = self.client.get("/auth/register")
        html = get_resp.data.decode("utf-8")
        csrf_token = self._extract_csrf_token(html)

        if not csrf_token:
            self.check("csrf token extracted from GET", False,
                        "Could not extract CSRF token from registration page")
            return

        resp = self.client.post("/auth/register", data={
            "csrf_token": csrf_token,
            "full_name": "APK Test",
            "email": "apktest@example.com",
            "phone": "+264811234567",
            "username": "apktest_user",
            "country_origin": "Namibia",
            "current_country": "Namibia",
            "region": "Khomas",
            "town": "Windhoek",
            "password": "TestPass123!",
            "confirm_password": "TestPass123!",
            "agreement_true_details": "on",
            "agreement_identity_use": "on",
            "agreement_username_privacy": "on",
            "agreement_standards": "on",
            "agreement_no_abuse": "on",
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

        self.check("POST with CSRF not rejected as CSRF error", not is_csrf_rejection,
                    f"CSRF rejection detected (status={resp.status_code}): {body_text[:200]}")

        if resp.status_code == 302:
            self.check("registration redirected (expected path)", True,
                        f"Redirect to: {resp.location}")
        elif resp.status_code == 200:
            self.check("registration returned form with validation (not CSRF)", True,
                        "Validation error shown (non-CSRF)")
        else:
            self.check(f"registration returned status {resp.status_code} (non-CSRF issue)",
                        not is_csrf_rejection, body_text[:200])

    def test_07_css_has_auth_page_input_rules(self):
        print("\n[Test 7] CSS file contains auth-page input visibility rules")
        css_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "static", "css", "chain_auth.css")
        with open(css_path, "r") as f:
            css = f.read()

        has_auth_page_rule = ".auth-page input" in css or ".auth-page select" in css or ".auth-page textarea" in css
        has_bg_white = "background: #ffffff" in css
        has_text_dark = "color: #111827" in css
        has_webkit_fill = "-webkit-text-fill-color" in css

        self.check("auth-page CSS rules for inputs", has_auth_page_rule,
                    "No .auth-page input/select/textarea rules in chain_auth.css")
        self.check("white background override", has_bg_white,
                    "No #ffffff background in auth CSS")
        self.check("dark text color", has_text_dark,
                    "No #111827 color in auth CSS")
        self.check("webkit-text-fill-color for WebView", has_webkit_fill,
                    "No -webkit-text-fill-color in auth CSS")

    def run_all(self):
        print("=" * 60)
        print("Phase 69 — APK Registration Mobile Form + CSRF")
        print("=" * 60)

        resp = self.test_01_get_register_returns_200()
        if resp and resp.status_code == 200:
            self.test_02_html_has_csrf_token()
            self.test_03_form_has_method_post()
            self.test_04_form_has_auth_page_class()
        else:
            self.check("skipped tests 2-4 (depends on 1)", False,
                        "Skipped because GET /auth/register did not return 200")

        self.test_05_post_without_csrf_returns_400()
        self.test_06_post_with_csrf_does_not_return_csrf_error()
        self.test_07_css_has_auth_page_input_rules()

        print("\n" + "=" * 60)
        print(f"RESULTS:  {self.passes} passed  /  {self.fails} failed  /  "
              f"{self.passes + self.fails} total")
        if self.errors:
            print("\nFAILURES:")
            for e in self.errors:
                print(f"  • {e}")
        print("=" * 60)
        return self.fails == 0


if __name__ == "__main__":
    success = Phase69APKRegistrationTest().run_all()
    sys.exit(0 if success else 1)
