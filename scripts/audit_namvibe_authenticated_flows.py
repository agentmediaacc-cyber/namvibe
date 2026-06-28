#!/usr/bin/env python3
"""
Phase Next +2 - NamVibe Authenticated Alpha/Beta Flow Audit.

Verifies logged-in user flows using alpha and beta test accounts.
Uses Flask test_client with session injection for authentication.

Rules:
  - No env keys changed
  - No database schema changes
  - No app.py rewrites
  - Uses existing test credentials from secrets/test_credentials.json
  - If beta account is missing, SKIP not FAIL
  - Fail only on login failure, 500 errors, invalid JSON, broken redirects

Usage:
    python3 scripts/audit_namvibe_authenticated_flows.py
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ.setdefault("CHAIN_DISABLE_SCHEDULER", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
os.environ["CHAIN_TEST_MODE"] = "1"

PASS = 0
FAIL = 0
SKIP = 0


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


def skip(label, detail=""):
    global SKIP
    msg = f"  [/]  SKIP  {label}"
    if detail:
        msg += f"  - {detail}"
    print(msg)
    SKIP += 1


def is_json_response(resp):
    ct = resp.content_type or ""
    return "application/json" in ct or resp.is_json


def login_client(app, profile_id, auth_user_id):
    """Create a test client with an authenticated session."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["profile_id"] = profile_id
        sess["auth_user_id"] = auth_user_id
        sess["user_id"] = auth_user_id
        sess["logged_in"] = True
    return client

