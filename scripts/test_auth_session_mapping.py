#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")

PASS = 0
FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        print(f"FAIL {name} {detail}")


def main():
    from app import create_app
    from services.ai.config import get_ai_config

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    auth_res = Mock(
        user=Mock(id="11111111-1111-4111-8111-111111111111", email="person@example.com", user_metadata={}),
        session=Mock(access_token="a", refresh_token="r", expires_in=3600),
    )
    profile = {"id": "profile-1", "auth_user_id": auth_res.user.id, "username": "person", "profile_completed": True}

    with patch("services.auth_service.get_supabase") as get_supabase, patch(
        "services.auth_service.provision_profile_for_auth_user",
        return_value=(profile, None),
    ):
        get_supabase.return_value.auth.sign_in_with_password.return_value = auth_res
        with app.test_client() as client:
            resp = client.post("/auth/login", data={"login_id": "person@example.com", "password": "goodpassword"})
            check("Email login resolves correct profile", resp.status_code == 302, resp.status_code)
            with client.session_transaction() as sess:
                check("Flask session contains authoritative identifiers", sess.get("auth_user_id") == auth_res.user.id and sess.get("profile_id") == profile["id"], dict(sess))
            logout_resp = client.get("/auth/logout")
            check("Logout clears authentication state", logout_resp.status_code == 302)
            with client.session_transaction() as sess:
                check("Session cleared after logout", not sess.get("auth_user_id") and not sess.get("profile_id"), dict(sess))

    with patch("services.auth_service.get_supabase") as get_supabase:
        get_supabase.return_value.auth.sign_in_with_password.side_effect = Exception("invalid login credentials")
        with app.test_client() as client:
            resp = client.post("/auth/login", data={"login_id": "person@example.com", "password": "badpassword"})
            with client.session_transaction() as sess:
                check("Invalid password does not create a session", not sess.get("auth_user_id") and resp.status_code == 200, dict(sess))

    with app.test_client() as client:
        resp = client.get("/profile/", follow_redirects=False)
        check("Existing protected routes still require authentication", resp.status_code in (302, 303), resp.status_code)

    cfg = get_ai_config()
    check("Recommendations remain disabled", cfg.recommendations_enabled is False)
    check("External AI remains disabled", cfg.external_calls_enabled is False)

    print(f"\nRESULT {PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
