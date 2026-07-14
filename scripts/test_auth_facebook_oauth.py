#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ["FACEBOOK_OAUTH_ENABLED"] = "true"
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
    from services.auth_service import handle_oauth_callback

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    with patch("api_routes.auth_routes.get_oauth_url", return_value="https://supabase.test/authorize?provider=facebook"):
        with app.test_client() as client:
            resp = client.get("/auth/facebook")
            check("Facebook start route uses safe callback", resp.status_code == 302 and "supabase.test" in (resp.headers.get("Location") or ""))

    user = Mock(id="22222222-2222-4222-8222-222222222222", email=None, user_metadata={"name": "Facebook User"})
    auth_session = Mock(access_token="a", refresh_token="r", expires_in=3600)
    with patch("services.auth_service.get_supabase") as get_supabase, patch(
        "services.auth_service.provision_profile_for_auth_user",
        return_value=({"id": "profile-2", "auth_user_id": user.id, "username": "facebookuser", "profile_completed": False}, None),
    ):
        get_supabase.return_value.auth.exchange_code_for_session.return_value = Mock(user=user, session=auth_session)
        ok, result = handle_oauth_callback("facebook", {"code": "abc", "state": "s1"}, mode="login", expected_state="s1")
        check("Missing Facebook email is handled safely", ok and result == "/profile/onboarding", result)

    print(f"\nRESULT {PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
