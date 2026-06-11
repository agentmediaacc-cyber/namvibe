"""
Phase 70 — Full App Inspection before VPS deployment.
Tests health, auth, profile, messages, calls, wallet, dating,
notifications, safety, admin, DB, Redis, and socket registration.
"""
import json, os, sys, time, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["CHAIN_DISABLE_CALL_WORKER"] = "1"
os.environ["CHAIN_DISABLE_SCHEDULER"] = "1"
os.environ["CHAIN_DEV_TOOLS"] = "1"

PASS = 0
FAIL = 0
WARN = 0

CREDENTIALS_PATH = ROOT / "secrets" / "test_credentials.json"
CREDENTIALS = {}
if CREDENTIALS_PATH.exists():
    CREDENTIALS = json.loads(CREDENTIALS_PATH.read_text())

CHAIN_STAR = CREDENTIALS.get("chain_star", {})
CHAIN_MOON = CREDENTIALS.get("chain_moon", {})
STAR_PROFILE_ID = CHAIN_STAR.get("profile_id", "")
MOON_PROFILE_ID = CHAIN_MOON.get("profile_id", "")
STAR_AUTH_ID = CHAIN_STAR.get("auth_user_id", "")
MOON_AUTH_ID = CHAIN_MOON.get("auth_user_id", "")
STAR_USERNAME = CHAIN_STAR.get("username", "")


def check(label, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}")


def warn(label, detail=""):
    global WARN
    WARN += 1
    msg = f"  [WARN] {label}"
    if detail:
        msg += f" -- {detail}"
    print(msg)


def login_client(app, profile_id, auth_user_id):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["profile_id"] = profile_id
        sess["auth_user_id"] = auth_user_id
        sess["user_id"] = profile_id
    return client


def test_page(client, path, label=None, expect=(200, 302, 308)):
    label = label or f"GET {path}"
    try:
        resp = client.get(path)
        if resp.status_code in expect:
            check(label, True)
        else:
            check(label, False)
            print(f"        got {resp.status_code}")
        return resp
    except Exception as e:
        check(label, False)
        print(f"        error: {e}")
        return None


def test_api_ok(client, method, path, json_data=None, label=None):
    label = label or f"{method} {path}"
    try:
        if method == "GET":
            resp = client.get(path)
        else:
            resp = client.post(path, json=json_data or {})
        data = resp.get_json() or {}
        ok = resp.status_code == 200 and data.get("ok") is True
        check(label, ok)
        if not ok:
            print(f"        status={resp.status_code} error={data.get('error', '?')[:60]}")
        return data
    except Exception as e:
        check(label, False)
        print(f"        error: {e}")
        return {}


def ensure_id(data, *keys):
    for k in keys:
        v = data.get(k, {})
        if isinstance(v, dict):
            return v.get("id") or v.get("thread_id")
        if v:
            return v
    return None


