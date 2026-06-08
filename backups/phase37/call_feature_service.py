import os
import uuid
from datetime import datetime, timezone
import json

from services.neon_service import fast_query, get_pool_status, write_query
from services.socketio_service import emit_to_profile

_CALLS = {}
_PARTICIPANTS = {}
_EVENTS = {}
_QUALITY = {}
_DEVICE_SETTINGS = {}
_RECORDING_SETTINGS = {}
_WAITING = {}


def _now_dt():
    return datetime.now(timezone.utc)


def _now():
    return _now_dt().isoformat()


def _uuid(value=None):
    if value:
        try:
            return str(uuid.UUID(str(value)))
        except (TypeError, ValueError):
            pass
    return str(uuid.uuid4())


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _write(sql, params=(), timeout_ms=900):
    if not _db_available():
        raise RuntimeError("db_unavailable")
    return write_query(sql, params, timeout_ms=timeout_ms)


def _active_call(profile_id):
    for call in _CALLS.values():
        if call.get("call_status") in {"ringing", "answered"} and profile_id in {call.get("caller_profile_id"), call.get("receiver_profile_id")}:
            return call
    if _db_available():
        rows = fast_query(
            "SELECT * FROM chain_call_sessions WHERE (caller_profile_id = %s OR receiver_profile_id = %s) AND call_status IN ('ringing', 'answered') LIMIT 1",
            (profile_id, profile_id),
            timeout_ms=500,
            default=[],
        )
        return rows[0] if rows else None
    return None


def start_call(caller_profile_id, receiver_profile_id=None, call_type="audio", conversation_id=None, **options):
    caller_profile_id = _uuid(caller_profile_id)
    receiver_profile_id = _uuid(receiver_profile_id) if receiver_profile_id else None
    active_caller = _active_call(caller_profile_id)
    active_receiver = _active_call(receiver_profile_id) if receiver_profile_id else None
    if active_caller or active_receiver:
        if options.get("allow_waiting") and active_receiver:
            waiting = record_call_waiting(active_receiver.get("id"), receiver_profile_id, caller_profile_id, {"call_type": call_type})
            return {"ok": False, "status": "waiting", "waiting": waiting.get("waiting")}
        return {"ok": False, "status": "busy"}
    call_id = str(uuid.uuid4())
    call = {
        "id": call_id,
        "conversation_id": _uuid(conversation_id) if conversation_id else None,
        "caller_profile_id": caller_profile_id,
        "receiver_profile_id": receiver_profile_id,
        "call_type": "video" if call_type == "video" else "audio",
        "is_group_call": bool(options.get("is_group_call") or options.get("conference")),
        "call_status": "ringing",
        "room_id": f"call-{call_id}",
        "started_at": _now(),
        "duration_seconds": 0,
    }
    try:
        _write(
            """
            INSERT INTO chain_call_sessions (id, conversation_id, caller_profile_id, receiver_profile_id, call_type, call_status, room_id, started_at, is_group_call)
            VALUES (%s, %s, %s, %s, %s, 'ringing', %s, now(), %s)
            """,
            (call["id"], call["conversation_id"], caller_profile_id, receiver_profile_id, call["call_type"], call["room_id"], call["is_group_call"]),
        )
        add_participant(call_id, caller_profile_id, "accepted")
        if receiver_profile_id:
            add_participant(call_id, receiver_profile_id, "ringing")
    except Exception:
        _CALLS[call_id] = call
        _PARTICIPANTS.setdefault(call_id, {})[caller_profile_id] = {"status": "accepted", "joined_at": _now()}
        if receiver_profile_id:
            _PARTICIPANTS.setdefault(call_id, {})[receiver_profile_id] = {"status": "ringing"}
    if receiver_profile_id:
        emit_to_profile(receiver_profile_id, "call:incoming", call)
    return {"ok": True, "call": call}


