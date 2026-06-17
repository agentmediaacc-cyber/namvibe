#!/usr/bin/env python3
"""
PHASE 87 — REAL APK AUTH FLOW TESTS.

Tests real HTTP behavior against a running Flask server.

Usage:
    python3 scripts/test_phase87_real_apk_auth_flow.py
"""

import os
import re
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

BASE_URL = os.environ.get("DEBUG_BASE_URL", "http://127.0.0.1:5000")
TIMEOUT = 30


class Phase87RealApkAuthFlow:
    def __init__(self):
        self.errors = []
        self.passes = 0
        self.fails = 0
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.session = requests.Session()
        self.unique = str(uuid.uuid4())[:8]
        self.ts = int(time.time())

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

    def get(self, path):
        return self.session.get(f"{BASE_URL}{path}", timeout=TIMEOUT)

    def post(self, path, data, allow_redirects=True):
        return self.session.post(f"{BASE_URL}{path}", data=data,
                                 allow_redirects=allow_redirects,
                                 timeout=TIMEOUT)

    def extract_csrf(self, html, name="csrf_token"):
        m = re.search(r'name="' + name + r'"\s+value="([^"]+)"', html)
        return m.group(1) if m else None

    def extract_title(self, html):
        m = re.search(r'<title>([^<]+)</title>', html)
        return m.group(1) if m else "(no title)"

    def extract_js_urls(self, html):
        return re.findall(r'<script[^>]*src="([^"]+)"', html)

    def extract_error(self, html):
        m = re.search(r'class="chain-auth-alert chain-auth-alert--error">\s*(.*?)</div>', html, re.DOTALL)
        if m:
            text = re.sub(r'<[^<]+>', '', m.group(1)).strip()
            return text[:200]
        return None

    # ── Test 1: Served /auth/register loads only auth_minimal.js for auth JS ──
    def test_01_register_loads_auth_minimal_only(self):
        print("\n[Test 1] Register page loads only auth_minimal.js")
        resp = self.get("/auth/register")
        self.check("status 200", resp.status_code == 200, f"got {resp.status_code}")
        html = resp.text
        js_urls = self.extract_js_urls(html)
        auth_js = [j for j in js_urls if "auth" in j.lower()]
        non_auth_js = [j for j in js_urls if "auth" not in j.lower() and j.endswith(".js")]
        self.check("auth_minimal.js loaded",
                    any("auth_minimal.js" in j for j in js_urls),
                    "auth_minimal.js not found")
        self.check("chain_register.js NOT loaded",
                    all("chain_register.js" not in j for j in js_urls),
                    "chain_register.js still loaded")
        self.check("namvibe_mobile_nav.js NOT loaded",
                    all("namvibe_mobile_nav.js" not in j for j in js_urls),
                    "namvibe_mobile_nav.js still loaded")
        self.check("no non-auth JS loaded",
                    len(non_auth_js) == 0,
                    f"Found non-auth JS: {non_auth_js}")
        return resp

    # ── Test 2: Served auth_minimal.js has no forbidden terms ──
    def test_02_auth_minimal_no_forbidden(self):
        print("\n[Test 2] auth_minimal.js has no forbidden terms")
        resp = self.get("/static/js/auth_minimal.js")
        self.check("auth_minimal.js fetchable", resp.status_code == 200, f"got {resp.status_code}")
        if resp.status_code != 200:
            return
        js = resp.text
        forbidden = ["preventDefault", "stopPropagation", "keydown", "keyup",
                      "beforeinput", "touchstart", "touchmove", "touchend",
                      "pointerdown"]
        for term in forbidden:
            self.check(f"no '{term}' in auth_minimal.js",
                        term not in js,
                        f"Found forbidden term: {term}")
        self.check("password toggle present", "toggle-password" in js)
        self.check("submit handler present", "addEventListener('submit'" in js or 'addEventListener("submit"' in js)

    # ── Test 3: Register page has all-world country datalist, no JS overlay ──
    def test_03_country_datalist(self):
        print("\n[Test 3] Register page has world country datalist")
        resp = self.get("/auth/register")
        html = resp.text
        country_count = html.count("<option value=")
        self.check(f"at least 195 country options",
                    country_count >= 195,
                    f"Only {country_count} countries")
        self.check("Namibia in datalist",
                    '<option value="Namibia">' in html,
                    "Namibia missing from datalist")
        self.check("input has list=country-list",
                    'list="country-list"' in html,
                    "Missing list attribute on country input")
        self.check("no country_suggestions overlay",
                    'id="country_suggestions"' not in html,
                    "country_suggestions div still present")
        self.check("no suggestions_username div",
                    'id="suggestions_username"' not in html,
                    "suggestions_username still present")
        self.check("no availability hints",
                    'availability_email' not in html,
                    "availability hints still present")

    # ── Test 4: Create account real POST returns 302 to /profile/onboarding ──
    def test_04_real_register_redirects_onboarding(self):
        print("\n[Test 4] Real registration POST redirects to /profile/onboarding")
        # Fresh session for this test
        local_session = requests.Session()
        get_resp = local_session.get(f"{BASE_URL}/auth/register", timeout=TIMEOUT)
        self.check("GET register 200", get_resp.status_code == 200)
        csrf = self.extract_csrf(get_resp.text)
        apk_csrf = self.extract_csrf(get_resp.text, "apk_csrf_token")
        self.check("csrf_token exists", bool(csrf))
        self.check("apk_csrf_token exists", bool(apk_csrf))
        if not csrf:
            return
        unique_suffix = str(uuid.uuid4())[:8]
        email = f"test87_{int(time.time())}_{unique_suffix}@example.com"
        username = f"tester_{unique_suffix}"
        phone = f"+26481{int(time.time()) % 10000000:07d}"
        form = {
            "csrf_token": csrf,
            "apk_csrf_token": apk_csrf or "",
            "full_name": f"Test User {unique_suffix}",
            "email": email,
            "username": username,
            "phone": phone,
            "country_origin": "Namibia",
            "date_of_birth": "2000-01-01",
            "gender": "male",
            "password": "TestPass123!",
            "confirm_password": "TestPass123!",
            "terms": "on",
            "human_confirmed": "on",
            "profile_type": "member",
            "signup_method": "email",
        }
        post_resp = local_session.post(
            f"{BASE_URL}/auth/register",
            data=form,
            allow_redirects=False,
            timeout=TIMEOUT,
        )
        self.check("POST status 302",
                    post_resp.status_code in (302, 303),
                    f"got {post_resp.status_code}")
        if post_resp.status_code in (302, 303):
            location = post_resp.headers.get("Location", "")
            self.check("Location contains /profile/onboarding",
                        "/profile/onboarding" in location,
                        f"got {location}")
            # Follow redirect
            follow = local_session.get(f"{BASE_URL}{location}", allow_redirects=True, timeout=TIMEOUT)
            self.check("redirect not to /auth/login",
                        "/auth/login" not in follow.url,
                        f"Redirected to login: {follow.url}")
            self.check("final page is /profile/onboarding or /profile/",
                        "/profile/" in follow.url,
                        f"got {follow.url}")
            self.check("session cookie persists after redirect",
                        bool(dict(local_session.cookies).get("session")),
                        "session cookie missing after registration")

    # ── Test 5: Redirect does not go to /auth/login ──
    def test_05_no_redirect_to_login(self):
        print("\n[Test 5] Registration redirect does NOT go to login")
        local_session = requests.Session()
        get_resp = local_session.get(f"{BASE_URL}/auth/register", timeout=TIMEOUT)
        if get_resp.status_code != 200:
            return
        csrf = self.extract_csrf(get_resp.text)
        if not csrf:
            return
        unique_suffix = str(uuid.uuid4())[:8]
        form = {
            "csrf_token": csrf,
            "apk_csrf_token": self.extract_csrf(get_resp.text, "apk_csrf_token") or "",
            "full_name": f"Test Login Redirect {unique_suffix}",
            "email": f"test_no_login_{int(time.time())}_{unique_suffix}@example.com",
            "username": f"nologin_{unique_suffix}",
            "phone": f"+26481{int(time.time()) % 10000000:07d}",
            "country_origin": "Namibia",
            "date_of_birth": "2000-01-01",
            "gender": "male",
            "password": "TestPass123!",
            "confirm_password": "TestPass123!",
            "terms": "on",
            "human_confirmed": "on",
            "profile_type": "member",
            "signup_method": "email",
        }
        post_resp = local_session.post(
            f"{BASE_URL}/auth/register",
            data=form,
            allow_redirects=True,
            timeout=TIMEOUT,
        )
        self.check("POST redirect not to login",
                    "/auth/login" not in post_resp.url,
                    f"Redirected to login URL: {post_resp.url}")
        # Also check that the final page is profile
        self.check("final page is profile",
                    "/profile/" in post_resp.url,
                    f"Final URL: {post_resp.url}")

    # ── Test 6: Register failure keeps user on register page with error ──
    def test_06_register_failure_stays_on_register(self):
        print("\n[Test 6] Registration failure keeps user on register page with error")
        local_session = requests.Session()
        get_resp = local_session.get(f"{BASE_URL}/auth/register", timeout=TIMEOUT)
        if get_resp.status_code != 200:
            return
        csrf = self.extract_csrf(get_resp.text)
        if not csrf:
            return
        # Submit with missing required field (no email)
        form = {
            "csrf_token": csrf,
            "apk_csrf_token": self.extract_csrf(get_resp.text, "apk_csrf_token") or "",
            "full_name": "",
            "email": "",
            "username": "",
            "phone": "",
            "country_origin": "",
            "date_of_birth": "",
            "gender": "",
            "password": "",
            "confirm_password": "",
            "terms": "",
            "human_confirmed": "",
        }
        post_resp = local_session.post(
            f"{BASE_URL}/auth/register",
            data=form,
            allow_redirects=True,
            timeout=TIMEOUT,
        )
        self.check("error keeps on register page",
                    "/auth/register" in post_resp.url,
                    f"Final URL: {post_resp.url}")
        error = self.extract_error(post_resp.text)
        self.check("error message displayed",
                    bool(error),
                    "No error message found on re-rendered page")

    # ── Test 7: Forgot/reset pages not raw Bad Request ──
    def test_07_forgot_reset_no_bad_request(self):
        print("\n[Test 7] Forgot/reset pages do not return raw Bad Request")
        for path in ["/auth/forgot-password", "/auth/reset-password"]:
            resp = self.get(path)
            self.check(f"GET {path} returns 200",
                        resp.status_code == 200,
                        f"got {resp.status_code}")
            self.check(f"GET {path} not raw Bad Request",
                        "Bad Request" not in resp.text[:100],
                        "Raw 'Bad Request' in response")
        # POST to forgot-password with missing email
        local_session = requests.Session()
        get_resp = local_session.get(f"{BASE_URL}/auth/forgot-password", timeout=TIMEOUT)
        if get_resp.status_code == 200:
            csrf = self.extract_csrf(get_resp.text)
            if csrf:
                post_resp = local_session.post(
                    f"{BASE_URL}/auth/forgot-password",
                    data={"csrf_token": csrf, "email": ""},
                    allow_redirects=False,
                    timeout=TIMEOUT,
                )
                self.check("POST forgot-password no Bad Request",
                            "Bad Request" not in post_resp.text[:100] if post_resp.status_code == 200 else True,
                            "Raw 'Bad Request' in response")

    # ── Test 8: Login page also uses auth_minimal.js ──
    def test_08_login_uses_auth_minimal(self):
        print("\n[Test 8] Login page uses auth_minimal.js")
        resp = self.get("/auth/login")
        self.check("status 200", resp.status_code == 200)
        if resp.status_code == 200:
            self.check("auth_minimal.js loaded",
                        "auth_minimal.js" in resp.text,
                        "Missing auth_minimal.js on login page")
            self.check("no inline submit handler script",
                        not ('document.addEventListener' in resp.text and 'DOMContentLoaded' in resp.text),
                        "Inline DOMContentLoaded script still present")

    # ── Test 9: Forgot password page uses auth_minimal.js ──
    def test_09_forgot_uses_auth_minimal(self):
        print("\n[Test 9] Forgot password page uses auth_minimal.js")
        resp = self.get("/auth/forgot-password")
        self.check("status 200", resp.status_code == 200)
        if resp.status_code == 200:
            self.check("auth_minimal.js loaded",
                        "auth_minimal.js" in resp.text,
                        "Missing auth_minimal.js on forgot page")

    # ── Test 10: Compile check ──
    def test_10_compile_check(self):
        print("\n[Test 10] Python files compile")
        files = [
            "app.py",
            "api_routes/auth_routes.py",
            "services/auth_service.py",
            "services/country_service.py",
            "services/profile_service.py",
            "services/neon_service.py",
        ]
        for rel in files:
            path = os.path.join(self.base_dir, rel)
            try:
                compile(open(path).read(), path, "exec")
                self.check(f"{rel} compiles", True)
            except SyntaxError as e:
                self.check(f"{rel} compiles", False, str(e))

    def run_all(self):
        print("=" * 55)
        print("  PHASE 87 — REAL APK AUTH FLOW")
        print(f"  Target: {BASE_URL}")
        print("=" * 55)
        tests = [
            self.test_01_register_loads_auth_minimal_only,
            self.test_02_auth_minimal_no_forbidden,
            self.test_03_country_datalist,
            self.test_04_real_register_redirects_onboarding,
            self.test_05_no_redirect_to_login,
            self.test_06_register_failure_stays_on_register,
            self.test_07_forgot_reset_no_bad_request,
            self.test_08_login_uses_auth_minimal,
            self.test_09_forgot_uses_auth_minimal,
            self.test_10_compile_check,
        ]
        for test in tests:
            try:
                test()
            except requests.ConnectionError:
                print(f"  FAIL  Connection error — is the Flask server running on {BASE_URL}?")
                self.fails += 1
            except Exception as e:
                print(f"  FAIL  Test crashed: {e}")
                self.fails += 1
        print("\n" + "=" * 55)
        total = self.passes + self.fails
        print(f"  Phase 87 Summary: {self.passes}/{total} passed")
        if self.fails:
            print(f"  Failures: {self.fails}")
            for err in self.errors:
                print(f"    - {err}")
        print("=" * 55)
        return self.fails == 0


if __name__ == "__main__":
    suite = Phase87RealApkAuthFlow()
    success = suite.run_all()
    sys.exit(0 if success else 1)
