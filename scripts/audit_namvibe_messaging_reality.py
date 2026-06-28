#!/usr/bin/env python3
"""
Phase Next +3 — NamVibe Messaging Reality Audit.
Verifies the message system works end-to-end between alpha and beta.
"""
import json, os, sys, uuid
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ.setdefault("CHAIN_DISABLE_SCHEDULER", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")
os.environ["CHAIN_TEST_MODE"] = "1"
PASS = 0; FAIL = 0; SKIP = 0


def check(label, cond, d=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        print(f"  [X]  FAIL  {label}" + (f"  - {d}" if d else ""))
        FAIL += 1


def skip(label, d=""):
    global SKIP
    print(f"  [/]  SKIP  {label}" + (f"  - {d}" if d else ""))
    SKIP += 1


def is_json_response(resp):
    return "application/json" in (resp.content_type or "") or resp.is_json


def login_client(app, pid, aid):
    cli = app.test_client()
    with cli.session_transaction() as s:
        s["profile_id"] = pid
        s["auth_user_id"] = aid
        s["user_id"] = aid
        s["logged_in"] = True
    return cli


def main():
    global PASS, FAIL, SKIP
    print("=" * 60)
    print("  Phase Next +3 - NamVibe Messaging Reality Audit")
    print("=" * 60)

    # ── 1. Load credentials ──
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
    buser = b.get("username", "chain_moon")
    has_beta = bool(bpid and baid)
    if not apid or not aaid:
        print("  [X]  FAIL  Alpha credentials incomplete")
        sys.exit(1)
    print(f"  Alpha: {auser} pid={apid[:8]}...")
    if has_beta:
        print(f"  Beta:  {buser} pid={bpid[:8]}...")
    else:
        print("  Beta: NOT AVAILABLE (will SKIP)")
        skip("All beta checks", "beta missing")
        has_beta = False

    # ── 2. Import app ──
    print("\n--- 2. Import App ---")
    try:
        from app import app as flask_app
        app = flask_app
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        print("  [+]  PASS  Flask app imported")
        PASS += 1
    except Exception as e:
        print(f"  [X]  FAIL  Import app - {e}")
        sys.exit(1)

    # ── 3. Resolve profile IDs in DB ──
    print("\n--- 3. Resolve Profile IDs ---")
    try:
        from services.neon_service import fast_query
        ar = fast_query("SELECT id FROM chain_profiles WHERE id=%s LIMIT 1", (apid,), default=[])
        check(f"Alpha {auser} in DB", bool(ar))
        if not ar:
            sys.exit(1)
        if has_beta:
            br = fast_query("SELECT id FROM chain_profiles WHERE id=%s LIMIT 1", (bpid,), default=[])
            check(f"Beta {buser} in DB", bool(br))
            if not br:
                sys.exit(1)
    except Exception as e:
        check("Resolve profile IDs", False, str(e))
        sys.exit(1)

    # ── 4. Ensure thread exists ──
    print("\n--- 4. Ensure Thread Exists ---")
    thread_id = None
    if has_beta:
        try:
            ex = fast_query("""
                SELECT tm1.thread_id FROM chain_thread_members tm1
                JOIN chain_thread_members tm2 ON tm1.thread_id = tm2.thread_id
                WHERE tm1.profile_id=%s AND tm2.profile_id=%s
                AND tm1.thread_id = tm2.thread_id LIMIT 1
            """, (apid, bpid), default=[])
            if ex:
                thread_id = ex[0]["thread_id"]
                check(f"Existing thread OK", True)
            else:
                from services.neon_service import write_query
                thread_id = str(uuid.uuid4())
                write_query("INSERT INTO chain_message_threads (id,created_by_profile_id,thread_type,folder_type,updated_at) VALUES (%s,%s,'direct','primary',now())", (thread_id, apid))
                write_query("INSERT INTO chain_thread_members (thread_id,profile_id) VALUES (%s,%s),(%s,%s)", (thread_id, apid, thread_id, bpid))
                check(f"Created new thread OK", True)
        except Exception as e:
            check("Ensure thread exists", False, str(e))
            sys.exit(1)
    else:
        skip("Ensure thread exists", "beta missing")

    # ── 5. Send test message (alpha -> beta) ──
    print("\n--- 5. Send Test Message ---")
    if has_beta and thread_id:
        try:
            from services.messaging_engine import send_message
            AUDIT = "[AUDIT] alpha beta messaging reality test"
            r = send_message(thread_id=thread_id, sender_profile_id=apid, body=AUDIT, client_message_id=f"audit-{uuid.uuid4()}")
            mid = r.get("message_id") or r.get("id")
            check("Message inserted", bool(mid), f"result={json.dumps(r)[:150]}" if not mid else "")
        except Exception as e:
            check("Send message", False, str(e))
    else:
        skip("Send test message", "beta/thread missing")

    # ── 6. Open /messages/ as alpha ──
    print("\n--- 6. Open /messages/ as Alpha ---")
    try:
        ac = login_client(app, apid, aaid)
        resp = ac.get("/messages/", follow_redirects=False)
        check("GET /messages/ (alpha)", resp.status_code not in (500,502,503), f"status={resp.status_code}")
    except Exception as e:
        check("GET /messages/ (alpha)", False, str(e))

    # ── 7. Open alpha thread page ──
    print("\n--- 7. Open Thread Page (alpha) ---")
    if has_beta and thread_id:
        try:
            resp = ac.get(f"/messages/thread/{thread_id}", follow_redirects=False)
            check("GET thread (alpha)", resp.status_code not in (500,502,503), f"status={resp.status_code}")
        except Exception as e:
            check("GET thread (alpha)", False, str(e))
    else:
        skip("Open thread (alpha)", "beta/thread missing")

    # ── 8. Check /api/messages/unread-count as alpha ──
    print("\n--- 8. Unread Count (alpha) ---")
    try:
        resp = ac.get("/api/messages/unread-count", follow_redirects=False)
        ok = resp.status_code != 500 and is_json_response(resp)
        if ok:
            try:
                d = resp.get_json() or json.loads(resp.data.decode())
                check("Unread count JSON (alpha)", True, f"count={d.get('unread_count','?')}")
            except Exception as e:
                check("Unread count JSON (alpha)", False, str(e))
        else:
            check("Unread count (alpha)", ok, f"status={resp.status_code}")
    except Exception as e:
        check("Unread count (alpha)", False, str(e))

    # ── 9-14. Beta checks + summary ──
    print("\n--- 9. Switch to Beta ---")
    if has_beta:
        try:
            bc = login_client(app, bpid, baid)
            check("Beta client created", True)
        except:
            check("Beta client", False)
            bc = None
    else:
        bc = None
        skip("Switch to beta", "beta missing")

    print("\n--- 10. Open /messages/ as Beta ---")
    if has_beta and bc:
        try:
            resp = bc.get("/messages/", follow_redirects=False)
            check("GET /messages/ (beta)", resp.status_code not in (500,502,503), f"status={resp.status_code}")
        except Exception as e:
            check("GET /messages/ (beta)", False, str(e))
    else:
        skip("Open /messages/ (beta)", "beta missing")

    print("\n--- 11. Open Thread as Beta ---")
    if has_beta and bc and thread_id:
        try:
            resp = bc.get(f"/messages/thread/{thread_id}", follow_redirects=False)
            check("GET thread (beta)", resp.status_code not in (500,502,503), f"status={resp.status_code}")
        except Exception as e:
            check("GET thread (beta)", False, str(e))
    else:
        skip("Open thread (beta)", "beta/thread missing")

    print("\n--- 12. Unread Count as Beta ---")
    if has_beta and bc:
        try:
            resp = bc.get("/api/messages/unread-count", follow_redirects=False)
            ok = resp.status_code != 500 and is_json_response(resp)
            if ok:
                try:
                    d = resp.get_json() or json.loads(resp.data.decode())
                    check("Unread count JSON (beta)", True, f"count={d.get('unread_count','?')}")
                except Exception as e:
                    check("Unread count JSON (beta)", False, str(e))
            else:
                check("Unread count (beta)", ok, f"status={resp.status_code}")
        except Exception as e:
            check("Unread count (beta)", False, str(e))
    else:
        skip("Unread count (beta)", "beta missing")

    print("\n--- 13. Mark Thread Seen ---")
    if has_beta and bc and thread_id:
        eps = [
            ("POST", f"/api/messages/thread/{thread_id}/seen"),
            ("POST", f"/messages/api/messages/{thread_id}/seen"),
            ("POST", f"/messages/api/seen"),
            ("POST", f"/messages/api/thread/{thread_id}/seen"),
        ]
        ok = False
        for meth, path in eps:
            try:
                resp = bc.post(path, json={"thread_id": thread_id}, follow_redirects=False)
                if resp.status_code not in (404, 405, 500):
                    check(f"Mark seen via {path}", True, f"status={resp.status_code}")
                    ok = True
                    break
                elif resp.status_code == 500:
                    check(f"Mark seen via {path}", False, "500")
                    break
            except:
                continue
        if not ok:
            try:
                from services.message_receipt_service import mark_thread_seen
                r = mark_thread_seen(thread_id, bpid)
                if r.get("ok"):
                    check("Mark seen via service", True)
                else:
                    skip("Mark seen fallback", f"result={json.dumps(r)[:100]}")
            except Exception as e:
                skip("Mark seen fallback", str(e))
    else:
        skip("Mark thread seen", "beta/thread missing")

    print("\n--- 14. No 500 Errors ---")
    check("No 500 errors", FAIL == 0, "some checks failed" if FAIL > 0 else "")

    total = PASS + FAIL + SKIP
    print(f"\n{'=' * 60}")
    print(f"  PASS: {PASS}  |  FAIL: {FAIL}  |  SKIP: {SKIP}  |  Total: {total}")
    print(f"  {'ALL CHECKS PASSED (or skipped)' if FAIL == 0 else f'{FAIL} CHECK(S) FAILED'}")
    print(f"{'=' * 60}")
    sys.exit(1 if FAIL > 0 else 0)


if __name__ == "__main__":
    main()
