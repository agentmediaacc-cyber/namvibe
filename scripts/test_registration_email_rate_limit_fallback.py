import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    os.environ["FLASK_ENV"] = "development"
    os.environ["ENV"] = "development"

    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    client = app.test_client()

    fake_rows = {}
    email = f"rate_limit_{uuid.uuid4().hex[:10]}@gmail.com"
    username = f"ratelimit_{uuid.uuid4().hex[:8]}"

    def fake_ensure_profile(auth_user_id, defaults=None):
        defaults = defaults or {}
        row = {
            **defaults,
            "id": str(uuid.uuid4()),
            "auth_user_id": auth_user_id,
            "email": defaults.get("email") or email,
            "username": defaults.get("username") or username,
            "email_verified": False,
            "is_verified": False,
        }
        fake_rows[auth_user_id] = row
        return row, None

    def fake_update_profile(profile_id, payload):
        for row in fake_rows.values():
            if row.get("id") == profile_id:
                row.update(payload)
                return row
        return None

    supabase = MagicMock()
    supabase.auth.sign_up.side_effect = Exception("email rate limit exceeded")

    form = {
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "username": username,
        "full_name": "Rate Limit Tester",
        "phone_code": "+264",
        "phone": "811234567",
        "date_of_birth": "1995-01-01",
        "country_origin": "Namibia",
        "region": "Khomas",
        "town": "Windhoek",
        "preferred_language": "English",
        "terms": "on",
        "human_confirmed": "on",
        "profile_type": "member",
    }

    with patch("services.auth_service.get_supabase", return_value=supabase), \
        patch("services.auth_service.get_auth_user_by_email", return_value=None), \
        patch("services.auth_service.safe_select", return_value=[]), \
        patch("services.auth_service._supabase_auth_email_exists", return_value=False), \
        patch("services.auth_service._profile_exists_by_username", return_value=False), \
        patch("services.auth_service.ensure_neon_profile", side_effect=fake_ensure_profile), \
        patch("services.profile_service._neon_update_profile", side_effect=fake_update_profile):

        response = client.post("/auth/register", data=form, follow_redirects=False)

    print("registration_status", response.status_code)
    print("registration_location", response.headers.get("Location"))
    assert response.status_code == 302, response.get_data(as_text=True)[:500]
    assert response.headers.get("Location") in {"/profile/", "/profile/onboarding"}

    with client.session_transaction() as sess:
        auth_user_id = sess.get("auth_user_id")
        profile_id = sess.get("profile_id")
        print("session_auth_user_id", auth_user_id)
        print("session_profile_id", profile_id)
        print("session_email", sess.get("email"))
        assert auth_user_id
        assert profile_id
        assert sess.get("user_id") == auth_user_id
        assert sess.get("email") == email

    row = fake_rows.get(auth_user_id)
    print("profile_row_exists", bool(row))
    print("profile_email_verified", row.get("email_verified") if row else None)
    print("profile_is_verified", row.get("is_verified") if row else None)
    print("profile_completed", row.get("profile_completed") if row else None)
    assert row and row.get("id") == profile_id
    assert row.get("email_verified") is False
    assert row.get("is_verified") is False

    with patch("api_routes.profile_routes.get_current_profile", return_value=row), \
        patch("api_routes.profile_routes.verify_profile_age", return_value=(True, None)), \
        patch("api_routes.profile_routes.is_profile_complete", return_value=True), \
        patch("api_routes.profile_routes.get_profile_bundle", return_value={"profile": row}), \
        patch("api_routes.profile_routes.build_profile_dashboard", return_value={"profile": row}), \
        patch("api_routes.profile_routes.get_my_notifications", return_value=([], [], 0)), \
        patch("api_routes.profile_routes.render_template", return_value="Not Verified"):

        profile_response = client.get("/profile/", follow_redirects=False)

    profile_body = profile_response.get_data(as_text=True)
    print("profile_status", profile_response.status_code)
    print("profile_shows_not_verified", "Not Verified" in profile_body)
    assert profile_response.status_code == 200
    assert "Not Verified" in profile_body


if __name__ == "__main__":
    main()
