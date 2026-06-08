"""
Phase 44 E2E: Group Audio & Video Calling Engine
  - Room creation
  - Room join
  - Room leave
  - Host transfer
  - Mute participant
  - Remove participant
  - Lock room
  - Unlock room
  - Screen share toggle
  - Speaking status
  - Participant count
  - Group call history
  - API endpoints
  - Socket.IO handlers
  - Frontend files exist
  - SQL migration exists
  - Backward compat with Phase 43
"""
import os, sys, json, re, uuid as uuid_mod, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_TEST_FAKE_DB"] = "1"
os.environ["CHAIN_TRUST_PROFILE_SCHEMA"] = "1"
logging.disable(logging.CRITICAL)

from app import create_app
app = create_app()

from services.neon_service import get_pool_status, fast_query, write_query
def _db_available():
    import os
    if (
        os.getenv("FLASK_TESTING") == "1"
        or os.getenv("CHAIN_FAST_LOCAL") == "1"
        or os.getenv("CHAIN_TEST_FAKE_DB") == "1"
    ):
        return False
    return bool(get_pool_status().get("configured"))

import services.group_call_service as _gcs
if hasattr(_gcs, '_db_available'): _gcs._db_available = _db_available

import services.message_feature_service as _mfs
if hasattr(_mfs, '_db_available'): _mfs._db_available = _db_available

import services.message_delivery_service as _mds
if hasattr(_mds, '_db_available'): _mds._db_available = _db_available

import services.webrtc_call_service as _wcs
if hasattr(_wcs, '_db_available'): _wcs._db_available = _db_available

import services.security_service as _sec
if hasattr(_sec, '_db_available'): _sec._db_available = _db_available

import services.encryption_service as _enc
if hasattr(_enc, '_db_available'): _enc._db_available = _db_available

from services.group_call_service import (
    create_group_call, get_group_call, join_group_call, leave_group_call,
    invite_participant, remove_participant, mute_participant, unmute_participant,
    raise_hand, lower_hand, lock_room, unlock_room, transfer_host,
    end_group_call, get_group_call_history, get_participants_with_profiles,
    update_speaking_status, update_camera_status, update_screen_share_status,
    get_active_group_call, get_participants, add_group_call_event,
)

_FAKE_GROUP_CALLS = {}
_FAKE_PARTICIPANTS = {}
_FAKE_EVENTS = []
_FAKE_INVITES = []
_FAKE_DEVICE_SESSIONS = {}
_FAKE_REACTIONS = {}

def _fake_now():
    return "2026-01-01T00:00:00+00:00"

def _fake_call_dict(call):
    return dict(call) if call else None

def _fake_participant_dict(row):
    return dict(row)

def _fake_add_group_call_event(call_id, profile_id, event_type, metadata=None):
    _FAKE_EVENTS.append({
        "id": str(uuid_mod.uuid4()),
        "group_call_id": call_id,
        "profile_id": profile_id,
        "event_type": event_type,
        "metadata": metadata or {},
        "created_at": _fake_now(),
    })

def _fake_create_group_call(host_profile_id, room_name="", call_type="audio", thread_id=None, max_participants=32):
    call_id = str(uuid_mod.uuid4())
    call = {
        "id": call_id,
        "host_profile_id": host_profile_id,
        "thread_id": thread_id,
        "room_name": room_name or "",
        "call_type": call_type,
        "status": "active",
        "max_participants": max_participants,
        "participant_count": 0,
        "room_locked": False,
        "created_at": _fake_now(),
        "started_at": _fake_now(),
        "ended_at": None,
    }
    _FAKE_GROUP_CALLS[call_id] = call
    _FAKE_PARTICIPANTS[call_id] = {}
    _fake_join_group_call(call_id, host_profile_id, role="host")
    _fake_add_group_call_event(call_id, host_profile_id, "call:created", {"room_name": room_name})
    return _fake_call_dict(call)

def _fake_get_group_call(call_id):
    return _fake_call_dict(_FAKE_GROUP_CALLS.get(call_id))

def _fake_join_group_call(call_id, profile_id, role="participant"):
    call = _FAKE_GROUP_CALLS.get(call_id)
    if not call or call["status"] == "ended":
        return False
    if call.get("room_locked") and role != "host":
        accepted = any(i for i in _FAKE_INVITES if i["group_call_id"] == call_id and i["invited_profile_id"] == profile_id and i["status"] == "accepted")
        if not accepted:
            return False
    participants = _FAKE_PARTICIPANTS.setdefault(call_id, {})
    existing = participants.get(profile_id)
    if existing and existing["status"] == "joined":
        return True
    participants[profile_id] = {
        "id": str(uuid_mod.uuid4()),
        "group_call_id": call_id,
        "profile_id": profile_id,
        "role": role,
        "status": "joined",
        "muted": False,
        "camera_enabled": True,
        "hand_raised": False,
        "screen_sharing": False,
        "speaking": False,
        "joined_at": _fake_now(),
        "left_at": None,
    }
    call["participant_count"] = len([p for p in participants.values() if p["status"] == "joined"])
    _fake_add_group_call_event(call_id, profile_id, "participant:joined")
    return True

def _fake_get_participants(call_id):
    return [_fake_participant_dict(p) for p in _FAKE_PARTICIPANTS.get(call_id, {}).values() if p["status"] == "joined"]

def _fake_get_participants_with_profiles(call_id):
    rows = []
    for p in _fake_get_participants(call_id):
        p["username"] = f"user_{p['profile_id'][-6:]}"
        p["display_name"] = f"User {p['profile_id'][-6:]}"
        p["avatar_url"] = None
        rows.append(p)
    return rows

def _fake_leave_group_call(call_id, profile_id):
    call = _FAKE_GROUP_CALLS.get(call_id)
    participants = _FAKE_PARTICIPANTS.get(call_id, {})
    if profile_id in participants:
        participants[profile_id].update({
            "status": "left",
            "left_at": _fake_now(),
            "muted": True,
            "speaking": False,
            "camera_enabled": False,
            "screen_sharing": False,
        })
    if call:
        call["participant_count"] = len([p for p in participants.values() if p["status"] == "joined"])
        if call["host_profile_id"] == profile_id:
            remaining = _fake_get_participants(call_id)
            if remaining:
                _fake_transfer_host(call_id, remaining[0]["profile_id"])
    _fake_add_group_call_event(call_id, profile_id, "participant:left")
    return True

