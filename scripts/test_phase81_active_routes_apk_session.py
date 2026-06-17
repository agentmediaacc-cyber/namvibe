#!/usr/bin/env python3
import os
import re
import sys
import uuid
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["FLASK_ENV"] = "development"
os.environ["ENV"] = "development"
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"
os.environ["CHAIN_DISABLE_DB_PING"] = "1"
os.environ["CHAIN_DISABLE_RATE_LIMITS"] = "1"
os.environ.setdefault("SECRET_KEY", "phase81-active-routes-secret")


APK_UA = "Mozilla/5.0 (Linux; Android 14; NamVibe APK) AppleWebKit/537.36 wv Capacitor"
APK_HOST = "192.168.179.30:5000"


class Phase81ActiveRoutesApkSession:
    def __init__(self):
        self.passes = 0
        self.fails = 0
        self.errors = []

    def check(self, name, condition, detail=""):
        if condition:
            self.passes += 1
            print(f"PASS {name}")
        else:
            self.fails += 1
            msg = f"FAIL {name}" + (f" - {detail}" if detail else "")
            self.errors.append(msg)
            print(msg)

    def run(self):
        from app import create_app
        import api_routes.auth_routes as auth_routes

        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.check("Flask route map contains /auth/debug-session", "/auth/debug-session" in rules, sorted(rules))
        self.check("Flask route map contains /debug/session", "/debug/session" in rules, sorted(rules))

        pre_auth_debug = client.get("/auth/debug-session", headers={"User-Agent": APK_UA, "Host": APK_HOST})
        self.check("/auth/debug-session returns 200", pre_auth_debug.status_code == 200, f"got {pre_auth_debug.status_code}")
        self.check("/auth/debug-session returns JSON", pre_auth_debug.is_json, pre_auth_debug.get_data(as_text=True)[:200])

        pre_app_debug = client.get("/debug/session", headers={"User-Agent": APK_UA, "Host": APK_HOST})
        self.check("/debug/session returns 200", pre_app_debug.status_code == 200, f"got {pre_app_debug.status_code}")
        self.check("/debug/session returns JSON", pre_app_debug.is_json, pre_app_debug.get_data(as_text=True)[:200])

        auth_user_id = str(uuid.uuid4())
        profile_id = str(uuid.uuid4())
        email = f"phase81_{uuid.uuid4().hex[:8]}@gmail.com"
        username = f"phase81_{uuid.uuid4().hex[:6]}"
        profile = {
            "id": profile_id,
            "auth_user_id": auth_user_id,
            "email": email,
            "username": username,
            "full_name": "Phase81 APK",
            "display_name": "Phase81 APK",
            "profile_completed": False,
            "email_verified": False,
            "is_verified": False,
        }

        def fake_register(email_arg, password, username_arg, full_name, extra=None):
            return {
                "ok": True,
                "auth_user_id": auth_user_id,
                "profile": {**profile, "email": email_arg.strip().lower(), "username": username_arg.strip()},
                "redirect_to": "/auth/login",
                "auth_provider": "local_fallback",
            }

        original_register = auth_routes.register_chain_user
        auth_routes.register_chain_user = fake_register
        try:
            get_resp = client.get("/auth/register", headers={"User-Agent": APK_UA, "Host": APK_HOST})
            html = get_resp.get_data(as_text=True)
            csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
            csrf = csrf_match.group(1) if csrf_match else ""
            self.check("/auth/register GET returns csrf", bool(csrf))

            post_resp = client.post(
                "/auth/register",
                data={
                    "csrf_token": csrf,
                    "full_name": "Phase81 APK",
                    "email": f" {email.upper()} ",
                    "username": f" {username} ",
                    "password": "Phase81Pass!",
                    "confirm_password": "Phase81Pass!",
                    "terms": "on",
                },
                headers={"User-Agent": APK_UA, "Host": APK_HOST},
                follow_redirects=False,
            )
            self.check("APK register POST redirects", post_resp.status_code == 302, f"got {post_resp.status_code}")
            self.check("APK register POST redirects to /profile/", post_resp.headers.get("Location") == "/profile/", post_resp.headers.get("Location", ""))
            self.check("APK register POST has Set-Cookie", "session=" in post_resp.headers.get("Set-Cookie", ""), post_resp.headers.get("Set-Cookie", ""))

            auth_debug = client.get("/auth/debug-session", headers={"User-Agent": APK_UA, "Host": APK_HOST})
            auth_debug_json = auth_debug.get_json() if auth_debug.is_json else {}
            self.check("/auth/debug-session after POST logged_in true", auth_debug_json.get("logged_in") is True, str(auth_debug_json))
            self.check("/auth/debug-session after POST has profile_id", auth_debug_json.get("profile_id") == profile_id, str(auth_debug_json))
            self.check("/auth/debug-session after POST has auth_user_id", auth_debug_json.get("auth_user_id") == auth_user_id, str(auth_debug_json))

            app_debug = client.get("/debug/session", headers={"User-Agent": APK_UA, "Host": APK_HOST})
            app_debug_json = app_debug.get_json() if app_debug.is_json else {}
            self.check("/debug/session after POST logged_in true", app_debug_json.get("logged_in") is True, str(app_debug_json))
            self.check("/debug/session after POST has profile_id", app_debug_json.get("profile_id") == profile_id, str(app_debug_json))
            self.check("/debug/session after POST has auth_user_id", app_debug_json.get("auth_user_id") == auth_user_id, str(app_debug_json))

            with patch("api_routes.profile_routes.get_current_profile", return_value=profile), \
                 patch("api_routes.profile_routes.verify_profile_age", return_value=(True, None)), \
                 patch("api_routes.profile_routes.is_profile_complete", return_value=False), \
                 patch("api_routes.profile_routes.get_profile_bundle", return_value={"profile": profile, "content": {"posts": [], "reels": [], "rooms": [], "stories": []}, "stats": {}}), \
                 patch("api_routes.profile_routes.build_profile_dashboard", return_value={"profile": profile, "content": {"posts": [], "reels": [], "rooms": [], "stories": []}, "stats": {}}), \
                 patch("api_routes.profile_routes.get_my_notifications", return_value=([], [], 0)), \
                 patch("api_routes.profile_routes.render_template", return_value="profile ok"):
                profile_resp = client.get("/profile/", headers={"User-Agent": APK_UA, "Host": APK_HOST}, follow_redirects=False)
                self.check("/profile/ after POST does not redirect to /auth/login", not (profile_resp.status_code in (301, 302, 303) and "/auth/login" in profile_resp.headers.get("Location", "")), f"{profile_resp.status_code} {profile_resp.headers.get('Location')}")
                self.check("/profile/ after POST opens", profile_resp.status_code == 200, f"got {profile_resp.status_code}")
        finally:
            auth_routes.register_chain_user = original_register

        print(f"Passed: {self.passes} Failed: {self.fails}")
        if self.errors:
            print("\n".join(self.errors))
        return 1 if self.fails else 0


if __name__ == "__main__":
    sys.exit(Phase81ActiveRoutesApkSession().run())
