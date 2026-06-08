"""
Phase 37 E2E: Real message send, persistence, seen, unread.
FAILS unless DB write is verified.
"""
import os, sys, uuid as uuid_mod
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "0"
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
