"""
Phase 69 — Real Communication Test.
Tests end-to-end message flow, calling, blocking, and notifications
using Flask test client with test user sessions.
"""
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["CHAIN_DISABLE_CALL_WORKER"] = "1"
os.environ["CHAIN_DISABLE_SCHEDULER"] = "1"

PASS = 0
FAIL = 0

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

if not STAR_PROFILE_ID or not MOON_PROFILE_ID:
    print("❌ Test credentials not found. Ensure secrets/test_credentials.json exists.")
    sys.exit(1)


def setup_django():
    pass


def check(label, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}")


def login_client(app, profile_id, auth_user_id):
    """Create a test client with an authenticated session."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["profile_id"] = profile_id
        sess["auth_user_id"] = auth_user_id
        sess["user_id"] = profile_id
    return client


def main():
    global PASS, FAIL

    print("=" * 60)
    print("Phase 69 — Real Communication Test")
    print("=" * 60)

    # Import app
    print("\n--- Importing app ---")
    try:
        os.environ["CHAIN_DEV_TOOLS"] = "1"
        from app import create_app
        app = create_app()
        check("App created", True)
    except Exception as e:
        check(f"App import failed: {e}", False)
        sys.exit(1)

    print(f"\nTest users: chain_star ({STAR_PROFILE_ID[:8]}...), chain_moon ({MOON_PROFILE_ID[:8]}...)")

    # =============================================================
    print("\n--- Create Thread ---")
    # =============================================================
    star = login_client(app, STAR_PROFILE_ID, STAR_AUTH_ID)
    thread_id = None
    try:
        resp = star.post("/messages/api/threads/start", json={
            "profile_id": MOON_PROFILE_ID,
            "client_event_id": f"test_create_{uuid.uuid4().hex[:12]}",
        })
        data = resp.get_json() or {}
        if resp.status_code == 200 and data.get("thread_id"):
            thread_id = data["thread_id"]
            check(f"Thread created/retrieved: {thread_id}", bool(thread_id))
        elif resp.status_code == 200 and data.get("ok"):
            thread_id = data.get("thread", {}).get("id") or data.get("thread_id")
            check(f"Thread created/retrieved: {thread_id}", bool(thread_id))
        else:
            check(f"Thread creation: {resp.status_code} {data.get('error', 'unknown')}", False)
    except Exception as e:
        check(f"Thread creation error: {e}", False)

    if not thread_id:
        # Try creating a thread directly in DB for testing
        try:
            from services.neon_service import write_query, fast_query
            existing = fast_query(
                """SELECT tm.thread_id FROM chain_thread_members tm
                   WHERE tm.profile_id IN (%s, %s)
                   GROUP BY tm.thread_id
                   HAVING COUNT(DISTINCT tm.profile_id) = 2
                   LIMIT 1""",
                (STAR_PROFILE_ID, MOON_PROFILE_ID), default=[],
            )
            if existing:
                thread_id = str(existing[0]["thread_id"])
                check(f"Found existing thread: {thread_id}", True)
            else:
                tid = str(uuid.uuid4())
                write_query(
                    "INSERT INTO chain_message_threads (id, created_by_profile_id, thread_type, folder_type, updated_at) VALUES (%s, %s, 'direct', 'primary', now())",
                    (tid, STAR_PROFILE_ID),
                )
                write_query(
                    "INSERT INTO chain_thread_members (thread_id, profile_id) VALUES (%s, %s), (%s, %s)",
                    (tid, STAR_PROFILE_ID, tid, MOON_PROFILE_ID),
                )
                thread_id = tid
                check(f"Direct DB thread created: {thread_id}", True)
        except Exception as e:
            check(f"Direct thread creation: {e}", False)

    # =============================================================
    print("\n--- Send Text Message ---")
    # =============================================================
    sent_msg_id = None
    if thread_id:
        try:
            resp = star.post("/messages/api/send", json={
                "thread_id": thread_id,
                "body": "Hello from Chain Star! This is a test message.",
                "client_event_id": f"test_msg_{uuid.uuid4().hex[:12]}",
            })
            data = resp.get_json() or {}
            if resp.status_code == 200 and data.get("ok"):
                sent_msg_id = data.get("message", {}).get("id") or data.get("message_id")
                check(f"Text message sent: {sent_msg_id}", True)
            else:
                check(f"Send message: {resp.status_code} {data.get('error', 'unknown')}", False)
        except Exception as e:
            check(f"Send message error: {e}", False)

    # =============================================================
    print("\n--- Verify DB Row ---")
    # =============================================================
    if sent_msg_id:
        try:
            from services.neon_service import fast_query
            rows = fast_query(
                "SELECT id, body, sender_profile_id, thread_id, delivery_status FROM chain_messages WHERE id = %s",
                (sent_msg_id,), default=[],
            )
            if rows:
                row = rows[0]
                check(f"DB row exists for message {sent_msg_id}", True)
                check(f"  body = '{row['body'][:40]}...'", "Hello" in str(row.get("body", "")))
                check(f"  sender = {row['sender_profile_id'][:8]}...", str(row["sender_profile_id"]) == STAR_PROFILE_ID)
                check(f"  thread = {str(row['thread_id'])[:8]}...", str(row["thread_id"]) == thread_id)
                check(f"  delivery_status = {row['delivery_status']}", row["delivery_status"] in ("sent", "delivered"))
            else:
                check("DB row exists", False)
        except Exception as e:
            check(f"DB query: {e}", False)

    # =============================================================
    print("\n--- Verify Receiver Inbox ---")
    # =============================================================
    if thread_id:
        try:
            moon = login_client(app, MOON_PROFILE_ID, MOON_AUTH_ID)
            resp = moon.get("/messages/api/inbox?folder=primary")
            data = resp.get_json() or {}
            if data.get("ok"):
                threads = data.get("message", {}).get("threads", [])
                found = any(str(t.get("id", "")) == thread_id for t in threads)
                check(f"Thread appears in moon's inbox", found)
            else:
                check(f"Inbox: {resp.status_code} {data.get('error', 'unknown')}", False)
        except Exception as e:
            check(f"Inbox error: {e}", False)

    # =============================================================
    print("\n--- Mark Delivered ---")
    # =============================================================
    if thread_id:
        try:
            resp = moon.post("/messages/api/delivered", json={
                "thread_id": thread_id,
            })
            data = resp.get_json() or {}
            check(f"Mark delivered: {data.get('ok')}", data.get("ok") is True)
        except Exception as e:
            check(f"Mark delivered: {e}", False)

    # =============================================================
    print("\n--- Mark Seen ---")
    # =============================================================
    if thread_id:
        try:
            resp = moon.post("/messages/api/seen", json={
                "thread_id": thread_id,
            })
            data = resp.get_json() or {}
            check(f"Mark seen: {data.get('ok')}", data.get("ok") is True)
        except Exception as e:
            check(f"Mark seen: {e}", False)

    # =============================================================
    print("\n--- Send Emoji Message ---")
    # =============================================================
    if thread_id:
        try:
            resp = star.post("/messages/api/send", json={
                "thread_id": thread_id,
                "body": "🔥🚀✨ Hello with emojis!",
                "client_event_id": f"test_emoji_{uuid.uuid4().hex[:12]}",
            })
            data = resp.get_json() or {}
            check(f"Emoji message sent: {data.get('ok')}", data.get("ok") is True)
        except Exception as e:
            check(f"Emoji message: {e}", False)

    # =============================================================
    print("\n--- Send Reaction ---")
    # =============================================================
    if sent_msg_id:
        try:
            resp = star.post("/messages/api/reaction", json={
                "message_id": sent_msg_id,
                "reaction": "👍",
                "action": "add",
            })
            data = resp.get_json() or {}
            check(f"Reaction added: {data.get('ok')}", data.get("ok") is True)
        except Exception as e:
            check(f"Reaction: {e}", False)

    # =============================================================
    print("\n--- Forward Message ---")
    # =============================================================
    if sent_msg_id and thread_id:
        try:
            resp = star.post("/messages/api/forward", json={
                "message_id": sent_msg_id,
                "target_thread_id": thread_id,
            })
            data = resp.get_json() or {}
            check(f"Forward message: {data.get('ok')}", data.get("ok") is True)
        except Exception as e:
            check(f"Forward: {e}", False)

    # =============================================================
    print("\n--- Delete Message ---")
    # =============================================================
    if sent_msg_id:
        try:
            resp = star.post("/messages/api/delete", json={
                "message_id": sent_msg_id,
                "for_everyone": False,
            })
            data = resp.get_json() or {}
            check(f"Delete message (for me): {data.get('ok')}", data.get("ok") is True)
        except Exception as e:
            check(f"Delete: {e}", False)

    # =============================================================
    print("\n--- Create Call Log ---")
    # =============================================================
    try:
        from services.neon_service import write_query
        call_id = str(uuid.uuid4())
        write_query(
            """INSERT INTO chain_calls (id, caller_profile_id, receiver_profile_id, call_type, status, started_at)
               VALUES (%s, %s, %s, 'audio', 'ended', now())""",
            (call_id, STAR_PROFILE_ID, MOON_PROFILE_ID),
        )
        write_query(
            """INSERT INTO chain_call_logs (call_id, profile_id, other_profile_id, direction, call_type, status, duration_seconds)
               VALUES (%s, %s, %s, 'outgoing', 'audio', 'ended', 45)""",
            (call_id, STAR_PROFILE_ID, MOON_PROFILE_ID),
        )
        write_query(
            """INSERT INTO chain_call_logs (call_id, profile_id, other_profile_id, direction, call_type, status, duration_seconds)
               VALUES (%s, %s, %s, 'incoming', 'audio', 'answered', 45)""",
            (call_id, MOON_PROFILE_ID, STAR_PROFILE_ID),
        )
        check(f"Call log created: {call_id[:8]}...", True)
    except Exception as e:
        check(f"Call log: {e}", False)

    # =============================================================
    print("\n--- Simulate Call Lifecycle Events (DB) ---")
    # =============================================================
    try:
        from services.neon_service import write_query, fast_query
        call_id2 = str(uuid.uuid4())
        write_query(
            """INSERT INTO chain_calls (id, caller_profile_id, receiver_profile_id, call_type, status, started_at)
               VALUES (%s, %s, %s, 'video', 'ringing', now())""",
            (call_id2, STAR_PROFILE_ID, MOON_PROFILE_ID),
        )
        rows = fast_query(
            "SELECT status FROM chain_calls WHERE id = %s", (call_id2,), default=[]
        )
        check(f"Call ringing: {rows[0]['status'] if rows else '?'}", rows and rows[0]["status"] == "ringing")
        write_query(
            "UPDATE chain_calls SET status = 'accepted', accepted_at = now() WHERE id = %s",
            (call_id2,),
        )
        rows2 = fast_query(
            "SELECT status FROM chain_calls WHERE id = %s", (call_id2,), default=[]
        )
        check(f"Call accepted: {rows2[0]['status'] if rows2 else '?'}", rows2 and rows2[0]["status"] == "accepted")
        write_query(
            "UPDATE chain_calls SET status = 'ended', ended_at = now(), duration_seconds = 120 WHERE id = %s",
            (call_id2,),
        )
        rows3 = fast_query(
            "SELECT status, duration_seconds FROM chain_calls WHERE id = %s", (call_id2,), default=[]
        )
        check(f"Call ended: {rows3[0]['status'] if rows3 else '?'} dur={rows3[0]['duration_seconds'] if rows3 else '?'}",
              rows3 and rows3[0]["status"] == "ended" and rows3[0]["duration_seconds"] == 120)
    except Exception as e:
        check(f"Call lifecycle: {e}", False)

    # =============================================================
    print("\n--- Missed Call Test ---")
    # =============================================================
    try:
        from services.neon_service import write_query, fast_query
        call_id3 = str(uuid.uuid4())
        write_query(
            """INSERT INTO chain_calls (id, caller_profile_id, receiver_profile_id, call_type, status, started_at)
               VALUES (%s, %s, %s, 'audio', 'missed', now() - interval '1 hour')""",
            (call_id3, MOON_PROFILE_ID, STAR_PROFILE_ID),
        )
        write_query(
            """INSERT INTO chain_call_logs (call_id, profile_id, other_profile_id, direction, call_type, status)
               VALUES (%s, %s, %s, 'incoming', 'audio', 'missed')""",
            (call_id3, STAR_PROFILE_ID, MOON_PROFILE_ID),
        )
        check("Missed call logged", True)
    except Exception as e:
        check(f"Missed call: {e}", False)

    # =============================================================
    print("\n--- Block Test ---")
    # =============================================================
    try:
        from services.neon_service import write_query
        from services.relationship_gate_service import is_blocked
        from services.moderation_engine import is_blocked as mod_is_blocked
        # Block moon by star
        block_id = str(uuid.uuid4())
        write_query(
            """INSERT INTO chain_blocks (id, blocker_profile_id, blocked_profile_id, created_at)
               VALUES (%s, %s, %s, now())
               ON CONFLICT (blocker_profile_id, blocked_profile_id)
               DO UPDATE SET deleted_at = NULL, created_at = now()""",
            (block_id, STAR_PROFILE_ID, MOON_PROFILE_ID),
        )
        b1 = is_blocked(STAR_PROFILE_ID, MOON_PROFILE_ID)
        check(f"Star can_message Moon after block: {b1}", b1 is True)
        # Try sending a message from moon to star (should fail because star blocked moon)
        moon_blocked = is_blocked(MOON_PROFILE_ID, STAR_PROFILE_ID)
        # is_blocked checks both directions, so moon -> star is also blocked
        check(f"Moon is blocked by Star", moon_blocked is True)
        # Cleanup block
        write_query(
            "UPDATE chain_blocks SET deleted_at = now() WHERE blocker_profile_id = %s AND blocked_profile_id = %s",
            (STAR_PROFILE_ID, MOON_PROFILE_ID),
        )
        b2 = is_blocked(STAR_PROFILE_ID, MOON_PROFILE_ID)
        check(f"Block removed: {b2}", b2 is False)
    except Exception as e:
        check(f"Block test: {e}", False)

    # =============================================================
    print("\n--- Notification Test ---")
    # =============================================================
    try:
        from services.neon_service import write_query, fast_query
        notif_id = str(uuid.uuid4())
        write_query(
            """INSERT INTO chain_notifications (id, recipient_profile_id, actor_profile_id, event_type, title, body, action_url)
               VALUES (%s, %s, %s, 'new_message', 'New Message', 'Test notification body', '/messages/test')""",
            (notif_id, MOON_PROFILE_ID, STAR_PROFILE_ID),
        )
        rows = fast_query(
            "SELECT id, is_read FROM chain_notifications WHERE id = %s",
            (notif_id,), default=[]
        )
        check(f"Notification created in DB: {rows[0]['id'][:8] if rows else '?'}...", bool(rows))
        if rows:
            write_query(
                "UPDATE chain_notifications SET is_read = TRUE, read_at = now() WHERE id = %s",
                (notif_id,),
            )
            rows2 = fast_query(
                "SELECT is_read FROM chain_notifications WHERE id = %s", (notif_id,), default=[]
            )
            check(f"Notification marked read: {rows2[0]['is_read'] if rows2 else '?'}", rows2 and rows2[0]["is_read"] is True)
    except Exception as e:
        check(f"Notification test: {e}", False)

    # =============================================================
    print("\n--- Unread Count API ---")
    # =============================================================
    try:
        star2 = login_client(app, STAR_PROFILE_ID, STAR_AUTH_ID)
        resp = star2.get("/messages/api/unread-count")
        data = resp.get_json() or {}
        if data.get("ok"):
            count = data.get("message", {}).get("unread_count", 0)
            check(f"Unread count API: {count}", isinstance(count, (int, float)))
        else:
            check(f"Unread count: {data.get('error', 'unknown')}", False)
    except Exception as e:
        check(f"Unread count: {e}", False)

    # =============================================================
    print("\n--- Socket Diagnostics ---")
    # =============================================================
    try:
        resp = star2.get("/messages/api/socket-diagnostics")
        data = resp.get_json() or {}
        check(f"Socket diagnostics: ok={data.get('ok')}", data.get("ok") is True)
    except Exception as e:
        check(f"Socket diagnostics: {e}", False)

    # =============================================================
    print("\n--- Realtime Health ---")
    # =============================================================
    try:
        resp = star2.get("/system/api/realtime-health")
        data = resp.get_json() or {}
        if data.get("ok"):
            check(f"SocketIO: {data.get('socketio')}", bool(data.get("socketio")))
            check(f"Redis: {data.get('redis')}", data.get("redis") in ("connected", "fallback"))
            check(f"Message routes: {data.get('message_routes')}", data.get("message_routes") is True)
            check(f"Call routes: {data.get('call_routes')}", data.get("call_routes") is True)
            check(f"Notification routes: {data.get('notification_routes')}", data.get("notification_routes") is True)
        else:
            check("Realtime health API failed", False)
    except Exception as e:
        check(f"Health: {e}", False)

    # =============================================================
    print(f"\n{'=' * 60}")
    print(f"Total: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 60}")
    if FAIL:
        print(f"❌ {FAIL} CHECK(S) FAILED")
        sys.exit(1)
    else:
        print("✅ ALL CHECKS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