def main():
    global PASS, FAIL, WARN

    print("=" * 60)
    print("Phase 70 — Full App Inspection")
    print("=" * 60)

    # ── 1. Import app ──────────────────────────────────────────────
    print("\n--- 1. App Import ---")
    try:
        from app import create_app
        app = create_app()
        check("App creates cleanly", True)
    except Exception as e:
        check(f"App import: {e}", False)
        sys.exit(1)

    # ── 2. Health Endpoint ─────────────────────────────────────────
    print("\n--- 2. System Health ---")
    anon = app.test_client()
    test_api_ok(anon, "GET", "/system/api/realtime-health", label="Realtime health endpoint")
    test_api_ok(anon, "GET", "/system/api/health", label="Health endpoint")

    # ── 3. Auth Pages ──────────────────────────────────────────────
    print("\n--- 3. Auth Pages ---")
    test_page(anon, "/auth/login", label="Login page")
    test_page(anon, "/auth/register", label="Register page")
    test_page(anon, "/auth/forgot-password", label="Forgot password page")

    # ── 4. Homepage ────────────────────────────────────────────────
    print("\n--- 4. Homepage & Feed ---")
    test_page(anon, "/", label="Homepage")
    test_page(anon, "/discover", label="Discover page")

    # ── 5. Authenticated Pages ─────────────────────────────────────
    print("\n--- 5. Authenticated Pages ---")
    if not STAR_PROFILE_ID:
        warn("Test credentials missing", "chain_star not found")
        print("       Skipping authenticated tests\n")
    else:
        star = login_client(app, STAR_PROFILE_ID, STAR_AUTH_ID)
        moon = login_client(app, MOON_PROFILE_ID, MOON_AUTH_ID)

        # Profile pages
        test_page(star, "/profile/", label="Profile page")
        test_page(star, "/profile/edit", label="Edit profile")
        test_page(star, "/profile/settings", label="Profile settings")
        test_page(star, "/profile/privacy", label="Profile privacy")
        test_page(star, "/profile/security", label="Profile security")
        if STAR_USERNAME:
            test_page(star, f"/profile/@{STAR_USERNAME}", label="Public profile by @username")
            test_page(star, f"/profile/{STAR_USERNAME}", label="Public profile by username")

        # Wallet pages
        test_page(star, "/wallet/", label="Wallet page")
        test_page(star, "/wallet/transactions", label="Wallet transactions")

        # Dating pages
        test_page(star, "/dating", label="Dating home")
        test_page(star, "/dating/discover", label="Dating discover")

        # Notifications
        test_page(star, "/notifications/", label="Notifications page")
        test_page(star, "/notifications/center", label="Notifications center")

        # Safety API
        test_api_ok(star, "GET", "/safety/api/trust-summary", label="Safety trust summary")

        # Admin pages
        test_page(star, "/admin/dashboard", label="Admin dashboard", expect=(200, 302, 308, 404))

    # ── 6. Messaging ─────────────────────────────────────────────
    print("\n--- 6. Messaging ---")
    if not STAR_PROFILE_ID:
        warn("Skipping messaging", "no test credentials")
    else:
        star = login_client(app, STAR_PROFILE_ID, STAR_AUTH_ID)
        moon = login_client(app, MOON_PROFILE_ID, MOON_AUTH_ID)

        # Thread start
        thread_id = None
        try:
            resp = star.post("/messages/api/threads/start", json={
                "profile_id": MOON_PROFILE_ID,
                "client_event_id": f"test_{uuid.uuid4().hex[:12]}",
            })
            data = resp.get_json() or {}
            if resp.status_code == 200 and data.get("thread_id"):
                thread_id = data["thread_id"]
                check("Thread start API", True)
            else:
                check("Thread start API", False)
                print(f"        status={resp.status_code} data={data}")
        except Exception as e:
            check(f"Thread start: {e}", False)

        if thread_id:
            # Send message
            msg_id = None
            try:
                resp = star.post("/messages/api/send", json={
                    "thread_id": thread_id,
                    "body": "Phase 70 inspection test message",
                    "client_event_id": f"test_{uuid.uuid4().hex[:12]}",
                })
                data = resp.get_json() or {}
                msg_id = ensure_id(data, "message")
                check("Send message API", bool(msg_id) and data.get("ok") is True)
                if not data.get("ok"):
                    print(f"        error={data.get('error', '?')}")
            except Exception as e:
                check(f"Send message: {e}", False)

            # Inbox
            test_api_ok(moon, "GET", "/messages/api/inbox?folder=primary", label="Inbox API")

            # Mark seen
            test_api_ok(moon, "POST", "/messages/api/seen", json_data={"thread_id": thread_id}, label="Mark seen")

            # Mark delivered
            test_api_ok(moon, "POST", "/messages/api/delivered", json_data={"thread_id": thread_id}, label="Mark delivered")

        # Unread count (returns {"ok": True, "message": {"unread_count": N}})
        try:
            resp = star.get("/messages/api/unread-count")
            data = resp.get_json() or {}
            if resp.status_code == 200 and data.get("ok") is True:
                check("Unread count API (messages)", True)
            else:
                check("Unread count API (messages)", False)
                print(f"        status={resp.status_code} data={data}")
        except Exception as e:
            check(f"Unread count API (messages): {e}", False)

        # Socket diagnostics
        test_api_ok(star, "GET", "/messages/api/socket-diagnostics", label="Socket diagnostics")

    # ── 7. Calls ─────────────────────────────────────────────────
    print("\n--- 7. Calls ---")
    if STAR_PROFILE_ID:
        star = login_client(app, STAR_PROFILE_ID, STAR_AUTH_ID)
        test_page(star, "/calls/recent", label="Call history page")
        # Call API
        test_api_ok(star, "GET", "/calls/api/notifications", label="Call notifications API")

    # ── 8. Wallet APIs ───────────────────────────────────────────
    print("\n--- 8. Wallet ---")
    if STAR_PROFILE_ID:
        star = login_client(app, STAR_PROFILE_ID, STAR_AUTH_ID)
        test_api_ok(star, "GET", "/wallet/api/balance", label="Wallet balance API")
        test_api_ok(star, "GET", "/wallet/api/transactions", label="Wallet transactions API")

    # ── 9. Notifications API ─────────────────────────────────────
    print("\n--- 9. Notifications ---")
    if STAR_PROFILE_ID:
        star = login_client(app, STAR_PROFILE_ID, STAR_AUTH_ID)
        test_api_ok(star, "GET", "/api/notifications", label="Notifications list API")
        # Unread count returns {"count": N}, not {"ok": true, ...}
        try:
            resp = star.get("/api/notifications/unread-count")
            data = resp.get_json() or {}
            check("Unread count API (notifications)", resp.status_code == 200 and "count" in data)
            if resp.status_code != 200 or "count" not in data:
                print(f"        status={resp.status_code} data={data}")
        except Exception as e:
            check(f"Unread count API (notifications): {e}", False)

    # ── 10. Safety Actions ───────────────────────────────────────
    print("\n--- 10. Safety ---")
    if STAR_PROFILE_ID and MOON_PROFILE_ID:
        star = login_client(app, STAR_PROFILE_ID, STAR_AUTH_ID)
        try:
            from services.relationship_gate_service import is_blocked
            from services.neon_service import write_query, fast_query
            # Block test
            block_id = str(uuid.uuid4())
            write_query(
                "INSERT INTO chain_blocks (id, blocker_profile_id, blocked_profile_id, created_at) VALUES (%s, %s, %s, now()) ON CONFLICT (blocker_profile_id, blocked_profile_id) DO UPDATE SET deleted_at = NULL, created_at = now()",
                (block_id, STAR_PROFILE_ID, MOON_PROFILE_ID),
            )
            check("Block user", is_blocked(STAR_PROFILE_ID, MOON_PROFILE_ID) is True)
            # Unblock
            write_query(
                "UPDATE chain_blocks SET deleted_at = now() WHERE blocker_profile_id = %s AND blocked_profile_id = %s",
                (STAR_PROFILE_ID, MOON_PROFILE_ID),
            )
            check("Unblock user", is_blocked(STAR_PROFILE_ID, MOON_PROFILE_ID) is False)
        except Exception as e:
            check(f"Block/unblock: {e}", False)

    # ── 11. Database ─────────────────────────────────────────────
    print("\n--- 11. Database ---")
    try:
        from services.neon_service import fast_query
        # Simple ping
        rows = fast_query("SELECT 1 AS ok", default=[])
        check("Neon database reachable", rows is not None and len(rows) > 0)
    except Exception as e:
        check(f"Neon database: {e}", False)

    # Key tables check
    required_tables = [
        "chain_profiles", "chain_messages", "chain_message_threads",
        "chain_thread_members", "chain_notifications", "chain_blocks",
        "chain_calls", "chain_call_logs", "chain_follows",
        "chain_message_reactions",
    ]
    try:
        # Check each table individually to avoid array type issues
        missing = []
        for tbl in required_tables:
            rows = fast_query(
                "SELECT table_name FROM information_schema.tables WHERE table_name = %s",
                (tbl,), default=[]
            )
            if not rows:
                missing.append(tbl)
        check("All required tables exist", len(missing) == 0)
        for t in missing:
            print(f"       Missing table: {t}")
    except Exception as e:
        check(f"Table check: {e}", False)

    # ── 12. Redis ────────────────────────────────────────────────
    print("\n--- 12. Redis ---")
    try:
        from services.redis_service import get_redis
        r = get_redis()
        ok = r is not None and bool(r.ping())
        check("Redis reachable", ok)
    except Exception:
        check("Redis reachable", False)

    # ── 13. Socket Events ────────────────────────────────────────
    print("\n--- 13. Socket Events ---")
    try:
        from services.socketio_service import socketio
        check("SocketIO accessible", socketio is not None)
    except ImportError as e:
        warn("SocketIO import", str(e)[:80])
        check("SocketIO accessible", False)

    # Verify events module loads
    try:
        import services.socket_events
        check("Socket events module loads", True)
    except Exception as e:
        check(f"Socket events module: {e}", False)

    # ── 14. Route Registration ───────────────────────────────────
    print("\n--- 14. Routes ---")
    try:
        rules = [r for r in app.url_map.iter_rules() if not r.rule.startswith("/static")]
        check(f"Total routes: {len(rules)}", len(rules) > 100)
    except Exception as e:
        check(f"Route count: {e}", False)

    # ── 15. Security ─────────────────────────────────────────────
    print("\n--- 15. Security ---")
    try:
        import subprocess
        result = subprocess.run(
            ["git", "ls-files", "secrets/"], capture_output=True, text=True, cwd=ROOT
        )
        tracked = [f for f in result.stdout.strip().split("\n") if f]
        check("No secrets tracked in git", len(tracked) == 0)
        for f in tracked[:5]:
            print(f"       TRACKED: {f}")
    except Exception:
        warn("Git check skipped")

    try:
        result = subprocess.run(
            ["git", "ls-files", ".env"], capture_output=True, text=True, cwd=ROOT
        )
        check("No .env in git", result.stdout.strip() == "")
    except Exception:
        pass

    # ── Summary ──────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    total = PASS + FAIL
    print(f"Total: {PASS} passed, {FAIL} failed, {WARN} warnings ({total} checks)")
    print(f"{'=' * 60}")
    if FAIL:
        print(f"❌ {FAIL} CHECK(S) FAILED")
        sys.exit(1)
    else:
        print("✅ ALL CHECKS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
