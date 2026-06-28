#!/usr/bin/env python3
"""
Phase Next +1 - NamVibe Real User Flow Audit.

Verifies that real app pages and API endpoints work after login/session fixes.
Uses Flask test_client - no external server needed.

Usage:
    python3 scripts/audit_namvibe_user_flows.py
"""

import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ.setdefault("CHAIN_DISABLE_SCHEDULER", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
os.environ["CHAIN_TEST_MODE"] = "1"

PASS = 0
FAIL = 0


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        print(f"  [+]  PASS  {label}")
        PASS += 1
    else:
        msg = f"  [X]  FAIL  {label}"
        if detail:
            msg += f"  - {detail}"
        print(msg)
        FAIL += 1


def is_redirect_to_login(resp):
    if resp.status_code in (301, 302, 303):
        location = resp.headers.get("Location", "")
        return "/auth/login" in location or "/login" in location
    return False


def is_json_response(resp):
    ct = resp.content_type or ""
    return "application/json" in ct or resp.is_json

def main():
    global PASS, FAIL

    print("=" * 60)
    print("  Phase Next +1 - NamVibe Real User Flow Audit")
    print("=" * 60)

    # 1. Import and create app
    print("\n--- 1. Create Flask app with test_client ---")
    try:
        from app import create_app
        app = create_app()
        print("  [import] app created successfully")
    except Exception as e:
        print(f"  [import] FAILED to create app: {e}")
        sys.exit(1)

    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    client = app.test_client()

    # 2. Page Routes
    print("\n--- 2. Page Routes (unauthenticated) ---")

    # 2a. /auth/login
    try:
        resp = client.get("/auth/login", follow_redirects=False)
        ok = resp.status_code == 200
        check("GET /auth/login -> 200", ok, f"got {resp.status_code}")
    except Exception as e:
        check("GET /auth/login", False, str(e))

    # 2b. /auth/register
    try:
        resp = client.get("/auth/register", follow_redirects=False)
        ok = resp.status_code == 200
        check("GET /auth/register -> 200", ok, f"got {resp.status_code}")
    except Exception as e:
        check("GET /auth/register", False, str(e))

    # 2c. /home (renders even when logged out)
    try:
        resp = client.get("/home", follow_redirects=False)
        ok = resp.status_code == 200
        check("GET /home -> 200", ok, f"got {resp.status_code}")
    except Exception as e:
        check("GET /home", False, str(e))

    # 2d. /messages/ (uses @login_required, expect 302 to /auth/login)
    try:
        resp = client.get("/messages/", follow_redirects=False)
        ok = resp.status_code == 200 or is_redirect_to_login(resp)
        check("GET /messages/ -> 200 or redirect to login", ok, f"got {resp.status_code}")
    except Exception as e:
        check("GET /messages/", False, str(e))

    # 2e. /profile/ (uses @login_required, expect 302 to /auth/login)
    try:
        resp = client.get("/profile/", follow_redirects=False)
        ok = resp.status_code == 200 or is_redirect_to_login(resp)
        check("GET /profile/ -> 200 or redirect to login", ok, f"got {resp.status_code}")
    except Exception as e:
        check("GET /profile/", False, str(e))

    # 2f. /discover/ (no login required)
    try:
        resp = client.get("/discover/", follow_redirects=False)
        ok = resp.status_code == 200
        check("GET /discover/ -> 200", ok, f"got {resp.status_code}")
    except Exception as e:
        check("GET /discover/", False, str(e))


    # 3. API Endpoints
    print("\n--- 3. API Endpoints (should return JSON, not HTML errors) ---")

    # 3a. /api/messages/unread-count
    try:
        resp = client.get("/api/messages/unread-count", follow_redirects=False)
        ok = True
        if resp.status_code == 500:
            ok = False
        elif is_redirect_to_login(resp):
            ok = True
        elif resp.status_code == 401 and is_json_response(resp):
            ok = True
        elif resp.status_code == 200 and is_json_response(resp):
            ok = True
        elif not is_json_response(resp):
            ok = False
        detail = f"status={resp.status_code}, ct={resp.content_type}"
        check("GET /api/messages/unread-count -> JSON or redirect", ok, detail)
    except Exception as e:
        check("GET /api/messages/unread-count", False, str(e))

    # 3b. /api/notifications/unread-count
    try:
        resp = client.get("/api/notifications/unread-count", follow_redirects=False)
        ok = True
        if resp.status_code == 500:
            ok = False
        elif is_redirect_to_login(resp):
            ok = True
        elif is_json_response(resp):
            ok = True
        else:
            ok = False
        detail = f"status={resp.status_code}, ct={resp.content_type}"
        check("GET /api/notifications/unread-count -> JSON or redirect", ok, detail)
    except Exception as e:
        check("GET /api/notifications/unread-count", False, str(e))

    # 3c. /api/homepage/feed
    try:
        resp = client.get("/api/homepage/feed", follow_redirects=False)
        ok = resp.status_code != 500 and is_json_response(resp)
        detail = f"status={resp.status_code}, ct={resp.content_type}"
        check("GET /api/homepage/feed -> JSON (not HTML error)", ok, detail)
    except Exception as e:
        check("GET /api/homepage/feed", False, str(e))

    # 3d. /api/homepage/stories
    try:
        resp = client.get("/api/homepage/stories", follow_redirects=False)
        ok = resp.status_code != 500 and is_json_response(resp)
        detail = f"status={resp.status_code}, ct={resp.content_type}"
        check("GET /api/homepage/stories -> JSON (not HTML error)", ok, detail)
    except Exception as e:
        check("GET /api/homepage/stories", False, str(e))

    # 3e. /api/homepage/reels
    try:
        resp = client.get("/api/homepage/reels", follow_redirects=False)
        ok = resp.status_code != 500 and is_json_response(resp)
        detail = f"status={resp.status_code}, ct={resp.content_type}"
        check("GET /api/homepage/reels -> JSON (not HTML error)", ok, detail)
    except Exception as e:
        check("GET /api/homepage/reels", False, str(e))

    # 4. Summary
    total = PASS + FAIL
    print(f"\n{'=' * 60}")
    if FAIL == 0:
        print(f"  ALL {total}/{total} CHECKS PASSED")
    else:
        print(f"  {PASS}/{total} PASSED, {FAIL} FAILED")
    print(f"{'=' * 60}\n")

    sys.exit(1 if FAIL > 0 else 0)


if __name__ == "__main__":
    main()

