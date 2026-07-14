#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ["GOOGLE_OAUTH_ENABLED"] = "true"
os.environ["SUPABASE_SITE_URL"] = "https://namvibe.com"
os.environ["SUPABASE_AUTH_REDIRECT_URL"] = "https://namvibe.com/auth/callback"

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

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    with patch("api_routes.auth_routes.get_oauth_url", return_value="https://supabase.test/authorize?provider=google") as oauth:
        with app.test_client() as client:
            resp = client.get("/auth/google")
            check("Google start route uses safe callback", resp.status_code == 302 and "supabase.test" in (resp.headers.get("Location") or ""))
            state = None
            with client.session_transaction() as sess:
                state = sess.get("oauth_state")
            check("Google start route stores oauth state", bool(state))
            check("Google start route passes generated state", oauth.call_args.kwargs.get("state") == state, oauth.call_args)

    user = Mock(id="11111111-1111-4111-8111-111111111111", email="google@example.com", user_metadata={})
    auth_session = Mock(access_token="a", refresh_token="r", expires_in=3600)
    with patch("services.auth_service.get_supabase") as get_supabase, patch(
        "services.auth_service.provision_profile_for_auth_user",
        return_value=({"id": "profile-1", "auth_user_id": user.id, "profile_completed": True}, None),
    ) as provision:
        get_supabase.return_value.auth.exchange_code_for_session.return_value = Mock(user=user, session=auth_session)
        from services.auth_service import handle_oauth_callback

        ok, result = handle_oauth_callback("google", {"code": "abc", "state": "state1"}, mode="login", expected_state="state1")
        check("Existing OAuth user does not create duplicate profile", ok and provision.call_count == 1, result)

    print(f"\nRESULT {PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
