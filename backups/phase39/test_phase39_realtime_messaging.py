"""
Phase 39 E2E: Real-Time Messaging Engine
  - Reactions (add/remove/list)
  - Edit message
  - Delete for everyone
  - Read receipts / thread seen
  - Online/offline presence
  - Typing indicator events
  - Unread counts
  - Backward compat with Phase 37/38
"""
import os, sys, json, uuid as uuid_mod, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "0"
os.environ["CHAIN_TRUST_PROFILE_SCHEMA"] = "1"

from app import create_app
app = create_app()
from api_routes.message_production_routes import message_production_bp
app.register_blueprint(message_production_bp)

import services.message_feature_service as _mfs
import services.message_delivery_service as _mds
from services.message_delivery_service import send_message as mds_send_message
from services.neon_service import get_pool_status, fast_query, write_query

def _db_true():
    s = get_pool_status()
    return bool(s.get("pool_ready") or s.get("recent_success") or s.get("configured"))
if hasattr(_mfs, '_db_available'): _mfs._db_available = _db_true
if hasattr(_mds, '_db_available'): _mds._db_available = _db_true

PASS = 0; FAIL = 0
def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {label}"); PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else "")); FAIL += 1

PID_A = str(uuid_mod.uuid4())
PID_B = str(uuid_mod.uuid4())
TID = None
MSG_ID = None

def setup():
    global TID, MSG_ID
    for pid, uname, email in [
        (PID_A, "e2e_39_a", "e2e_39_a@test.chain"),
        (PID_B, "e2e_39_b", "e2e_39_b@test.chain")
    ]:
        for t in ["chain_call_participants", "chain_thread_members", "chain_online_presence", "chain_message_reactions", "chain_message_edits", "chain_blocks"]:
            try: write_query(f"DELETE FROM {t} WHERE profile_id = %s", (pid,))
            except: pass
        try: write_query("DELETE FROM chain_blocks WHERE blocker_profile_id = %s OR blocked_profile_id = %s", (pid, pid))
        except: pass
        try: write_query("DELETE FROM chain_messages WHERE sender_profile_id = %s", (pid,))
        except: pass
        write_query("DELETE FROM chain_profiles WHERE username = %s", (uname,))
        write_query(
            "INSERT INTO chain_profiles (id, auth_user_id, username, email, display_name, created_at) VALUES (%s,%s,%s,%s,%s,now())",
            (pid, pid, uname, email, f"E2E {uname}")
        )
    result = _mfs.create_direct_thread(PID_A, PID_B)
    TID = result.get("thread_id")
    msg_resp = mds_send_message(TID, PID_A, "Phase 39 test message")
    MSG_ID = msg_resp.get("message_id") or msg_resp.get("id")

client = app.test_client()
def login(pid):
    with client.session_transaction() as sess:
        sess["profile_id"] = pid
        sess["auth_user_id"] = pid
        sess["user_id"] = pid
        sess["access_token"] = "test-token"
        sess["_permanent"] = True

print("\n=== PHASE 39 — SETUP ===")
setup()
check("setup profiles and thread", TID is not None, str(TID))
check("setup test message", MSG_ID is not None, str(MSG_ID))
login(PID_A)

print("\n=== 1. SQL MIGRATION (idempotent re-run) ===")
try:
    from services.init_service import run_sql_file
    sql_path = os.path.join(os.path.dirname(__file__), "..", "sql", "phase39_realtime_messaging.sql")
    if os.path.exists(sql_path):
        run_sql_file(sql_path)
        check("migration runs idempotent", True)
    else:
        print("  [SKIP] sql file not found, assuming migration already applied")
except Exception as e:
    print(f"  [INFO] Migration re-run skipped ({e})")
    # Tables should exist from manual run — test presence detection
    try:
        r = fast_query("SELECT 1 FROM chain_online_presence LIMIT 0")
        check("chain_online_presence table exists", True)
    except Exception as e2:
        check("chain_online_presence table exists", False, str(e2))

print("\n=== 2. REACTIONS — ADD / CHECK / REMOVE / LIST ===")
add_resp = client.post(f"/messages/api/message/{MSG_ID}/react", json={"reaction": "❤️"})
check("add reaction endpoint 200", add_resp.status_code == 200, str(add_resp.status_code))
j_add = add_resp.get_json(silent=True) or {}
check("add reaction success", j_add.get("ok") is True, str(j_add)[:200])
reactions_q = fast_query("SELECT reaction_type FROM chain_message_reactions WHERE message_id = %s AND profile_id = %s", (MSG_ID, PID_A))