def start_group_call(caller_profile_id, participant_ids=None, call_type="video", conversation_id=None):
    result = start_call(caller_profile_id, None, call_type=call_type, conversation_id=conversation_id, is_group_call=True, conference=True)
    if not result.get("ok"):
        return result
    call_id = result["call"]["id"]
    for participant_id in participant_ids or []:
        add_participant(call_id, participant_id, "invited")
        emit_to_profile(_uuid(participant_id), "call:incoming", result["call"])
    return result


def add_participant(call_id, profile_id, status="invited"):
    call_id = _uuid(call_id)
    profile_id = _uuid(profile_id)
    try:
        _write("INSERT INTO chain_call_participants (call_session_id, profile_id, status, joined_at) VALUES (%s, %s, %s, CASE WHEN %s = 'accepted' THEN now() ELSE NULL END) ON CONFLICT DO NOTHING", (call_id, profile_id, status, status))
    except Exception:
        _PARTICIPANTS.setdefault(call_id, {})[profile_id] = {"status": status, "joined_at": _now() if status == "accepted" else None}
    return {"ok": True}


def record_quality_event(call_id, profile_id, event_type, quality_score=None, payload=None):
    call_id = _uuid(call_id)
    profile_id = _uuid(profile_id) if profile_id else None
    record = {"id": str(uuid.uuid4()), "call_session_id": call_id, "profile_id": profile_id, "event_type": event_type, "quality_score": quality_score, "payload": payload or {}, "created_at": _now()}
    try:
        _write(
            "INSERT INTO chain_call_quality_events (id, call_session_id, profile_id, event_type, quality_score, payload) VALUES (%s, %s, %s, %s, %s, %s::jsonb)",
            (record["id"], call_id, profile_id, event_type, quality_score, json.dumps(payload or {})),
        )
    except Exception:
        _QUALITY.setdefault(call_id, []).append(record)
    emit_to_profile(profile_id, "call:quality", record) if profile_id else None
    return {"ok": True, "quality_event": record}


