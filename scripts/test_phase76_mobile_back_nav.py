"""
Phase 76 — Mobile Back/Return Button + Smooth Navigation.

Tests:
1. base.html includes namvibe_mobile_nav.js.
2. namvibe_mobile_nav.js contains history.back fallback.
3. namvibe_mobile_nav.js does not contain document.body preventDefault.
4. namvibe_mobile_nav.js ignores input/textarea/select typing (no keydown block).
5. login page has data-go-back button.
6. register page has data-go-back button.
7. CSS has min-height 44px for back button.
8. CSS has touch-action manipulation on buttons/links.
9. form inputs preserve touch-action auto in CSS.
10. No old register stepper text.
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
os.environ["SECRET_KEY"] = "test-phase76-secret-key"

from app import create_app


class Phase76MobileBackNavTest:
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

    def test_01_base_has_nav_js(self):
        print("\n[Test 1] base.html includes namvibe_mobile_nav.js")
        base_path = os.path.join(self.base_dir, "templates", "base.html")
        with open(base_path) as f:
            html = f.read()
        self.check("namvibe_mobile_nav.js script tag",
                    'namvibe_mobile_nav.js' in html,
                    "Missing namvibe_mobile_nav.js in base.html")
        self.check("defer attribute",
                    'defer' in html and 'namvibe_mobile_nav.js' in html,
                    "Missing defer attribute on nav script")

    def test_02_js_has_history_back(self):
        print("\n[Test 2] namvibe_mobile_nav.js contains history.back fallback")
        js_path = os.path.join(self.base_dir, "static", "js", "namvibe_mobile_nav.js")
        with open(js_path) as f:
            js = f.read()
        self.check("history.back() present",
                    "history.back" in js,
                    "Missing history.back() call")
        self.check("fallback to /",
                    'window.location.href = "/"' in js or 'location.href = "/"' in js,
                    "Missing fallback redirect to /")
        self.check("delegated click handler",
                    "addEventListener(\"click\"" in js,
                    "Missing click event delegation")
        self.check("touchend handler",
                    "addEventListener(\"touchend\"" in js,
                    "Missing touchend handler for Android WebView")

    def test_03_no_body_preventdefault(self):
        print("\n[Test 3] JS does not contain document.body preventDefault")
        js_path = os.path.join(self.base_dir, "static", "js", "namvibe_mobile_nav.js")
        with open(js_path) as f:
            js = f.read()
        bad = "document.body" in js and "preventDefault" in js
        self.check("no document.body preventDefault", not bad,
                    "JS uses document.body preventDefault")

    def test_04_js_ignores_inputs(self):
        print("\n[Test 4] JS does not block input/textarea/select typing")
        js_path = os.path.join(self.base_dir, "static", "js", "namvibe_mobile_nav.js")
        with open(js_path) as f:
            js = f.read()
        has_input_block = "keydown" in js or "Backspace" in js or "Delete" in js
        self.check("no keydown/Backspace/Delete in JS", not has_input_block,
                    "JS contains keydown or Backspace/Delete handling (may block typing)")

    def test_05_login_has_back_button(self):
        print("\n[Test 5] login page has data-go-back button")
        resp = self.client.get("/auth/login")
        html = resp.data.decode("utf-8")
        self.check("data-go-back on login",
                    'data-go-back' in html,
                    "Missing data-go-back on login page")
        self.check("auth-back-btn on login",
                    'auth-back-btn' in html,
                    "Missing auth-back-btn class on login")

    def test_06_register_has_back_button(self):
        print("\n[Test 6] register page has data-go-back button")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        self.check("data-go-back on register",
                    'data-go-back' in html,
                    "Missing data-go-back on register page")
        self.check("auth-back-btn on register",
                    'auth-back-btn' in html,
                    "Missing auth-back-btn class on register")

    def test_07_css_min_height_44px(self):
        print("\n[Test 7] CSS has min-height 44px for back button")
        css_path = os.path.join(self.base_dir, "static", "css", "chain_auth.css")
        with open(css_path) as f:
            css = f.read()
        self.check("min-height: 44px in .auth-back-btn",
                    'min-height: 44px' in css and '.auth-back-btn' in css,
                    "Missing min-height 44px for back button")
        self.check("touch-action: manipulation in .auth-back-btn",
                    'touch-action: manipulation' in css,
                    "Missing touch-action: manipulation")

    def test_08_css_button_touch(self):
        print("\n[Test 8] CSS has touch-action manipulation on buttons/links")
        base_path = os.path.join(self.base_dir, "templates", "base.html")
        with open(base_path) as f:
            html = f.read()
        has_manipulation = 'touch-action: manipulation' in html
        has_btn_selector = 'button' in html and 'touch-action' in html
        self.check("touch-action: manipulation in base.html CSS",
                    has_manipulation,
                    "Missing touch-action manipulation rule")

    def test_09_inputs_touch_auto(self):
        print("\n[Test 9] form inputs preserve touch-action auto")
        base_path = os.path.join(self.base_dir, "templates", "base.html")
        with open(base_path) as f:
            html = f.read()
        # Should have input, textarea, select { touch-action: auto }
        has_input_auto = 'touch-action: auto' in html
        self.check("input,textarea,select { touch-action: auto }",
                    has_input_auto,
                    "Missing touch-action: auto for form inputs")

    def test_10_no_old_wizard(self):
        print("\n[Test 10] No old register stepper text")
        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        forbidden = ["Step 1 of 7", "Your account starts here", "data-step=", "chain-register-stepper"]
        for phrase in forbidden:
            self.check(f"no '{phrase}'", phrase not in html,
                        f"Found old wizard text: {phrase}")

    def run_all(self):
        print("=" * 60)
        print("Phase 76 — Mobile Back Button + Smooth Navigation")
        print("=" * 60)

        self.test_01_base_has_nav_js()
        self.test_02_js_has_history_back()
        self.test_03_no_body_preventdefault()
        self.test_04_js_ignores_inputs()
        self.test_05_login_has_back_button()
        self.test_06_register_has_back_button()
        self.test_07_css_min_height_44px()
        self.test_08_css_button_touch()
        self.test_09_inputs_touch_auto()
        self.test_10_no_old_wizard()

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
    success = Phase76MobileBackNavTest().run_all()
    sys.exit(0 if success else 1)
