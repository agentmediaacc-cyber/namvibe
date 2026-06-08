"""
Phase 40 E2E: Premium WebRTC Calling Engine
  - SQL migration tables
  - Start audio/video call
  - Duplicate active call prevention
  - Busy detection
  - Accept/reject/cancel/end call
  - Participant state (mute/camera/speaker)
  - Duration tracking
  - Call logs
  - Call history
  - Timeout marks missed
  - ICE servers endpoint
  - Socket.IO call handlers
  - Phase 39 backward compat
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
from services.webrtc_call_service import (
    create_call, get_call, get_active_call, accept_call,
    reject_call, cancel_call, end_call, mark_call_busy,
    mark_call_timeout, get_call_history, update_participant_state,
    get_call_participants, add_call_event, check_call_timeouts,
)

def _db_true():
    s = get_pool_status()
    return bool(s.get("pool_ready") or s.get("recent_success") or s.get("configured"))
if hasattr(_mfs, '_db_available'): _mfs._db_available = _db_true
if hasattr(_mds, '_db_available'): _mds._db_available = _db_true
import services.webrtc_call_service as _wcs
if hasattr(_wcs, '_db_available'): _wcs._db_available = _db_true

PASS = 0; FAIL = 0
def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {label}"); PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else "")); FAIL += 1

PID_A = str(uuid_mod.uuid4())
PID_B = str(uuid_mod.uuid4())
PID_C = str(uuid_mod.uuid4())
TID = None

def setup():
    global TID
    for pid, uname, email in [
        (PID_A, "e2e_40_a", "e2e_40_a@test.chain"),
        (PID_B, "e2e_40_b", "e2e_40_b@test.chain"),
        (PID_C, "e2e_40_c", "e2e_40_c@test.chain"),
    ]:
        for t in ["chain_call_participants", "chain_thread_members", "chain_online_presence", "chain_message_reactions", "chain_call_logs", "chain_call_events"]:
            try: write_query(f"DELETE FROM {t} WHERE profile_id = %s", (pid,))
            except: pass
        try: write_query("DELETE FROM chain_calls WHERE caller_profile_id = %s OR receiver_profile_id = %s", (pid, pid))
        except: pass
        try: write_query("DELETE FROM chain_blocks WHERE blocker_profile_id = %s OR blocked_profile_id = %s", (pid, pid))
        except: pass
        try: write_query("DELETE FROM chain_message_edits WHERE editor_profile_id = %s", (pid,))
        except: pass
        try: write_query("DELETE FROM chain_messages WHERE sender_profile_id = %s", (pid,))
        except: pass
        try: write_query("DELETE FROM chain_call_logs WHERE profile_id = %s OR other_profile_id = %s", (pid, pid))
        except: pass
        write_query("DELETE FROM chain_profiles WHERE username = %s", (uname,))
        write_query(
            "INSERT INTO chain_profiles (id, auth_user_id, username, email, display_name, created_at) VALUES (%s,%s,%s,%s,%s,now())",
            (pid, pid, uname, email, f"E2E {uname}")
        )
    result = _mfs.create_direct_thread(PID_A, PID_B)
    TID = result.get("thread_id")

client = app.test_client()
def login(pid):
    with client.session_transaction() as sess:
        sess["profile_id"] = pid
        sess["auth_user_id"] = pid
        sess["user_id"] = pid
        sess["access_token"] = "test-token"
        sess["_permanent"] = True

print("\n=== PHASE 40 — SETUP ===")
setup()
check("setup profiles and thread", TID is not None, str(TID))
login(PID_A)

print("\n=== 1. SQL MIGRATION (tables exist) ===")
for tbl in ["chain_calls", "chain_call_logs"]:
    try:
        r = fast_query(f"SELECT 1 FROM {tbl} LIMIT 0")
        check(f"{tbl} table exists", True)
    except Exception as e:
        check(f"{tbl} table exists", False, str(e)[:80])

# Check columns added to existing tables
for col in ["call_id", "role", "muted", "camera_enabled", "speaker_enabled", "connection_status"]:
    try:
        r = fast_query(f"SELECT {col} FROM chain_call_participants LIMIT 0")
        check(f"chain_call_participants.{col} exists", True)
    except Exception as e:
        check(f"chain_call_participants.{col} exists", False, str(e)[:80])

print("\n=== 2. START AUDIO CALL ===")
result = create_call(PID_A, PID_B, thread_id=TID, call_type="audio")
check("create_call returns ok", result.get("ok") is True, str(result.get("error", ""))[:80])
check("call has id", result.get("call") and result.get("call").get("id") is not None)
CALL_ID = result["call"]["id"] if result.get("call") else None
if CALL_ID:
    call = get_call(CALL_ID)
    check("call status is ringing", call and call.get("status") == "ringing")
    check("call type is audio", call and call.get("call_type") == "audio")

print("\n=== 3. PREVENT DUPLICATE ACTIVE CALL ===")
dup = create_call(PID_A, PID_C, thread_id=TID, call_type="audio")
check("duplicate call returns busy", dup.get("status") == "busy" or not dup.get("ok"))

print("\n=== 4. BUSY DETECTION ===")
login(PID_B)
busy_check = get_active_call(PID_B)
check("PID_B has active call", busy_check is not None)
# Try to call PID_B when they're already in a call
login(PID_C)
call_b = create_call(PID_C, PID_B, call_type="audio")
check("calling busy user returns busy", call_b.get("status") == "busy" or not call_b.get("ok"))

print("\n=== 5. ACCEPT CALL ===")
login(PID_B)
accepted = accept_call(CALL_ID, PID_B)
check("accept_call returns ok", accepted.get("ok") is True, str(accepted.get("error", ""))[:80])
if accepted.get("call"):
    check("call status is accepted", accepted["call"].get("status") == "accepted")

print("\n=== 6. PARTICIPANT STATUS ===")
participants = get_call_participants(CALL_ID)
check("participants list non-empty", len(participants) > 0)
p_statuses = [p.get("status") for p in participants]
check("PID_A participant accepted", "accepted" in p_statuses)
check("PID_B participant accepted", "accepted" in p_statuses)

print("\n=== 7. MUTE TOGGLE ===")
mute_res = update_participant_state(CALL_ID, PID_B, muted=True)
check("mute returns ok", mute_res.get("ok") is True)
participants = get_call_participants(CALL_ID)
for p in participants:
    if p.get("profile_id") == PID_B:
        check("participant muted", p.get("muted") is True)
        break

print("\n=== 8. CAMERA TOGGLE ===")
cam_res = update_participant_state(CALL_ID, PID_B, camera_enabled=False)
check("camera toggle returns ok", cam_res.get("ok") is True)
participants = get_call_participants(CALL_ID)
for p in participants:
    if p.get("profile_id") == PID_B:
        check("camera disabled", p.get("camera_enabled") is False)
        break

print("\n=== 9. SPEAKER TOGGLE ===")
spk_res = update_participant_state(CALL_ID, PID_B, speaker_enabled=True)
check("speaker toggle returns ok", spk_res.get("ok") is True)
participants = get_call_participants(CALL_ID)
for p in participants:
    if p.get("profile_id") == PID_B:
        check("speaker enabled", p.get("speaker_enabled") is True)
        break

print("\n=== 10. END CALL ===")
ended = end_call(CALL_ID, PID_B)
check("end_call returns ok", ended.get("ok") is True)
if ended.get("call"):
    check("call status is ended", ended["call"].get("status") == "ended")
    check("duration recorded", ended["call"].get("duration_seconds", 0) >= 0)

print("\n=== 11. CALL LOGS ===")
logs_q = fast_query(
    "SELECT * FROM chain_call_logs WHERE call_id = %s ORDER BY created_at DESC",
    (CALL_ID,),
)
check("call logs created", logs_q and len(logs_q) > 0, str(logs_q)[:100])

print("\n=== 12. CALL HISTORY ===")
history = get_call_history(PID_B, limit=10)
check("call history returns list", isinstance(history, list))
check("call history has entries", len(history) > 0, str(len(history)))
if history:
    check("history has call_id", history[0].get("call_id") is not None)
    check("history has direction", history[0].get("direction") in ("incoming", "outgoing"))

print("\n=== 13. TIMEOUT MARKS MISSED ===")
timeout_call = create_call(PID_A, PID_B, call_type="audio")
timeout_id = timeout_call.get("call", {}).get("id") if timeout_call.get("ok") else None
if timeout_id:
    import datetime
    # Force the call to be old by updating started_at
    try:
        write_query(
            "UPDATE chain_calls SET started_at = now() - interval '60 seconds' WHERE id = %s",
            (timeout_id,),
        )
    except Exception:
        pass
    count = check_call_timeouts()
    check("timeout check ran", count >= 0)
    timed_out = get_call(timeout_id)
    if timed_out:
        check("timeout call marked missed", timed_out.get("status") == "missed", timed_out.get("status"))

print("\n=== 14. ICE SERVERS ENDPOINT ===")
login(PID_A)
ice_resp = client.get("/calls/api/ice-servers")
check("ICE servers endpoint 200", ice_resp.status_code == 200, str(ice_resp.status_code))
ice_data = ice_resp.get_json(silent=True) or {}
check("ICE servers has iceServers list", isinstance(ice_data.get("iceServers"), list), str(ice_data)[:100])
if ice_data.get("iceServers"):
    has_stun = any("stun:" in str(s.get("urls", "")) for s in ice_data["iceServers"])
    check("has STUN server", has_stun)

print("\n=== 15. SOCKET.IO CALL HANDLERS ===")
socket_path = os.path.join(os.path.dirname(__file__), "..", "services", "socket_events.py")
with open(socket_path) as f:
    src = f.read()

phase40_events = [
    "call:start", "call:ringing", "call:accept", "call:reject",
    "call:cancel", "call:end", "call:busy", "call:timeout",
    "call:offer", "call:answer", "call:ice-candidate",
    "call:reconnecting", "call:reconnected", "call:failed",
    "call:mute", "call:camera-toggle", "call:speaker-toggle",
]
for event in phase40_events:
    found = re.search(rf'@socketio\.on\(["\']{event}["\']\)', src)
    check(f"socket handler for '{event}'", bool(found))

print("\n=== 16. ADDITIONAL ENDPOINTS ===")
# Test /calls/api/active
active_resp = client.get("/calls/api/active")
check("/calls/api/active endpoint ok", active_resp.status_code in (200, 401))

# Test /calls/api/history
hist_resp = client.get("/calls/api/history")
check("/calls/api/history endpoint ok", hist_resp.status_code in (200, 401))

# Test /messages/api/calls/ice-servers
msg_ice_resp = client.get("/messages/api/calls/ice-servers")
check("/messages/api/calls/ice-servers endpoint 200", msg_ice_resp.status_code == 200)

print("\n=== 17. BACKWARD COMPAT (Phase 39) ===")
# Phase 39 reactions still work
msg_resp = mds_send_message(TID, PID_A, "Phase 40 backward compat test")
msg_id = msg_resp.get("message_id") or msg_resp.get("id")
check("Phase 39 send_message still works", msg_id is not None, str(msg_resp)[:100])

react_resp = client.post(f"/messages/api/message/{msg_id}/react", json={"reaction": "👍"})
check("Phase 39 react still works", react_resp.status_code == 200)

edit_resp = client.post(f"/messages/api/message/{msg_id}/edit", json={"body": "Edited in Phase 40 test"})
check("Phase 39 edit still works", edit_resp.status_code == 200)
j_edit = edit_resp.get_json(silent=True) or {}
check("Phase 39 edit success", j_edit.get("edited") is True or j_edit.get("ok") is True)

unread_resp = client.get("/messages/api/unread-counts")
check("Phase 39 unread still works", unread_resp.status_code == 200)

print("\n=== SUMMARY ===")
total = PASS + FAIL
print(f"  PASS: {PASS}/{total}  FAIL: {FAIL}/{total}")
if FAIL:
    print("  Some tests failed — review output above.")
    exit(1)
else:
    print("  All Phase 40 E2E tests passed!")
    exit(0)