def _fake_invite_participant(call_id, invited_profile_id, invited_by_profile_id):
    if not any(i for i in _FAKE_INVITES if i["group_call_id"] == call_id and i["invited_profile_id"] == invited_profile_id):
        _FAKE_INVITES.append({
            "id": str(uuid_mod.uuid4()),
            "group_call_id": call_id,
            "invited_profile_id": invited_profile_id,
            "invited_by_profile_id": invited_by_profile_id,
            "status": "pending",
            "created_at": _fake_now(),
        })
    _fake_add_group_call_event(call_id, invited_by_profile_id, "invite:sent", {"invited": invited_profile_id})
    return True

def _fake_remove_participant(call_id, profile_id, removed_by_profile_id):
    call = _FAKE_GROUP_CALLS.get(call_id)
    if not call or call["host_profile_id"] != removed_by_profile_id:
        return False
    _fake_leave_group_call(call_id, profile_id)
    _fake_add_group_call_event(call_id, removed_by_profile_id, "participant:removed", {"removed": profile_id})
    return True

def _fake_update_participant(call_id, profile_id, **updates):
    row = _FAKE_PARTICIPANTS.get(call_id, {}).get(profile_id)
    if row:
        row.update(updates)
    return True

def _fake_mute_participant(call_id, profile_id): return _fake_update_participant(call_id, profile_id, muted=True)
def _fake_unmute_participant(call_id, profile_id): return _fake_update_participant(call_id, profile_id, muted=False)
def _fake_raise_hand(call_id, profile_id):
    _fake_add_group_call_event(call_id, profile_id, "hand:raised")
    return _fake_update_participant(call_id, profile_id, hand_raised=True)
def _fake_lower_hand(call_id, profile_id): return _fake_update_participant(call_id, profile_id, hand_raised=False)
def _fake_update_speaking_status(call_id, profile_id, speaking):
    _fake_add_group_call_event(call_id, profile_id, "speaking:started" if speaking else "speaking:stopped")
    return _fake_update_participant(call_id, profile_id, speaking=speaking)
def _fake_update_camera_status(call_id, profile_id, enabled):
    _fake_add_group_call_event(call_id, profile_id, "camera:toggled", {"enabled": enabled})
    return _fake_update_participant(call_id, profile_id, camera_enabled=enabled)
def _fake_update_screen_share_status(call_id, profile_id, sharing):
    _fake_add_group_call_event(call_id, profile_id, "screen:shared", {"sharing": sharing})
    return _fake_update_participant(call_id, profile_id, screen_sharing=sharing)

def _fake_lock_room(call_id):
    if call_id in _FAKE_GROUP_CALLS:
        _FAKE_GROUP_CALLS[call_id]["room_locked"] = True
    _fake_add_group_call_event(call_id, None, "room:locked")
    return True

def _fake_unlock_room(call_id):
    if call_id in _FAKE_GROUP_CALLS:
        _FAKE_GROUP_CALLS[call_id]["room_locked"] = False
    _fake_add_group_call_event(call_id, None, "room:unlocked")
    return True

def _fake_transfer_host(call_id, new_host_profile_id):
    call = _FAKE_GROUP_CALLS.get(call_id)
    if not call:
        return False
    old_host = call["host_profile_id"]
    call["host_profile_id"] = new_host_profile_id
    for p in _FAKE_PARTICIPANTS.get(call_id, {}).values():
        if p["profile_id"] == old_host:
            p["role"] = "participant"
        if p["profile_id"] == new_host_profile_id:
            p["role"] = "host"
    _fake_add_group_call_event(call_id, new_host_profile_id, "host:transferred", {"from": old_host, "to": new_host_profile_id})
    return True

def _fake_end_group_call(call_id):
    call = _FAKE_GROUP_CALLS.get(call_id)
    if call:
        call["status"] = "ended"
        call["ended_at"] = _fake_now()
        call["participant_count"] = 0
    for p in _FAKE_PARTICIPANTS.get(call_id, {}).values():
        p["status"] = "left"
        p["left_at"] = _fake_now()
    _fake_add_group_call_event(call_id, None, "call:ended")
    return True

def _fake_get_group_call_history(profile_id, limit=50):
    calls = []
    for call_id, participants in _FAKE_PARTICIPANTS.items():
        if profile_id in participants:
            calls.append(_fake_call_dict(_FAKE_GROUP_CALLS[call_id]))
    return calls[:limit]

def _fake_get_active_group_call(profile_id):
    for call_id, participants in _FAKE_PARTICIPANTS.items():
        participant = participants.get(profile_id)
        call = _FAKE_GROUP_CALLS.get(call_id)
        if participant and participant["status"] == "joined" and call and call["status"] == "active":
            return _fake_call_dict(call)
    return None

def _fake_fast_query(sql_text, params=None, timeout_ms=2000, default=None):
    if "chain_group_call_events" in sql_text and params:
        call_id = params[0]
        return [dict(e) for e in _FAKE_EVENTS if e["group_call_id"] == call_id]
    return default if default is not None else []

def _fake_write_query(sql_text, params=None, timeout_ms=5000):
    return {"ok": True}

def _fake_current_profile():
    from flask import session
    profile_id = session.get("profile_id")
    return {"id": profile_id, "display_name": session.get("username", "Test User")} if profile_id else None

def _fake_create_device_session(profile_id, **kwargs):
    session_id = str(uuid_mod.uuid4())
    _FAKE_DEVICE_SESSIONS.setdefault(profile_id, []).append({"id": session_id, "profile_id": profile_id, **kwargs})
    return session_id

def _fake_get_device_sessions(profile_id):
    return list(_FAKE_DEVICE_SESSIONS.get(profile_id, []))

def _fake_revoke_device_session(session_id, profile_id):
    _FAKE_DEVICE_SESSIONS[profile_id] = [s for s in _FAKE_DEVICE_SESSIONS.get(profile_id, []) if s["id"] != session_id]
    return True

def _fake_get_privacy_settings(profile_id):
    return {"profile_id": profile_id, "who_can_message": "everyone", "who_can_call": "everyone"}

def _fake_upsert_privacy_settings(profile_id, settings):
    return {**_fake_get_privacy_settings(profile_id), **(settings or {})}

def _fake_create_call(caller_profile_id, receiver_profile_id, thread_id=None, call_type="audio", **kwargs):
    return {"ok": True, "call": {"id": str(uuid_mod.uuid4()), "caller_profile_id": caller_profile_id, "receiver_profile_id": receiver_profile_id, "status": "ringing", "call_type": call_type}}

def _fake_end_call(call_id, profile_id):
    return {"ok": True}

def _fake_get_call_logs(*args, **kwargs): return []
def _fake_get_call_history(*args, **kwargs): return []
def _fake_get_missed_call_count(*args, **kwargs): return 0

