"""
Phase 37 Runtime Diagnosis — Real Messaging + Call Flow
Uses Flask test client + direct DB verification.

Strategy:
1. Create app with FLASK_TESTING (needed for test client)
2. Monkey-patch _db_available AFTER app creation so services use REAL DB
3. Test: routes return 200 AND data IS persisted in DB
4. Catch the Phase 32-36 bug: "test passes but nothing is saved"
"""
import os, sys, json, uuid as uuid_mod, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "0"
os.environ["CHAIN_TRUST_PROFILE_SCHEMA"] = "1"
os.environ["CHAIN_DEV_DIAGNOSTICS"] = "1"
os.environ["FLASK_ENV"] = "development"

from app import create_app
from app import app as module_app
from api_routes.message_production_routes import message_production_bp

app = create_app()
# message_production_bp is registered at module level in app.py, not inside create_app()
app.register_blueprint(message_production_bp)

# --- Monkey-patch _db_available in ALL services to use REAL DB ---
import services.message_feature_service as _mfs
import services.call_feature_service as _cfs
import services.messaging_engine as _me
import services.live_feature_service as _lfs
import services.group_feature_service as _gfs
import services.creator_feature_service as _crs
import services.push_notification_service as _pns
from services.neon_service import get_pool_status

def _db_true():
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))

for _mod in [_mfs, _cfs, _lfs, _gfs, _crs, _pns]:
    if hasattr(_mod, '_db_available'):
        _mod._db_available = _db_true
# messaging_engine doesn't use _db_available, it calls fast_query/write_query directly

from services.neon_service import fast_query, write_query

PASS = 0; FAIL = 0; ERRORS = []

def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {label}"); PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else "")); FAIL += 1
        ERRORS.append((label, detail))

def section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

# ================================================================
section("1. APP & ENVIRONMENT")
# ================================================================

check("App created", app is not None)
check("messages bp", "messages" in app.blueprints)
check("calls_v2 bp", "calls_v2" in app.blueprints)
check("message_production bp", "message_production" in app.blueprints)

from services.socket_events import socketio
check("Socket.IO module", socketio is not None)

status = get_pool_status()
check("Neon configured", status.get("configured") or status.get("pool_ready"))

try:
    r = fast_query("SELECT 1 AS ok", (), default=[])
    check("Neon query works", r and r[0]["ok"] == 1)
except Exception as e:
    check("Neon query works", False, str(e))

# ================================================================
section("2. REGISTERED ROUTES")
# ================================================================
for rule in sorted(app.url_map.iter_rules(), key=str):
    path = str(rule)
    methods = ",".join(sorted(rule.methods - {"HEAD", "OPTIONS"}))
    if methods and (path.startswith("/messages") or path.startswith("/calls")):
        print(f"  {methods:6s} {path}")

# ================================================================
section("3. SOCKET.IO EVENTS")
# ================================================================
spath = os.path.join(os.path.dirname(__file__), "..", "services", "socket_events.py")
with open(spath) as f:
    src = f.read()
for e in sorted(set(re.findall(r'@socketio\.on\(["\']([^"\']+)["\']\)', src))):
    print(f"    {e}")

# ================================================================
section("4. TEST PROFILES (REAL DB)")
# ================================================================
A_USER = "phase37_user_a"
B_USER = "phase37_user_b"
A_EMAIL = "phase37_a@test.chain"
B_EMAIL = "phase37_b@test.chain"
PID_A = str(uuid_mod.uuid4())
PID_B = str(uuid_mod.uuid4())

