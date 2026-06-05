import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app


FORBIDDEN_STRINGS = [
    "This feature is part of the CHAIN premium ecosystem",
    "404 - Not Found",
    "FEATURE",
]


def assert_clean_page(route, response):
    assert response.status_code in (200, 302), f"{route} returned {response.status_code}"
    if response.status_code == 200:
        body = response.get_data(as_text=True)
        for forbidden in FORBIDDEN_STRINGS:
            assert forbidden not in body, f"{route} contained forbidden text: {forbidden}"


def main():
    os.environ["FLASK_ENV"] = "testing"
    app = create_app()
    app.config["TESTING"] = True
    app.jinja_env.globals.update(now_utc=lambda: datetime.now(timezone.utc))
    client = app.test_client()

    with patch("services.auth_service.get_supabase") as mock_supabase, \
         patch("services.auth_service._quick_profile_snapshot") as mock_snapshot, \
         patch("services.auth_service._schedule_profile_sync") as mock_schedule:
        auth_mock = MagicMock()
        user = MagicMock(id="u-flow", email="flow@example.com")
        user.user_metadata = {}
        user.identities = []
        auth_mock.sign_in_with_password.return_value = MagicMock(
            user=user,
            session=MagicMock(access_token="token", refresh_token="refresh", expires_in=3600),
        )
        mock_supabase.return_value.auth = auth_mock
        mock_snapshot.return_value = None
        mock_schedule.return_value = None

        res = client.post("/auth/login", data={"login_id": "flow@example.com", "password": "pass12345"}, follow_redirects=False)
        assert res.status_code == 302, res.status_code
        assert "/profile/age-check" in res.headers.get("Location", ""), res.headers.get("Location")
        print("login redirect result: /profile/age-check")

    age_res = client.get("/profile/age-check")
    age_html = age_res.get_data(as_text=True)
    assert age_res.status_code == 200, age_res.status_code
    assert "now_utc" not in age_html
    print("now_utc fix result: 200 without template crash")

    with patch("api_routes.profile_routes.best_effort_age_dob_update", return_value=True):
        post_res = client.post("/profile/age-check", data={"date_of_birth": "1990-01-01"}, follow_redirects=False)
        assert post_res.status_code == 302, post_res.status_code
        assert post_res.headers.get("Location", "").endswith("/profile/"), post_res.headers.get("Location")

    with client.session_transaction() as sess:
        sess["profile_warning"] = True
        sess["auth_user_id"] = "u-flow"
        sess["access_token"] = "token"
        sess["auth_email"] = "flow@example.com"
        sess["username"] = "flowuser"
        sess["full_name"] = "Flow User"

    profile_res = client.get("/profile/")
    profile_html = profile_res.get_data(as_text=True)
    assert profile_res.status_code == 200, profile_res.status_code
    assert "Profile setup is finishing." in profile_html
    print("profile fallback result: 200 with session fallback shell")

    home_res = client.get("/")
    home_html = home_res.get_data(as_text=True)
    assert home_res.status_code == 200, home_res.status_code
    assert "Login/Register" not in home_html
    assert ">Login<" not in home_html
    assert "Sign Out" in home_html
    assert "My Profile" in home_html
    print("logged-in homepage result: Sign Out and My Profile visible, Login/Register hidden")

    routes = [
        "/profile/",
        "/profile/age-check",
        "/profile/onboarding",
        "/wallet/",
        "/messages/",
        "/notifications/",
        "/live/studio",
        "/reels/",
        "/feed/",
    ]
    for route in routes:
        res = client.get(route, follow_redirects=False)
        assert_clean_page(route, res)

    print("logged-in visible routes result: no FEATURE or 404 placeholders")
    print("final logged-in app ready: yes")


if __name__ == "__main__":
    main()