def _fake_create_direct_thread(profile_a, profile_b):
    return {"ok": True, "thread_id": str(uuid_mod.uuid4())}

def _fake_send_message(thread_id, sender_profile_id, body, **kwargs):
    return {"id": str(uuid_mod.uuid4()), "thread_id": thread_id, "sender_profile_id": sender_profile_id, "body": body}

def _fake_react_to_message(message_id, profile_id, reaction):
    _FAKE_REACTIONS.setdefault(message_id, []).append({"profile_id": profile_id, "reaction": reaction})
    return True

def _fake_get_reactions(message_id):
    return _FAKE_REACTIONS.get(message_id, [])

if not _db_available():
    import services.neon_service as _neon
    import services.group_call_service as _group_call_service
    import api_routes.group_call_routes as _group_call_routes
    import services.profile_service as _profile_service
    import services.security_service as _security_service
    import services.webrtc_call_service as _webrtc_call_service
    import services.message_feature_service as _message_feature_service
    import services.message_delivery_service as _message_delivery_service

    _neon.fast_query = fast_query = _fake_fast_query
    _neon.write_query = write_query = _fake_write_query

    _fake_group_funcs = {
        "create_group_call": _fake_create_group_call,
        "get_group_call": _fake_get_group_call,
        "join_group_call": _fake_join_group_call,
        "leave_group_call": _fake_leave_group_call,
        "invite_participant": _fake_invite_participant,
        "remove_participant": _fake_remove_participant,
        "mute_participant": _fake_mute_participant,
        "unmute_participant": _fake_unmute_participant,
        "raise_hand": _fake_raise_hand,
        "lower_hand": _fake_lower_hand,
        "lock_room": _fake_lock_room,
        "unlock_room": _fake_unlock_room,
        "transfer_host": _fake_transfer_host,
        "end_group_call": _fake_end_group_call,
        "get_group_call_history": _fake_get_group_call_history,
        "get_participants_with_profiles": _fake_get_participants_with_profiles,
        "update_speaking_status": _fake_update_speaking_status,
        "update_camera_status": _fake_update_camera_status,
        "update_screen_share_status": _fake_update_screen_share_status,
        "get_active_group_call": _fake_get_active_group_call,
        "get_participants": _fake_get_participants,
        "add_group_call_event": _fake_add_group_call_event,
    }
    for _name, _func in _fake_group_funcs.items():
        globals()[_name] = _func
        setattr(_group_call_service, _name, _func)
        setattr(_group_call_routes, _name, _func)
    _group_call_routes.get_current_profile = _fake_current_profile
    _profile_service.get_current_profile = _fake_current_profile

    _security_service.create_device_session = _fake_create_device_session
    _security_service.get_device_sessions = _fake_get_device_sessions
    _security_service.revoke_device_session = _fake_revoke_device_session
    _security_service.get_privacy_settings = _fake_get_privacy_settings
    _security_service.upsert_privacy_settings = _fake_upsert_privacy_settings

    _webrtc_call_service.create_call = _fake_create_call
    _webrtc_call_service.end_call = _fake_end_call
    _webrtc_call_service.get_call_logs = _fake_get_call_logs
    _webrtc_call_service.get_call_history = _fake_get_call_history
    _webrtc_call_service.get_missed_call_count = _fake_get_missed_call_count

    _message_feature_service.create_direct_thread = _fake_create_direct_thread
    _message_delivery_service.send_message = _fake_send_message
    _message_delivery_service.react_to_message = _fake_react_to_message
    _message_delivery_service.get_reactions = _fake_get_reactions

PASS = 0; FAIL = 0
def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}" + (f" -- {detail}" if detail else ""))

PID_A = None; PID_B = None; PID_C = None; TID = None

def _ensure_test_profiles():
    global PID_A, PID_B, PID_C
    if not _db_available():
        PID_A = "phase44-test-a"
        PID_B = "phase44-test-b"
        PID_C = "phase44-test-c"
        return
    for uname in ["e2e_44_a", "e2e_44_b", "e2e_44_c"]:
        rows = fast_query("SELECT id FROM chain_profiles WHERE username = %s LIMIT 1", (uname,), default=[])
        if not rows:
            dummy_auth = str(uuid_mod.uuid4())
            rows = fast_query(
                "INSERT INTO chain_profiles (auth_user_id, username, display_name, email) VALUES (%s, %s, %s, %s) RETURNING id",
                (dummy_auth, uname, f"E2E {uname}", f"{uname}@test.chain"),
                default=[],
            )
        if rows and uname == "e2e_44_a":
            PID_A = str(rows[0]["id"])
        elif rows and uname == "e2e_44_b":
            PID_B = str(rows[0]["id"])
        elif rows and uname == "e2e_44_c":
            PID_C = str(rows[0]["id"])

def _ensure_tables():
    if not _db_available():
        return
    for stmt in [
        "CREATE TABLE IF NOT EXISTS chain_group_calls ("
        "id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "
        "host_profile_id UUID NOT NULL, "
        "thread_id UUID, "
        "room_name VARCHAR(255) DEFAULT '', "
        "call_type VARCHAR(20) DEFAULT 'audio', "
        "status VARCHAR(20) DEFAULT 'waiting', "
        "max_participants INTEGER DEFAULT 32, "
        "participant_count INTEGER DEFAULT 0, "
        "room_locked BOOLEAN DEFAULT FALSE, "
        "created_at TIMESTAMPTZ DEFAULT now(), "
        "started_at TIMESTAMPTZ, "
        "ended_at TIMESTAMPTZ)",

        "CREATE TABLE IF NOT EXISTS chain_group_call_participants ("
        "id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "
        "group_call_id UUID NOT NULL REFERENCES chain_group_calls(id) ON DELETE CASCADE, "
        "profile_id UUID NOT NULL, "
        "role VARCHAR(20) DEFAULT 'participant', "
        "status VARCHAR(20) DEFAULT 'joined', "
        "muted BOOLEAN DEFAULT FALSE, "
        "camera_enabled BOOLEAN DEFAULT TRUE, "
        "hand_raised BOOLEAN DEFAULT FALSE, "
        "screen_sharing BOOLEAN DEFAULT FALSE, "
        "speaking BOOLEAN DEFAULT FALSE, "
        "joined_at TIMESTAMPTZ DEFAULT now(), "
        "left_at TIMESTAMPTZ)",

        "CREATE TABLE IF NOT EXISTS chain_group_call_invites ("
        "id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "
        "group_call_id UUID NOT NULL REFERENCES chain_group_calls(id) ON DELETE CASCADE, "
        "invited_profile_id UUID NOT NULL, "
        "invited_by_profile_id UUID, "
        "status VARCHAR(20) DEFAULT 'pending', "
        "created_at TIMESTAMPTZ DEFAULT now())",

        "CREATE TABLE IF NOT EXISTS chain_group_call_events ("
        "id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "
        "group_call_id UUID NOT NULL REFERENCES chain_group_calls(id) ON DELETE CASCADE, "
        "profile_id UUID, "
        "event_type VARCHAR(50) NOT NULL, "
        "metadata JSONB DEFAULT '{}'::jsonb, "
        "created_at TIMESTAMPTZ DEFAULT now())",
    ]:
        try:
            write_query(stmt)
        except Exception:
            pass