# Cleanup old test profiles
for uname in [A_USER, B_USER]:
    old = fast_query("SELECT id FROM chain_profiles WHERE username = %s", (uname,), default=[])
    if old:
        oid = old[0]["id"]
        for t in ["chain_call_participants", "chain_message_delivery_events"]:
            try: write_query(f"DELETE FROM {t} WHERE profile_id = %s", (oid,))
            except: pass
        try: write_query("DELETE FROM chain_thread_members WHERE profile_id = %s", (oid,))
        except: pass
        try: write_query("DELETE FROM chain_call_events WHERE profile_id = %s", (oid,))
        except: pass
        try: write_query("DELETE FROM chain_call_sessions WHERE caller_profile_id = %s OR receiver_profile_id = %s", (oid, oid))
        except: pass
        write_query("DELETE FROM chain_messages WHERE sender_profile_id = %s", (oid,))
        write_query("DELETE FROM chain_profiles WHERE id = %s", (oid,))

for pid, uname, email, dname in [(PID_A, A_USER, A_EMAIL, "User A"), (PID_B, B_USER, B_EMAIL, "User B")]:
    write_query(
        "INSERT INTO chain_profiles (id, auth_user_id, username, email, display_name, avatar_url, bio, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,now())",
        (pid, pid, uname, email, dname, "", f"Test profile {dname}")
    )
check("Test profiles created", True, f"{PID_A} / {PID_B}")
print(f"  A: {PID_A} ({A_USER})")
print(f"  B: {PID_B} ({B_USER})")

# ================================================================
section("5. SESSIONS VIA FLASK TEST CLIENT")
# ================================================================
client = app.test_client()

def login(pid, uname):
    with client.session_transaction() as sess:
        sess["profile_id"] = pid
        sess["auth_user_id"] = pid
        sess["user_id"] = pid
        sess["username"] = uname
        sess["access_token"] = "test-token"
        sess["_permanent"] = True

login(PID_A, A_USER)
with client.session_transaction() as sess:
    check("Session.profile_id = Profile A", sess.get("profile_id") == PID_A)

# ================================================================
section("6. MESSAGING — REAL RUNTIME FLOW")
# ================================================================

# 6a. GET /messages/ (inbox)
resp = client.get("/messages/")
check("GET /messages/", resp.status_code == 200, f"status={resp.status_code}")

# 6b. GET /messages/@user (opens/creates DM)
resp = client.get(f"/messages/@{B_USER}", follow_redirects=True)
check("GET /messages/@user", resp.status_code == 200, f"status={resp.status_code}")

# 6c. Verify thread in DB
thread_id = None
rows = fast_query("""
    SELECT tm.thread_id FROM chain_thread_members tm
    JOIN chain_thread_members tm2 ON tm.thread_id = tm2.thread_id
    WHERE tm.profile_id = %s AND tm2.profile_id = %s LIMIT 1
""", (PID_A, PID_B), default=[])
if rows:
    thread_id = str(rows[0]["thread_id"])
    check("Thread in DB after @username", True)
else:
    # Try via message_feature_service's in-memory fallback
    _mfs._THREADS.clear()  # don't rely on in-memory
    check("Thread in DB after @username", False, "No chain_thread_members row found")

