"""
Phase 81 — Post-Register Session + Mobile Reels CSRF + JS Keyboard Guards.

Tests:
  1. Register page renders (GET /auth/register).
  2. Login page has Create Account link/button.
  3. _apply_registration_session sets all is_logged_in() keys.
  4. Mocked registration → session set → profile redirect.
  5. Reels API endpoints are CSRF-exempt in app.py.
  6. reels.js keyboard handler guards against input interference.
  7. namvibe_2026_home.js keyboard handler guards against input interference.
  8. tiktok_home.js keyboard handler guards against input interference.
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
os.environ["CHAIN_DISABLE_RATE_LIMITS"] = "1"
os.environ["SECRET_KEY"] = "test-phase81-secret-key"

from app import create_app
from flask import session
from unittest.mock import MagicMock, patch


class Phase81PostRegisterMobileReelsTest:
    def __init__(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.errors = []
        self.passes = 0
        self.fails = 0
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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

    # ── Test 1: Register page renders ──
    def test_01_register_page_renders(self):
        print("\n[Test 1] GET /auth/register returns 200")
        resp = self.client.get("/auth/register")
        self.check("status 200", resp.status_code == 200, f"got {resp.status_code}")
        html = resp.data.decode("utf-8")
        self.check("has csrf_token", 'name="csrf_token"' in html, "Missing csrf_token field")
        self.check("has date_of_birth", 'name="date_of_birth"' in html, "Missing date_of_birth")
        self.check("has country_origin", 'name="country_origin"' in html, "Missing country_origin")
        self.check("has Create Account button",
                    bool(re.search(r'>Create Account</button>', html)),
                    "Missing Create Account button")
        return resp

    # ── Test 2: Login page Create Account link ──
    def test_02_login_page_create_account(self):
        print("\n[Test 2] Login page has Create Account link")
        resp = self.client.get("/auth/login")
        self.check("login page status 200", resp.status_code == 200, f"got {resp.status_code}")
        html = resp.data.decode("utf-8")
        has_create_link = bool(re.search(
            r'<a[^>]*href="/auth/register"[^>]*>Create account</a>', html
        ))
        self.check("link to /auth/register labeled Create account",
                    has_create_link, "No Create account link found on login page")
        has_register_btn = bool(re.search(
            r'chain-auth-register-btn', html
        ))
        self.check("prominent register button class present",
                    has_register_btn, "Missing chain-auth-register-btn class")

    # ── Test 3: Session keys ──
    def test_03_session_keys_set(self):
        print("\n[Test 3] _apply_registration_session keys match is_logged_in()")
        from api_routes.auth_routes import _apply_registration_session
        from services.session_service import is_logged_in

        with self.app.test_request_context():
            result = {
                "ok": True,
                "profile": {
                    "id": "test-profile-123",
                    "username": "testuser",
                    "full_name": "Test User",
                    "email": "test@example.com",
                    "date_of_birth": "2000-01-01",
                    "profile_completed": False,
                },
                "auth_user_id": "test-auth-user-456",
                "access_token": "test-access-token-789",
            }
            _apply_registration_session(result)
            logged_in = is_logged_in()
            self.check("is_logged_in() after _apply_registration_session", logged_in,
                        "is_logged_in() returned False after session keys were set")
            self.check("auth_user_id set",
                        session.get("auth_user_id") == "test-auth-user-456")
            self.check("profile_id set",
                        session.get("profile_id") == "test-profile-123")
            self.check("access_token set",
                        session.get("access_token") == "test-access-token-789")
            self.check("logged_in flag",
                        session.get("logged_in") is True)

    # ── Test 4: Mocked registration → session set → profile redirect ──
    @patch('services.auth_service.get_supabase')
    @patch('services.auth_service.safe_select')
    @patch('services.auth_service._supabase_auth_email_exists')
    @patch('services.profile_service.ensure_neon_profile')
    @patch('services.profile_service._neon_insert_profile')
    def test_04_mocked_register_redirects_to_profile(self, mock_neon_insert, mock_ensure, mock_exists_auth, mock_select, mock_supabase):
        print("\n[Test 4] Mocked registration → session → profile redirect")
        mock_select.return_value = []
        mock_neon_insert.return_value = None
        mock_exists_auth.return_value = False
        mock_profile = {
            "id": "test-profile-id",
            "auth_user_id": "test-auth-user-id",
            "username": "testreguser",
            "full_name": "Test Registration",
            "email": "testreg@example.com",
            "profile_completed": False,
            "date_of_birth": "2000-01-01",
        }
        mock_ensure.return_value = (mock_profile, None)
        mock_auth_res = MagicMock()
        mock_auth_res.user = MagicMock(id="test-auth-user-id", email="testreg@example.com",
                                        email_confirmed_at=None, confirmed_at=None)
        mock_auth_res.session = MagicMock(access_token="mock-access-token",
                                           refresh_token="mock-refresh-token")
        mock_supabase.return_value.auth.sign_up.return_value = mock_auth_res
        with self.app.test_request_context("/auth/register"):
            with patch('services.auth_service.table_exists', return_value=False):
                with patch('services.profile_service._neon_update_profile', return_value=mock_profile):
                    with patch('services.auth_service.write_query', return_value=[{"id": "test-profile-id"}]):
                        from services.auth_service import register_chain_user
                        ok_result = register_chain_user(
                            email="testreg@example.com",
                            password="TestPass123!",
                            username="testreguser",
                            full_name="Test Registration",
                            extra={
                                "terms_accepted": True,
                                "human_confirmed": True,
                                "date_of_birth": "2000-01-01",
                                "phone": "+264811234001",
                                "country_origin": "Testland",
                                "current_country": "Testland",
                                "country": "Testland",
                                "phone_code": "",
                                "region": "",
                                "town": "",
                                "profile_type": "member",
                                "profile_completed": False,
                            },
                        )
        self.check("registration ok", bool(ok_result.get("ok")),
                    f"Registration failed: {ok_result.get('error')}")
        profile = ok_result.get("profile") or {}
        self.check("profile has id", bool(profile.get("id")),
                    "Profile missing id in result")
        auth_user_id = ok_result.get("auth_user_id")
        self.check("auth_user_id present", bool(auth_user_id),
                    "auth_user_id missing in result")
        redirect_to = ok_result.get("redirect_to")
        self.check("redirect_to set", redirect_to == "/profile/",
                    f"Unexpected redirect: {redirect_to}")
        self.check("access_token in result",
                    bool(ok_result.get("access_token")),
                    "access_token missing from registration result")

    # ── Test 5: Reels CSRF exemptions ──
    def test_05_reels_csrf_exempt(self):
        print("\n[Test 5] Reels API endpoints are CSRF-exempt")
        app_path = os.path.join(self.base_dir, "app.py")
        with open(app_path) as f:
            content = f.read()
        endpoints = [
            "api_routes.reels_routes.api_view",
            "api_routes.reels_routes.api_like",
            "api_routes.reels_routes.api_comment",
            "api_routes.reels_routes.api_save",
            "api_routes.reels_routes.api_share",
            "api_routes.reels_routes.api_delete",
            "api_routes.reels_routes.api_event",
        ]
        for ep in endpoints:
            self.check(f"csrf.exempt({ep})", ep in content,
                        f"Missing csrf.exempt for {ep}")

    # ── Test 6: reels.js keyboard guard ──
    def test_06_reels_js_keyboard_guard(self):
        print("\n[Test 6] reels.js keyboard handler guards input")
        js_path = os.path.join(self.base_dir, "static", "js", "reels.js")
        with open(js_path) as f:
            js = f.read()
        has_guard = "tagName || ''" in js and ("e.key === 'ArrowDown'" in js or "e.key === 'ArrowUp'" in js)
        self.check("reels.js guard present", has_guard,
                    "reels.js missing input guard before keyboard shortcuts")

    # ── Test 7: namvibe_2026_home.js keyboard guard ──
    def test_07_namvibe_home_js_keyboard_guard(self):
        print("\n[Test 7] namvibe_2026_home.js keyboard handler guards input")
        js_path = os.path.join(self.base_dir, "static", "js", "namvibe_2026_home.js")
        with open(js_path) as f:
            js = f.read()
        has_guard = "tagName || ''" in js and ("e.key === 'ArrowDown'" in js or "e.key === 'ArrowUp'" in js)
        self.check("namvibe_2026_home.js guard present", has_guard,
                    "namvibe_2026_home.js missing input guard")

    # ── Test 8: tiktok_home.js keyboard guard ──
    def test_08_tiktok_home_js_keyboard_guard(self):
        print("\n[Test 8] tiktok_home.js keyboard handler guards input")
        js_path = os.path.join(self.base_dir, "static", "js", "tiktok_home.js")
        with open(js_path) as f:
            js = f.read()
        has_guard = "tagName || ''" in js and ("e.key === 'ArrowDown'" in js or "e.key === 'ArrowUp'" in js)
        self.check("tiktok_home.js guard present", has_guard,
                    "tiktok_home.js missing input guard")

    # ── Test 9: Login page prominent register call-to-action ──
    def test_09_login_page_no_account_prompt(self):
        print("\n[Test 9] Login page has 'No account?' prompt")
        resp = self.client.get("/auth/login")
        html = resp.data.decode("utf-8")
        has_no_account = "No account?" in html
        has_create_link = bool(re.search(
            r'<a[^>]*href="/auth/register"[^>]*>Create account</a>', html
        ))
        self.check("No account? text present", has_no_account,
                    "Missing 'No account?' prompt on login page")
        self.check("Create account link present", has_create_link,
                    "Missing Create account link on login page")

    # ── Test 10: codebase compile check ──
    def test_10_compile_check(self):
        print("\n[Test 10] Python syntax validation")
        import py_compile
        files_to_check = [
            "app.py",
            "api_routes/auth_routes.py",
            "services/auth_service.py",
            "services/session_service.py",
            "static/js/reels.js",
            "static/js/namvibe_2026_home.js",
            "static/js/tiktok_home.js",
        ]
        for rel_path in files_to_check:
            full_path = os.path.join(self.base_dir, rel_path)
            if full_path.endswith(".py"):
                try:
                    py_compile.compile(full_path, doraise=True)
                    self.check(f"{rel_path} compiles", True)
                except py_compile.PyCompileError as e:
                    self.check(f"{rel_path} compiles", False, str(e))

    def run_all(self):
        print("=" * 60)
        print("Phase 81 — Post-Register Session + Mobile Reels")
        print("=" * 60)

        self.test_01_register_page_renders()
        self.test_02_login_page_create_account()
        self.test_03_session_keys_set()
        self.test_04_mocked_register_redirects_to_profile()
        self.test_05_reels_csrf_exempt()
        self.test_06_reels_js_keyboard_guard()
        self.test_07_namvibe_home_js_keyboard_guard()
        self.test_08_tiktok_home_js_keyboard_guard()
        self.test_09_login_page_no_account_prompt()
        self.test_10_compile_check()

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
    success = Phase81PostRegisterMobileReelsTest().run_all()
    sys.exit(0 if success else 1)