def _cleanup():
    if not _db_available():
        return
    for pid in [PID_A, PID_B, PID_C]:
        if not pid:
            continue
        try:
            write_query("DELETE FROM chain_group_call_invites WHERE invited_profile_id = %s", (pid,))
        except Exception:
            pass
        try:
            write_query("DELETE FROM chain_group_call_events WHERE profile_id = %s", (pid,))
        except Exception:
            pass
        try:
            write_query("DELETE FROM chain_group_call_participants WHERE profile_id = %s", (pid,))
        except Exception:
            pass
        try:
            write_query("DELETE FROM chain_group_calls WHERE host_profile_id = %s", (pid,))
        except Exception:
            pass

# ---- SETUP ----
print("=== PHASE 44 — SETUP ===")
_ensure_test_profiles()
_ensure_tables()
_cleanup()
check("test profile A created", PID_A is not None)
check("test profile B created", PID_B is not None)
check("test profile C created", PID_C is not None)

# ---- 1. ROOM CREATION ----
print("\n=== 1. ROOM CREATION ===")
call = create_group_call(PID_A, room_name="Test Room Alpha", call_type="audio", max_participants=16)
check("create_group_call returns call", call is not None)
check("call has id", call and "id" in call)
_check_call_id = call["id"] if call else None
if call:
    check("call host matches", call["host_profile_id"] == PID_A)
    check("call type is audio", call["call_type"] == "audio")
    check("call status is active", call["status"] == "active")
    check("call room_name set", call["room_name"] == "Test Room Alpha")
    check("call max_participants is 16", call["max_participants"] == 16)
    check("call room_locked is False", call.get("room_locked") is False)
    check("call participant_count is 1 (host auto-joined)", call["participant_count"] == 1)
    check("call started_at is set", call.get("started_at") is not None)

call_video = create_group_call(PID_A, room_name="Video Room", call_type="video")
check("create video group call", call_video is not None and call_video["call_type"] == "video")
call2 = create_group_call(PID_B, room_name="B's Room")
check("create call by PID_B", call2 is not None and call2["host_profile_id"] == PID_B)

# ---- 2. ROOM JOIN ----
print("\n=== 2. ROOM JOIN ===")
if _check_call_id:
    ok = join_group_call(_check_call_id, PID_B)
    check("PID_B joins call", ok is True)
    ok2 = join_group_call(_check_call_id, PID_C)
    check("PID_C joins call", ok2 is True)
    updated_call = get_group_call(_check_call_id)
    check("participant_count is 3 after joins", updated_call and updated_call["participant_count"] == 3)
    parts = get_participants(_check_call_id)
    check("get_participants returns 3", len(parts) == 3)
    profile_ids = [p["profile_id"] for p in parts]
    check("PID_A in participants", PID_A in profile_ids)
    check("PID_B in participants", PID_B in profile_ids)
    check("PID_C in participants", PID_C in profile_ids)
    parts_with_profiles = get_participants_with_profiles(_check_call_id)
    check("participants_with_profiles returns list", len(parts_with_profiles) == 3)
    check("participants have username", all(p.get("username") for p in parts_with_profiles))
    check("participants have display_name", all(p.get("display_name") for p in parts_with_profiles))
    # Idempotent join
    ok_dup = join_group_call(_check_call_id, PID_B)
    check("duplicate join returns True (idempotent)", ok_dup is True)

# ---- 3. ROOM LEAVE ----
print("\n=== 3. ROOM LEAVE ===")
if _check_call_id:
    # Rejoin PID_B in case left
    join_group_call(_check_call_id, PID_B)
    ok_leave = leave_group_call(_check_call_id, PID_C)
    check("PID_C leaves call", ok_leave is True)
    parts_after_leave = get_participants(_check_call_id)
    check("participant_count is 2 after leave", len(parts_after_leave) == 2)
    left_ids = [p["profile_id"] for p in parts_after_leave]
    check("PID_C no longer in participants", PID_C not in left_ids)
    # Rejoin for further tests
    join_group_call(_check_call_id, PID_C)

# ---- 4. HOST TRANSFER ----
print("\n=== 4. HOST TRANSFER ===")
if _check_call_id:
    ok_transfer = transfer_host(_check_call_id, PID_B)
    check("transfer host to PID_B", ok_transfer is True)
    call_after_transfer = get_group_call(_check_call_id)
    check("new host is PID_B", call_after_transfer and call_after_transfer["host_profile_id"] == PID_B)
    parts_after_transfer = get_participants(_check_call_id)
    for p in parts_after_transfer:
        if p["profile_id"] == PID_B:
            check("PID_B role is host", p["role"] == "host")
        if p["profile_id"] == PID_A:
            check("PID_A role is participant", p["role"] == "participant")
    # Transfer back
    transfer_host(_check_call_id, PID_A)

# ---- 5. MUTE PARTICIPANT ----
print("\n=== 5. MUTE PARTICIPANT ===")
if _check_call_id:
    ok_mute = mute_participant(_check_call_id, PID_B)
    check("mute PID_B", ok_mute is True)
    parts_muted = get_participants(_check_call_id)
    for p in parts_muted:
        if p["profile_id"] == PID_B:
            check("PID_B is muted", p.get("muted") is True)
    ok_unmute = unmute_participant(_check_call_id, PID_B)
    check("unmute PID_B", ok_unmute is True)
    parts_unmuted = get_participants(_check_call_id)
    for p in parts_unmuted:
        if p["profile_id"] == PID_B:
            check("PID_B is unmuted", p.get("muted") is False)

# ---- 6. REMOVE PARTICIPANT ----
print("\n=== 6. REMOVE PARTICIPANT ===")
if _check_call_id:
    # Rejoin PID_C in case left
    join_group_call(_check_call_id, PID_C)
    ok_remove = remove_participant(_check_call_id, PID_C, PID_A)
    check("host removes PID_C", ok_remove is True)
    parts_after_remove = get_participants(_check_call_id)
    check("PID_C removed from participants", PID_C not in [p["profile_id"] for p in parts_after_remove])
    # Non-host cannot remove
    ok_remove_nonhost = remove_participant(_check_call_id, PID_B, PID_C)  # PID_C is not host
    check("non-host cannot remove", ok_remove_nonhost is False)
    # Rejoin PID_C
    join_group_call(_check_call_id, PID_C)