def main():
    global PASS, FAIL, SKIP

    print("=" * 60)
    print("  Phase Next +2 - NamVibe Authenticated Alpha/Beta Flow Audit")
    print("=" * 60)

    # 1. Load credentials
    print("\n--- 1. Load Test Credentials ---")
    creds_path = ROOT / "secrets" / "test_credentials.json"
    if not creds_path.exists():
        print("  [X]  FAIL  test_credentials.json not found at secrets/test_credentials.json")
        sys.exit(1)

    creds = json.loads(creds_path.read_text())
    alpha_data = creds.get("chain_star", {})
    beta_data = creds.get("chain_moon", {})

    alpha_pid = alpha_data.get("profile_id", "")
    alpha_aid = alpha_data.get("auth_user_id", "")
    alpha_user = alpha_data.get("username", "chain_star")
    beta_pid = beta_data.get("profile_id", "")
    beta_aid = beta_data.get("auth_user_id", "")
    beta_user = beta_data.get("username", "chain_moon")
    has_beta = bool(beta_pid and beta_aid)

    if not alpha_pid or not alpha_aid:
        print("  [X]  FAIL  Alpha credentials (chain_star) incomplete - need profile_id and auth_user_id")
        sys.exit(1)

    print(f"  Alpha: username={alpha_user}, profile_id={alpha_pid[:8]}...")
    if has_beta:
        print(f"  Beta:  username={beta_user}, profile_id={beta_pid[:8]}...")
    else:
        print("  Beta:  NOT AVAILABLE (will SKIP beta-dependent checks)")

    # 2. Import and create app
    print("\n--- 2. Create Flask app ---")
    try:
        from app import create_app
        app = create_app()
        print("  [import] app created successfully")
    except Exception as e:
        print(f"  [import] FAILED to create app: {e}")
        sys.exit(1)

    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SERVER_NAME"] = "test.local"

    # 3. Login alpha user
    print("\n--- 3. Login Alpha User ---")
    try:
        alpha_client = login_client(app, alpha_pid, alpha_aid)
        # Verify session was set
        with alpha_client.session_transaction() as sess:
            sess_ok = sess.get("profile_id") == alpha_pid and sess.get("auth_user_id") == alpha_aid
        check("Alpha login (session set: profile_id + auth_user_id)", sess_ok)
    except Exception as e:
        check("Alpha login", False, str(e))
        sys.exit(1)

    # 4. Confirm session/auth status via debug endpoint
    print("\n--- 4. Confirm Session/Auth Status ---")
    try:
        resp = alpha_client.get("/auth/debug-session", follow_redirects=False)
        ok = resp.status_code == 200 and is_json_response(resp)
        if ok:
            data = resp.get_json() or {}
            has_profile = bool(data.get("profile_id") or data.get("session", {}).get("profile_id"))
            ok = has_profile
        check("GET /auth/debug-session -> JSON with profile_id", ok, f"status={resp.status_code}")
    except Exception as e:
        check("GET /auth/debug-session", False, str(e))


    # 5. Open /home (authenticated)
    print("\n--- 5. Open /home (authenticated) ---")
    try:
        resp = alpha_client.get("/home", follow_redirects=False)
        ok = resp.status_code == 200
        check("GET /home -> 200", ok, f"got {resp.status_code}")
    except Exception as e:
        check("GET /home", False, str(e))

    # 6. Open /profile/ (authenticated)
    print("\n--- 6. Open /profile/ (authenticated) ---")
    try:
        resp = alpha_client.get("/profile/", follow_redirects=False)
        ok = resp.status_code == 200
        check("GET /profile/ -> 200", ok, f"got {resp.status_code}")
    except Exception as e:
        check("GET /profile/", False, str(e))

    # 7. Open /messages/ (authenticated)
    print("\n--- 7. Open /messages/ (authenticated) ---")
    try:
        resp = alpha_client.get("/messages/", follow_redirects=False)
        ok = resp.status_code == 200
        check("GET /messages/ -> 200", ok, f"got {resp.status_code}")
    except Exception as e:
        check("GET /messages/", False, str(e))

    # 8. Open /discover/ (authenticated)
    print("\n--- 8. Open /discover/ (authenticated) ---")
    try:
        resp = alpha_client.get("/discover/", follow_redirects=False)
        ok = resp.status_code == 200
        check("GET /discover/ -> 200", ok, f"got {resp.status_code}")
    except Exception as e:
        check("GET /discover/", False, str(e))

    # 9. Check unread messages API
    print("\n--- 9. Unread Messages API ---")
    try:
        resp = alpha_client.get("/api/messages/unread-count", follow_redirects=False)
        ok = is_json_response(resp) and resp.status_code != 500
        if resp.status_code in (200, 401) and is_json_response(resp):
            ok = True
        detail = f"status={resp.status_code}, ct={resp.content_type}"
        check("GET /api/messages/unread-count -> JSON", ok, detail)
    except Exception as e:
        check("GET /api/messages/unread-count", False, str(e))

    # 10. Check notifications unread API
    print("\n--- 10. Notifications Unread API ---")
    try:
        resp = alpha_client.get("/api/notifications/unread-count", follow_redirects=False)
        ok = is_json_response(resp) and resp.status_code != 500
        detail = f"status={resp.status_code}, ct={resp.content_type}"
        check("GET /api/notifications/unread-count -> JSON", ok, detail)
    except Exception as e:
        check("GET /api/notifications/unread-count", False, str(e))

    # 11. Try opening beta profile by username
    print("\n--- 11. Beta Profile by Username ---")
    if has_beta:
        try:
            resp = alpha_client.get(f"/profile/@{beta_user}", follow_redirects=False)
            ok = resp.status_code == 200
            check(f"GET /profile/@{beta_user} -> 200", ok, f"got {resp.status_code}")
        except Exception as e:
            check(f"GET /profile/@{beta_user}", False, str(e))
    else:
        skip("GET /profile/@beta", "beta credentials missing")

    # 12. Try starting/opening message thread with beta
    print("\n--- 12. Message Thread with Beta ---")
    if has_beta:
        try:
            # Look up existing direct thread first
            import uuid
            from services.neon_service import fast_query
            existing = fast_query(
                """
                SELECT tm.thread_id
                FROM chain_thread_members tm1
                JOIN chain_thread_members tm2 USING (thread_id)
                WHERE tm1.profile_id = %s AND tm2.profile_id = %s
                  AND tm1.thread_id = tm2.thread_id
                LIMIT 1
                """,
                (alpha_pid, beta_pid), default=[],
            )
            if existing:
                thread_id = existing[0]["thread_id"]
                # Open the thread page
                resp = alpha_client.get(f"/messages/thread/{thread_id}", follow_redirects=False)
                ok = resp.status_code in (200, 302)
                check(f"Open existing thread with beta (id={str(thread_id)[:8]}...)", ok, f"status={resp.status_code}")
            else:
                # Try starting a thread via API
                from services.neon_service import write_query
                thread_id = str(uuid.uuid4())
                write_query(
                    "INSERT INTO chain_message_threads (id, created_by_profile_id, thread_type, folder_type, updated_at) VALUES (%s, %s, 'direct', 'primary', now())",
                    (thread_id, alpha_pid),
                )
                write_query(
                    "INSERT INTO chain_thread_members (thread_id, profile_id) VALUES (%s, %s), (%s, %s)",
                    (thread_id, alpha_pid, thread_id, beta_pid),
                )
                resp = alpha_client.get(f"/messages/thread/{thread_id}", follow_redirects=False)
                ok = resp.status_code in (200, 302)
                check(f"Create and open new thread with beta (id={str(thread_id)[:8]}...)", ok, f"status={resp.status_code}")
        except Exception as e:
            check("Message thread with beta", False, str(e))
    else:
        skip("Message thread with beta", "beta credentials missing")

    # 13. Summary
    total = PASS + FAIL + SKIP
    print(f"\n{'=' * 60}")
    print(f"  PASS: {PASS}  |  FAIL: {FAIL}  |  SKIP: {SKIP}  |  Total: {total}")
    if FAIL == 0:
        print(f"  ALL CHECKS PASSED (or skipped)")
    else:
        print(f"  {FAIL} CHECK(S) FAILED")
    print(f"{'=' * 60}\n")

    sys.exit(1 if FAIL > 0 else 0)


if __name__ == "__main__":
    main()