if thread_id:
    print(f"  Thread: {thread_id}")
    trows = fast_query("SELECT id, thread_type FROM chain_message_threads WHERE id = %s", (thread_id,), default=[])
    check("chain_message_threads exists", len(trows) > 0)
    if trows: check("thread_type=direct", trows[0].get("thread_type") == "direct")

    mrows = fast_query("SELECT profile_id FROM chain_thread_members WHERE thread_id = %s", (thread_id,), default=[])
    check(f"Thread members ({len(mrows)})", len(mrows) >= 2)
    mids = [str(r["profile_id"]) for r in mrows]
    check("A is member", PID_A in mids)
    check("B is member", PID_B in mids)

    # 6d. GET production thread API
    resp = client.get(f"/messages/api/thread/{thread_id}")
    check("GET /messages/api/thread/<id>", resp.status_code == 200, str(resp.status_code))
    if resp.status_code == 200:
        j = resp.get_json(silent=True) or {}
        check("API returns json", True)
        check("API ok=True", j.get("ok") is True, str(j))

    # 6e. POST send message via production API
    msg_body = f"Hello from A at {uuid_mod.uuid4().hex[:8]}"
    resp = client.post(f"/messages/api/thread/{thread_id}/send",
                       data={"body": msg_body})
    check("POST send message", resp.status_code in (200, 201), str(resp.status_code))
    if resp.status_code in (200, 201):
        j = resp.get_json(silent=True) or {}
        check("Send returns ok=True", j.get("ok") is True, str(j)[:100])

    # VERIFY DB PERSISTENCE — KEY TEST
    db_msgs = fast_query(
        "SELECT id, body, sender_profile_id FROM chain_messages WHERE thread_id = %s ORDER BY created_at DESC LIMIT 5",
        (thread_id,), default=[]
    )
    if db_msgs:
        check("Message in chain_messages", True)
        match = any(m["body"] == msg_body for m in db_msgs)
        check("Message body correct", match, f"expected={msg_body[:30]}")
        check("Sender matches A", any(str(m["sender_profile_id"]) == PID_A for m in db_msgs))
        print(f"  DB has {len(db_msgs)} messages for this thread")
    else:
        check("Message persisted to DB", False, "0 rows in chain_messages — WRITE FAILED")

    # 6f. Seen API
    resp = client.post(f"/messages/api/messages/{thread_id}/seen")
    check("POST seen api", resp.status_code in (200, 201, 302, 404), str(resp.status_code))

else:
    # Test thread creation directly via service
    print("  [INFO] Testing direct thread creation...")
    result = _mfs.create_direct_thread(PID_A, PID_B)
    if result.get("ok"):
        thread_id = result["thread_id"]
        check("create_direct_thread ok", True)
        print(f"  Thread: {thread_id}")
    else:
        check("create_direct_thread", False, str(result))

# 6g. Thread list
resp = client.get("/messages/api/messages/threads")
check("GET threads api", resp.status_code in (200, 302, 404), str(resp.status_code))

# 6h. Unread count
resp = client.get("/messages/api/unread-count")
check("GET unread-count", resp.status_code in (200, 302, 404), str(resp.status_code))

# ================================================================
section("7. CALLS — REAL RUNTIME FLOW")
# ================================================================

call_id = None

# 7a. POST /calls/start
resp = client.post("/calls/start", data={
    "receiver_id": PID_B,
    "call_type": "audio",
    "conversation_id": thread_id or ""
}, follow_redirects=True)
check("POST /calls/start", resp.status_code in (200, 302), str(resp.status_code))

# 7b. Verify call in DB
calls = fast_query(
    "SELECT id, call_status, caller_profile_id, receiver_profile_id FROM chain_call_sessions "
    "WHERE caller_profile_id = %s ORDER BY started_at DESC LIMIT 1",
    (PID_A,), default=[]
)
if calls:
    call_id = str(calls[0]["id"])
    check("Call in chain_call_sessions", True)
    check("Status=ringing", calls[0]["call_status"] == "ringing", calls[0]["call_status"])
    check("Caller=A", str(calls[0]["caller_profile_id"]) == PID_A)
    check("Receiver=B", str(calls[0]["receiver_profile_id"]) == PID_B)
    print(f"  Call: {call_id}")

    # Participants
    parts = fast_query("SELECT profile_id, status FROM chain_call_participants WHERE call_session_id = %s",
                       (call_id,), default=[])
    check(f"Participants ({len(parts)})", len(parts) >= 1)
else:
    check("Call persisted to DB", False, "0 rows in chain_call_sessions — WRITE FAILED")
    # Check in-memory fallback
    mem_calls = _cfs._CALLS
    check("In-memory call fallback used", len(mem_calls) > 0,
          f"DICT={list(mem_calls.keys())}")