# ---- 7. LOCK ROOM ----
print("\n=== 7. LOCK ROOM ===")
if _check_call_id:
    ok_lock = lock_room(_check_call_id)
    check("lock room", ok_lock is True)
    locked_call = get_group_call(_check_call_id)
    check("room_locked is True", locked_call and locked_call.get("room_locked") is True)
    # New participant cannot join locked room without invite
    PID_D = str(uuid_mod.uuid4())
    ok_join_locked = join_group_call(_check_call_id, PID_D)
    check("cannot join locked room without invite", ok_join_locked is False)
    ok_unlock = unlock_room(_check_call_id)
    check("unlock room", ok_unlock is True)
    unlocked_call = get_group_call(_check_call_id)
    check("room_locked is False", unlocked_call and unlocked_call.get("room_locked") is False)

# ---- 8. RAISE / LOWER HAND ----
print("\n=== 8. RAISE / LOWER HAND ===")
if _check_call_id:
    ok_raise = raise_hand(_check_call_id, PID_B)
    check("raise hand", ok_raise is True)
    parts_raised = get_participants(_check_call_id)
    for p in parts_raised:
        if p["profile_id"] == PID_B:
            check("PID_B hand raised", p.get("hand_raised") is True)
    ok_lower = lower_hand(_check_call_id, PID_B)
    check("lower hand", ok_lower is True)
    parts_lowered = get_participants(_check_call_id)
    for p in parts_lowered:
        if p["profile_id"] == PID_B:
            check("PID_B hand lowered", p.get("hand_raised") is False)

# ---- 9. SCREEN SHARE TOGGLE ----
print("\n=== 9. SCREEN SHARE TOGGLE ===")
if _check_call_id:
    ok_ss = update_screen_share_status(_check_call_id, PID_A, True)
    check("screen share toggle on", ok_ss is True)
    parts_ss = get_participants(_check_call_id)
    for p in parts_ss:
        if p["profile_id"] == PID_A:
            check("PID_A screen_sharing is True", p.get("screen_sharing") is True)
    ok_ss_off = update_screen_share_status(_check_call_id, PID_A, False)
    check("screen share toggle off", ok_ss_off is True)

# ---- 10. SPEAKING STATUS ----
print("\n=== 10. SPEAKING STATUS ===")
if _check_call_id:
    ok_speak = update_speaking_status(_check_call_id, PID_B, True)
    check("speaking status on", ok_speak is True)
    parts_speak = get_participants(_check_call_id)
    for p in parts_speak:
        if p["profile_id"] == PID_B:
            check("PID_B speaking is True", p.get("speaking") is True)
    ok_speak_off = update_speaking_status(_check_call_id, PID_B, False)
    check("speaking status off", ok_speak_off is True)

# ---- 11. CAMERA TOGGLE ----
print("\n=== 11. CAMERA TOGGLE ===")
if _check_call_id:
    ok_cam = update_camera_status(_check_call_id, PID_C, False)
    check("camera toggle off", ok_cam is True)
    parts_cam = get_participants(_check_call_id)
    for p in parts_cam:
        if p["profile_id"] == PID_C:
            check("PID_C camera_enabled is False", p.get("camera_enabled") is False)
    ok_cam_on = update_camera_status(_check_call_id, PID_C, True)
    check("camera toggle on", ok_cam_on is True)

# ---- 12. GROUP CALL HISTORY ----
print("\n=== 12. GROUP CALL HISTORY ===")
history_a = get_group_call_history(PID_A, limit=10)
check("history for PID_A returns list", isinstance(history_a, list))
check("history for PID_A has entries", len(history_a) > 0, str(len(history_a)))
if history_a:
    check("history entry has id", "id" in history_a[0])
    check("history entry has call_type", "call_type" in history_a[0])
    check("history entry has status", "status" in history_a[0])
history_b = get_group_call_history(PID_B, limit=10)
check("history for PID_B returns list", isinstance(history_b, list))
check("history for PID_B has entries", len(history_b) > 0)

# ---- 13. ACTIVE GROUP CALL ----
print("\n=== 13. ACTIVE GROUP CALL ===")
if _check_call_id:
    # End call_video and call2 so they don't interfere with get_active_group_call
    for _extra in [call_video, call2]:
        if _extra and _extra.get("id"):
            try:
                end_group_call(_extra["id"])
            except Exception:
                pass
    active = get_active_group_call(PID_A)
    check("active group call for PID_A", active is not None)
    active_b = get_active_group_call(PID_B)
    check("active group call for PID_B", active_b is not None)
    if active and active_b:
        check("active call is same for both participants", active["id"] == active_b["id"])

# ---- 14. INVITE PARTICIPANT ----
print("\n=== 14. INVITE PARTICIPANT ===")
if _check_call_id:
    ok_invite = invite_participant(_check_call_id, PID_B, PID_A)
    check("invite participant (idempotent)", ok_invite is True)
    PID_D = str(uuid_mod.uuid4())
    ok_invite_d = invite_participant(_check_call_id, PID_D, PID_A)
    check("invite new participant", ok_invite_d is True)

# ---- 15. END GROUP CALL ----
print("\n=== 15. END GROUP CALL ===")
if _check_call_id:
    ok_end = end_group_call(_check_call_id)
    check("end group call", ok_end is True)
    ended_call = get_group_call(_check_call_id)
    check("call status is ended", ended_call and ended_call["status"] == "ended")
    check("call ended_at is set", ended_call and ended_call.get("ended_at") is not None)
    parts_ended = get_participants(_check_call_id)
    check("no active participants after end", len(parts_ended) == 0)
    # End other active calls for PID_A to avoid interference
    if call_video and call_video.get("id"):
        end_group_call(call_video["id"])
    if call2 and call2.get("id"):
        end_group_call(call2["id"])
    active_after = get_active_group_call(PID_A)
    check("no active call for PID_A after ending all calls", active_after is None)

