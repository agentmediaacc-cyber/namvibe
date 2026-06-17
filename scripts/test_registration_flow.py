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
os.environ["SECRET_KEY"] = "registration-flow-test-secret"


def main():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    client = app.test_client()

    rows_by_user = {}
    users_by_email = {}
    password = "StrongPass123!"
    email = f"signup_{uuid.uuid4().hex[:10]}@mail.test"
    username = f"user_{uuid.uuid4().hex[:8]}"
    auth_user_id = str(uuid.uuid4())

    def profile_for_email(value):
        for row in rows_by_user.values():
            if row.get("email") == value or row.get("normalized_email") == value:
                return row
        return None

    def profile_for_username(value):
        for row in rows_by_user.values():
            if row.get("username") == value:
                return row
        return None

    def fake_fast_query(sql, params=None, **kwargs):
        lowered = " ".join(str(sql).lower().split())
        params = params or ()
        if "select 'email' as taken_type" in lowered:
            dup_email, dup_username = params[0], params[1]
            if profile_for_email(dup_email):
                return [{"taken_type": "email"}]
            if profile_for_username(dup_username):
                return [{"taken_type": "username"}]
            return []
        return []

    def fake_find_login_profile(login_id, columns=None):
        key = (login_id or "").strip().lower()
        if "@" in key:
            return profile_for_email(key)
        return profile_for_username(key)

    def fake_ensure_profile_for_user(user_id, email=None, username=None, defaults=None):
        defaults = defaults or {}
        row = rows_by_user.get(user_id) or profile_for_email(email)
        if not row:
            row = {
                "id": str(uuid.uuid4()),
                "auth_user_id": user_id,
                "email": email or defaults.get("email"),
                "normalized_email": email or defaults.get("normalized_email") or defaults.get("email"),
                "username": username or defaults.get("username"),
                "full_name": defaults.get("full_name") or defaults.get("display_name") or username,
                "display_name": defaults.get("display_name") or defaults.get("full_name") or username,
                "bio": "",
                "phone": None,
                "town": None,
                "avatar_url": None,
                "email_verified": False,
                "is_verified": False,
                "profile_completion": 0,
                "profile_completed": False,
                "onboarding_step": "profile",
            }
        row.update({key: value for key, value in defaults.items() if value not in (None, "")})
        row["auth_user_id"] = user_id
        row["email"] = row.get("email") or email
        row["normalized_email"] = row.get("normalized_email") or row.get("email")
        row["username"] = row.get("username") or username
        row["profile_completed"] = False
        row["email_verified"] = False
        row["is_verified"] = False
        rows_by_user[user_id] = row
        return row, None

    supabase = MagicMock()

    def fake_sign_up(payload):
        sign_email = payload["email"]
        if sign_email in users_by_email:
            raise Exception("user_already_exists")
        user = SimpleNamespace(id=auth_user_id, email=sign_email, user_metadata=payload.get("options", {}).get("data", {}))
        users_by_email[sign_email] = user
        return SimpleNamespace(user=user, session=None)

    def fake_sign_in(payload):
        sign_email = payload["email"]
        if sign_email not in users_by_email:
            raise Exception("invalid login credentials")
        return SimpleNamespace(
            user=users_by_email[sign_email],
            session=SimpleNamespace(access_token="test-token", refresh_token="test-refresh"),
        )

    supabase.auth.sign_up.side_effect = fake_sign_up
    supabase.auth.sign_in_with_password.side_effect = fake_sign_in

    patches = [
        patch("services.auth_service.get_supabase", return_value=supabase),
        patch("services.auth_service.get_auth_user_by_email", return_value=None),
        patch("services.auth_service.fast_query", side_effect=fake_fast_query),
        patch("services.auth_service._find_login_profile", side_effect=fake_find_login_profile),
        patch("services.auth_service._quick_profile_snapshot", side_effect=lambda user, resolved_email=None, timeout_ms=300: profile_for_email(resolved_email)),
        patch("services.auth_service._ensure_profile_dependencies", return_value=None),
        patch("services.auth_service._schedule_profile_sync", return_value=None),
        patch("services.profile_service.ensure_profile_for_user", side_effect=fake_ensure_profile_for_user),
        patch("api_routes.profile_routes.get_current_profile", side_effect=lambda: rows_by_user.get(auth_user_id)),
        patch("api_routes.profile_routes.get_profile_bundle", side_effect=lambda *args, **kwargs: {"profile": rows_by_user.get(auth_user_id), "content": {"posts": [], "reels": [], "rooms": [], "stories": []}, "stats": {}}),
        patch("api_routes.profile_routes.build_profile_dashboard", side_effect=lambda **kwargs: {"profile": kwargs.get("profile"), "content": {"posts": [], "reels": [], "rooms": [], "stories": []}, "stats": {}}),
        patch("api_routes.profile_routes.get_my_notifications", return_value=([], [], 0)),
        patch("api_routes.profile_routes.render_template", return_value="profile ok"),
    ]

    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9], patches[10], patches[11], patches[12]:
        register = client.post(
            "/auth/register",
            data={
                "username": username,
                "email": email,
                "password": password,
                "confirm_password": password,
                "terms": "on",
            },
            follow_redirects=False,
        )
        body = register.get_data(as_text=True).lower()
        assert register.status_code == 302, body[:500]
        assert register.headers.get("Location") == "/profile/"
        assert "verify" not in body
        assert "email not found" not in body

        profile = rows_by_user.get(auth_user_id)
        assert profile, "profile row was not created"
        assert profile["email"] == email
        assert profile["username"] == username
        assert profile["email_verified"] is False
        assert profile["is_verified"] is False
        assert profile["profile_completed"] is False

        profile_page = client.get("/profile/", follow_redirects=False)
        assert profile_page.status_code == 200

        client.get("/auth/logout")
        login = client.post("/auth/login", data={"login_id": email, "password": password}, follow_redirects=False)
        login_body = login.get_data(as_text=True).lower()
        assert login.status_code == 302, login_body[:500]
        assert login.headers.get("Location") == "/profile/"
        assert "email not found" not in login_body

        duplicate = client.post(
            "/auth/register",
            data={
                "username": f"{username}_2",
                "email": email,
                "password": password,
                "confirm_password": password,
                "terms": "on",
            },
            follow_redirects=True,
        )
        duplicate_body = duplicate.get_data(as_text=True).lower()
        assert "already has" in duplicate_body or "already in use" in duplicate_body
        assert "email not found" not in duplicate_body

    print("PASS registration flow")
    print("PASS no verification required")
    print("PASS profile row created")
    print("PASS login works after registration")
    print("PASS incomplete profile does not block profile access")
    print("PASS duplicate email gives clear message")
    print("PASS no email-not-found after registration")
    return 0


if __name__ == "__main__":
    sys.exit(main())