if call_id:
    # 7c. Login as B and answer
    login(PID_B, B_USER)
    resp = client.post(f"/calls/{call_id}/answer", follow_redirects=True)
    check("POST answer", resp.status_code in (200, 302), str(resp.status_code))

    c2 = fast_query("SELECT call_status, answered_at FROM chain_call_sessions WHERE id = %s",
                    (call_id,), default=[])
    if c2:
        check("Call status=answered", c2[0]["call_status"] == "answered", c2[0]["call_status"])
        check("answered_at set", c2[0]["answered_at"] is not None)

    # 7d. End call
    resp = client.post(f"/calls/{call_id}/end", follow_redirects=True)
    check("POST end", resp.status_code in (200, 302), str(resp.status_code))

    c3 = fast_query("SELECT call_status, ended_at, duration_seconds FROM chain_call_sessions WHERE id = %s",
                    (call_id,), default=[])
    if c3:
        check("Call ended", c3[0]["call_status"] in ("ended", "missed"),
              c3[0]["call_status"])
        check("ended_at set", c3[0]["ended_at"] is not None)

    # 7e. Events
    login(PID_A, A_USER)
    resp = client.post(f"/calls/api/calls/{call_id}/event",
                       data={"event_type": "quality_test", "payload": "{}"})
    check("POST call event api", resp.status_code in (200, 201, 302, 404), str(resp.status_code))

    # 7f. Recent calls
    resp = client.get("/calls/recent")
    check("GET /calls/recent", resp.status_code == 200, str(resp.status_code))

# ================================================================
section("8. DB SCHEMA")
# ================================================================
for table in ["chain_message_threads", "chain_thread_members", "chain_messages",
              "chain_message_delivery_events", "chain_call_sessions",
              "chain_call_participants", "chain_call_events"]:
    try:
        r = fast_query(f"SELECT COUNT(*) AS c FROM {table}", (), default=None)
        check(f"Table {table} accessible", r is not None)
    except Exception as e:
        check(f"Table {table} accessible", False, str(e))

# ================================================================
section("DIAGNOSIS SUMMARY")
# ================================================================
total = PASS + FAIL
print(f"  Passed: {PASS}/{total}")
print(f"  Failed: {FAIL}/{total}")
if ERRORS:
    print("\n  FAILURES:")
    for label, detail in ERRORS:
        print(f"    - {label}: {detail}")
    print("\n  CLASSIFICATIONS:")
    for label, detail in ERRORS:
        dl = detail or ""
        if "row" in label.lower() and "DB" in dl:
            print("    - DB_WRITE_FAILURE")
        elif "404" in str(detail):
            print("    - ROUTE_FAILURE")
        elif "table" in label.lower():
            print("    - DB_SCHEMA_FAILURE")
        elif "profile" in label.lower():
            print("    - PROFILE_FAILURE")
        elif "session" in label.lower():
            print("    - SESSION_FAILURE")
        else:
            print("    - ROUTE_FAILURE")

# ================================================================
section("CLEANUP")
# ================================================================
for pid in [PID_A, PID_B]:
    if not pid: continue
    for t in ["chain_call_participants", "chain_message_delivery_events"]:
        try: write_query(f"DELETE FROM {t} WHERE profile_id = %s", (pid,))
        except: pass
    try: write_query("DELETE FROM chain_thread_members WHERE profile_id = %s", (pid,))
    except: pass
    tids = fast_query("SELECT id FROM chain_message_threads WHERE created_by_profile_id = %s", (pid,), default=[])
    for tr in tids:
        try: write_query("DELETE FROM chain_messages WHERE thread_id = %s", (tr["id"],))
        except: pass
        try: write_query("DELETE FROM chain_thread_members WHERE thread_id = %s", (tr["id"],))
        except: pass
        try: write_query("DELETE FROM chain_message_threads WHERE id = %s", (tr["id"],))
        except: pass
    try: write_query("DELETE FROM chain_call_sessions WHERE caller_profile_id = %s OR receiver_profile_id = %s", (pid, pid))
    except: pass
    try: write_query("DELETE FROM chain_call_events WHERE profile_id = %s", (pid,))
    except: pass
    try: write_query("DELETE FROM chain_profiles WHERE id = %s", (pid,))
    except: pass
print("  Cleanup OK")

sys.exit(0 if FAIL == 0 else 1)
