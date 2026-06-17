"""
Phase 79 — APK CSRF fallback and fast register readiness.

Run:
  ./venv/bin/python3 scripts/test_phase79_apk_csrf_fallback_speed.py
"""

import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ["FLASK_ENV"] = "development"
os.environ["ENV"] = "development"
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"
os.environ["CHAIN_DISABLE_DB_PING"] = "1"
os.environ.setdefault("SECRET_KEY", "test-phase79-secret-key")

from app import create_app
import api_routes.auth_routes as auth_routes


def extract(html, name):
    match = re.search(rf'name="{re.escape(name)}"\s+value="([^"]+)"', html)
    return match.group(1) if match else None


class Phase79ApkCsrfFallbackSpeed:
    def __init__(self):
        self.app = create_app()
        self.errors = []

    def check(self, name, condition, detail=""):
        print(f"{'PASS' if condition else 'FAIL'} {name}" + (f" -- {detail}" if detail else ""))
        if not condition:
            self.errors.append(f"{name}: {detail}")

    def run(self):
        print("\n[1] Hidden stateless APK CSRF token exists")
        client = self.app.test_client()
        get_resp = client.get("/auth/register")
        html = get_resp.data.decode("utf-8")
        flask_token = extract(html, "csrf_token")
        apk_token = extract(html, "apk_csrf_token")
        self.check("GET /auth/register 200", get_resp.status_code == 200, str(get_resp.status_code))
        self.check("normal csrf_token exists", bool(flask_token))
        self.check("apk_csrf_token exists", bool(apk_token))

        print("\n[2] POST without Flask session cookie but with APK token")
        original_register = auth_routes.register_chain_user
        try:
            def fake_register(email, password, username, full_name, extra=None):
                return {
                    "ok": True,
                    "auth_user_id": "6c61ccdc-1d82-4d7b-b093-448e888f0079",
                    "profile": {
                        "id": "phase79-profile",
                        "auth_user_id": "6c61ccdc-1d82-4d7b-b093-448e888f0079",
                        "email": email,
                        "username": username,
                        "full_name": full_name,
                        "date_of_birth": (extra or {}).get("date_of_birth"),
                    },
                    "redirect_to": "/profile/",
                }

            auth_routes.register_chain_user = fake_register
            fresh_no_cookie_client = self.app.test_client()
            post_resp = fresh_no_cookie_client.post("/auth/register", data={
                "csrf_token": flask_token or "",
                "apk_csrf_token": apk_token,
                "full_name": "Phase79 APK User",
                "email": "phase79apk@namvibe.com",
                "username": "phase79apk",
                "phone": "+26482999999",
                "country_origin": "Namibia",
                "date_of_birth": "2000-01-15",
                "gender": "female",
                "password": "Phase79Pass!",
                "confirm_password": "Phase79Pass!",
                "terms": "on",
            }, follow_redirects=False)
        finally:
            auth_routes.register_chain_user = original_register

        body = post_resp.data.decode("utf-8", errors="replace").lower()
        self.check("no session expired page", "your session expired. please try again." not in body)
        self.check("no CSRF session token missing", "csrf session token missing" not in body)
        self.check("APK fallback reaches register success", post_resp.status_code in (302, 303), f"status {post_resp.status_code}")
        self.check("redirects to profile", (post_resp.headers.get("Location") or "").startswith("/profile"), str(post_resp.headers.get("Location")))

        print("\n[3] Bad/missing APK token still fails safely")
        bad_client = self.app.test_client()
        bad_resp = bad_client.post("/auth/register", data={
            "csrf_token": flask_token or "",
            "apk_csrf_token": "bad-token",
            "full_name": "Bad Token",
            "email": "badphase79@namvibe.com",
        })
        bad_body = bad_resp.data.decode("utf-8", errors="replace")
        self.check("bad fallback token is rejected", bad_resp.status_code == 200 and "Your session expired. Please try again." in bad_body, f"status {bad_resp.status_code}")

        print("\n[4] Availability APIs are fast advisory checks")
        api_client = self.app.test_client()
        for path in (
            "/auth/api/check-email?email=phase79@namvibe.com",
            "/auth/api/check-username?username=phase79user",
            "/auth/api/check-phone?phone=%2B26482999999",
        ):
            start = time.perf_counter()
            resp = api_client.get(path)
            elapsed_ms = (time.perf_counter() - start) * 1000
            data = resp.get_json(silent=True) or {}
            self.check(f"{path} returns JSON", resp.is_json and data.get("ok") is True, str(data))
            self.check(f"{path} under 500ms", elapsed_ms < 500, f"{elapsed_ms:.1f}ms")

        print("\n[5] Register JS remains normal form submit")
        with open(os.path.join(ROOT, "static", "js", "chain_register.js")) as f:
            js = f.read()
        self.check("no fetch('/auth/register')", not re.search(r'fetch\s*\(\s*["\']/auth/register', js))
        self.check("no preventDefault", "preventDefault" not in js)
        self.check("no Backspace/Delete blocking", "Backspace" not in js and "Delete" not in js)

        print("\nPHASE79_APK_CSRF_FALLBACK_READY=" + ("true" if not self.errors else "false"))
        print("PHASE79_FAST_AVAILABILITY_READY=" + ("true" if not self.errors else "false"))
        return not self.errors


if __name__ == "__main__":
    ok = Phase79ApkCsrfFallbackSpeed().run()
    sys.exit(0 if ok else 1)