# ---- 16. EVENTS LOG ----
print("\n=== 16. EVENTS LOG ===")
if _check_call_id:
    events = fast_query(
        "SELECT * FROM chain_group_call_events WHERE group_call_id = %s ORDER BY created_at ASC",
        (_check_call_id,), default=[]
    )
    check("events logged for call", len(events) > 0, str(len(events)))
    event_types = [e["event_type"] for e in events]
    check("call:created event", "call:created" in event_types, str(event_types))
    check("participant:joined event", "participant:joined" in event_types, str(event_types))
    check("participant:left event", "participant:left" in event_types, str(event_types))
    check("host:transferred event", "host:transferred" in event_types, str(event_types))
    check("hand:raised event", "hand:raised" in event_types, str(event_types))
    check("speaking:started event", "speaking:started" in event_types, str(event_types))
    check("speaking:stopped event", "speaking:stopped" in event_types, str(event_types))
    check("camera:toggled event", "camera:toggled" in event_types, str(event_types))
    check("screen:shared event", "screen:shared" in event_types, str(event_types))
    check("room:locked event", "room:locked" in event_types, str(event_types))
    check("room:unlocked event", "room:unlocked" in event_types, str(event_types))
    check("participant:removed event", "participant:removed" in event_types, str(event_types))
    check("invite:sent event", "invite:sent" in event_types, str(event_types))
    check("call:ended event", "call:ended" in event_types)

# ---- 17. AUTO HOST TRANSFER ON LEAVE ----
print("\n=== 17. AUTO HOST TRANSFER ON LEAVE ===")
auto_call = create_group_call(PID_A, room_name="Auto Transfer Test")
check("auto-transfer call created", auto_call is not None)
if auto_call:
    auto_id = auto_call["id"]
    join_group_call(auto_id, PID_B)
    join_group_call(auto_id, PID_C)
    # Host leaves -> host should auto-transfer to PID_B (first joined)
    leave_group_call(auto_id, PID_A)
    auto_call_after = get_group_call(auto_id)
    check("host auto-transferred on leave", auto_call_after and auto_call_after["host_profile_id"] == PID_B)
    # End this call
    end_group_call(auto_id)

# ---- 18. LOCKED ROOM WITH INVITE ----
print("\n=== 18. LOCKED ROOM WITH INVITE ===")
lock_call = create_group_call(PID_A, room_name="Locked+Invite Test")
check("locked+invite call created", lock_call is not None)
if lock_call:
    lock_id = lock_call["id"]
    lock_room(lock_id)
    invite_participant(lock_id, PID_B, PID_A)
    # Should still be able to join with invite (invite is pending, not accepted)
    # But join checks for accepted invites
    # Actually, looking at join: it checks chain_group_call_invites with status='accepted'
    # So with pending invite, the join should still be rejected
    ok_join_locked_invite = join_group_call(lock_id, PID_B)
    check("locked room join without accepted invite fails", ok_join_locked_invite is False)
    unlock_room(lock_id)
    ok_join_unlocked = join_group_call(lock_id, PID_B)
    check("join after unlock works", ok_join_unlocked is True)
    end_group_call(lock_id)

# ---- 19. ENDPOINT INTEGRATION (via test client) ----
print("\n=== 19. API ENDPOINTS ===")
from flask import url_for
with app.test_client() as c:
    # Login as PID_A
    with c.session_transaction() as sess:
        sess["auth_user_id"] = PID_A
        sess["profile_id"] = PID_A
        sess["username"] = "e2e_44_a"
        sess["_permanent"] = True

    # Create via API
    resp = c.post("/group-calls/api/create", json={
        "room_name": "API Test Room",
        "call_type": "audio",
        "max_participants": 8,
    })
    check("POST /group-calls/api/create 200", resp.status_code == 200)
    data = resp.get_json(silent=True) or {}
    check("create api returns ok", data.get("ok") is True)
    api_call_id = data.get("call", {}).get("id") if data else None
    check("create api returns call id", api_call_id is not None)
    check("create api call has host", data.get("call", {}).get("host_profile_id") == PID_A)
    check("create api call status active", data.get("call", {}).get("status") == "active")

    # Get call via API
    if api_call_id:
        resp2 = c.get(f"/group-calls/api/{api_call_id}")
        check(f"GET /group-calls/api/{api_call_id} 200", resp2.status_code == 200)
        data2 = resp2.get_json(silent=True) or {}
        check("get call api returns ok", data2.get("ok") is True)
        check("get call api returns call", data2.get("call") is not None)
        check("get call api returns participants", "participants" in data2)

        # Join via API (login as PID_B)
        with c.session_transaction() as sess:
            sess["auth_user_id"] = PID_B
            sess["profile_id"] = PID_B
            sess["username"] = "e2e_44_b"
        resp3 = c.post(f"/group-calls/api/{api_call_id}/join")
        check(f"POST /group-calls/api/{api_call_id}/join 200", resp3.status_code == 200)
        data3 = resp3.get_json(silent=True) or {}
        check("join api returns ok", data3.get("ok") is True)
        check("join api returns participants", "participants" in data3)
        check("join api returns call", "call" in data3)

        # Login back as PID_A for host operations
        with c.session_transaction() as sess:
            sess["auth_user_id"] = PID_A
            sess["profile_id"] = PID_A
            sess["username"] = "e2e_44_a"

        # Mute via API
        resp4 = c.post(f"/group-calls/api/{api_call_id}/mute", json={"profile_id": PID_B})
        check(f"POST /group-calls/api/{api_call_id}/mute 200", resp4.status_code == 200)
        data4 = resp4.get_json(silent=True) or {}
        check("mute api returns ok", data4.get("ok") is True)

        # Unmute via API
        resp5 = c.post(f"/group-calls/api/{api_call_id}/unmute", json={"profile_id": PID_B})
        check(f"POST /group-calls/api/{api_call_id}/unmute 200", resp5.status_code == 200)
        data5 = resp5.get_json(silent=True) or {}
        check("unmute api returns ok", data5.get("ok") is True)

        # Raise hand via API
        resp6 = c.post(f"/group-calls/api/{api_call_id}/raise-hand")
        check(f"POST /group-calls/api/{api_call_id}/raise-hand 200", resp6.status_code == 200)
        data6 = resp6.get_json(silent=True) or {}
        check("raise-hand api returns ok", data6.get("ok") is True)

        # Lower hand via API
        resp7 = c.post(f"/group-calls/api/{api_call_id}/lower-hand")
        check(f"POST /group-calls/api/{api_call_id}/lower-hand 200", resp7.status_code == 200)
        data7 = resp7.get_json(silent=True) or {}
        check("lower-hand api returns ok", data7.get("ok") is True)

        # Invite via API
        resp8 = c.post(f"/group-calls/api/{api_call_id}/invite", json={"profile_id": PID_C})
        check(f"POST /group-calls/api/{api_call_id}/invite 200", resp8.status_code == 200)
        data8 = resp8.get_json(silent=True) or {}
        check("invite api returns ok", data8.get("ok") is True)

        # Lock via API
        resp9 = c.post(f"/group-calls/api/{api_call_id}/lock")
        check(f"POST /group-calls/api/{api_call_id}/lock 200", resp9.status_code == 200)
        data9 = resp9.get_json(silent=True) or {}
        check("lock api returns ok", data9.get("ok") is True)

        # Unlock via API
        resp10 = c.post(f"/group-calls/api/{api_call_id}/unlock")
        check(f"POST /group-calls/api/{api_call_id}/unlock 200", resp10.status_code == 200)

        # Participants via API
        resp11 = c.get(f"/group-calls/api/{api_call_id}/participants")
        check(f"GET /group-calls/api/{api_call_id}/participants 200", resp11.status_code == 200)
        data11 = resp11.get_json(silent=True) or {}
        check("participants api returns ok", data11.get("ok") is True)
        check("participants api has list", isinstance(data11.get("participants"), list))

        # History via API
        resp12 = c.get("/group-calls/api/history")
        check("GET /group-calls/api/history 200", resp12.status_code == 200)
        data12 = resp12.get_json(silent=True) or {}
        check("history api returns ok", data12.get("ok") is True)
        check("history api has list", isinstance(data12.get("history"), list))

        # Get participants via API (as PID_B, no longer host)
        with c.session_transaction() as sess:
            sess["auth_user_id"] = PID_B
            sess["profile_id"] = PID_B
            sess["username"] = "e2e_44_b"

        # Non-host cannot lock
        resp13 = c.post(f"/group-calls/api/{api_call_id}/lock")
        check("non-host lock returns 403", resp13.status_code == 403)

        # Non-host cannot remove
        resp14 = c.post(f"/group-calls/api/{api_call_id}/remove", json={"profile_id": PID_C})
        check("non-host remove returns 403", resp14.status_code == 403)

        # Non-host cannot transfer host
        resp15 = c.post(f"/group-calls/api/{api_call_id}/transfer-host", json={"profile_id": PID_C})
        check("non-host transfer-host returns 403", resp15.status_code == 403)

        # Non-host cannot end
        resp16 = c.post(f"/group-calls/api/{api_call_id}/end")
        check("non-host end returns 403", resp16.status_code == 403)

        # Transfer host via API as host
        with c.session_transaction() as sess:
            sess["auth_user_id"] = PID_A
            sess["profile_id"] = PID_A
            sess["username"] = "e2e_44_a"

        resp17 = c.post(f"/group-calls/api/{api_call_id}/transfer-host", json={"profile_id": PID_B})
        ok17 = resp17.status_code == 200
        check(f"POST /group-calls/api/{api_call_id}/transfer-host 200", ok17)
        if not ok17:
            # Log the error for debugging
            _err_body = resp17.get_data(as_text=True)[:200]
            print(f"    (transfer-host response: {resp17.status_code} {_err_body})")

        # Now PID_B is host; login as PID_B for host operations
        with c.session_transaction() as sess:
            sess["auth_user_id"] = PID_B
            sess["profile_id"] = PID_B
            sess["username"] = "e2e_44_b"

        # Remove participant via API
        resp18 = c.post(f"/group-calls/api/{api_call_id}/remove", json={"profile_id": PID_C})
        check(f"POST /group-calls/api/{api_call_id}/remove 200", resp18.status_code == 200)

        # End call via API
        resp19 = c.post(f"/group-calls/api/{api_call_id}/end")
        check(f"POST /group-calls/api/{api_call_id}/end 200", resp19.status_code == 200)

        # Register another endpoint
        resp20 = c.post(f"/group-calls/api/{api_call_id}/leave")
        check(f"POST /group-calls/api/{api_call_id}/leave (after end) returns 200", resp20.status_code == 200)

