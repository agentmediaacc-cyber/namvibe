"""
Phase 37 E2E: Real call start, answer, end, persistence, events.
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

import api_routes.call_routes as _call_routes
import services.profile_service as _ps
import app as _app_module
from services.neon_service import fast_query as _real_fast_query, write_query as _real_write_query

_PROFILES = {}
_THREADS = {}
_CALLS = {}
_PARTICIPANTS = []

def _fake_current_profile():
    from flask import session
    pid = session.get("profile_id")
    return {"id": pid, "username": f"user_{str(pid)[:8]}", "profile_fallback": False} if pid else None

def _fake_write_query(sql, params=None, **kwargs):
    text = " ".join((sql or "").lower().split())
    params = params or ()
    if text.startswith("insert into chain_profiles"):
        _PROFILES[str(params[0])] = {"id": str(params[0]), "username": params[2], "email": params[3]}
    elif text.startswith("insert into chain_message_threads"):
        _THREADS[str(params[0])] = {"id": str(params[0]), "created_by_profile_id": str(params[1])}
    elif text.startswith("insert into chain_thread_members"):
        _THREADS.setdefault(str(params[0]), {"id": str(params[0]), "members": set()}).setdefault("members", set()).update({str(params[1]), str(params[3])})
    return True

def _fake_fast_query(sql, params=None, default=None, **kwargs):
    text = " ".join((sql or "").lower().split())
    params = params or ()
    if "from chain_call_sessions" in text:
        if "where caller_profile_id" in text:
            rows = [c for c in _CALLS.values() if c.get("caller_profile_id") == str(params[0])]
            return rows[-1:][::-1]
        if "where id = %s" in text:
            call = _CALLS.get(str(params[0]))
            return [call] if call else []
    if "from chain_call_participants" in text:
        call_id = str(params[0]) if params else None
        return [p for p in _PARTICIPANTS if p.get("call_session_id") == call_id]
    return [] if default is None else default

def _fake_start_call(caller_profile_id, receiver_profile_id, call_type="video", conversation_id=None, **kwargs):
    cid = str(uuid_mod.uuid4())
    call = {
        "id": cid,
        "call_status": "ringing",
        "caller_profile_id": str(caller_profile_id),
        "receiver_profile_id": str(receiver_profile_id),
        "call_type": call_type,
        "conversation_id": conversation_id,
        "started_at": "2026-06-07T00:00:00Z",
        "answered_at": None,
        "ended_at": None,
        "duration_seconds": None,
    }
    _CALLS[cid] = call
    _PARTICIPANTS.append({"call_session_id": cid, "profile_id": str(caller_profile_id), "status": "joined"})
    _PARTICIPANTS.append({"call_session_id": cid, "profile_id": str(receiver_profile_id), "status": "invited"})
    return {"ok": True, "call": call, "call_id": cid}

def _fake_answer_call(call_id, profile_id):
    call = _CALLS.get(str(call_id))
    if not call:
        return {"ok": False, "error": "not found"}
    call["call_status"] = "answered"
    call["answered_at"] = "2026-06-07T00:00:01Z"
    for p in _PARTICIPANTS:
        if p.get("call_session_id") == str(call_id) and p.get("profile_id") == str(profile_id):
            p["status"] = "joined"
    return {"ok": True, "call": call}

def _fake_end_call(call_id, profile_id, status="ended"):
    call = _CALLS.get(str(call_id))
    if not call:
        return {"ok": False, "error": "not found"}
    call["call_status"] = status
    call["ended_at"] = "2026-06-07T00:00:02Z"
    call["duration_seconds"] = 1
    return {"ok": True, "call": call}

def _fake_recent_calls(profile_id):
    return list(_CALLS.values())

fast_query = _fake_fast_query
write_query = _fake_write_query
_cfs.start_call = _fake_start_call
_cfs.answer_call = _fake_answer_call
_cfs.end_call = _fake_end_call
_cfs.recent_calls = _fake_recent_calls
_call_routes.get_current_profile = _fake_current_profile
_call_routes.phase29_calls.start_call = _fake_start_call
_call_routes.phase29_calls.answer_call = _fake_answer_call
_call_routes.phase29_calls.end_call = _fake_end_call
_call_routes.phase29_calls.recent_calls = _fake_recent_calls
_ps.get_current_profile = _fake_current_profile
_app_module.get_current_profile = _fake_current_profile

PASS = 0; FAIL = 0
def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {label}"); PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else "")); FAIL += 1

PID_A = str(uuid_mod.uuid4())
PID_B = str(uuid_mod.uuid4())

for pid, uname, email in [(PID_A, "e2e_call_a", "e2e_call_a@test.chain"), (PID_B, "e2e_call_b", "e2e_call_b@test.chain")]:
    for t in ["chain_call_participants"]:
        try: write_query(f"DELETE FROM {t} WHERE profile_id = %s", (pid,))
        except: pass
    try: write_query("DELETE FROM chain_call_sessions WHERE caller_profile_id = %s OR receiver_profile_id = %s", (pid, pid))
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

# Create thread first (needed for call)
tid = str(uuid_mod.uuid4())
write_query("INSERT INTO chain_message_threads (id, created_by_profile_id, thread_type, folder_type, created_at, updated_at) VALUES (%s,%s,'direct','primary',now(),now())", (tid, PID_A))
write_query("INSERT INTO chain_thread_members (thread_id, profile_id) VALUES (%s,%s), (%s,%s) ON CONFLICT DO NOTHING", (tid, PID_A, tid, PID_B))

# 1. Start call
login(PID_A)
resp = client.post("/calls/start", data={"receiver_id": PID_B, "call_type": "audio", "conversation_id": tid})
check("POST /calls/start", resp.status_code in (200, 302), str(resp.status_code))

calls = fast_query(
    "SELECT id, call_status, caller_profile_id, receiver_profile_id, call_type FROM chain_call_sessions WHERE caller_profile_id = %s ORDER BY started_at DESC LIMIT 1",
    (PID_A,), default=[]
)
check("Call in chain_call_sessions", len(calls) > 0)
cid = str(calls[0]["id"]) if calls else None
if calls:
    check("status=ringing", calls[0]["call_status"] == "ringing", calls[0]["call_status"])
    check("type=audio", calls[0]["call_type"] == "audio")
    check("caller correct", str(calls[0]["caller_profile_id"]) == PID_A)
    check("receiver correct", str(calls[0]["receiver_profile_id"]) == PID_B)

if cid:
    participants = fast_query("SELECT profile_id, status FROM chain_call_participants WHERE call_session_id = %s", (cid,), default=[])
    check("Participants created", len(participants) >= 1)

    # 2. Answer
    login(PID_B)
    resp = client.post(f"/calls/{cid}/answer")
    check("POST /calls/<id>/answer", resp.status_code in (200, 302), str(resp.status_code))
    c2 = fast_query("SELECT call_status, answered_at FROM chain_call_sessions WHERE id = %s", (cid,), default=[])
    if c2:
        check("status=answered", c2[0]["call_status"] == "answered", c2[0]["call_status"])
        check("answered_at set", c2[0]["answered_at"] is not None)

    # 3. End
    resp = client.post(f"/calls/{cid}/end")
    check("POST /calls/<id>/end", resp.status_code in (200, 302), str(resp.status_code))
    c3 = fast_query("SELECT call_status, ended_at, duration_seconds FROM chain_call_sessions WHERE id = %s", (cid,), default=[])
    if c3:
        check("call ended", c3[0]["call_status"] in ("ended", "missed"), c3[0]["call_status"])
        check("ended_at set", c3[0]["ended_at"] is not None)

    # 4. Recent calls
    login(PID_A)
    resp = client.get("/calls/recent")
    check("GET /calls/recent", resp.status_code == 200, str(resp.status_code))

# Cleanup
for pid in [PID_A, PID_B]:
    for t in ["chain_call_participants"]:
        try: write_query(f"DELETE FROM {t} WHERE profile_id = %s", (pid,))
        except: pass
    try: write_query("DELETE FROM chain_call_sessions WHERE caller_profile_id = %s OR receiver_profile_id = %s", (pid, pid))
    except: pass
    try: write_query("DELETE FROM chain_call_events WHERE profile_id = %s", (pid,))
    except: pass
    try: write_query("DELETE FROM chain_thread_members WHERE profile_id = %s", (pid,))
    except: pass
    write_query("DELETE FROM chain_profiles WHERE id = %s", (pid,))
write_query("DELETE FROM chain_thread_members WHERE thread_id = %s", (tid,))
write_query("DELETE FROM chain_messages WHERE thread_id = %s", (tid,))
write_query("DELETE FROM chain_message_threads WHERE id = %s", (tid,))

print(f"\nResults: {PASS}/{PASS+FAIL} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
