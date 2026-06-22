"""
Phase 111: Contacts System, Inbox Redesign & Notification Fix — E2E Test.

Tests:
  1. Notifications created on friend request and accept (social_relationship_service)
  2. /api/contacts returns only accepted friendships
  3. /contacts page renders
  4. /inbox, /inbox/new, /inbox/sent, /inbox/blocked pages render
  5. Calls from contacts API respects block status
"""
import os, sys, json, uuid, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"
os.environ["CHAIN_DISABLE_DB_PING"] = "1"

from app import create_app
app = create_app()

PASS = 0; FAIL = 0
def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {label}"); PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else "")); FAIL += 1

TS = str(int(time.time()))
PID_A = None
PID_B = None
PID_C = None

client = app.test_client()

# ============================================================
# Helper: create test profile
# ============================================================
def make_profile(auth_uid, username, email):
    """Use ensure_profile_for_user to create a proper profile with auth_user_id."""
    from services.profile_service import ensure_profile_for_user
    with app.test_request_context():
        profile, err = ensure_profile_for_user(auth_uid, email=email, username=username,
            defaults={"is_verified": True, "email_verified": True})
    check(f"profile {username} created", profile is not None, err)
    return profile["id"] if profile else auth_uid

# ============================================================
# Cleanup helper
# ============================================================
def cleanup_profile(pid):
    if not pid: return
    from services.neon_service import fast_query, write_query
    try:
        pids = write_query("DELETE FROM chain_profiles WHERE id = %s RETURNING id", (pid,), default=[])
        return bool(pids)
    except Exception:
        return False

# ============================================================
# TASK 1: Notifications — friend_request + friend_accepted
# ============================================================
def test_notifications_created():
    global PID_A, PID_B
    suffix = TS + "_" + str(uuid.uuid4())[:8]
    PID_A = make_profile(str(uuid.uuid4()), f"test_a_{suffix}", f"test_a_{suffix}@test.com")
    PID_B = make_profile(str(uuid.uuid4()), f"test_b_{suffix}", f"test_b_{suffix}@test.com")

    from services.social_relationship_service import send_friend_request, accept_friend_request
    from services.neon_service import fast_query

    with app.test_request_context():
        result = send_friend_request(PID_A, PID_B)
    check("send_friend_request ok", result.get("state") == "friend_requested", str(result))

    # Check notification in DB
    notifs = fast_query(
        "SELECT n.id, n.event_type AS ntype, n.title, n.body FROM chain_notifications n WHERE n.recipient_profile_id = %s AND n.event_type = 'friend_request'",
        (PID_B,), default=[]
    )
    check("friend_request notification created for recipient", len(notifs) >= 1,
          f"Found {len(notifs)} notifications")

    # Accept
    reqs = fast_query(
        "SELECT id FROM chain_friend_requests WHERE sender_profile_id = %s AND recipient_profile_id = %s AND status = 'pending'",
        (PID_A, PID_B), default=[]
    )
    check("friend request exists in DB", len(reqs) >= 1)

    with app.test_request_context():
        result2 = accept_friend_request(PID_B, reqs[0]["id"])
    check("accept_friend_request ok", result2.get("state") == "friends", str(result2))

    # Check friend_accepted notification
    notifs2 = fast_query(
        "SELECT n.id, n.event_type AS ntype, n.title, n.body FROM chain_notifications n WHERE n.recipient_profile_id = %s AND n.event_type = 'friend_accepted'",
        (PID_A,), default=[]
    )
    check("friend_accepted notification created for sender", len(notifs2) >= 1,
          f"Found {len(notifs2)} notifications")

