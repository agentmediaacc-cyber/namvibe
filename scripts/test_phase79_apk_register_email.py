#!/usr/bin/env python3
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


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
os.environ.setdefault("SECRET_KEY", "phase79-apk-email-secret")


class Phase79ApkRegisterEmail:
    def __init__(self):
        self.passes = 0
        self.fails = 0
        self.errors = []
        self.rows = {}

    def check(self, name, condition, detail=""):
        if condition:
            self.passes += 1
            print(f"PASS {name}")
        else:
            self.fails += 1
            message = f"FAIL {name}" + (f" - {detail}" if detail else "")
            self.errors.append(message)
            print(message)

    def fake_ensure_profile_for_user(self, user_id, email=None, username=None, defaults=None):
        defaults = defaults or {}
        row = {
            "id": str(uuid.uuid4()),
            "auth_user_id": user_id,
            "email": (email or defaults.get("email") or "").strip().lower(),
            "normalized_email": (email or defaults.get("normalized_email") or defaults.get("email") or "").strip().lower(),
            "username": username or defaults.get("username"),
            "full_name": defaults.get("full_name") or username,
            "display_name": defaults.get("display_name") or defaults.get("full_name") or username,
            "phone": defaults.get("phone"),
            "email_verified": False,
            "is_verified": False,
            "profile_completed": False,
        }
        self.rows[user_id] = row
        return row, None

    def supabase_invalid(self):
        supabase = MagicMock()
        supabase.auth.sign_up.side_effect = Exception('Email address "king@gmail.com" is invalid')
        return supabase

    def run(self):
        from app import create_app
        from services.auth_service import _email_valid_format, register_chain_user

        valid_emails = [
            "king@gmail.com",
            "person@yahoo.com",
            "member@outlook.com",
            "user.name+tag@gmail.com",
            "contact@namibia.com.na",
            "resident@iway.na",
        ]
        for email in valid_emails:
            self.check(f"local validation accepts {email}", _email_valid_format(email), "local regex rejected valid email")
        self.check("king@gmail.com passes local validation", _email_valid_format("king@gmail.com"))

        patches = [
            patch("services.auth_service.get_supabase", return_value=self.supabase_invalid()),
            patch("services.auth_service.fast_query", return_value=[]),
            patch("services.auth_service.get_auth_user_by_email", return_value=None),
            patch("services.profile_service.ensure_profile_for_user", side_effect=self.fake_ensure_profile_for_user),
        ]

        with patches[0], patches[1], patches[2], patches[3]:
            direct = register_chain_user(
                " KING@gmail.com ",
                "Phase79Pass!",
                " king_user ",
                " King User ",
                extra={"terms_accepted": True, "phone": " 0812345678 "},
            )
            self.check("Supabase invalid valid email falls back locally", direct.get("ok") is True, str(direct))
            self.check("Fallback provider is local_fallback", direct.get("auth_provider") == "local_fallback", str(direct))
            self.check("Normalized email is lowercased", (direct.get("profile") or {}).get("email") == "king@gmail.com", str(direct.get("profile")))
            self.check("Registration redirects after fallback", direct.get("redirect_to") == "/profile/", str(direct))
            self.check("No email invalid returned from fallback", "invalid" not in str(direct.get("error") or "").lower(), str(direct))

        app = create_app()
        app.config["TESTING"] = True
        apk_ua = "Mozilla/5.0 (Linux; Android 14; NamVibe APK) AppleWebKit/537.36 wv Capacitor"

        with patch("services.auth_service.get_supabase", return_value=self.supabase_invalid()), \
             patch("services.auth_service.fast_query", return_value=[]), \
             patch("services.auth_service.get_auth_user_by_email", return_value=None), \
             patch("services.profile_service.ensure_profile_for_user", side_effect=self.fake_ensure_profile_for_user):
            client = app.test_client()
            get_resp = client.get("/auth/register", headers={"User-Agent": apk_ua, "Host": "192.168.179.30:5000"})
            html = get_resp.get_data(as_text=True)
            import re
            match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
            csrf = match.group(1) if match else ""
            post_resp = client.post(
                "/auth/register",
                data={
                    "csrf_token": csrf,
                    "full_name": "King User",
                    "email": " king@gmail.com ",
                    "username": " king_apk ",
                    "password": "Phase79Pass!",
                    "confirm_password": "Phase79Pass!",
                    "terms": "on",
                },
                headers={"User-Agent": apk_ua, "Host": "192.168.179.30:5000"},
                follow_redirects=False,
            )
            body = post_resp.get_data(as_text=True)
            self.check("APK-style registration redirects", post_resp.status_code in (302, 303), f"status {post_resp.status_code} body {body[:200]}")
            self.check("APK-style registration does not show email invalid", "email address" not in body.lower() and "invalid" not in body.lower(), body[:300])
            self.check("APK-style registration location is profile", post_resp.headers.get("Location") == "/profile/", str(post_resp.headers))

        print(f"Passed: {self.passes} Failed: {self.fails}")
        if self.errors:
            print("\n".join(self.errors))
        return 1 if self.fails else 0


if __name__ == "__main__":
    sys.exit(Phase79ApkRegisterEmail().run())
