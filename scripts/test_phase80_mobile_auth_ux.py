"""
Phase 80 — mobile auth UX polish tests.

Run:
  ./venv/bin/python3 scripts/test_phase80_mobile_auth_ux.py
"""

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ["FLASK_ENV"] = "development"
os.environ["ENV"] = "development"
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"
os.environ["CHAIN_DISABLE_DB_PING"] = "1"
os.environ.setdefault("SECRET_KEY", "test-phase80-secret-key")

from app import create_app


class Phase80MobileAuthUx:
    def __init__(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.errors = []
        self.root = ROOT

    def check(self, name, condition, detail=""):
        print(f"{'PASS' if condition else 'FAIL'} {name}" + (f" -- {detail}" if detail else ""))
        if not condition:
            self.errors.append(f"{name}: {detail}")

    def read(self, *parts):
        with open(os.path.join(self.root, *parts)) as f:
            return f.read()

    def page(self, path):
        response = self.client.get(path)
        return response, response.data.decode("utf-8", errors="replace")

    def run(self):
        register_response, register_html = self.page("/auth/register")
        login_response, login_html = self.page("/auth/login")
        js = self.read("static", "js", "chain_register.js")
        nav_js = self.read("static", "js", "namvibe_mobile_nav.js")
        css = self.read("static", "css", "chain_auth.css")
        base = self.read("templates", "base.html")

        print("\n[1] Auth markup")
        self.check("register page loads", register_response.status_code == 200, str(register_response.status_code))
        self.check("login page loads", login_response.status_code == 200, str(login_response.status_code))
        self.check("register page avoids rendered sidebar", 'class="sidebar"' not in register_html and 'id="social-drawer"' not in register_html)
        self.check("register page contains auth mobile/social classes", "auth-mobile-social" in register_html and "auth-social-card" in register_html)
        self.check("login page contains auth mobile/social classes", "auth-mobile-social" in login_html and "auth-social-card" in login_html)
        self.check("back button exists on register", "auth-back-btn" in register_html and "data-go-back" in register_html)
        self.check("back button exists on login", "auth-back-btn" in login_html and "data-go-back" in login_html)
        self.check("Create Account button visible", 'id="register_submit"' in register_html and ">Create Account</button>" in register_html)

        print("\n[2] Register JS typing safety")
        keydown_handlers = re.findall(r'addEventListener\(\s*["\']keydown["\']([\s\S]{0,180})', js)
        self.check("chain_register.js has no keydown blocking", "preventDefault" not in "".join(keydown_handlers))
        self.check("chain_register.js has no Backspace/Delete blocking", "Backspace" not in js and "Delete" not in js)
        value_assignments = re.findall(r'([A-Za-z0-9_$?.]+\.value)\s*(?<![=!<>])=(?!=)', js)
        allowed_assignments = {"countryInput.value"}
        self.check("chain_register.js has no input.value assignment except suggestion click", set(value_assignments).issubset(allowed_assignments), str(value_assignments))
        debounce_match = re.search(r"CHECK_DEBOUNCE_MS\s*=\s*(\d+)", js)
        debounce_ms = int(debounce_match.group(1)) if debounce_match else 0
        self.check("chain_register.js has debounce >= 900ms", debounce_ms >= 900, str(debounce_ms))
        self.check("chain_register.js uses AbortController", "AbortController" in js)
        country_cap = re.search(r"\.slice\(\s*0\s*,\s*(\d+)\s*\)", js)
        cap = int(country_cap.group(1)) if country_cap else 999
        self.check("country suggestions max <= 6", cap <= 6, str(cap))
        input_handler = re.search(r'addEventListener\(\s*["\']input["\']([\s\S]{0,160})', js)
        self.check("no fetch duplicate check runs on every keypress without debounce", bool(input_handler) and "scheduleCheck" in input_handler.group(0) and "fetch(" not in input_handler.group(0))
        self.check("auth page JS is under 15KB", len(js.encode("utf-8")) < 15 * 1024, str(len(js.encode("utf-8"))))
        self.check("mobile nav has no global touch preventDefault", "touchstart" not in nav_js and "touchmove" not in nav_js and "touchend" not in nav_js)

        print("\n[3] CSS mobile and keyboard safety")
        self.check("CSS has min-height 100svh or 100dvh", "min-height: 100svh" in css or "min-height: 100dvh" in css)
        self.check("CSS has input font-size 16px", "font-size: 16px" in css)
        self.check("CSS has input min-height 48px", "min-height: 48px" in css)
        self.check("CSS has touch-action:auto for inputs", "touch-action: auto" in css)
        self.check("CSS has touch-action:manipulation for buttons/links", "touch-action: manipulation" in css)
        self.check("CSS has animated background/wallpaper", "@keyframes authWallpaperShift" in css and "animation: authWallpaperShift" in css)
        self.check("auth card scrolls with keyboard", "overflow-y: auto" in css and "-webkit-overflow-scrolling: touch" in css)
        blocking_overlay = re.search(r"\.(?:auth|chain).*overlay[^{}]*\{[^}]*pointer-events:\s*(auto|all)", css)
        self.check("no overlay class has pointer-events blocking auth inputs", not blocking_overlay, blocking_overlay.group(0) if blocking_overlay else "")

        print("\n[4] Base auth surface")
        self.check("base template defines auth surface", "is_auth_surface" in base and "chain-shell--auth" in base)
        self.check("base skips app chrome on auth", "not is_auth_surface" in base and "app-floating-create" in base)

        print("\n[5] Compile")
        compile_result = subprocess.run(
            [
                "./venv/bin/python3",
                "-m",
                "compileall",
                "templates",
                "static",
                "scripts/test_phase80_mobile_auth_ux.py",
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        self.check("compile passes", compile_result.returncode == 0, (compile_result.stdout + compile_result.stderr)[-500:])

        print("\nPHASE80_MOBILE_AUTH_UX_READY=" + ("true" if not self.errors else "false"))
        if self.errors:
            print("\nFailures:")
            for error in self.errors:
                print(error)
        return not self.errors


if __name__ == "__main__":
    ok = Phase80MobileAuthUx().run()
    sys.exit(0 if ok else 1)
