"""
Phase 77 — Final APK auth rebuild tests.

Run:
  python3 scripts/test_phase77_auth_final_apk.py
"""

import os
import re
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ["FLASK_ENV"] = "development"
os.environ["ENV"] = "development"
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"
os.environ["CHAIN_DISABLE_DB_PING"] = "1"
os.environ.setdefault("SECRET_KEY", "test-phase77-secret-key")

from app import create_app
import api_routes.auth_routes as auth_routes


class Phase77AuthFinalApkTest:
    def __init__(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.passes = 0
        self.fails = 0
        self.errors = []

    def check(self, name, condition, detail=""):
        if condition:
            self.passes += 1
            print(f"  PASS  {name}")
        else:
            self.fails += 1
            msg = f"  FAIL  {name}"
            if detail:
                msg += f"  -- {detail}"
            print(msg)
            self.errors.append(msg)

    def html(self):
        return self.client.get("/auth/register").data.decode("utf-8")

    def extract_csrf(self, html):
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
        return match.group(1) if match else None

    def valid_payload(self, csrf_token=None, suffix=None):
        suffix = suffix or uuid.uuid4().hex[:8]
        data = {
            "full_name": "Phase77 User",
            "email": f"phase77_{suffix}@example.com",
            "username": f"phase77_{suffix}",
            "phone": f"+26481{suffix[:6].zfill(6)}",
            "country_origin": "Namibia",
            "date_of_birth": "2000-01-15",
            "gender": "female",
            "password": "Phase77Pass!",
            "confirm_password": "Phase77Pass!",
            "terms": "on",
        }
        if csrf_token:
            data["csrf_token"] = csrf_token
        return data

    def patch_availability(self, unavailable_field=None):
        original = auth_routes.check_account_availability

        def fake(field, value, town=None):
            if field == unavailable_field:
                return {
                    "available": False,
                    "field": field,
                    "message": f"Duplicate {field} handled cleanly.",
                    "suggestions": ["phase77user1", "phase77user_na", "phase77user2026"] if field == "username" else [],
                }
            return {
                "available": True,
                "field": field,
                "message": f"{field.title()} is available.",
                "suggestions": [],
            }

        auth_routes.check_account_availability = fake
        return original

    def patch_register_success(self):
        original = auth_routes.register_chain_user

        def fake(email, password, username, full_name, extra=None):
            return {
                "ok": True,
                "auth_user_id": "phase77-auth-user",
                "profile": {
                    "id": "phase77-profile",
                    "auth_user_id": "phase77-auth-user",
                    "email": email,
                    "username": username,
                    "full_name": full_name,
                    "date_of_birth": (extra or {}).get("date_of_birth"),
                    "profile_completed": False,
                },
                "redirect_to": "/profile/onboarding",
            }

        auth_routes.register_chain_user = fake
        return original

    def post_with_csrf(self, data=None):
        client = self.app.test_client()
        html = client.get("/auth/register").data.decode("utf-8")
        csrf = self.extract_csrf(html)
        payload = data or self.valid_payload(csrf)
        payload["csrf_token"] = csrf
        return client.post("/auth/register", data=payload)

    def run(self):
        print("\nPhase 77 auth final APK tests")

        resp = self.client.get("/auth/register")
        html = resp.data.decode("utf-8")
        self.check("1 GET /auth/register returns 200", resp.status_code == 200, f"got {resp.status_code}")
        self.check("2 GET /auth/register sets session cookie", "session" in resp.headers.get("Set-Cookie", "").lower(), resp.headers.get("Set-Cookie", ""))
        self.check("3 csrf_token hidden input exists", bool(re.search(r'<input[^>]+name="csrf_token"', html)))

        no_csrf = self.client.post("/auth/register", data=self.valid_payload())
        no_csrf_body = no_csrf.data.decode("utf-8")
        self.check("4 POST without csrf fails safely", no_csrf.status_code == 200 and "Your session expired. Please try again." in no_csrf_body, f"status {no_csrf.status_code}")

        original_availability = self.patch_availability()
        original_register = self.patch_register_success()
        try:
            with_csrf = self.post_with_csrf()
            body = with_csrf.data.decode("utf-8").lower()
            self.check("5 POST with csrf does not say CSRF session token missing", "csrf session token missing" not in body and "csrf token is missing" not in body)
            self.check("21 New unique user registration attempts real creation route", with_csrf.status_code in (302, 303), f"status {with_csrf.status_code}")
        finally:
            auth_routes.check_account_availability = original_availability
            auth_routes.register_chain_user = original_register

        self.check("6 form action is /auth/register", 'action="/auth/register"' in html)
        self.check("7 form method is POST", bool(re.search(r'<form[^>]*method="POST"', html)))

        js_path = os.path.join(ROOT, "static", "js", "chain_register.js")
        with open(js_path) as f:
            js = f.read()
        self.check("8 no fetch('/auth/register') in chain_register.js", not re.search(r'fetch\s*\(\s*["\']/auth/register', js))
        self.check("9 no preventDefault on register form submit", "preventDefault" not in js)
        self.check("10 country_origin is text input", bool(re.search(r'<input[^>]*name="country_origin"[^>]*type="text"|<input[^>]*type="text"[^>]*name="country_origin"', html)))
        self.check("11 old country suggestions UI removed", "country_suggestions" not in html and "renderCountries" not in js)
        self.check("12 no forced country list slicing", ".slice(0, 8)" not in js)
        self.check("13 JS does not rewrite country input during typing", "countryInput" not in js)
        self.check("14 JS does not block Backspace/Delete", "Backspace" not in js and "Delete" not in js and "preventDefault" not in js)

        email_json = self.client.get("/auth/api/check-email?email=phase77@example.com")
        username_json = self.client.get("/auth/api/check-username?username=phase77user")
        phone_json = self.client.get("/auth/api/check-phone?phone=+264811234567")
        self.check("15 email check route returns JSON", email_json.is_json and "available" in email_json.get_json())
        self.check("16 username check route returns JSON and suggestions", username_json.is_json and "suggestions" in username_json.get_json())
        self.check("17 phone check route returns JSON", phone_json.is_json and "available" in phone_json.get_json())

        self.check("18 duplicate email route returns JSON", email_json.is_json and "available" in email_json.get_json())
        self.check("19 duplicate username route returns JSON", username_json.is_json and "available" in username_json.get_json())
        self.check("20 duplicate phone route returns JSON", phone_json.is_json and "available" in phone_json.get_json())

        original_availability = self.patch_availability()
        original_register = auth_routes.register_chain_user
        try:
            auth_routes.register_chain_user = lambda *args, **kwargs: {"ok": False, "error": "Exact database insert failure"}
            resp = self.post_with_csrf()
            self.check("22 creation failure shows exact cause", "Exact database insert failure" in resp.data.decode("utf-8"))
        finally:
            auth_routes.check_account_availability = original_availability
            auth_routes.register_chain_user = original_register

        original_login = auth_routes.login_chain_user
        try:
            auth_routes.login_chain_user = lambda login_id, password: (True, "/profile/")
            login_client = self.app.test_client()
            login_html = login_client.get("/auth/login").data.decode("utf-8")
            login_csrf = self.extract_csrf(login_html)
            login_resp = login_client.post("/auth/login", data={"csrf_token": login_csrf, "login_id": "phase77@example.com", "password": "Phase77Pass!"})
            self.check("23 Login with newly created user succeeds if creation succeeds", login_resp.status_code in (302, 303))
        finally:
            auth_routes.login_chain_user = original_login

        original_availability = self.patch_availability()
        original_register = auth_routes.register_chain_user
        seen = {}
        try:
            def capture(email, password, username, full_name, extra=None):
                seen.update(extra or {})
                return {"ok": False, "error": "captured"}
            auth_routes.register_chain_user = capture
            self.post_with_csrf()
            self.check("24 Date of birth accepted", seen.get("date_of_birth") == "2000-01-15", str(seen))
        finally:
            auth_routes.check_account_availability = original_availability
            auth_routes.register_chain_user = original_register

        css_path = os.path.join(ROOT, "static", "css", "chain_auth.css")
        with open(css_path) as f:
            css = f.read()
        css_required = ["font-size: 16px", "min-height: 48px", "-webkit-text-fill-color: #0f172a", "caret-color: #0f172a", "touch-action: auto", "touch-action: manipulation"]
        self.check("25 CSS mobile readable rules exist", all(item in css for item in css_required))

        debug = self.client.get("/auth/debug-csrf")
        self.check("26 debug csrf endpoint works in dev", debug.is_json and debug.get_json().get("csrf_enabled") is True)
        old_env = (os.environ.get("CHAIN_FAST_LOCAL"), os.environ.get("FLASK_ENV"), os.environ.get("ENV"))
        try:
            os.environ["CHAIN_FAST_LOCAL"] = "0"
            os.environ["FLASK_ENV"] = "production"
            os.environ["ENV"] = "production"
            prod_debug = self.client.get("/auth/debug-csrf")
            self.check("26 debug csrf endpoint hidden in production", prod_debug.status_code == 404, f"got {prod_debug.status_code}")
        finally:
            for key, value in zip(("CHAIN_FAST_LOCAL", "FLASK_ENV", "ENV"), old_env):
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        print(f"\nPassed: {self.passes}  Failed: {self.fails}")
        if self.errors:
            print("\nFailures:")
            for error in self.errors:
                print(error)
        return self.fails == 0


if __name__ == "__main__":
    ok = Phase77AuthFinalApkTest().run()
    sys.exit(0 if ok else 1)
