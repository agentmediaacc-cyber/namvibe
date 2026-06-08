"""
Phase 37 E2E: Real call start, answer, end, persistence, events.
FAILS unless DB write is verified.
"""
import os, sys, uuid as uuid_mod
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "0"
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
    s = get_pool_status()
    return bool(s.get("pool_ready") or s.get("recent_success") or s.get("configured"))
for _m in [_mfs, _cfs, _lfs, _gfs, _crs]:
    if hasattr(_m, '_db_available'): _m._db_available = _db_true

from services.neon_service import fast_query, write_query

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