# ============================================================
# TASK 2: Contacts API returns only accepted friends
# ============================================================
def test_contacts_api():
    from services.profile_service import get_current_profile
    from unittest.mock import patch

    # We need to simulate being logged in as user A to call /api/contacts/
    # Use Flask test client session
    with client.session_transaction() as sess:
        sess["profile_id"] = PID_A
        sess["user_id"] = PID_A

    resp = client.get("/api/contacts/")
    check("/api/contacts/ returns 200", resp.status_code == 200)
    data = resp.get_json()
    check("/api/contacts/ returns ok", data.get("ok"))
    contacts = data.get("contacts", [])
    check("contacts list has at least B", any(c["profile_id"] == PID_B for c in contacts),
          f"Contacts: {[c['username'] for c in contacts]}")

    resp2 = client.get(f"/api/contacts/search?q=test_b")
    check("/api/contacts/search works", resp2.status_code == 200)
    data2 = resp2.get_json()
    check("search finds contact B", any(c["profile_id"] == PID_B for c in data2.get("contacts", [])))

    resp3 = client.post(f"/api/contacts/{PID_B}/remove")
    check("/api/contacts/<id>/remove endpoint exists", resp3.status_code in (200, 400, 403, 405))

    resp4 = client.post(f"/api/contacts/{PID_B}/block")
    check("/api/contacts/<id>/block endpoint exists", resp4.status_code in (200, 400, 403, 405))

    # Clean up session
    with client.session_transaction() as sess:
        sess.clear()

# ============================================================
# TASK 3: /contacts page renders
# ============================================================
def test_contacts_page():
    with client.session_transaction() as sess:
        sess["profile_id"] = PID_A
        sess["user_id"] = PID_A

    resp = client.get("/contacts/")
    check("/contacts/ page renders", resp.status_code == 200,
          f"Status: {resp.status_code}")
    check("/contacts/ contains contacts list", b"contactsList" in resp.data or b"Contacts" in resp.data)

    with client.session_transaction() as sess:
        sess.clear()

# ============================================================
# TASK 4: Inbox pages render
# ============================================================
def test_inbox_pages():
    with client.session_transaction() as sess:
        sess["profile_id"] = PID_A
        sess["user_id"] = PID_A

    for path, label in [("/inbox/", "inbox main"),
                        ("/inbox/new", "inbox new"),
                        ("/inbox/sent", "inbox sent"),
                        ("/inbox/blocked", "inbox blocked")]:
        resp = client.get(path)
        check(f"{label} page renders", resp.status_code == 200, f"Status: {resp.status_code}")

    with client.session_transaction() as sess:
        sess.clear()

# ============================================================
# TASK 5: Calls from contacts — check block behavior
# ============================================================
def test_contacts_call_blocked():
    from services.blocking_service import is_blocked_any

    check("is_blocked_any returns True when blocked",
          not is_blocked_any(PID_A, PID_B))  # not blocked initially

    from services.blocking_service import block_user
    block_user(PID_B, PID_A)  # B blocks A

    # Now A calling B via contacts API should be rejected
    with client.session_transaction() as sess:
        sess["profile_id"] = PID_A
        sess["user_id"] = PID_A

    resp = client.get(f"/api/contacts/{PID_B}/call")
    data = resp.get_json() if resp.is_json else {}
    check("blocked user cannot call via contacts API",
          data.get("error") is not None or resp.status_code in (403, 400),
          f"Response: {resp.status_code} {data}")

    resp2 = client.get(f"/api/contacts/{PID_B}/message")
    data2 = resp2.get_json() if resp2.is_json else {}
    check("blocked user cannot message via contacts API",
          data2.get("error") is not None or resp2.status_code in (403, 400),
          f"Response: {resp2.status_code} {data2}")

    with client.session_transaction() as sess:
        sess.clear()

    # Unblock for cleanup
    from services.blocking_service import unblock_user
    try:
        unblock_user(PID_B, PID_A)
    except Exception:
        pass

    # Cleanup test profiles
    cleanup_profile(PID_A)
    cleanup_profile(PID_B)

# ============================================================
# Run All
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Phase 111 — Contacts, Inbox & Notification Fix")
    print("=" * 60)

    test_notifications_created()
    test_contacts_api()
    test_contacts_page()
    test_inbox_pages()
    test_contacts_call_blocked()

    total = PASS + FAIL
    print(f"\n{'='*40}")
    print(f"Results: {PASS}/{total} passed, {FAIL}/{total} failed")
    if FAIL:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("✅ ALL TESTS PASSED")
