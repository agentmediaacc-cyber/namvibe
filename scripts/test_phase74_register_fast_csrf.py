"""
Phase 74 — Fix Registration Speed, Country Search, and CSRF Bad Request.

Tests:
1. GET /auth/register returns 200.
2. No old 7-step wizard text.
3. country_origin is plain text input (not select, not heavy datalist).
4. No huge country option list (>15 options).
5. Create Account button exists and not hidden.
6. date_of_birth field exists.
7. Form method POST, action /auth/register.
8. csrf_token hidden input exists.
9. POST without CSRF returns 400 (CSRF error).
10. POST with CSRF does NOT return CSRF missing/session token missing.
11. HTML does NOT contain fetch submit hijack for /auth/register.
12. chain_register.js does NOT contain fetch("/auth/register").
13. chain_register.js does NOT prevent normal form submit (no validateSubmit blocking).
14. chain_register.js does NOT reference CHAIN_LOCATIONS or window.CHAIN_LOCATIONS.
15. CSS readable input rules exist (Phase 73 date + Phase 72 OAuth).
16. Response has no-cache headers.
17. Country input allows delete/correct (is text input, not select).
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
os.environ["SECRET_KEY"] = "test-secret-key-for-phase74"

from app import create_app


class Phase74RegisterFastCSRFTest:
    def __init__(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.errors = []
        self.passes = 0
        self.fails = 0

    def _fresh_html(self, url="/auth/register"):
        fresh = self.app.test_client()
        resp = fresh.get(url)
        return fresh, resp

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
        print("\n[Test 2] No old 7-step wizard text")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        forbidden = [
            "Step 1 of 7", "Your account starts here",
            "chain-register-progress-text", "chain-auth-step-label",
            "data-step=", "chain-register-stepper", "step-dot",
        ]
        for phrase in forbidden:
            self.check(f"no '{phrase}'", phrase not in html, f"Found forbidden: {phrase}")
        return html

    def test_03_country_is_text_input(self):
        print("\n[Test 3] country_origin is text input (not select, not heavy list)")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        # Must be type="text" not type="select" or large datalist
        self.check("type=text country input",
                   bool(re.search(r'<input[^>]*name="country_origin"[^>]*type="text"', html) or
                          re.search(r'<input[^>]*type="text"[^>]*name="country_origin"', html)),
                   "country_origin is NOT a text input")
        self.check("no select[name=country_origin]",
                   not bool(re.search(r'<select[^>]*name="country_origin"', html)),
                   "country_origin IS a select (should be text)")
        # Count datalist options in country-list if present
        options_count = len(re.findall(r'<option\s+value="[^"]*">', html))
        self.check("total option tags <= 15 (fast)",
                   options_count <= 15,
                   f"Too many option tags: {options_count}")

    def test_04_country_deletable(self):
        print("\n[Test 4] Country input allows delete/correct (is free text)")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        # Free text input without locked pattern or forced value
        has_pattern = bool(re.search(r'name="country_origin"[^>]*pattern', html) or
                           re.search(r'pattern[^>]*name="country_origin"', html))
        has_required = bool(re.search(r'name="country_origin"[^>]*\brequired\b', html) or
                            re.search(r'\brequired\b[^>]*name="country_origin"', html))
        self.check("no locked pattern on country", not has_pattern,
                   "country_origin has pattern attribute (would block free text)")
        self.check("country input has required flag", has_required,
                   "country_origin missing required attribute")

    def test_05_create_account_button(self):
        print("\n[Test 5] Create Account button exists and visible")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        self.check("button with 'Create Account' text",
                   bool(re.search(r'>Create Account</button>', html)),
                   "Create Account button missing")
        css_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "css", "chain_auth.css"
        )
        with open(css_path) as f:
            css = f.read()
        hidden_rule = bool(re.search(r'#register_submit\s*\{[^}]*display:\s*none', css))
        self.check("button not hidden by CSS", not hidden_rule,
                   "register_submit still has display:none in CSS")

    def test_06_dob_field(self):
        print("\n[Test 6] date_of_birth field exists")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        self.check("input[name=date_of_birth] exists",
                   bool(re.search(r'name="date_of_birth"', html)),
                   "Missing date_of_birth field")

    def test_07_form_method_action(self):
        print("\n[Test 7] Form method POST, action /auth/register")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        self.check("method=POST",
                   bool(re.search(r'<form[^>]*method="POST"', html)),
                   "Form method not POST")
        self.check("action=/auth/register",
                   bool(re.search(r'action="/auth/register"', html)),
                   "Form action not /auth/register")
        self.check("autocomplete=on",
                   bool(re.search(r'autocomplete="on"', html)),
                   "Form missing autocomplete=on")

    def test_08_csrf_token(self):
        print("\n[Test 8] csrf_token hidden input exists")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        self.check("csrf_token input",
                   bool(re.search(r'name="csrf_token"', html)),
                   "Missing csrf_token field")
        self.check("meta csrf-token",
                   bool(re.search(r'<meta\s+name="csrf-token"', html)),
                   "Missing meta csrf-token tag")

    def test_09_post_without_csrf(self):
        print("\n[Test 9] POST without CSRF returns 400")
        resp = self.client.post("/auth/register", data={
            "full_name": "No CSRF",
            "email": "nocsrf@test.com",
        })
        self.check("CSRF error (400 or CSRF text)",
                   resp.status_code == 400 or b"csrf" in resp.data.lower(),
                   f"Expected CSRF error, got {resp.status_code}")

    def test_10_post_with_csrf(self):
        print("\n[Test 10] POST with CSRF does NOT return CSRF error")
        get_resp = self.client.get("/auth/register")
        html = get_resp.data.decode("utf-8")
        csrf_token = self._extract_csrf(html)
        if not csrf_token:
            self.check("csrf extracted", False, "Could not extract CSRF token")
            return

        resp = self.client.post("/auth/register", data={
            "csrf_token": csrf_token,
            "full_name": "Test User",
            "email": "testcsrf@example.com",
            "username": "testcsrf",
            "phone": "+264811234555",
            "country_origin": "Namibia",
            "date_of_birth": "2000-01-15",
            "gender": "male",
            "password": "TestPass123!",
            "confirm_password": "TestPass123!",
            "terms": "on",
        })
        body = resp.data.decode("utf-8").lower()
        is_csrf_specific = (
            "the csrf token is missing" in body
            or "the csrf token has expired" in body
            or "csrf session token" in body
            or "session token missing" in body
        )
        is_csrf_rejection = is_csrf_specific and resp.status_code == 400
        self.check("not CSRF rejection", not is_csrf_rejection,
                   f"Got CSRF rejection with token: {resp.data[:200]}")
        self.check("acceptable (200 or 302)",
                   resp.status_code in (200, 302),
                   f"Unexpected status {resp.status_code}")

    def test_11_no_fetch_hijack(self):
        print("\n[Test 11] HTML does NOT contain fetch submit hijack for /auth/register")
        _, resp = self._fresh_html()
        html = resp.data.decode("utf-8")
        # Check no inline JS that fetches /auth/register
        fetch_register = bool(re.search(r'fetch\s*\(\s*["\']/auth/register', html))
        hijack = bool(re.search(r'preventDefault|return\s+false', html) and 'submit' in html.lower())
        self.check("no fetch('/auth/register') in HTML", not fetch_register,
                   "Found fetch('/auth/register') in HTML")
        self.check("submit not hijacked in inline HTML",
                    not (hijack and bool(re.search(r'submit', html.lower()))),
                    "Submit might be hijacked in inline HTML")

    def test_12_js_no_fetch_register(self):
        print("\n[Test 12] chain_register.js does NOT contain fetch('/auth/register')")
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "js", "chain_register.js"
        )
        with open(js_path) as f:
            js = f.read()
        self.check("no fetch('/auth/register')",
                   'fetch("/auth/register")' not in js and "fetch('/auth/register')" not in js,
                   "chain_register.js contains fetch('/auth/register')")

    def test_13_js_no_submit_block(self):
        print("\n[Test 13] chain_register.js does NOT prevent normal form submit")
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "js", "chain_register.js"
        )
        with open(js_path) as f:
            js = f.read()
        # Should NOT contain preventDefault, validateSubmit blocking, or return false
        has_prevent = "preventDefault" in js
        has_validatesubmit = "validateSubmit" in js
        has_return_false = bool(re.search(r'onsubmit\s*=\s*"return false"', js))
        self.check("no preventDefault in JS", not has_prevent,
                   "chain_register.js has preventDefault (blocks submit)")
        self.check("no validateSubmit blocking", not has_validatesubmit,
                   "chain_register.js has validateSubmit function (may block submit)")

    def test_14_js_no_country_library(self):
        print("\n[Test 14] chain_register.js does NOT reference CHAIN_LOCATIONS")
        js_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "js", "chain_register.js"
        )
        with open(js_path) as f:
            js = f.read()
        self.check("no CHAIN_LOCATIONS in JS",
                   "CHAIN_LOCATIONS" not in js and "chain_locations" not in js.lower(),
                   "chain_register.js still references CHAIN_LOCATIONS")
        self.check("no chain_locations.js script in HTML",
                   'chain_locations.js' not in open(
                       os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "templates", "auth", "register.html")
                   ).read(),
                   "register.html still loads chain_locations.js")

    def test_15_css_readable_rules(self):
        print("\n[Test 15] CSS readable input rules exist")
        css_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "css", "chain_auth.css"
        )
        with open(css_path) as f:
            css = f.read()
        self.check("date input CSS exists",
                   "input[type=\"date\"]" in css,
                   "Missing input[type=date] CSS rule")
        self.check("date white bg",
                   "background: #ffffff" in css,
                   "Missing white background for date")
        self.check("calendar picker indicator",
                   "calendar-picker-indicator" in css,
                   "Missing calendar picker indicator")
        self.check("register OAuth button CSS",
                   ".register-card .chain-auth-oauth" in css,
                   "Missing register OAuth button CSS")

    def test_16_no_cache_headers(self):
        print("\n[Test 16] Auth routes have no-cache headers")
        _, resp = self._fresh_html()
        cache_ctrl = resp.headers.get("Cache-Control", "")
        pragma = resp.headers.get("Pragma", "")
        self.check("Cache-Control contains no-store",
                   "no-store" in cache_ctrl,
                   f"Missing no-store: {cache_ctrl}")
        self.check("Pragma: no-cache",
                   "no-cache" in pragma,
                   f"Missing Pragma: {pragma}")

    def test_17_required_fields_all_present(self):
        print("\n[Test 17] All 11 required fields present")
        _, resp = self._fresh_html()
        html = resp.data.decode("utf-8")
        fields = [
            "full_name", "email", "username", "phone",
            "country_origin", "date_of_birth", "gender",
            "password", "confirm_password", "terms",
        ]
        for field in fields:
            self.check(f"field '{field}' present",
                       bool(re.search(r'name="' + re.escape(field) + r'"', html)),
                       f"Missing field: {field}")
        # Also check button
        self.check("Create Account button text",
                   bool(re.search(r'Create Account', html)),
                   "Button text not found")

    def run_all(self):
        print("=" * 60)
        print("Phase 74 — Fix Registration Speed, Country, CSRF")
        print("=" * 60)

        self.test_01_page_returns_200()
        self.test_02_no_old_wizard()
        self.test_03_country_is_text_input()
        self.test_04_country_deletable()
        self.test_05_create_account_button()
        self.test_06_dob_field()
        self.test_07_form_method_action()
        self.test_08_csrf_token()
        self.test_09_post_without_csrf()
        self.test_10_post_with_csrf()
        self.test_11_no_fetch_hijack()
        self.test_12_js_no_fetch_register()
        self.test_13_js_no_submit_block()
        self.test_14_js_no_country_library()
        self.test_15_css_readable_rules()
        self.test_16_no_cache_headers()
        self.test_17_required_fields_all_present()

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
    success = Phase74RegisterFastCSRFTest().run_all()
    sys.exit(0 if success else 1)
