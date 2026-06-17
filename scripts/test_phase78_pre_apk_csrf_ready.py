"""
Phase 78 — pre-APK CSRF and registration readiness.

Run:
  ./venv/bin/python3 scripts/test_phase78_pre_apk_csrf_ready.py
"""

import json
import os
import re
import subprocess
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("ENV", "development")
os.environ.setdefault("FLASK_TESTING", "1")
os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
os.environ.setdefault("SECRET_KEY", "namvibe-local-dev-secret-change-before-production")

from app import create_app
from services.neon_service import fast_query


COOKIE_FILE = "/tmp/nv_cookie.txt"
REGISTER_URL = "http://127.0.0.1:5000/auth/register"


def extract_csrf(html):
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return match.group(1) if match else None


class Phase78PreApkReady:
    def __init__(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.errors = []
        self.cookie_status = {}
        self.csrf_status = {}
        self.registration_status = {}
        self.login_status = {}
        self.apk_status = {}
        self.js_status = {}

    def check(self, name, condition, detail=""):
        line = f"{'PASS' if condition else 'FAIL'} {name}"
        if detail:
            line += f" -- {detail}"
        print(line)
        if not condition:
            self.errors.append(line)
        return condition

    def check_config(self):
        print("\n[1] Flask config")
        config_path = os.path.join(ROOT, "config", "settings.py")
        with open(config_path) as f:
            settings = f.read()
        secret_stable = "uuid.uuid4" not in settings and "namvibe-local-dev-secret-change-before-production" in settings
        self.check("SECRET_KEY stable in local dev", secret_stable)
        self.check("SESSION_COOKIE_SECURE=False for local HTTP", self.app.config.get("SESSION_COOKIE_SECURE") is False, str(self.app.config.get("SESSION_COOKIE_SECURE")))
        self.check('SESSION_COOKIE_SAMESITE="Lax"', self.app.config.get("SESSION_COOKIE_SAMESITE") == "Lax", str(self.app.config.get("SESSION_COOKIE_SAMESITE")))
        self.check("SESSION_COOKIE_HTTPONLY=True", self.app.config.get("SESSION_COOKIE_HTTPONLY") is True, str(self.app.config.get("SESSION_COOKIE_HTTPONLY")))
        self.check("WTF_CSRF_TIME_LIMIT=None in dev", self.app.config.get("WTF_CSRF_TIME_LIMIT") is None, str(self.app.config.get("WTF_CSRF_TIME_LIMIT")))

    def check_get_register(self):
        print("\n[2] GET /auth/register")
        response = self.client.get("/auth/register")
        html = response.data.decode("utf-8", errors="replace")
        set_cookie = response.headers.get("Set-Cookie", "")
        token = extract_csrf(html)
        self.cookie_status["set_cookie"] = set_cookie
        self.csrf_status["token_present"] = bool(token)
        self.check("GET returns 200", response.status_code == 200, f"got {response.status_code}")
        self.check("sets session cookie", "session=" in set_cookie.lower(), set_cookie)
        self.check("contains hidden csrf_token", bool(token))
        self.check("contains Create Account button", ">Create Account</button>" in html)
        self.check("contains country input", 'name="country_origin"' in html and 'type="text"' in html)
        self.check("contains date_of_birth", 'name="date_of_birth"' in html)
        self.check("no old Step 1 of 7 text", "Step 1 of 7" not in html)
        return token

    def registration_payload(self, csrf):
        suffix = uuid.uuid4().hex[:8]
        email = f"phase78real{suffix}@namvibe.com"
        username = f"phase78real{suffix[:6]}"
        password = "Phase78RealPass!"
        return {
            "csrf_token": csrf,
            "full_name": "Phase78 Real User",
            "email": email,
            "username": username,
            "phone": f"+26482{suffix[:6]}",
            "country_origin": "Namibia",
            "date_of_birth": "2000-01-15",
            "gender": "female",
            "password": password,
            "confirm_password": password,
            "terms": "on",
        }, email, username, password

    def check_registration_and_login(self):
        print("\n[3] Same-cookie POST /auth/register, DB profile, login")
        client = self.app.test_client()
        get_response = client.get("/auth/register")
        csrf = extract_csrf(get_response.data.decode("utf-8", errors="replace"))
        payload, email, username, password = self.registration_payload(csrf)
        post_response = client.post("/auth/register", data=payload, follow_redirects=False)
        body = post_response.data.decode("utf-8", errors="replace").lower()
        location = post_response.headers.get("Location") or ""
        self.registration_status.update({
            "status_code": post_response.status_code,
            "location": location,
            "email": email,
            "username": username,
            "csrf_missing_text": "csrf session token missing" in body or "csrf token is missing" in body,
        })
        self.check("no CSRF session token missing", not self.registration_status["csrf_missing_text"])
        self.check("registration redirects", post_response.status_code in (302, 303), f"status {post_response.status_code}")
        self.check("redirect target is profile/login/completion", location.startswith(("/profile", "/auth/login")), location)

        rows = fast_query(
            """
            SELECT id, auth_user_id, email, username, date_of_birth, country_origin
            FROM chain_profiles
            WHERE lower(email) = lower(%s) OR lower(username) = lower(%s)
            LIMIT 1
            """,
            (email, username),
            timeout_ms=3000,
            default=[],
        )
        profile = rows[0] if rows else None
        self.registration_status["profile"] = profile
        dob = str((profile or {}).get("date_of_birth") or "")
        self.check("DB profile exists", bool(profile), str(profile))
        self.check("date_of_birth saved", dob == "2000-01-15", dob)

        login_client = self.app.test_client()
        login_get = login_client.get("/auth/login")
        login_csrf = extract_csrf(login_get.data.decode("utf-8", errors="replace"))
        login_response = login_client.post(
            "/auth/login",
            data={"csrf_token": login_csrf, "login_id": email, "password": password},
            follow_redirects=False,
        )
        self.login_status.update({
            "status_code": login_response.status_code,
            "location": login_response.headers.get("Location") or "",
        })
        self.check("login succeeds", login_response.status_code in (302, 303), f"status {login_response.status_code}")
        self.check("login redirects to profile", self.login_status["location"].startswith("/profile"), self.login_status["location"])

    def run_curl_probe(self):
        print("\n[4] curl cookie probe")
        try:
            subprocess.run(["rm", "-f", COOKIE_FILE], check=False)
            get = subprocess.run(
                ["curl", "-sS", "-c", COOKIE_FILE, "-b", COOKIE_FILE, "-i", REGISTER_URL],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
            output = get.stdout + get.stderr
            token = extract_csrf(output)
            has_cookie = "set-cookie:" in output.lower() and "session=" in output.lower()
            self.cookie_status["curl_get_status"] = get.returncode
            self.cookie_status["curl_set_cookie"] = has_cookie
            self.check("curl GET completed", get.returncode == 0, output[-300:])
            self.check("curl GET has Set-Cookie session", has_cookie)
            self.check("curl GET extracted csrf_token", bool(token))
            if token:
                post = subprocess.run(
                    [
                        "curl", "-sS", "-c", COOKIE_FILE, "-b", COOKIE_FILE, "-i",
                        "-d", f"csrf_token={token}&full_name=Curl+Probe",
                        REGISTER_URL,
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                post_output = post.stdout + post.stderr
                csrf_missing = "csrf session token missing" in post_output.lower() or "csrf token is missing" in post_output.lower()
                self.csrf_status["curl_post_csrf_missing"] = csrf_missing
                self.check("curl POST same cookie/token not CSRF missing", not csrf_missing, post_output[-300:])
        except Exception as error:
            self.check("curl probe", False, str(error))

    def check_apk_config(self):
        print("\n[5] Android APK URL")
        path = os.path.join(ROOT, "mobile_android", "capacitor.config.json")
        with open(path) as f:
            config = json.load(f)
        url = (config.get("server") or {}).get("url")
        capacitor_http_enabled = ((config.get("plugins") or {}).get("CapacitorHttp") or {}).get("enabled")
        self.apk_status.update({"url": url, "capacitor_http_enabled": capacitor_http_enabled})
        self.check("server.url is http://192.168.179.30:5000", url == "http://192.168.179.30:5000", str(url))
        self.check("CapacitorHttp enabled is false", capacitor_http_enabled is False, str(capacitor_http_enabled))

    def check_js_typing(self):
        print("\n[6] JS typing/delete")
        with open(os.path.join(ROOT, "static", "js", "chain_register.js")) as f:
            js = f.read()
        no_fetch_submit = not re.search(r'fetch\s*\(\s*["\']/auth/register', js)
        no_prevent = "preventDefault" not in js
        no_global_keydown = not re.search(r'document(?:\.body)?\.addEventListener\(\s*["\']keydown', js)
        no_delete_block = "Backspace" not in js and "Delete" not in js
        value_assignments = re.findall(r"([A-Za-z0-9_$?.]+\.value)\s*(?<![=!<>])=(?!=)", js)
        disallowed_value_assignments = [
            assignment for assignment in value_assignments
            if assignment != "countryInput.value"
        ]
        country_click_write = re.search(
            r'button\.addEventListener\(\s*["\']click["\'][\s\S]{0,180}countryInput\.value\s*=',
            js,
        )
        no_typing_rewrite = not disallowed_value_assignments and bool(country_click_write)
        self.js_status.update({
            "no_fetch_submit": no_fetch_submit,
            "no_prevent_default": no_prevent,
            "no_global_keydown": no_global_keydown,
            "no_delete_block": no_delete_block,
            "no_typing_rewrite": no_typing_rewrite,
        })
        self.check('no fetch("/auth/register")', no_fetch_submit)
        self.check("no preventDefault on form submit", no_prevent)
        self.check("no global keydown blocking", no_global_keydown)
        self.check("no Backspace/Delete blocking", no_delete_block)
        self.check("no input.value rewriting while typing", no_typing_rewrite)

    def run(self):
        self.check_config()
        self.check_get_register()
        self.check_registration_and_login()
        self.run_curl_probe()
        self.check_apk_config()
        self.check_js_typing()

        apk_csrf_ready = (
            not self.errors
            and self.cookie_status.get("curl_set_cookie") is True
            and self.csrf_status.get("token_present") is True
            and self.csrf_status.get("curl_post_csrf_missing") is False
        )
        apk_register_ready = (
            not self.errors
            and bool(self.registration_status.get("profile"))
            and self.registration_status.get("status_code") in (302, 303)
            and self.login_status.get("status_code") in (302, 303)
        )
        print("\nSUMMARY")
        print(f"COOKIE_STATUS={self.cookie_status}")
        print(f"CSRF_STATUS={self.csrf_status}")
        print(f"REGISTRATION_STATUS={{'status_code': {self.registration_status.get('status_code')}, 'location': {self.registration_status.get('location')!r}, 'profile_exists': {bool(self.registration_status.get('profile'))}}}")
        print(f"LOGIN_STATUS={self.login_status}")
        print(f"APK_URL_STATUS={self.apk_status}")
        print(f"JS_TYPING_DELETE_STATUS={self.js_status}")
        print(f"APK_CSRF_READY={'true' if apk_csrf_ready else 'false'}")
        print(f"APK_REGISTER_READY={'true' if apk_register_ready else 'false'}")
        return apk_csrf_ready and apk_register_ready


if __name__ == "__main__":
    ok = Phase78PreApkReady().run()
    sys.exit(0 if ok else 1)