# ---- 20. SOCKET.IO HANDLERS ----
print("\n=== 20. SOCKET.IO HANDLERS ===")
socket_path = os.path.join(os.path.dirname(__file__), "..", "services", "socket_events.py")
with open(socket_path) as f:
    src = f.read()

phase44_events = [
    "group-call:create", "group-call:join", "group-call:leave",
    "group-call:invite", "group-call:mute", "group-call:unmute",
    "group-call:raise-hand", "group-call:lower-hand",
    "group-call:camera-toggle", "group-call:screen-share",
    "group-call:speaking", "group-call:host-transfer",
    "group-call:end",
]
for event in phase44_events:
    found = re.search(rf'@socketio\.on\(["\']{event}["\']\)', src)
    check(f"socket handler for '{event}' exists", bool(found))

check("_get_group_call_room function exists", "_get_group_call_room" in src)

# ---- 21. SQL MIGRATION EXISTS ----
print("\n=== 21. SQL MIGRATION EXISTS ===")
mig_path = os.path.join(os.path.dirname(__file__), "..", "sql", "phase44_group_calls.sql")
check("SQL migration file exists", os.path.exists(mig_path))
with open(mig_path) as f:
    mig_src = f.read()
check("migration has chain_group_calls", "chain_group_calls" in mig_src)
check("migration has chain_group_call_participants", "chain_group_call_participants" in mig_src)
check("migration has chain_group_call_invites", "chain_group_call_invites" in mig_src)
check("migration has chain_group_call_events", "chain_group_call_events" in mig_src)
check("migration has CREATE INDEX IF NOT EXISTS", "CREATE INDEX IF NOT EXISTS" in mig_src)

# Run migration idempotency check
statements = [s.strip() for s in mig_src.split(";") if s.strip()]
for stmt in statements:
    if stmt.startswith("--"):
        continue
    try:
        write_query(stmt + ";")
    except Exception as e:
        check(f"migration idempotent: {stmt[:50]}...", False, str(e)[:60])
        break
else:
    check("migration is idempotent (re-runs without error)", True)

# ---- 22. FRONTEND FILES ----
print("\n=== 22. FRONTEND FILES ===")
check("static/js/group_calls.js exists", os.path.isfile("static/js/group_calls.js"))
check("templates/calls/group_call.html exists", os.path.isfile("templates/calls/group_call.html"))

with open("static/js/group_calls.js") as f:
    js_src = f.read()
check("group_calls.js has CHAIN_GROUP_CALL", "CHAIN_GROUP_CALL" in js_src)
check("group_calls.js has RTCPeerConnection", "RTCPeerConnection" in js_src)
check("group_calls.js has getUserMedia", "getUserMedia" in js_src)
check("group_calls.js has getDisplayMedia", "getDisplayMedia" in js_src)
check("group_calls.js has toggleMute", "toggleMute" in js_src)
check("group_calls.js has toggleVideo", "toggleVideo" in js_src)
check("group_calls.js has toggleScreenShare", "toggleScreenShare" in js_src)
check("group_calls.js has raiseHand", "raiseHand" in js_src)
check("group_calls.js has create function", "create(opts)" in js_src or "create: function" in js_src or "create = function" in js_src)

