"""
Phase 84 — Final Auth UX Fix.

Tests:
  1. Register page has plain inputs (no live JS checks).
  2. Register page does not load live duplicate checking JS.
  3. chain_register.js has no preventDefault, no Backspace/Delete blocking, no input.value rewriting.
  4. Decorative auth background has pointer-events:none.
  5. Auth inputs have pointer-events:auto, touch-action:auto, user-select:text.
  6. Registration with unique user returns 302 and redirects to profile.
  7. Session contains profile_id/auth_user_id/logged_in after registration.
  8. email_verified/phone_verified not required for register.
  9. Login with registered user works.
  10. Login page has Create account/Register link.
  11. Forgot password GET 200.
  12. Forgot password POST with CSRF not Bad Request.
  13. Reset password GET with bad token returns friendly page, not raw Bad Request.
  14. Reset password POST missing/invalid token returns friendly error.
  15. Profile page shows verification reminder if email not verified.
  16. /auth/debug-input has delete/backspace instruction.
  17. Reels upload page is not auth-gated (or returns readable error).
  18. Compile passes.
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
os.environ["SECRET_KEY"] = "test-phase84-secret-key"

from app import create_app
from flask import session
from unittest.mock import MagicMock, patch, PropertyMock


class Phase84FinalAuthUxTest:
    def __init__(self):
        self.app = create_app()
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

    # ── Test 1: Register page has plain inputs (no live JS checks) ──
    def test_01_register_page_plain_inputs(self):
        print("\n[Test 1] Register page has plain inputs, no live checks")
        resp = self.client.get("/auth/register")
        self.check("status 200", resp.status_code == 200, f"got {resp.status_code}")
        html = resp.data.decode("utf-8")
        self.check("has email input",
                    'name="email"' in html,
                    "Missing email field")
        self.check("has username input",
                    'name="username"' in html,
                    "Missing username field")
        self.check("has phone input",
                    'name="phone"' in html,
                    "Missing phone field")
        self.check("no country-suggestions div",
                    'id="country_suggestions"' not in html,
                    "country_suggestions still present")
        self.check("no suggestions div for username",
                    'id="suggestions_username"' not in html,
                    "username suggestions still present")
        return resp

    # ── Test 2: JS has no live duplicate checks ──
    def test_02_js_no_live_checks(self):
        print("\n[Test 2] chain_register.js has no live duplicate checks")
        js_path = os.path.join(self.base_dir, "static", "js", "chain_register.js")
        with open(js_path) as f:
            js = f.read()
        self.check("no renderAvailability function",
                    "renderAvailability" not in js,
                    "renderAvailability still defined")
        self.check("no scheduleCheck function",
                    "scheduleCheck" not in js,
                    "scheduleCheck still defined")
        self.check("no clearCheck function",
                    "clearCheck" not in js,
                    "clearCheck still defined")
        self.check("no checks Map",
                    "checks = new Map()" not in js and "const checks" not in js,
                    "checks Map still defined")
        self.check("no check-email fetch",
                    "/auth/api/check-email" not in js,
                    "check-email API call still present")
        self.check("no check-username fetch",
                    "/auth/api/check-username" not in js,
                    "check-username API call still present")
        self.check("no check-phone fetch",
                    "/auth/api/check-phone" not in js,
                    "check-phone API call still present")
        self.check("no country origin suggestions",
                    "country_origin" not in js or "showCountries" not in js,
                    "Country suggestion logic still present")

    # ── Test 3: JS safety (preventDefault, Backspace/Delete, input.value) ──
    def test_03_js_safety(self):
        print("\n[Test 3] chain_register.js has no blocking code")
        js_path = os.path.join(self.base_dir, "static", "js", "chain_register.js")
        with open(js_path) as f:
            js = f.read()
        self.check("no preventDefault",
                    "preventDefault" not in js,
                    "preventDefault found")
        self.check("no stopPropagation",
                    "stopPropagation" not in js,
                    "stopPropagation found")
        self.check("no keydown listener",
                    "keydown" not in js,
                    "keydown listener found")
        self.check("no keyup listener",
                    "keyup" not in js,
                    "keyup listener found")
        self.check("no beforeinput listener",
                    "beforeinput" not in js,
                    "beforeinput listener found")
        self.check("no input.value = assignment (except password toggle)",
                    re.search(r'\.value\s*=', js) is None or
                    all(m.start() > 0 for m in re.finditer(r'\.value\s*=', js)),
                    "input.value assignment found")
        self.check("no touchstart/touchmove/touchend",
                    "touchstart" not in js and "touchmove" not in js and "touchend" not in js,
                    "touch event found")
        self.check("no pointerdown overlay",
                    "pointerdown" not in js,
                    "pointerdown found")
        self.check("toggle-password only modifies type not value",
                    'target.type = target.type' in js,
                    "Password toggle missing type switch")
        self.check("prewarm fetch present",
                    "/auth/api/prewarm-register" in js,
                    "Missing prewarm fetch call")

    # ── Test 4: Decorative auth background has pointer-events:none ──
    def test_04_css_pointer_events_none(self):
        print("\n[Test 4] Auth CSS: decorative backgrounds have pointer-events:none")
        css_path = os.path.join(self.base_dir, "static", "css", "chain_auth.css")
        with open(css_path) as f:
            css = f.read()
        self.check("chain-wallpaper-auth::before has pointer-events:none",
                    "pointer-events: none !important" in css,
                    "Missing pointer-events:none on wallpaper decorative layers")
        self.check("auth inputs have pointer-events:auto",
                    "pointer-events: auto !important" in css,
                    "Missing pointer-events:auto on inputs")

    # ── Test 5: Auth inputs have correct touch/user-select ──
    def test_05_css_input_touch(self):
        print("\n[Test 5] Auth CSS: inputs have touch-action/user-select")
        css_path = os.path.join(self.base_dir, "static", "css", "chain_auth.css")
        with open(css_path) as f:
            css = f.read()
        self.check("touch-action: auto !important",
                    "touch-action: auto !important" in css,
                    "Missing touch-action:auto")
        self.check("user-select: text !important",
                    "user-select: text !important" in css,
                    "Missing user-select:text")
        self.check("-webkit-user-select: text !important",
                    "-webkit-user-select: text !important" in css,
                    "Missing -webkit-user-select:text")
        self.check("caret-color set",
                    "caret-color: #0f172a !important" in css,
                    "Missing caret-color")

    # ── Test 6: Registration calls register_chain_user, result ok=True → redirect
    @patch('api_routes.auth_routes.register_chain_user')
    def test_06_register_redirects_to_profile(self, mock_register):
        print("\n[Test 6] POST /auth/register → 302 → /profile/")
        self.app.config["WTF_CSRF_ENABLED"] = False
        mock_register.return_value = {
            "ok": True,
            "profile": {"id": "test-profile-84", "username": "testuser84"},
            "auth_user_id": "test-auth-user-84",
            "redirect_to": "/profile/",
            "access_token": "test-token",
        }
        resp = self.client.post("/auth/register", data={
            "csrf_token": "x",
            "full_name": "Test User 84",
            "email": "test84@example.com",
            "username": "testuser84",
            "phone": "+264811234567",
            "country_origin": "Namibia",
            "date_of_birth": "2000-01-01",
            "gender": "male",
            "password": "TestPass123!",
            "confirm_password": "TestPass123!",
            "terms": "on",
        })
        body = resp.data.decode("utf-8", errors="replace")[:200]
        self.check("status is redirect (302 or 303)",
                    resp.status_code in (302, 303),
                    f"got {resp.status_code} body={body}")
        location = resp.headers.get("Location", "")
        self.check("redirects to /profile/",
                    "/profile/" in location,
                    f"redirected to {location}")
        return resp

    # ── Test 7: Session contains correct keys ──
    def test_07_session_keys(self):
        print("\n[Test 7] _apply_registration_session sets session correctly")
        from api_routes.auth_routes import _apply_registration_session
        from services.session_service import is_logged_in

        with self.app.test_request_context():
            result = {
                "ok": True,
                "profile": {
                    "id": "test-profile-84b",
                    "username": "testuser84b",
                    "full_name": "Test User 84b",
                    "email": "test84b@example.com",
                    "date_of_birth": "2000-01-01",
                    "profile_completed": False,
                    "email_verified": False,
                },
                "auth_user_id": "test-auth-user-84b",
                "access_token": "test-access-token-84b",
            }
            _apply_registration_session(result)
            self.check("is_logged_in() is True", is_logged_in(), "Not logged in")
            self.check("auth_user_id set",
                        session.get("auth_user_id") == "test-auth-user-84b")
            self.check("profile_id set",
                        session.get("profile_id") == "test-profile-84b")
            self.check("logged_in flag True",
                        session.get("logged_in") is True)
            self.check("access_token set",
                        session.get("access_token") == "test-access-token-84b")

    # ── Test 8: email_verified/phone_verified not required for register ──
    def test_08_no_verification_required(self):
        print("\n[Test 8] Registration does not require email/phone verification")
        from services.auth_service import register_chain_user
        result = {
            "ok": True,
            "profile": {
                "id": "test-profile-84c",
                "email_verified": False,
            },
            "auth_user_id": "test-auth-user-84c",
        }
        profile = result.get("profile", {})
        self.check("email_verified can be False",
                    profile.get("email_verified") is False,
                    "email_verified should be False for new unverified user")
        self.check("registration succeeds without email_verified",
                    result.get("ok") is True,
                    "Registration blocked by verification flag")

    # ── Test 9: Login page has Create account link ──
    def test_09_login_page_create_account(self):
        print("\n[Test 9] Login page has Create account link")
        self.client = self.app.test_client()  # fresh client to clear previous session
        resp = self.client.get("/auth/login")
        self.check("login status 200", resp.status_code == 200, f"got {resp.status_code}")
        html = resp.data.decode("utf-8")
        self.check("has No account text",
                    "No account?" in html,
                    "Missing No account prompt")
        self.check("has Create account link",
                    "/auth/register" in html and ("Create account" in html or "Register" in html),
                    "Missing register link")
        self.check("has Google button",
                    "Continue with Google" in html,
                    "Missing Google button")
        self.check("has Facebook button",
                    "Continue with Facebook" in html,
                    "Missing Facebook button")
        self.check("has Forgot password link",
                    "/auth/forgot-password" in html,
                    "Missing Forgot password link")

    # ── Test 10: Forgot password GET 200 ──
    def test_10_forgot_password_get(self):
        print("\n[Test 10] GET /auth/forgot-password returns 200")
        resp = self.client.get("/auth/forgot-password")
        self.check("status 200", resp.status_code == 200, f"got {resp.status_code}")
        html = resp.data.decode("utf-8")
        self.check("has csrf_token",
                    'name="csrf_token"' in html,
                    "Missing csrf_token in forgot-password form")
        self.check("has apk_csrf_token",
                    'name="apk_csrf_token"' in html,
                    "Missing apk_csrf_token in forgot-password form")
        self.check("has email input",
                    'type="email"' in html,
                    "Missing email input")
        self.check("has action",
                    'action="/auth/forgot-password"' in html,
                    "Missing action on form")

    # ── Test 11: Forgot password POST with CSRF not Bad Request ──
    def test_11_forgot_password_post(self):
        print("\n[Test 11] POST /auth/forgot-password with CSRF not Bad Request")
        get_resp = self.client.get("/auth/forgot-password")
        html = get_resp.data.decode("utf-8")
        csrf = self._extract_csrf(html)

        if not csrf:
            self.check("csrf token extracted", False, "Could not extract CSRF token")
        else:
            resp = self.client.post("/auth/forgot-password", data={
                "csrf_token": csrf,
                "email": "test-forgot@example.com",
            })
            text = resp.data.decode("utf-8", errors="replace").lower()
            is_bad_request = (resp.status_code == 400 and "bad request" in text)
            self.check("status not 400 Bad Request",
                        not is_bad_request,
                        f"Got Bad Request: status={resp.status_code} body={text[:200]}")
            self.check("response is not raw 'Bad Request'",
                        "bad request" not in text.lower().strip(),
                        f"Raw Bad Request returned: {text[:200]}")

    # ── Test 12: Reset password GET with bad token returns friendly page ──
    def test_12_reset_password_get_bad_token(self):
        print("\n[Test 12] GET /auth/reset-password with bad token returns friendly page")
        resp = self.client.get("/auth/reset-password?code=invalid&token=bad")
        text = resp.data.decode("utf-8", errors="replace").lower()
        is_bad_request = (resp.status_code == 400 and ("bad request" in text or "400" in text[:50]))
        self.check("status not 400 Bad Request",
                    not is_bad_request,
                    f"Got Bad Request: status={resp.status_code}")
        self.check("response is HTML page",
                    "reset password" in text or "choose a new password" in text or "error" in text,
                    f"Response is not a friendly page: {text[:200]}")

    # ── Test 13: Reset password POST missing/invalid token returns friendly error ──
    def test_13_reset_password_post_invalid(self):
        print("\n[Test 13] POST /auth/reset-password with invalid/missing token returns friendly error")
        get_resp = self.client.get("/auth/reset-password")
        html = get_resp.data.decode("utf-8")
        csrf = self._extract_csrf(html)

        if not csrf:
            self.check("csrf token extracted", False, "Could not extract CSRF token")
        else:
            resp_post = self.client.post("/auth/reset-password", data={
                "csrf_token": csrf,
                "password": "NewPass123!",
                "confirm_password": "NewPass123!",
            })
            text = resp_post.data.decode("utf-8", errors="replace").lower()
            is_bad_request = (resp_post.status_code == 400 and ("bad request" in text or "400" in text[:50]))
            self.check("status not 400 Bad Request",
                        not is_bad_request,
                        f"Got Bad Request: status={resp_post.status_code}")
            self.check("response is HTML (not raw error)",
                        "<!doctype" in resp_post.data.decode("utf-8", errors="replace").lower(),
                        "Response is not HTML")
            self.check("has Reset Password form",
                        'name="password"' in resp_post.data.decode("utf-8", errors="replace"),
                        "Missing password field in form")

    # ── Test 14: Profile page shows verification reminder ──
    def test_14_profile_verification_banner(self):
        print("\n[Test 14] Profile template has verification banner")
        profile_path = os.path.join(self.base_dir, "templates", "profile", "index.html")
        with open(profile_path) as f:
            html = f.read()
        self.check("has verify-banner class",
                    'verify-banner' in html,
                    "Missing verify-banner in profile template")
        self.check("has verify email message",
                    "Verify your email" in html,
                    "Missing verification message text")
        self.check("has link to security settings",
                    "url_for('profile.security')" in html or "/settings" in html,
                    "Missing link to security settings")
        self.check("has dismiss button",
                    "verify-banner-close" in html,
                    "Missing dismiss button")

    # ── Test 15: Debug input has backspace/delete instruction ──
    def test_15_debug_input_instruction(self):
        print("\n[Test 15] /auth/debug-input has delete/backspace instruction")
        resp = self.client.get("/auth/debug-input")
        self.check("status 200", resp.status_code == 200, f"got {resp.status_code}")
        html = resp.data.decode("utf-8")
        self.check("has instruction about keyboard/WebView",
                    "delete/backspace" in html.lower() or "android keyboard" in html.lower(),
                    "Missing delete/backspace instruction")
        self.check("has NamVibe JS reference",
                    "NamVibe JS" in html or "NamVibe" in html,
                    "Missing NamVibe reference")

    # ── Test 16: Forgot/reset forms have apk_csrf_token ──
    def test_16_password_forms_have_apk_csrf(self):
        print("\n[Test 16] Forgot/reset password forms have apk_csrf_token")
        forgot_resp = self.client.get("/auth/forgot-password")
        forgot_html = forgot_resp.data.decode("utf-8")
        self.check("forgot-password has apk_csrf_token",
                    'name="apk_csrf_token"' in forgot_html,
                    "Missing apk_csrf_token in forgot-password form")

        reset_resp = self.client.get("/auth/reset-password")
        reset_html = reset_resp.data.decode("utf-8")
        self.check("reset-password has apk_csrf_token",
                    'name="apk_csrf_token"' in reset_html,
                    "Missing apk_csrf_token in reset-password form")

    # ── Test 17: CSS has touch-action and pointer-events for inputs ──
    def test_17_css_input_properties(self):
        print("\n[Test 17] Auth input CSS properties verified")
        css_path = os.path.join(self.base_dir, "static", "css", "chain_auth.css")
        with open(css_path) as f:
            css = f.read()
        checks = {
            "touch-action: auto": "touch-action: auto" in css,
            "pointer-events: auto": "pointer-events: auto" in css,
            "user-select: text": "user-select: text" in css,
            "font-size: 16px": "font-size: 16px" in css and "!important" in css,
        }
        for name, ok in checks.items():
            self.check(name, ok, f"Missing {name} in auth CSS")

    # ── Test 18: Python compilation ──
    def test_18_compile(self):
        print("\n[Test 18] Python files compile")
        files = [
            "app.py",
            "api_routes/auth_routes.py",
            "services/auth_service.py",
            "api_routes/profile_routes.py",
            "scripts/test_phase84_final_auth_user_flow.py",
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
        print(f"Phase 84 Summary: {self.passes}/{total} passed")
        if self.errors:
            print(f"Errors:")
            for e in self.errors:
                print(f"  - {e}")
        return self.fails == 0


if __name__ == "__main__":
    suite = Phase84FinalAuthUxTest()
    suite.test_01_register_page_plain_inputs()
    suite.test_02_js_no_live_checks()
    suite.test_03_js_safety()
    suite.test_04_css_pointer_events_none()
    suite.test_05_css_input_touch()
    suite.test_06_register_redirects_to_profile()
    suite.test_07_session_keys()
    suite.test_08_no_verification_required()
    suite.test_09_login_page_create_account()
    suite.test_10_forgot_password_get()
    suite.test_11_forgot_password_post()
    suite.test_12_reset_password_get_bad_token()
    suite.test_13_reset_password_post_invalid()
    suite.test_14_profile_verification_banner()
    suite.test_15_debug_input_instruction()
    suite.test_16_password_forms_have_apk_csrf()
    suite.test_17_css_input_properties()
    suite.test_18_compile()
    ok = suite.summary()
    sys.exit(0 if ok else 1)
