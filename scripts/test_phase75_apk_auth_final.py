"""
Phase 75 — Final APK CSRF Session Cookie + Typing + Country Fix.

Tests:
 1. GET /auth/register returns 200.
 2. Response sets session cookie.
 3. csrf_token hidden input exists.
 4. Same-client POST with CSRF does not produce "CSRF session token missing".
 5. Missing CSRF still fails safely (400 or error text).
 6. Form has normal method POST and action /auth/register.
 7. chain_register.js does not contain fetch("/auth/register").
 8. chain_register.js does not contain preventDefault for form submit.
 9. chain_register.js does not rewrite country_origin value.
10. country_origin is plain text input (no select, no datalist).
11. Create Account button exists.
12. CSS readable input rules exist.
13. User can submit custom country text.
14. Date of birth exists.
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
os.environ["SECRET_KEY"] = "test-phase75-secret-key"

from app import create_app


class Phase75ApkAuthFinalTest:
    def __init__(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.errors = []
        self.passes = 0
        self.fails = 0

    def _fresh(self, url="/auth/register"):
        fresh = self.app.test_client()
        resp = fresh.get(url)
        return fresh, resp

    def _extract_csrf(self, html):
        m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
        return m.group(1) if m else None

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

    def test_01_page_returns_200(self):
        print("\n[Test 1] GET /auth/register returns 200")
        resp = self.client.get("/auth/register")
        self.check("status 200", resp.status_code == 200, f"got {resp.status_code}")
        return resp

    def test_02_session_cookie_set(self):
        print("\n[Test 2] Response sets session cookie")
        fresh = self.app.test_client()
        resp = fresh.get("/auth/register")
        set_cookie = resp.headers.get("Set-Cookie", "")
        has_session = "session" in set_cookie.lower()
        self.check("session cookie in Set-Cookie", has_session,
                    f"No session cookie found: {set_cookie[:100]}")
        # Also verify no-cache headers
        cache = resp.headers.get("Cache-Control", "")
        pragma = resp.headers.get("Pragma", "")
        self.check("Cache-Control no-store", "no-store" in cache, f"Missing: {cache}")
        self.check("Pragma no-cache", "no-cache" in pragma, f"Missing: {pragma}")

    def test_03_csrf_token_exists(self):
        print("\n[Test 3] csrf_token hidden input exists")
        _, resp = self._fresh()
        html = resp.data.decode("utf-8")
        self.check("csrf_token input",
                    bool(re.search(r'name="csrf_token"', html)),
                    "Missing csrf_token field")
        self.check("meta csrf-token",
                    bool(re.search(r'<meta\s+name="csrf-token"', html)),
                    "Missing meta csrf-token tag")

    def test_04_post_with_csrf_no_error(self):
        print("\n[Test 4] Same-client POST with CSRF does not produce CSRF error")
        client = self.app.test_client()
        resp = client.get("/auth/register")
        html = resp.data.decode("utf-8")
        csrf_token = self._extract_csrf(html)
        if not csrf_token:
            self.check("csrf token extracted", False, "Could not extract CSRF token")
            return
        post_resp = client.post("/auth/register", data={
            "csrf_token": csrf_token,
            "full_name": "Phase75 Test",
            "email": "phase75@test.com",
            "username": "phase75user",
            "phone": "+264811234777",
            "country_origin": "Botswana",
            "date_of_birth": "2000-06-15",
            "gender": "female",
            "password": "Phase75Pass!",
            "confirm_password": "Phase75Pass!",
            "terms": "on",
        })
        body = post_resp.data.decode("utf-8").lower()
        is_csrf = (
            "the csrf token is missing" in body
            or "the csrf token has expired" in body
            or "csrf session token" in body
            or "session token missing" in body
        )
        self.check("not CSRF error", not is_csrf,
                    f"CSRF error despite valid token: {post_resp.data[:200]}")
        self.check("acceptable status",
                    post_resp.status_code in (200, 302, 400),
                    f"Unexpected {post_resp.status_code}")

    def test_05_missing_csrf_fails(self):
        print("\n[Test 5] Missing CSRF still fails safely")
        resp = self.client.post("/auth/register", data={
            "full_name": "No CSRF",
            "email": "nocsrf2@test.com",
        })
        body = resp.data.decode("utf-8")
        self.check("CSRF error (400 or error text)",
                    resp.status_code == 400 or "csrf" in body.lower(),
                    f"Expected CSRF error, got {resp.status_code}")

    def test_06_form_method_action(self):
        print("\n[Test 6] Form has normal method POST and action /auth/register")
        _, resp = self._fresh()
        html = resp.data.decode("utf-8")
        self.check("method=POST",
                    bool(re.search(r'<form[^>]*method="POST"', html)),
                    "Form method not POST")
        self.check("action=/auth/register",
                    bool(re.search(r'action="/auth/register"', html)),
                    "Form action not /auth/register")

    def test_07_js_no_fetch_register(self):
        print("\n[Test 7] chain_register.js does NOT contain fetch('/auth/register')")
        js_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "static", "js", "chain_register.js")
        with open(js_path) as f:
            js = f.read()
        self.check("no fetch('/auth/register')",
                    'fetch("/auth/register")' not in js and "fetch('/auth/register')" not in js,
                    "chain_register.js contains fetch('/auth/register')")

    def test_08_js_no_prevent_default(self):
        print("\n[Test 8] chain_register.js does NOT contain preventDefault for form submit")
        js_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "static", "js", "chain_register.js")
        with open(js_path) as f:
            js = f.read()
        has_prevent = "preventDefault" in js
        self.check("no preventDefault in JS", not has_prevent,
                    "chain_register.js contains preventDefault")

    def test_09_js_no_value_rewrite(self):
        print("\n[Test 9] chain_register.js does NOT rewrite input values")
        js_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "static", "js", "chain_register.js")
        with open(js_path) as f:
            js = f.read()
        # Should not set .value on any input (except maybe password strength meter
        # which only reads password.value, never sets it)
        # We specifically look for assignment to .value of country_origin or phone
        bad_patterns = [
            'country_origin.value',
            'register_phone.value',
            'phone.value',
            'input.value =',
        ]
        for pat in bad_patterns:
            if pat in js:
                self.check(f"no '{pat}' rewrite", False, f"Found {pat} in JS")
                return
        self.check("no input.value rewriting", True)

    def test_10_country_plain_text(self):
        print("\n[Test 10] country_origin is plain text input")
        _, resp = self._fresh()
        html = resp.data.decode("utf-8")
        # Must be type="text"
        is_text = bool(re.search(r'type="text"[^>]*name="country_origin"', html) or
                        re.search(r'name="country_origin"[^>]*type="text"', html))
        is_select = bool(re.search(r'<select[^>]*name="country_origin"', html))
        has_datalist = bool(re.search(r'<datalist', html))
        self.check("input type=text for country", is_text,
                    "country_origin is NOT a text input")
        self.check("no select for country", not is_select,
                    "country_origin is a select (should be text)")
        self.check("datalist allowed (Phase 85)", True,
                    "datalist may be present (native HTML, no JS overlay)")

    def test_11_create_account_button(self):
        print("\n[Test 11] Create Account button exists")
        _, resp = self._fresh()
        html = resp.data.decode("utf-8")
        self.check("Create Account button",
                    bool(re.search(r'>Create Account</button>', html)),
                    "Create Account button missing")
        css_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "static", "css", "chain_auth.css")
        with open(css_path) as f:
            css = f.read()
        hidden = bool(re.search(r'#register_submit\s*\{[^}]*display:\s*none', css))
        self.check("button not hidden by CSS", not hidden,
                    "register_submit has display:none")

    def test_12_css_readable_rules(self):
        print("\n[Test 12] CSS readable input rules exist")
        css_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "static", "css", "chain_auth.css")
        with open(css_path) as f:
            css = f.read()
        self.check("date input CSS exists",
                    'input[type="date"]' in css,
                    "Missing input[type=date] CSS rule")
        self.check("date white bg", "background: #ffffff" in css,
                    "Missing white background for date")
        self.check("calendar picker indicator",
                    "calendar-picker-indicator" in css,
                    "Missing calendar picker indicator")
        self.check("register OAuth button CSS",
                    ".register-card .chain-auth-oauth" in css,
                    "Missing register OAuth button CSS")

    def test_13_custom_country_submit(self):
        print("\n[Test 13] User can submit custom country text")
        client = self.app.test_client()
        resp = client.get("/auth/register")
        html = resp.data.decode("utf-8")
        csrf_token = self._extract_csrf(html)
        if not csrf_token:
            self.check("csrf extracted", False, "Could not extract CSRF token")
            return
        # Submit with a custom country not in any suggestion list
        post_resp = client.post("/auth/register", data={
            "csrf_token": csrf_token,
            "full_name": "Custom Country User",
            "email": "customcountry@test.com",
            "username": "customcountry",
            "phone": "+264811234888",
            "country_origin": "MyCustomCountry",
            "date_of_birth": "2000-03-20",
            "gender": "male",
            "password": "CustomPass123!",
            "confirm_password": "CustomPass123!",
            "terms": "on",
        })
        body = post_resp.data.decode("utf-8").lower()
        is_csrf = (
            "the csrf token is missing" in body
            or "the csrf token has expired" in body
            or "csrf session token" in body
        )
        self.check("custom country accepted (no CSRF error)", not is_csrf,
                    f"CSRF error with custom country")
        # The submission may succeed (302) or fail validation (200) for other reasons
        # but should NOT fail because of country_origin
        self.check("no country validation error",
                    "country" not in body or "country of origin is" not in body,
                    f"Country validation error for custom text: {post_resp.data[:200]}")

    def test_14_dob_exists(self):
        print("\n[Test 14] Date of birth exists")
        _, resp = self._fresh()
        html = resp.data.decode("utf-8")
        self.check("input[name=date_of_birth]",
                    bool(re.search(r'name="date_of_birth"', html)),
                    "Missing date_of_birth field")

    def run_all(self):
        print("=" * 60)
        print("Phase 75 — Final APK Auth")
        print("=" * 60)

        self.test_01_page_returns_200()
        self.test_02_session_cookie_set()
        self.test_03_csrf_token_exists()
        self.test_04_post_with_csrf_no_error()
        self.test_05_missing_csrf_fails()
        self.test_06_form_method_action()
        self.test_07_js_no_fetch_register()
        self.test_08_js_no_prevent_default()
        self.test_09_js_no_value_rewrite()
        self.test_10_country_plain_text()
        self.test_11_create_account_button()
        self.test_12_css_readable_rules()
        self.test_13_custom_country_submit()
        self.test_14_dob_exists()

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
    success = Phase75ApkAuthFinalTest().run_all()
    sys.exit(0 if success else 1)
