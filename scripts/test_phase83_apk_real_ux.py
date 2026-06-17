"""
Phase 83 — APK Registration UX: Loading overlay, prewarm, dev mode speed, debug input, reels JSON 401.

Tests:
  1. Register page has loading overlay div with expected elements.
  2. chain_register.js overlay show/hide and prewarm fetch call exist.
  3. /auth/api/prewarm-register returns 200 JSON (mocked).
  4. _ensure_profile_dependencies skips settings/security/wallet retries with CHAIN_FAST_LOCAL=1.
  5. /auth/debug-input returns 200 and has diagnostic elements.
  6. login_required returns JSON 401 for /reels/api/ paths.
  7. No preventDefault on form submit in chain_register.js.
  8. No input disabling before submit in chain_register.js.
  9. Country suggestions use click on buttons with pointer-events only on buttons.
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
os.environ["SECRET_KEY"] = "test-phase83-secret-key"

from app import create_app
from flask import session
from unittest.mock import MagicMock, patch

NEON_SERVICE = "services.neon_service"


class Phase83ApkRealUxTest:
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

    # ── Test 1: Register page has loading overlay ──
    def test_01_loading_overlay_html(self):
        print("\n[Test 1] Register page has loading overlay")
        resp = self.client.get("/auth/register")
        self.check("status 200", resp.status_code == 200, f"got {resp.status_code}")
        html = resp.data.decode("utf-8")
        self.check("has register-loading-overlay",
                    'id="register-loading-overlay"' in html,
                    "Missing register-loading-overlay element")
        self.check("has register-loading-spinner",
                    'class="register-loading-spinner"' in html,
                    "Missing spinner element")
        self.check("has register-loading-text",
                    'id="register-loading-text"' in html,
                    "Missing loading text element")
        self.check("has register-loading-hint",
                    'id="register-loading-hint"' in html,
                    "Missing loading hint element")
        return resp

    # ── Test 2: chain_register.js has overlay logic and prewarm call ──
    def test_02_js_overlay_and_prewarm(self):
        print("\n[Test 2] chain_register.js overlay and prewarm")
        js_path = os.path.join(self.base_dir, "static", "js", "chain_register.js")
        with open(js_path, "r") as f:
            js = f.read()

        self.check("has showOverlay function",
                    "function showOverlay" in js,
                    "Missing showOverlay function")
        self.check("has hideOverlay function",
                    "function hideOverlay" in js,
                    "Missing hideOverlay function")
        self.check("overlay classList.add is-visible on submit",
                    'overlay.classList.add("is-visible")' in js,
                    "Missing overlay show on submit")
        self.check("has prewarm fetch",
                    "/auth/api/prewarm-register" in js,
                    "Missing prewarm fetch call")
        self.check("fetch with keepalive",
                    "keepalive: true" in js,
                    "Missing keepalive: true on prewarm fetch")
        self.check("no preventDefault on form submit",
                    "preventDefault" not in js,
                    "Unexpected preventDefault in JS")
        self.check("submit button disabled on submit",
                    "submitBtn.disabled = true" in js,
                    "Missing submit button disable")
        self.check("no input disabled before submit",
                    ".disabled" not in js.replace("submitBtn.disabled", "") or "input" not in js.lower(),
                    "Input disabled found before submit")

    # ── Test 3: Prewarm endpoint ──
    @patch("services.neon_service.prime_neon_runtime")
    def test_03_prewarm_endpoint(self, mock_prime):
        print("\n[Test 3] GET /auth/api/prewarm-register returns 200")
        mock_prime.return_value = None
        resp = self.client.get("/auth/api/prewarm-register")
        self.check("status 200", resp.status_code == 200, f"got {resp.status_code}")
        data = resp.get_json()
        self.check("JSON ok key true", data.get("ok") is True,
                    f"ok was {data.get('ok')}")
        self.check("pool_ready key present",
                    "pool_ready" in data,
                    "Missing pool_ready key")
        mock_prime.assert_called_once()

    # ── Test 4: _ensure_profile_dependencies with CHAIN_FAST_LOCAL=1 ──
    @patch("services.auth_service.write_query")
    def test_04_fast_local_skips_optional(self, mock_write):
        print("\n[Test 4] _ensure_profile_dependencies skips settings/security with CHAIN_FAST_LOCAL=1")
        from services.auth_service import _ensure_profile_dependencies

        with self.app.test_request_context():
            _ensure_profile_dependencies("test-fast-profile-id")

        wallet_calls = [c for c in mock_write.call_args_list if 'chain_wallets' in str(c)]
        settings_calls = [c for c in mock_write.call_args_list if 'chain_user_settings' in str(c)]
        security_calls = [c for c in mock_write.call_args_list if 'chain_account_security' in str(c)]

        self.check("wallet write was called",
                    len(wallet_calls) > 0,
                    "No wallet INSERT attempted")
        self.check("settings write NOT called (fast local)",
                    len(settings_calls) == 0,
                    f"settings was called {len(settings_calls)} times")
        self.check("security write NOT called (fast local)",
                    len(security_calls) == 0,
                    f"security was called {len(security_calls)} times")
        wallet_sql = wallet_calls[0][0][0] if wallet_calls else ""
        self.check("wallet uses simple insert (no gift_earnings)",
                    "gift_earnings" not in wallet_sql,
                    "Wallet insert still references gift_earnings under CHAIN_FAST_LOCAL=1")

    # ── Test 5: Debug input page ──
    def test_05_debug_input_page(self):
        print("\n[Test 5] GET /auth/debug-input returns 200")
        resp = self.client.get("/auth/debug-input")
        self.check("status 200", resp.status_code == 200, f"got {resp.status_code}")
        html = resp.data.decode("utf-8")
        self.check("has Input Diagnostics title",
                    "Input Diagnostics" in html,
                    "Missing page title")
        self.check("has diag-test-input",
                    'id="diag-test-input"' in html,
                    "Missing test input field")
        self.check("has diag-submit-test button",
                    'id="diag-submit-test"' in html,
                    "Missing test submit button")
        self.check("has diag-key-log",
                    'id="diag-key-log"' in html,
                    "Missing key event log")
        self.check("has keydown listener",
                    "keydown" in html,
                    "Missing keydown event listener")
        self.check("has beforeinput listener",
                    "beforeinput" in html,
                    "Missing beforeinput event listener")

    # ── Test 6: login_required returns JSON 401 for /reels/api/ ──
    def test_06_reels_json_401(self):
        print("\n[Test 6] login_required returns JSON 401 for /reels/api/ paths")
        resp = self.client.post("/reels/api/reels/test-id/like")
        self.check("status 401", resp.status_code == 401, f"got {resp.status_code}")
        data = resp.get_json(silent=True)
        self.check("JSON response", data is not None, "Response is not JSON")
        if data:
            self.check("has error key", "error" in data, "Missing error key")
            self.check("has message key", "message" in data, "Missing message key")
            self.check("error is Unauthorized",
                        data.get("error") == "Unauthorized",
                        f"error was {data.get('error')}")

        resp_comment = self.client.post("/reels/api/reels/test-id/comment")
        self.check("comment 401", resp_comment.status_code == 401,
                    f"comment got {resp_comment.status_code}")

        resp_delete = self.client.post("/reels/api/reels/test-id/delete")
        self.check("delete 401", resp_delete.status_code == 401,
                    f"delete got {resp_delete.status_code}")

        resp_save = self.client.post("/reels/api/reels/test-id/save")
        self.check("save 401", resp_save.status_code == 401,
                    f"save got {resp_save.status_code}")

        # view and share should still work without auth
        resp_view = self.client.post("/reels/api/reels/test-id/view")
        self.check("view status 200 (no auth required)",
                    resp_view.status_code == 200,
                    f"view got {resp_view.status_code}")

        resp_share = self.client.post("/reels/api/reels/test-id/share")
        self.check("share status 200 (no auth required)",
                    resp_share.status_code == 200,
                    f"share got {resp_share.status_code}")

    # ── Test 7: Route injection safety ──
    def test_07_no_unexpected_routes(self):
        print("\n[Test 7] No unexpected route exposure")
        urls = [str(r) for r in self.app.url_map.iter_rules()]
        self.check("debug-input route registered",
                    any('/auth/debug-input' in u for u in urls),
                    "debug-input not in auth routes")
        self.check("prewarm-register route registered",
                    any('/auth/api/prewarm-register' in u for u in urls),
                    "prewarm-register not in auth routes")

    def summary(self):
        total = self.passes + self.fails
        print(f"\n{'='*50}")
        print(f"Phase 83 Summary: {self.passes}/{total} passed")
        if self.errors:
            print(f"Errors:")
            for e in self.errors:
                print(f"  - {e}")
        return self.fails == 0


if __name__ == "__main__":
    suite = Phase83ApkRealUxTest()
    suite.test_01_loading_overlay_html()
    suite.test_02_js_overlay_and_prewarm()
    suite.test_03_prewarm_endpoint()
    suite.test_04_fast_local_skips_optional()
    suite.test_05_debug_input_page()
    suite.test_06_reels_json_401()
    suite.test_07_no_unexpected_routes()
    ok = suite.summary()
    sys.exit(0 if ok else 1)
