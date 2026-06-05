import os
import sys
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app


def _assert_under(label, elapsed_ms, budget_ms):
    print(f"{label}: {elapsed_ms:.1f}ms (budget {budget_ms}ms)")
    assert elapsed_ms < budget_ms, f"{label} exceeded budget: {elapsed_ms:.1f}ms >= {budget_ms}ms"


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
        auth_mock.sign_in_with_password.return_value = MagicMock(
            user=MagicMock(id="u-login", email="speed@example.com", user_metadata={}),
            session=MagicMock(access_token="token", refresh_token="refresh", expires_in=3600),
        )
        mock_supabase.return_value.auth = auth_mock

        def slow_snapshot(*args, **kwargs):
            time.sleep(0.35)
            return None

        mock_snapshot.side_effect = slow_snapshot
        mock_schedule.return_value = None

        started = time.perf_counter()
        login_res = client.post(
            "/auth/login",
            data={"login_id": "speed@example.com", "password": "pass12345"},
            follow_redirects=False,
        )
        login_elapsed_ms = (time.perf_counter() - started) * 1000
        assert login_res.status_code == 302, f"login status={login_res.status_code}"
        assert "/profile/age-check" in login_res.headers.get("Location", ""), login_res.headers.get("Location")
        _assert_under("login speed result", login_elapsed_ms, 800)

    with client.session_transaction() as sess:
        sess["auth_user_id"] = "u-login"
        sess["access_token"] = "token"
        sess["age_check_required"] = True
        sess["username"] = "speeduser"
        sess["full_name"] = "Speed User"
        sess["auth_email"] = "speed@example.com"

    started = time.perf_counter()
    age_res = client.get("/profile/age-check")
    age_elapsed_ms = (time.perf_counter() - started) * 1000
    assert age_res.status_code == 200, f"age-check status={age_res.status_code}"
    _assert_under("age-check speed result", age_elapsed_ms, 300)

    with client.session_transaction() as sess:
        sess.clear()

    started = time.perf_counter()
    unread_res = client.get("/api/notifications/unread-count")
    unread_elapsed_ms = (time.perf_counter() - started) * 1000
    unread_payload = unread_res.get_json() or {}
    assert unread_res.status_code == 200, f"unread status={unread_res.status_code}"
    assert unread_payload.get("count") == 0, unread_payload
    _assert_under("unread-count optimization result", unread_elapsed_ms, 300)

    with client.session_transaction() as sess:
        sess.clear()
        sess["auth_user_id"] = "u-fallback"
        sess["access_token"] = "token"
        sess["profile_warning"] = True
        sess["username"] = "fallbackuser"
        sess["full_name"] = "Fallback User"
        sess["auth_email"] = "fallback@example.com"

    started = time.perf_counter()
    fallback_res = client.get("/profile/")
    fallback_elapsed_ms = (time.perf_counter() - started) * 1000
    fallback_html = fallback_res.get_data(as_text=True)
    assert fallback_res.status_code == 200, f"fallback status={fallback_res.status_code}"
    assert "Profile setup is finishing." in fallback_html
    _assert_under("profile fallback result", fallback_elapsed_ms, 800)

    print("final local login ready: yes")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"test_login_speed failed: {error}")
        raise