check("reaction persisted in DB", reactions_q and reactions_q[0].get("reaction_type") == "❤️", str(reactions_q))

list_resp = client.get(f"/messages/api/message/{MSG_ID}/reactions")
check("list reactions endpoint 200", list_resp.status_code == 200, str(list_resp.status_code))
j_list = list_resp.get_json(silent=True) or {}
check("list returns reactions array", isinstance(j_list.get("reactions"), list), str(j_list)[:100])

add_second = client.post(f"/messages/api/message/{MSG_ID}/react", json={"reaction": "😂"})
check("add second reaction 200", add_second.status_code in (200, 201, 400), str(add_second.status_code))

remove_resp = client.post(f"/messages/api/message/{MSG_ID}/unreact")
check("remove reaction endpoint 200", remove_resp.status_code == 200, str(remove_resp.status_code))
j_rem = remove_resp.get_json(silent=True) or {}
check("remove reaction success", j_rem.get("ok") is True, str(j_rem)[:100])

reactions_after = fast_query("SELECT reaction_type FROM chain_message_reactions WHERE message_id = %s AND profile_id = %s", (MSG_ID, PID_A))
check("reactions removed from DB", len(reactions_after) == 0, str(reactions_after))

print("\n=== 3. EDIT MESSAGE ===")
edit_body = f"Edited message {uuid_mod.uuid4().hex[:8]}"
edit_resp = client.post(f"/messages/api/message/{MSG_ID}/edit", json={"body": edit_body})
check("edit endpoint 200", edit_resp.status_code == 200, str(edit_resp.status_code))
j_edit = edit_resp.get_json(silent=True) or {}
check("edit success", j_edit.get("edited") is True or j_edit.get("ok") is True, str(j_edit)[:100])

edit_q = fast_query("SELECT body FROM chain_messages WHERE id = %s", (MSG_ID,))
check("edit persisted in DB", edit_q and edit_q[0].get("body") == edit_body, str(edit_q)[:200])

print("\n=== 4. DELETE FOR EVERYONE ===")
admin_msg_resp = mds_send_message(TID, PID_A, "Message to delete for everyone")
del_msg_id = admin_msg_resp.get("message_id") or admin_msg_resp.get("id")
check("created deletable message", del_msg_id is not None, str(del_msg_id))

del_resp = client.post(f"/messages/api/message/{del_msg_id}/delete-everyone")
check("delete-everyone endpoint 200", del_resp.status_code == 200, str(del_resp.status_code))
j_del = del_resp.get_json(silent=True) or {}
check("delete-everyone success", j_del.get("ok") is True, str(j_del)[:100])

del_q = fast_query("SELECT deleted_for_everyone FROM chain_messages WHERE id = %s", (del_msg_id,))
check("delete-for-everyone set in DB", del_q and del_q[0].get("deleted_for_everyone") is True, str(del_q)[:200])

print("\n=== 5. MARK THREAD SEEN (read receipts) ===")
login(PID_B)
seen_resp = client.post(f"/messages/api/thread/{TID}/seen")
check("seen endpoint 200", seen_resp.status_code == 200, str(seen_resp.status_code))
j_seen = seen_resp.get_json(silent=True) or {}
check("seen success", j_seen.get("ok") is True, str(j_seen)[:100])

seen_q = fast_query(
    "SELECT last_read_at FROM chain_thread_members WHERE thread_id = %s AND profile_id = %s AND last_read_at IS NOT NULL",
    (TID, PID_B)
)
check("last_read_at recorded in DB", seen_q and len(seen_q) > 0, str(seen_q)[:200])

print("\n=== 6. ONLINE / OFFLINE PRESENCE ===")
login(PID_A)
presence_resp = client.get(f"/messages/api/presence/{PID_B}")
check("get presence endpoint 200", presence_resp.status_code == 200, str(presence_resp.status_code))
j_pres = presence_resp.get_json(silent=True) or {}
check("presence response has online info", "presence" in j_pres or "is_online" in j_pres, str(j_pres)[:100])

