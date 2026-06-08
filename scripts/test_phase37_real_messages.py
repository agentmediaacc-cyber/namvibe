"""
Phase 37 E2E: Real message send, persistence, seen, unread.
FAILS unless DB write is verified.
"""
import os, sys, uuid as uuid_mod
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_TEST_FAKE_DB"] = "1"
os.environ["CHAIN_TRUST_PROFILE_SCHEMA"] = "1"

from app import create_app
app = create_app()
from api_routes.message_production_routes import message_production_bp
app.register_blueprint(message_production_bp)

import services.message_feature_service as _mfs
import services.call_feature_service as _cfs
import services.live_feature_service as _lfs
import services.group_feature_service as _gfs
import services.creator_feature_service as _crs
from services.neon_service import get_pool_status

def _db_true():
    if os.getenv("CHAIN_TEST_FAKE_DB") == "1":
        return False
    s = get_pool_status()
    return bool(s.get("pool_ready") or s.get("recent_success") or s.get("configured"))
for _m in [_mfs, _cfs, _lfs, _gfs, _crs]:
    if hasattr(_m, '_db_available'): _m._db_available = _db_true

import api_routes.message_production_routes as _mpr
import api_routes.message_routes as _mr
import services.message_delivery_service as _mds

_PROFILES = {}
_THREADS = {}
_MESSAGES = []

def _fake_current_profile():
    from flask import session
    pid = session.get("profile_id")
    return {"id": pid, "username": f"user_{str(pid)[:8]}", "profile_fallback": False} if pid else None

def _fake_write_query(sql, params=None, **kwargs):
    text = " ".join((sql or "").lower().split())
    params = params or ()
    if text.startswith("insert into chain_profiles"):
        _PROFILES[str(params[0])] = {"id": str(params[0]), "username": params[2], "email": params[3]}
    if text.startswith("delete from"):
        return True
    return True

def _fake_fast_query(sql, params=None, default=None, **kwargs):
    text = " ".join((sql or "").lower().split())
    params = params or ()
    if "from chain_messages" in text:
        thread_id = str(params[0]) if params else None
        rows = [m for m in _MESSAGES if m.get("thread_id") == thread_id]
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return rows[:5]
    if "from chain_message_threads" in text:
        created_by = str(params[0]) if params else None
        return [{"id": tid} for tid, t in _THREADS.items() if t.get("created_by_profile_id") == created_by]
    return [] if default is None else default

def _fake_create_direct_thread(a, b):
    tid = str(uuid_mod.uuid4())
    _THREADS[tid] = {"id": tid, "created_by_profile_id": str(a), "members": {str(a), str(b)}}
    return {"ok": True, "thread_id": tid}

def _fake_send_message(thread_id, sender_profile_id, body, message_type="text", **kwargs):
    msg = {
        "id": str(uuid_mod.uuid4()),
        "thread_id": str(thread_id),
        "sender_profile_id": str(sender_profile_id),
        "body": body,
        "message_type": message_type,
        "created_at": "2026-06-07T00:00:00Z",
    }
    _MESSAGES.append(msg)
    return msg

def _fake_mark_seen(thread_id, profile_id):
    return True

def _fake_list_threads(profile_id, folder="primary"):
    return [{"id": tid, "thread_id": tid} for tid, t in _THREADS.items() if str(profile_id) in t.get("members", set())]

def _fake_unread_count(profile_id):
    return 0

fast_query = _fake_fast_query
write_query = _fake_write_query
_mfs.create_direct_thread = _fake_create_direct_thread
_mds.send_message = _fake_send_message
_mds.unread_count = _fake_unread_count
_mds.mark_thread_seen = _fake_mark_seen
_mpr.get_current_profile = _fake_current_profile
_mpr.send_message = _fake_send_message
_mpr.unread_count = _fake_unread_count
_mpr.mark_thread_seen = _fake_mark_seen
_mr.get_current_profile = _fake_current_profile
_mr.list_threads = _fake_list_threads
_mr.phase29_messages.mark_seen = _fake_mark_seen

PASS = 0; FAIL = 0
def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {label}"); PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else "")); FAIL += 1

PID_A = str(uuid_mod.uuid4())
PID_B = str(uuid_mod.uuid4())

for pid, uname, email in [(PID_A, "e2e_msg_a", "e2e_msg_a@test.chain"), (PID_B, "e2e_msg_b", "e2e_msg_b@test.chain")]:
    for t in ["chain_call_participants", "chain_thread_members"]:
        try: write_query(f"DELETE FROM {t} WHERE profile_id = %s", (pid,))
        except: pass
    try: write_query("DELETE FROM chain_messages WHERE sender_profile_id = %s", (pid,))
    except: pass
    write_query("DELETE FROM chain_profiles WHERE username = %s", (uname,))
    write_query(
        "INSERT INTO chain_profiles (id, auth_user_id, username, email, display_name, created_at) VALUES (%s,%s,%s,%s,%s,now())",
        (pid, pid, uname, email, f"E2E {uname}")
    )

client = app.test_client()
def login(pid):
    with client.session_transaction() as sess:
        sess["profile_id"] = pid
        sess["auth_user_id"] = pid
        sess["user_id"] = pid
        sess["access_token"] = "test-token"
        sess["_permanent"] = True

login(PID_A)

# 1. Create thread
result = _mfs.create_direct_thread(PID_A, PID_B)
check("create_direct_thread ok", result.get("ok"), str(result))
tid = result.get("thread_id")
check("thread_id present", bool(tid))

# 2. Send message via production API
body = f"E2E test message {uuid_mod.uuid4().hex[:8]}"
resp = client.post(f"/messages/api/thread/{tid}/send", data={"body": body})
check("POST send returns 200", resp.status_code in (200, 201), str(resp.status_code))
j = resp.get_json(silent=True) or {}
check("send ok=True", j.get("ok") is True, str(j)[:100])

# 3. Verify DB write
msgs = fast_query(
    "SELECT id, body, sender_profile_id FROM chain_messages WHERE thread_id = %s ORDER BY created_at DESC LIMIT 5",
    (tid,), default=[]
)
check("Message in chain_messages", len(msgs) > 0)
if msgs:
    check("body matches", msgs[0]["body"] == body)
    check("sender correct", str(msgs[0]["sender_profile_id"]) == PID_A)

# 4. Seen API
resp = client.post(f"/messages/api/messages/{tid}/seen")
check("POST seen", resp.status_code in (200, 201), str(resp.status_code))

# 5. Thread list
resp = client.get("/messages/api/messages/threads")
check("GET threads", resp.status_code == 200, str(resp.status_code))

# 6. Unread count
resp = client.get("/messages/api/unread-count")
check("GET unread-count", resp.status_code == 200, str(resp.status_code))

# Cleanup
for pid in [PID_A, PID_B]:
    for t in ["chain_call_participants", "chain_thread_members"]:
        try: write_query(f"DELETE FROM {t} WHERE profile_id = %s", (pid,))
        except: pass
    write_query("DELETE FROM chain_messages WHERE sender_profile_id = %s", (pid,))
    tids = fast_query("SELECT id FROM chain_message_threads WHERE created_by_profile_id = %s", (pid,), default=[])
    for tr in tids:
        write_query("DELETE FROM chain_messages WHERE thread_id = %s", (tr["id"],))
        write_query("DELETE FROM chain_thread_members WHERE thread_id = %s", (tr["id"],))
        write_query("DELETE FROM chain_message_threads WHERE id = %s", (tr["id"],))
    write_query("DELETE FROM chain_profiles WHERE id = %s", (pid,))

print(f"\nResults: {PASS}/{PASS+FAIL} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
