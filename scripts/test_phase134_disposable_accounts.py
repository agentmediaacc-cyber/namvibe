#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from phase134_test_auth_utils import (
    full_url, get_credentials, has_credentials, login, make_session,
    manual_account_instructions, print_header, Results, warn_missing_credentials,
)

R = Results()
print_header("PHASE 134 - DISPOSABLE ACCOUNT CHECK")

session = make_session()
try:
    response = session.get(full_url("/auth/login"), timeout=30)
    R.ok("login page reachable") if response.status_code == 200 else R.fail(f"login page returned {response.status_code}")
except Exception as exc:
    R.fail(f"login page request failed: {exc}")

if not has_credentials():
    warn_missing_credentials(R)
    R.warn(manual_account_instructions())
else:
    creds = get_credentials()
    for key in ("user_a", "user_b"):
        user = creds[key]
        s = make_session()
        response = login(s, user)
        if response.status_code in (200, 302) and "/auth/login" not in response.url:
            R.ok(f"{key} login works")
        else:
            R.fail(f"{key} login failed with status {response.status_code}")
        profile = s.get(full_url("/profile/"), timeout=30, allow_redirects=True)
        R.ok(f"{key} /profile/ loads") if profile.status_code == 200 else R.fail(f"{key} /profile/ returned {profile.status_code}")
        body = profile.text.lower()
        if user.get("username", "").lower() in body or "profile" in body:
            R.ok(f"{key} session identity detectable")
        else:
            R.warn(f"{key} session identity not obvious in /profile/")
        if (user.get("username") or "").startswith("phase134_"):
            R.ok(f"{key} username has disposable prefix")
        else:
            R.warn(f"{key} username is not phase134-prefixed; verify account is disposable")

R.summary("PHASE 134 - DISPOSABLE ACCOUNT CHECK")

