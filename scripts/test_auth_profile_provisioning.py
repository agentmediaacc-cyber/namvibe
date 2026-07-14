#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("CHAIN_FAST_LOCAL", "1")

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


def auth_user():
    return SimpleNamespace(
        id="11111111-1111-4111-8111-111111111111",
        email="person@example.com",
        user_metadata={"username": "person", "full_name": "Person Example"},
        email_confirmed_at="now",
        confirmed_at="now",
    )


def main():
    from services.auth_service import provision_profile_for_auth_user

    existing = {"id": "profile-1", "auth_user_id": auth_user().id, "username": "person", "email": "person@example.com"}
    with patch("services.profile_service._neon_get_profile_by", return_value=existing), patch(
        "services.profile_service._neon_update_profile", return_value=existing
    ), patch("services.profile_service._neon_insert_profile") as insert_mock:
        profile, error = provision_profile_for_auth_user(auth_user(), metadata={"username": "person"})
        check("Profile provisioning returns existing profile", profile == existing and error is None)
        check("Profile provisioning is idempotent", insert_mock.call_count == 0)

    inserted = {"id": "profile-2", "auth_user_id": auth_user().id, "username": "person2", "email": "person@example.com"}
    with patch("services.profile_service.ensure_profile_for_user", return_value=(inserted, None)):
        profile, error = provision_profile_for_auth_user(auth_user(), metadata={"username": "person2"})
        check("Missing Neon profile is provisioned safely", profile == inserted and error is None)

    print(f"\nRESULT {PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