def save_device_settings(profile_id, **settings):
    profile_id = _uuid(profile_id)
    payload = {
        "profile_id": profile_id,
        "preferred_audio_input": settings.get("preferred_audio_input"),
        "preferred_audio_output": settings.get("preferred_audio_output"),
        "preferred_video_input": settings.get("preferred_video_input"),
        "hd_enabled": bool(settings.get("hd_enabled", True)),
        "noise_suppression": bool(settings.get("noise_suppression", True)),
        "background_blur": bool(settings.get("background_blur", False)),
    }
    try:
        _write(
            """
            INSERT INTO chain_call_device_settings
            (profile_id, preferred_audio_input, preferred_audio_output, preferred_video_input, hd_enabled, noise_suppression, background_blur)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            tuple(payload[key] for key in ["profile_id", "preferred_audio_input", "preferred_audio_output", "preferred_video_input", "hd_enabled", "noise_suppression", "background_blur"]),
        )
    except Exception:
        _DEVICE_SETTINGS[profile_id] = payload
    return {"ok": True, "settings": payload}


def save_recording_setting(profile_id, allow_recording=False):
    profile_id = _uuid(profile_id)
    try:
        _write("INSERT INTO chain_call_recording_settings (profile_id, allow_recording) VALUES (%s, %s)", (profile_id, bool(allow_recording)))
    except Exception:
        _RECORDING_SETTINGS[profile_id] = {"allow_recording": bool(allow_recording)}
    return {"ok": True, "allow_recording": bool(allow_recording)}


def record_call_waiting(call_id, waiting_profile_id, incoming_profile_id=None, payload=None):
    call_id = _uuid(call_id)
    waiting_profile_id = _uuid(waiting_profile_id)
    incoming_profile_id = _uuid(incoming_profile_id) if incoming_profile_id else None
    record = {"id": str(uuid.uuid4()), "call_session_id": call_id, "waiting_profile_id": waiting_profile_id, "incoming_profile_id": incoming_profile_id, "status": "waiting", "payload": payload or {}}
    try:
        _write(
            "INSERT INTO chain_call_waiting_events (id, call_session_id, waiting_profile_id, incoming_profile_id, payload) VALUES (%s, %s, %s, %s, %s::jsonb)",
            (record["id"], call_id, waiting_profile_id, incoming_profile_id, json.dumps(payload or {})),
        )
    except Exception:
        _WAITING[record["id"]] = record
    emit_to_profile(waiting_profile_id, "call:waiting", record)
    return {"ok": True, "waiting": record}


def answer_call(call_id, profile_id):
    call_id = _uuid(call_id)
    profile_id = _uuid(profile_id)
    answered_at = _now()
    try:
        _write("UPDATE chain_call_sessions SET call_status = 'answered', answered_at = now() WHERE id = %s", (call_id,))
        _write("UPDATE chain_call_participants SET status = 'accepted', joined_at = COALESCE(joined_at, now()) WHERE call_session_id = %s AND profile_id = %s", (call_id, profile_id))
    except Exception:
        _CALLS.setdefault(call_id, {"id": call_id})["call_status"] = "answered"
        _CALLS[call_id]["answered_at"] = answered_at
    call = get_call(call_id)
    if call and call.get("caller_profile_id"):
        emit_to_profile(call["caller_profile_id"], "call:answered", {"call_id": call_id, "profile_id": profile_id})
    return {"ok": True, "call": call or {"id": call_id, "call_status": "answered"}}


def end_call(call_id, profile_id, status="ended"):
    call_id = _uuid(call_id)
    profile_id = _uuid(profile_id)
    call = get_call(call_id) or {"id": call_id}
    started = call.get("answered_at") or call.get("started_at")
    duration = 0
    if started:
        try:
            duration = max(0, int((_now_dt() - datetime.fromisoformat(str(started).replace("Z", "+00:00"))).total_seconds()))
        except Exception:
            duration = 0
    final_status = status if status in {"ended", "missed", "rejected"} else "ended"
    try:
        _write("UPDATE chain_call_sessions SET call_status = %s, ended_at = now(), duration_seconds = %s WHERE id = %s", (final_status, duration, call_id))
        _write("UPDATE chain_call_participants SET status = 'left', left_at = now() WHERE call_session_id = %s AND profile_id = %s", (call_id, profile_id))
    except Exception:
        _CALLS.setdefault(call_id, call).update({"call_status": final_status, "ended_at": _now(), "duration_seconds": duration})
    for participant_id in list((_PARTICIPANTS.get(call_id) or {}).keys()):
        if participant_id != profile_id:
            emit_to_profile(participant_id, "call:ended", {"call_id": call_id, "status": final_status})
    return {"ok": True, "call": get_call(call_id) or _CALLS.get(call_id)}


def record_event(call_id, profile_id, event_type, payload=None):
    call_id = _uuid(call_id)
    profile_id = _uuid(profile_id) if profile_id else None
    event_type = event_type or "unknown"
    event = {"call_session_id": call_id, "profile_id": profile_id, "event_type": event_type, "payload": payload or {}, "created_at": _now()}
    try:
        _write("INSERT INTO chain_call_events (call_session_id, profile_id, event_type, payload) VALUES (%s, %s, %s, %s::jsonb)", (call_id, profile_id, event_type, str(payload or {}).replace("'", '"')))
    except Exception:
        _EVENTS.setdefault(call_id, []).append(event)
    return {"ok": True, "event": event}


def get_call(call_id):
    call_id = _uuid(call_id)
    if _db_available():
        rows = fast_query("SELECT * FROM chain_call_sessions WHERE id = %s LIMIT 1", (call_id,), timeout_ms=500, default=[])
        if rows:
            return rows[0]
    return _CALLS.get(call_id)


def recent_calls(profile_id):
    profile_id = _uuid(profile_id)
    if _db_available():
        rows = fast_query("SELECT * FROM chain_call_sessions WHERE caller_profile_id = %s OR receiver_profile_id = %s ORDER BY started_at DESC LIMIT 50", (profile_id, profile_id), timeout_ms=700, default=[])
        if rows:
            return rows
    return [call for call in _CALLS.values() if profile_id in {call.get("caller_profile_id"), call.get("receiver_profile_id")}]
