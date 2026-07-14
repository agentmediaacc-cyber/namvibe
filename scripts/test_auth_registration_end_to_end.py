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


def fake_user(uid="11111111-1111-4111-8111-111111111111", email="person@example.com", confirmed=False):
    user = Mock()
    user.id = uid
    user.email = email
    user.user_metadata = {"username": "person", "full_name": "Person Example"}
    user.email_confirmed_at = "now" if confirmed else None
    user.confirmed_at = "now" if confirmed else None
    return user


def main():
    from app import create_app
    from services.auth_service import register_chain_user

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    with app.test_client() as client:
        resp = client.get("/auth/register")
        check("Registration page returns 200", resp.status_code == 200, resp.status_code)

    no_session_res = Mock(user=fake_user(), session=None)
    with patch("services.auth_service.get_supabase") as get_supabase, patch(
        "services.auth_service.provision_profile_for_auth_user",
        return_value=({"id": "profile-1", "auth_user_id": fake_user().id, "profile_completed": False}, None),
    ) as provision:
        get_supabase.return_value.auth.sign_up.return_value = no_session_res
        result = register_chain_user("Person@Example.com", "goodpassword", "person", "Person Example", {"terms_accepted": True})
        check("Valid registration calls Supabase once", get_supabase.return_value.auth.sign_up.call_count == 1)
        check("Confirmation-required response treated as success", result.get("ok") and result.get("requires_confirmation") is True, result)
        defaults = provision.call_args.kwargs.get("metadata") or {}
        check("Password is never written to Neon", "password_hash" not in defaults and "password" not in defaults, defaults)

    with patch("services.auth_service._check_email_username_phone_taken", return_value="EMAIL_EXISTS"), patch(
        "services.auth_service.get_supabase"
    ) as get_supabase:
        result = register_chain_user("person@example.com", "goodpassword", "person", "Person Example", {"terms_accepted": True})
        check("Existing email does not call Supabase signup", get_supabase.return_value.auth.sign_up.call_count == 0)
        check("Existing email does not create duplicate profile", result.get("error") == "EMAIL_EXISTS", result)

    with patch("api_routes.auth_routes.register_chain_user") as register_mock:
        register_mock.return_value = {
            "ok": True,
            "requires_confirmation": True,
            "profile": {"id": "profile-1", "auth_user_id": fake_user().id, "profile_completed": False},
            "auth_user_id": fake_user().id,
        }
        with app.test_client() as client:
            resp = client.post(
                "/auth/register",
                data={
                    "full_name": "Person Example",
                    "email": "person@example.com",
                    "username": "person",
                    "password": "goodpassword",
                    "confirm_password": "goodpassword",
                    "terms": "on",
                },
            )
            body = resp.data.decode("utf-8", errors="replace")
            check("Unverified registration shows check email page", resp.status_code == 200 and "Check Your Email" in body)

    print(f"\nRESULT {PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