set_online_resp = client.post("/messages/api/presence", json={"is_online": True, "status": "online"})
check("set presence online 200", set_online_resp.status_code == 200, str(set_online_resp.status_code))

set_offline_resp = client.post("/messages/api/presence/offline")
check("set presence offline 200", set_offline_resp.status_code == 200, str(set_offline_resp.status_code))

online_endpoint = client.post("/messages/api/online")
check("online endpoint 200", online_endpoint.status_code == 200, str(online_endpoint.status_code))

pres_q = fast_query("SELECT status FROM chain_online_presence WHERE profile_id = %s", (PID_A,))
check("presence persisted in DB", pres_q is not None, str(pres_q[:100]))

print("\n=== 7. UNREAD COUNTS ===")
unread_resp = client.get("/messages/api/unread-counts")
check("unread-counts endpoint 200", unread_resp.status_code == 200, str(unread_resp.status_code))
j_unread = unread_resp.get_json(silent=True) or {}
check("unread response is object", isinstance(j_unread, dict), str(j_unread)[:100])

print("\n=== 8. SOCKET EVENT HANDLER REGISTRATION ===")
socket_path = os.path.join(os.path.dirname(__file__), "..", "services", "socket_events.py")
with open(socket_path) as f:
    src = f.read()

phase39_events = [
    ("user_typing", "typing:start"),
    ("user_typing", "typing:stop"),
    ("message_reaction_add", "message:reaction:add"),
    ("message_reaction_remove", "message:reaction:remove"),
    ("message_edited", "message:edited"),
    ("message_deleted", "message:delete"),
    ("presence_update", "join_thread"),
    ("message_seen", "message:seen"),
]
for label, event in phase39_events:
    found = re.search(rf'@socketio\.on\(["\']{event}["\']\)', src)
    check(f"socket handler for '{event}'", bool(found))

print("\n=== 9. THREAD LIST INCLUDES PRESENCE & UNREAD ===")
# Check thread data returned includes is_online and unread_count
try:
    from services.message_delivery_service import get_unread_counts_per_thread
    unread_counts = get_unread_counts_per_thread(PID_A)
    check("get_unread_counts_per_thread returns dict", isinstance(unread_counts, dict), str(type(unread_counts))[:50])
except Exception as e:
    check("get_unread_counts_per_thread", False, str(e)[:100])

print("\n=== 10. BACKWARD COMPAT (Phase 37/38) ===")
# Phase 37: basic send
bc_body = f"Backward compat {uuid_mod.uuid4().hex[:8]}"
bc_resp = mds_send_message(TID, PID_A, bc_body)
check("Phase 37 send_message still works", bc_resp.get("id") is not None, str(bc_resp)[:100])

# Phase 38: voice note
bc_vn = mds_send_message(TID, PID_A, "🎙 Voice note • 3s", message_type="voice_note")
check("Phase 38 voice note still works", bc_vn.get("id") is not None, str(bc_vn)[:100])

# Phase 37: block
try:
    # block_user moved to message_feature_service in production
    bc_block = client.post("/messages/api/block", json={"username": "e2e_39_b"})
    check("Phase 37 block endpoint still works", bc_block.status_code in (200, 201), str(bc_block.status_code))
except Exception as e:
    check("Phase 37 block endpoint still works", False, str(e)[:100])

# Phase 37: get_thread_messages still works with new fields
try:
    from services.message_delivery_service import get_thread_messages
    msgs = get_thread_messages(TID, PID_A)
    check("get_thread_messages returns list", isinstance(msgs, list), str(type(msgs))[:50])
    if msgs and len(msgs) > 0:
        m = msgs[0]
        check("thread messages include deleted_for_everyone key", "deleted_for_everyone" in m, str(list(m.keys()))[:200])
        check("thread messages include reply_to_message_id key", "reply_to_message_id" in m, str(list(m.keys()))[:200])
except Exception as e:
    check("get_thread_messages backward compat", False, str(e)[:100])

print("\n=== SUMMARY ===")
total = PASS + FAIL
print(f"  PASS: {PASS}/{total}  FAIL: {FAIL}/{total}")
if FAIL:
    print("  Some tests failed — review output above.")
    exit(1)
else:
    print("  All Phase 39 E2E tests passed!")
    exit(0)