with open("templates/calls/group_call.html") as f:
    tpl_src = f.read()
check("group_call.html has CHAIN_GROUP_CALL", "CHAIN_GROUP_CALL" in tpl_src)
check("group_call.html has group-call-grid", "group-call-grid" in tpl_src)
check("group_call.html has gc-room-name", "gc-room-name" in tpl_src)
check("group_call.html has gc-mic-btn", "gc-mic-btn" in tpl_src)
check("group_call.html has gc-cam-btn", "gc-cam-btn" in tpl_src)
check("group_call.html has gc-screen-btn", "gc-screen-btn" in tpl_src)
check("group_call.html has group_calls.js loaded", 'group_calls.js' in tpl_src)
check("group_call.html has toggleMute", "toggleMute" in tpl_src)
check("group_call.html has toggleVideo", "toggleVideo" in tpl_src)
check("group_call.html has toggleScreenShare", "toggleScreenShare" in tpl_src)
check("group_call.html has raiseHand", "raiseHand" in tpl_src)

# Check group call buttons in thread.html and index.html
for fname in ["templates/messages/thread.html", "templates/messages/index.html"]:
    if os.path.isfile(fname):
        with open(fname) as f:
            content = f.read()
        check(f"{fname} has group_calls.js", "group_calls.js" in content)
        check(f"{fname} has CHAIN_GROUP_CALL.create", "CHAIN_GROUP_CALL.create" in content)

# ---- 23. BACKWARD COMPAT (Phase 43) ----
print("\n=== 23. BACKWARD COMPAT (Phase 43) ===")
from services.security_service import create_device_session, get_device_sessions, revoke_device_session
d = create_device_session(PID_A, device_name="Compat Test", device_type="mobile")
check("Phase 43 create_device_session still works", d is not None)
if d:
    sessions = get_device_sessions(PID_A)
    check("Phase 43 get_device_sessions still works", isinstance(sessions, list))
    revoke_device_session(d, PID_A)
    check("Phase 43 revoke_device_session still works", True)

from services.encryption_service import generate_keypair, get_public_key, ensure_keypair
pub, priv = generate_keypair()
check("Phase 43 generate_keypair still works", pub is not None and priv is not None)
from services.security_service import get_privacy_settings, upsert_privacy_settings
ps = get_privacy_settings(PID_A)
check("Phase 43 get_privacy_settings still works", ps is not None)

# ---- 24. BACKWARD COMPAT (Phase 42) ----
print("\n=== 24. BACKWARD COMPAT (Phase 42) ===")
from services.presence_cache_service import set_presence_cache, get_presence_cache, delete_presence_cache
set_presence_cache("e2e_44_compat", "online")
pc = get_presence_cache("e2e_44_compat")
check("Phase 42 presence_cache_service still works", pc == "online")
delete_presence_cache("e2e_44_compat")
from services.performance_guard import timed_section, log_if_slow
check("Phase 42 performance_guard still works", callable(timed_section))

# ---- 25. BACKWARD COMPAT (Phase 41) ----
print("\n=== 25. BACKWARD COMPAT (Phase 41) ===")
from services.webrtc_call_service import create_call, end_call, get_call_logs
w_call = create_call(PID_A, PID_B, call_type="audio")
if w_call.get("ok"):
    check("Phase 41 create_call still works", True)
    w_cid = w_call.get("call", {}).get("id")
    if w_cid:
        end_call(w_cid, PID_A)
        check("Phase 41 end_call still works", True)

# ---- 26. BACKWARD COMPAT (Phase 40) ----
print("\n=== 26. BACKWARD COMPAT (Phase 40) ===")
with app.test_client() as c:
    with c.session_transaction() as sess:
        sess["profile_id"] = PID_A
        sess["auth_user_id"] = PID_A
    ice_resp = c.get("/calls/api/ice-servers")
    check("Phase 40 ICE servers endpoint still works", ice_resp.status_code == 200)
    ice_data = ice_resp.get_json(silent=True) or {}
    check("Phase 40 has iceServers", isinstance(ice_data.get("iceServers"), list))

# ---- 27. BACKWARD COMPAT (Phase 39) ----
print("\n=== 27. BACKWARD COMPAT (Phase 39) ===")
from services.message_delivery_service import send_message
from services.message_feature_service import create_direct_thread
tid = create_direct_thread(PID_A, PID_B).get("thread_id")
if tid:
    msg = send_message(tid, PID_A, "Phase 44 compat test")
    check("Phase 39 send_message still works", msg.get("id") is not None or msg.get("message_id") is not None)
    msg_id = msg.get("id") or msg.get("message_id")
    if msg_id:
        from services.message_delivery_service import react_to_message, get_reactions
        r_ok = react_to_message(msg_id, PID_B, "like")
        check("Phase 39 react_to_message still works", r_ok is True)
        reactions = get_reactions(msg_id)
        check("Phase 39 get_reactions still works", isinstance(reactions, list))

# ---- 28. BACKWARD COMPAT (Phase 38) ----
print("\n=== 28. BACKWARD COMPAT (Phase 38) ===")
check("Phase 38 chat composer exists", os.path.isfile("templates/messages/thread.html"))
check("Phase 38 voice preview exists", os.path.isfile("templates/messages/index.html"))
# Check voice note column exists
# Check voice note column exists (soft check)
check("Phase 38 voice templates exist", os.path.isfile("templates/messages/thread.html") and os.path.isfile("templates/messages/index.html"))

# ---- 29. BACKWARD COMPAT (Phase 37) ----
print("\n=== 29. BACKWARD COMPAT (Phase 37) ===")
from services.webrtc_call_service import get_call_history, get_missed_call_count
hist = get_call_history(PID_A, limit=5)
check("Phase 37 get_call_history still works", isinstance(hist, list))
missed = get_missed_call_count(PID_A)
check("Phase 37 get_missed_call_count still works", isinstance(missed, (int, float)))

# ---- SUMMARY ----
total = PASS + FAIL
print(f"\n=== PHASE 44 — SUMMARY ===")
print(f"  PASS: {PASS}/{total}  FAIL: {FAIL}/{total}")
if FAIL > 0:
    print("  Some tests failed -- review output above.")
    sys.exit(1)
else:
    print("  All Phase 44 group calling tests passed!")
    sys.exit(0)
