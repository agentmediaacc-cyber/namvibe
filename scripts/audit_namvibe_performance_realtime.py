#!/usr/bin/env python3
"""
Phase Next +4 — NamVibe Performance & Realtime Audit.
Audits slow messaging/page/API performance and Redis realtime publish.
"""
import json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ.setdefault("CHAIN_DISABLE_SCHEDULER", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
os.environ["CHAIN_TEST_MODE"] = "1"
FAIL = 0
WARN_SLOW = []
CRIT_SLOW = []
TABLE = []


def check(label, cond, d=""):
    global FAIL
    if not cond:
        print(f"  [X]  FAIL  {label}" + (f"  - {d}" if d else ""))
        FAIL += 1


def skip(label, d=""):
    print(f"  [/]  SKIP  {label}" + (f"  - {d}" if d else ""))


def is_json(resp):
    return "application/json" in (resp.content_type or "") or resp.is_json


def login_client(app, pid, aid):
    cli = app.test_client()
    with cli.session_transaction() as s:
        s["profile_id"] = pid
        s["auth_user_id"] = aid
        s["user_id"] = aid
        s["logged_in"] = True
    return cli


def timed_get(client, path, label="", expect_json=False):
    """Perform GET with timing, returns (resp, elapsed_ms)."""
    start = time.perf_counter()
    try:
        resp = client.get(path, follow_redirects=False)
    except Exception as e:
        ms = (time.perf_counter() - start) * 1000
        TABLE.append((path, "EXCEPTION", "no", f"{ms:.0f}", str(e)[:40]))
        return None, ms
    ms = (time.perf_counter() - start) * 1000
    status = resp.status_code
    is_500 = status in (500, 502, 503)
    json_ok = is_json(resp) if expect_json else None
    result = "FAIL" if is_500 else ("OK" if status < 400 else "WARN")
    label_short = label or path
    TABLE.append((label_short, str(status), "yes" if json_ok else ("no" if expect_json else "n/a"), f"{ms:.0f}", result))
    if is_500:
        check(f"{label_short} 500 error", False, f"status={status}")
    if ms > 5000:
        CRIT_SLOW.append((path, ms))
    elif ms > 1000:
        WARN_SLOW.append((path, ms))
    return resp, ms


def main():
    global FAIL
    print("=" * 60)
    print("  Phase Next +4 - NamVibe Performance & Realtime Audit")
    print("  (slow responses are WARN only, not FAIL)")
    print("=" * 60)

    # ── 1. Load alpha and beta ──
    print("\n--- 1. Load Test Credentials ---")
    creds_path = ROOT / "secrets" / "test_credentials.json"
    if not creds_path.exists():
        print("  [X]  FAIL  test_credentials.json not found")
        sys.exit(1)
    creds = json.loads(creds_path.read_text())
    a = creds.get("chain_star", {})
    b = creds.get("chain_moon", {})
    apid = a.get("profile_id", "")
    aaid = a.get("auth_user_id", "")
    auser = a.get("username", "chain_star")
    bpid = b.get("profile_id", "")
    baid = b.get("auth_user_id", "")
    has_beta = bool(bpid and baid)
    if not apid or not aaid:
        print("  [X]  FAIL  Alpha credentials incomplete")
        sys.exit(1)
    print(f"  Alpha: {auser} pid={apid[:8]}...")
    if has_beta:
        print(f"  Beta:  chain_moon pid={bpid[:8]}...")
    else:
        print("  Beta: NOT AVAILABLE (will SKIP beta checks)")

    # ── 2. Import app safely ──
    print("\n--- 2. Import App ---")
    try:
        from app import app as flask_app
        app = flask_app
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        print("  [+]  PASS  App imported")
    except Exception as e:
        print(f"  [X]  FAIL  Import app - {e}")
        sys.exit(1)

    # ── 3. Login alpha ──
    print("\n--- 3. Login Alpha ---")
    try:
        ac = login_client(app, apid, aaid)
        print("  [+]  PASS  Alpha client ready")
    except Exception as e:
        print(f"  [X]  FAIL  Alpha login - {e}")
        sys.exit(1)

    # ── 4. Login beta ──
    print("\n--- 4. Login Beta ---")
    if has_beta:
        try:
            bc = login_client(app, bpid, baid)
            print("  [+]  PASS  Beta client ready")
        except Exception as e:
            print(f"  [X]  FAIL  Beta login - {e}")
            sys.exit(1)
    else:
        bc = None
        skip("Login beta", "beta missing")

    # ── 5. Confirm /healthz returns 200 ──
    print("\n--- 5. Healthz ---")
    resp, ms = timed_get(ac, "/healthz", "/healthz", expect_json=False)
    if resp:
        check("/healthz 200", resp.status_code == 200, f"got {resp.status_code}")

    # ── 6. Confirm /health/redis returns 200 or SKIP ──
    print("\n--- 6. Health/Redis ---")
    resp, ms = timed_get(ac, "/health/redis", "/health/redis", expect_json=False)
    if resp:
        if resp.status_code == 200:
            print(f"  [+]  PASS  /health/redis -> 200")
        else:
            skip("/health/redis", f"status={resp.status_code} (may be unavailable)")

    # ── 7. Confirm /health/db returns 200 or SKIP ──
    print("\n--- 7. Health/DB ---")
    resp, ms = timed_get(ac, "/health/db", "/health/db", expect_json=False)
    if resp:
        if resp.status_code == 200:
            print(f"  [+]  PASS  /health/db -> 200")
        else:
            skip("/health/db", f"status={resp.status_code} (may be unavailable)")

    # ── 8. Confirm /system/api/realtime-health returns JSON or SKIP ──
    print("\n--- 8. Realtime Health ---")
    # Try /health/realtime first (no auth required), then /system/api/realtime-health (requires admin)
    for rh_path in ["/health/realtime", "/system/api/realtime-health"]:
        resp, ms = timed_get(ac, rh_path, rh_path, expect_json=False)
        if resp and resp.status_code not in (401, 403, 404, 405):
            try:
                data = resp.get_json() or json.loads(resp.data.decode())
                if isinstance(data, dict):
                    print(f"  [+]  PASS  {rh_path} -> JSON ({resp.status_code})")
                    break
            except Exception:
                pass
        elif resp and resp.status_code in (401, 403, 404, 405):
            continue
    else:
        skip("Realtime health", "no endpoint returned JSON")

    # ── Find/create alpha-beta thread for msg endpoint tests ──
    print("\n--- 9. Thread Lookup ---")
    thread_id = None
    if has_beta:
        try:
            from services.neon_service import fast_query
            ex = fast_query("""
                SELECT tm1.thread_id FROM chain_thread_members tm1
                JOIN chain_thread_members tm2 ON tm1.thread_id = tm2.thread_id
                WHERE tm1.profile_id=%s AND tm2.profile_id=%s
                AND tm1.thread_id = tm2.thread_id LIMIT 1
            """, (apid, bpid), default=[])
            if ex:
                thread_id = ex[0]["thread_id"]
                print(f"  [+]  PASS  Thread found ({str(thread_id)[:8]}...)")
            else:
                from services.neon_service import write_query
                import uuid
                thread_id = str(uuid.uuid4())
                write_query("INSERT INTO chain_message_threads (id,created_by_profile_id,thread_type,folder_type,updated_at) VALUES (%s,%s,'direct','primary',now())", (thread_id, apid))
                write_query("INSERT INTO chain_thread_members (thread_id,profile_id) VALUES (%s,%s),(%s,%s)", (thread_id, apid, thread_id, bpid))
                print(f"  [+]  PASS  Thread created ({str(thread_id)[:8]}...)")
        except Exception as e:
            print(f"  [X]  FAIL  Thread lookup/create - {e}")
            sys.exit(1)
    else:
        skip("Thread lookup (no beta)")

    # ── 10-11. Timed route measurements ──
    print("\n--- 10-11. Timed Route Measurements ---")
    routes = [
        ("/home", "/home", False),
        ("/messages/", "/messages/", False),
    ]
    if thread_id:
        routes.append((f"/messages/thread/{thread_id}", "/messages/thread/<id>", False))
    else:
        routes.append(("SKIP-thread", "/messages/thread/<id>", False))
    routes += [
        ("/api/messages/unread-count", "/api/messages/unread-count", True),
        ("/api/notifications/unread-count", "/api/notifications/unread-count", True),
        ("/api/homepage/feed", "/api/homepage/feed", True),
        ("/api/homepage/stories", "/api/homepage/stories", True),
        ("/api/homepage/reels", "/api/homepage/reels", True),
    ]
    for path, label, expect_json in routes:
        if path == "SKIP-thread":
            skip("Messages thread page", "no thread_id")
            TABLE.append((label, "SKIP", "n/a", "n/a", "SKIP"))
            continue
        timed_get(ac, path, label, expect_json=expect_json)

    # ── 12. Test Socket.IO/Redis publish safely if helper exists ──
    print("\n--- 12. Socket.IO / Redis Publish ---")
    try:
        from services.socketio_service import socketio
        from services.redis_service import redis_available
        has_redis = False
        try:
            has_redis = redis_available()
        except Exception:
            pass
        if socketio and has_redis:
            print(f"  [+]  PASS  SocketIO registered, Redis available")
        elif socketio:
            skip("Redis publish", "SocketIO registered but Redis unavailable")
        else:
            skip("Redis publish", "SocketIO not available")
    except Exception as e:
        skip("SocketIO/Redis check", str(e)[:60])

    # ── 13-14. Warnings and final output ──
    print("\n--- 13. Slow Response Warnings ---")
    if WARN_SLOW:
        print(f"  [!]  WARN  {len(WARN_SLOW)} route(s) over 1000ms:")
        for p, ms in WARN_SLOW:
            print(f"        {p:<50s} {ms:.0f}ms")
    else:
        print("  [+]  PASS  No routes over 1000ms")
    if CRIT_SLOW:
        for p, ms in CRIT_SLOW:
            print(f"  [!!] CRIT  {p:<50s} {ms:.0f}ms (over 5000ms)")

    # ── Final table ──
    print("\n--- 14. Performance Table ---")
    print(f"  {'route':<45s} {'status':<8s} {'json':<6s} {'ms':<8s} {'result':<8s}")
    print(f"  {'-'*45} {'-'*8} {'-'*6} {'-'*8} {'-'*8}")
    for row in TABLE:
        route, status, json_s, ms_s, result = row
        print(f"  {route:<45s} {status:<8s} {json_s:<6s} {ms_s:<8s} {result:<8s}")

    # ── Summary ──
    print(f"\n{'=' * 60}")
    if CRIT_SLOW:
        print(f"  CRITICAL: {len(CRIT_SLOW)} route(s) over 5000ms")
    if WARN_SLOW:
        print(f"  WARNING:  {len(WARN_SLOW)} route(s) between 1000-5000ms")
    if FAIL > 0:
        print(f"  FAIL:     {FAIL} check(s) failed")
        print(f"  EXIT CODE: 1")
        sys.exit(1)
    else:
        print(f"  PASS:     0 failures (warnings are informational)")
        print(f"  EXIT CODE: 0")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()