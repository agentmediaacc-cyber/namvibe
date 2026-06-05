import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    os.environ["FLASK_ENV"] = "development"
    os.environ["ENV"] = "development"
    os.environ["CHAIN_FAST_LOCAL"] = "1"

    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    auth_user_id = str(uuid.uuid4())
    email = f"reglogin_{uuid.uuid4().hex[:10]}@example.com"
    username = f"reglogin_{uuid.uuid4().hex[:8]}"
    password = "Password123!"
    fake_rows = {}

    def fake_ensure_profile(uid, defaults=None):
        defaults = defaults or {}
        row = fake_rows.get(uid)
        if not row:
            row = {
                "id": str(uuid.uuid4()),
                "auth_user_id": uid,
                "email": defaults.get("email"),
                "normalized_email": defaults.get("normalized_email") or defaults.get("email"),
                "username": defaults.get("username"),
                "full_name": defaults.get("full_name"),
                "display_name": defaults.get("display_name") or defaults.get("full_name"),
                "phone": defaults.get("phone"),
                "country_origin": defaults.get("country_origin"),
                "current_country": defaults.get("current_country") or defaults.get("country"),
                "country": defaults.get("country") or defaults.get("current_country"),
                "region": defaults.get("region"),
                "town": defaults.get("town"),
                "email_verified": False,
                "is_verified": False,
                "profile_completed": True,
            }
            fake_rows[uid] = row
        row.update({key: value for key, value in defaults.items() if value is not None})
        row["auth_user_id"] = uid
        return row, None

    def fake_update_profile(profile_id, payload):
        for row in fake_rows.values():
            if row.get("id") == profile_id:
                row.update({key: value for key, value in payload.items() if value is not None})
                return row
        return None

    def fake_safe_select(table, columns="*", limit=20, filters=None, order_by="created_at", desc=True):
        if table != "chain_profiles":
            return []
        filters = filters or {}
        for row in fake_rows.values():
            if all(row.get(key) == value for key, value in filters.items()):
                return [row]
        return []

    supabase = MagicMock()
    supabase.auth.sign_up.return_value = SimpleNamespace(
        user=SimpleNamespace(id=auth_user_id, email=email, user_metadata={}),
        session=None,
    )
    supabase.auth.sign_in_with_password.side_effect = Exception("email not confirmed")

    form = {
        "email": email,
        "password": password,
        "confirm_password": password,
        "username": username,
        "full_name": "Register Login Tester",
        "phone_code": "+264",
        "phone": "811234567",
        "country_origin": "Namibia",
        "current_country": "Namibia",
        "region": "Khomas",
        "town": "Windhoek",
        "agreement_true_details": "on",
        "agreement_identity_use": "on",
        "agreement_username_privacy": "on",
        "agreement_standards": "on",
        "agreement_no_abuse": "on",
        "terms": "on",
        "human_confirmed": "on",
        "profile_type": "member",
    }

    patches = [
        patch("services.auth_service.get_supabase", return_value=supabase),
        patch("services.auth_service.get_auth_user_by_email", return_value=None),
        patch("services.auth_service.safe_select", side_effect=fake_safe_select),
        patch("services.auth_service._supabase_auth_email_exists", return_value=False),
        patch("services.auth_service._profile_exists_by_username", return_value=False),
        patch("services.auth_service.ensure_neon_profile", side_effect=fake_ensure_profile),
        patch("services.auth_service._ensure_profile_dependencies", return_value=None),
        patch("services.profile_service._neon_update_profile", side_effect=fake_update_profile),
        patch("services.profile_service.get_profile_by_username", side_effect=lambda value: next((row for row in fake_rows.values() if row.get("username") == value), None)),
        patch("services.profile_service.get_current_profile", side_effect=lambda: next(iter(fake_rows.values()), None)),
        patch("api_routes.profile_routes.get_current_profile", side_effect=lambda: next(iter(fake_rows.values()), None)),
        patch("api_routes.profile_routes.verify_profile_age", return_value=(True, None)),
        patch("api_routes.profile_routes.is_profile_complete", return_value=True),
        patch("api_routes.profile_routes.get_profile_bundle", side_effect=lambda *args, **kwargs: {"profile": next(iter(fake_rows.values()), None)}),
        patch("api_routes.profile_routes.build_profile_dashboard", side_effect=lambda *args, **kwargs: {"profile": kwargs.get("profile") or (args[0] if args else None)}),
        patch("api_routes.profile_routes.get_my_notifications", return_value=([], [], 0)),
        patch("api_routes.profile_routes.render_template", return_value="Not Verified"),
    ]

    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9], patches[10], patches[11], patches[12], patches[13], patches[14], patches[15], patches[16]:
        register_response = client.post("/auth/register", data=form, follow_redirects=False)
        print("register_status", register_response.status_code)
        print("register_location", register_response.headers.get("Location"))
        assert register_response.status_code == 302, register_response.get_data(as_text=True)[:500]
        assert register_response.headers.get("Location") == "/profile/"

        with client.session_transaction() as sess:
            print("register_session_auth_user_id", sess.get("auth_user_id"))
            print("register_session_user_id", sess.get("user_id"))
            print("register_session_profile_id", sess.get("profile_id"))
            print("register_session_email", sess.get("email"))
            assert sess.get("auth_user_id") == auth_user_id
            assert sess.get("user_id") == auth_user_id
            assert sess.get("profile_id")
            assert sess.get("email") == email

        profile_row = next(iter(fake_rows.values()), None)
        print("profile_row_exists", bool(profile_row))
        assert profile_row
        assert profile_row.get("auth_user_id") == auth_user_id
        assert profile_row.get("email") == email
        assert profile_row.get("username") == username
        assert profile_row.get("full_name") == "Register Login Tester"
        assert profile_row.get("phone") == "+264811234567"
        assert profile_row.get("country_origin") == "Namibia"
        assert profile_row.get("country") == "Namibia"
        assert profile_row.get("region") == "Khomas"
        assert profile_row.get("town") == "Windhoek"
        assert profile_row.get("email_verified") is False
        assert profile_row.get("is_verified") is False

        client.get("/auth/logout")
        username_login = client.post("/auth/login", data={"login_id": username, "password": password}, follow_redirects=False)
        username_body = username_login.get_data(as_text=True)
        print("username_login_status", username_login.status_code)
        print("username_login_location", username_login.headers.get("Location"))
        assert "Username not found" not in username_body
        assert username_login.status_code == 302
        assert username_login.headers.get("Location") == "/profile/"
        with client.session_transaction() as sess:
            assert sess.get("profile_id") == profile_row.get("id")

        client.get("/auth/logout")
        email_login = client.post("/auth/login", data={"login_id": email, "password": password}, follow_redirects=False)
        print("email_login_status", email_login.status_code)
        print("email_login_location", email_login.headers.get("Location"))
        assert email_login.status_code == 302
        assert email_login.headers.get("Location") == "/profile/"
        with client.session_transaction() as sess:
            assert sess.get("profile_id") == profile_row.get("id")

        profile_response = client.get("/profile/", follow_redirects=False)
        print("profile_status", profile_response.status_code)
        assert profile_response.status_code == 200


if __name__ == "__main__":
    main()
