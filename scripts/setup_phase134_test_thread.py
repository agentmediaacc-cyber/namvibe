#!/usr/bin/env python3
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from phase134_test_auth_utils import (
    get_credentials, has_credentials, load_context, login, make_session,
    print_header, request_json, Results, save_context, unique_test_id, warn_missing_credentials,
)

R = Results()
print_header("PHASE 134 - TEST THREAD SETUP")

if not has_credentials():
    warn_missing_credentials(R)
    R.warn("test thread setup skipped safely")
else:
    creds = get_credentials()
    s = make_session()
    response = login(s, creds["user_a"])
    if response.status_code not in (200, 302) or "/auth/login" in response.url:
        R.fail(f"user A login failed ({response.status_code})")
    else:
        R.ok("user A login works")
        target = creds["user_b"].get("username") or creds["user_b"].get("email")
        found = False
        for endpoint in (f"/calls/api/contacts/search?q={target}", f"/messages/api/search?q={target}", f"/api/search/users?q={target}"):
            res, data = request_json(s, "GET", endpoint)
            if res.status_code in (200, 401, 403):
                R.ok(f"contact/search endpoint checked: {endpoint}")
                if data.get("contacts") or data.get("users") or data.get("results"):
                    found = True
                    break
            elif res.status_code == 404:
                R.warn(f"search endpoint unavailable: {endpoint}")
            else:
                R.fail(f"search endpoint {endpoint} returned {res.status_code}")
        context = load_context()
        context.update({
            "test_id": context.get("test_id") or unique_test_id(),
            "thread_id": context.get("thread_id") or os.environ.get("NAMVIBE_TEST_THREAD_ID"),
            "user_a": creds["user_a"].get("username") or creds["user_a"].get("email"),
            "user_b": creds["user_b"].get("username") or creds["user_b"].get("email"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        save_context(context)
        R.ok("tmp/phase134_test_context.json saved without passwords")
        if context.get("thread_id"):
            R.ok("test thread id available")
        else:
            R.warn("test thread id not created automatically; set NAMVIBE_TEST_THREAD_ID or create a disposable thread manually")
        if not found:
            R.warn("user B was not resolved through safe search endpoints")

R.summary("PHASE 134 - TEST THREAD SETUP")

