import os
import uuid
import json
from datetime import datetime, timezone, timedelta

from services.neon_service import fast_query, write_query, get_pool_status
from services.socketio_service import emit_to_profile


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _uuid(value=None):
    if value:
        try:
            return str(uuid.UUID(str(value)))
        except (TypeError, ValueError):
            pass
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


def _call_dict(row):
    return {
        "id": str(row["id"]),
        "caller_profile_id": str(row["caller_profile_id"]),
        "receiver_profile_id": str(row["receiver_profile_id"]),
        "thread_id": str(row["thread_id"]) if row.get("thread_id") else None,
        "call_type": row.get("call_type", "audio"),
        "call_mode": row.get("call_mode", "audio"),
        "status": row.get("status", "ringing"),
        "started_at": row["started_at"].isoformat() if row.get("started_at") else None,
        "accepted_at": row["accepted_at"].isoformat() if row.get("accepted_at") else None,
        "ended_at": row["ended_at"].isoformat() if row.get("ended_at") else None,
        "duration_seconds": row.get("duration_seconds", 0),
        "end_reason": row.get("end_reason"),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def get_active_call(profile_id):
    profile_id = _uuid(profile_id)
    if _db_available():
        rows = fast_query(
            """SELECT * FROM chain_calls
               WHERE (caller_profile_id = %s OR receiver_profile_id = %s)
                 AND status IN ('ringing', 'accepted')
               ORDER BY created_at DESC LIMIT 1""",
            (profile_id, profile_id),
            timeout_ms=500, default=[],
        )
        if rows:
            return _call_dict(rows[0])
    return None


def get_call(call_id):
    call_id = _uuid(call_id)
    if _db_available():
        rows = fast_query(
            "SELECT * FROM chain_calls WHERE id = %s LIMIT 1",
            (call_id,), timeout_ms=500, default=[],
        )
        if rows:
            return _call_dict(rows[0])
    return None


def create_call(caller_profile_id, receiver_profile_id, thread_id=None, call_type="audio"):
    caller_profile_id = _uuid(caller_profile_id)
    receiver_profile_id = _uuid(receiver_profile_id)
    call_id = str(uuid.uuid4())

    active_caller = get_active_call(caller_profile_id)
    if active_caller:
        return {"ok": False, "error": "caller_busy", "status": "busy"}

    active_receiver = get_active_call(receiver_profile_id)
    if active_receiver:
        return {"ok": False, "error": "receiver_busy", "status": "busy"}

    try:
        write_query(
            """INSERT INTO chain_calls (id, caller_profile_id, receiver_profile_id, thread_id, call_type, call_mode, status)
               VALUES (%s, %s, %s, %s, %s, %s, 'ringing')""",
            (call_id, caller_profile_id, receiver_profile_id, thread_id, call_type, call_type),
        )
    except Exception:
        return {"ok": False, "error": "db_error", "status": "failed"}

    try:
        write_query(
            """INSERT INTO chain_call_participants (call_session_id, call_id, profile_id, role, status, joined_at)
               VALUES (%s, %s, %s, 'caller', 'accepted', now())""",
            (None, call_id, caller_profile_id),
        )
    except Exception:
        pass

    try:
        write_query(
            """INSERT INTO chain_call_participants (call_session_id, call_id, profile_id, role, status)
               VALUES (%s, %s, %s, 'receiver', 'ringing')""",
            (None, call_id, receiver_profile_id),
        )
    except Exception:
        pass

    call = get_call(call_id)
    return {"ok": True, "call": call}


def accept_call(call_id, profile_id):
    call_id = _uuid(call_id)
    profile_id = _uuid(profile_id)
    call = get_call(call_id)
    if not call:
        return {"ok": False, "error": "not_found"}
    if call["status"] != "ringing":
        return {"ok": False, "error": "not_ringing"}

    try:
        write_query(
            "UPDATE chain_calls SET status = 'accepted', accepted_at = now(), updated_at = now() WHERE id = %s",
            (call_id,),
        )
        write_query(
            """UPDATE chain_call_participants SET status = 'accepted', joined_at = COALESCE(joined_at, now())
               WHERE (call_id = %s OR call_session_id = %s) AND profile_id = %s""",
            (call_id, call_id, profile_id),
        )
    except Exception:
        pass

    updated = get_call(call_id)
    return {"ok": True, "call": updated}


def reject_call(call_id, profile_id):
    call_id = _uuid(call_id)
    profile_id = _uuid(profile_id)
    call = get_call(call_id)
    if not call:
        return {"ok": False, "error": "not_found"}

    try:
        write_query(
            "UPDATE chain_calls SET status = 'rejected', ended_at = now(), end_reason = 'declined', updated_at = now() WHERE id = %s",
            (call_id,),
        )
        write_query(
            """UPDATE chain_call_participants SET status = 'declined', left_at = now()
               WHERE (call_id = %s OR call_session_id = %s) AND profile_id = %s""",
            (call_id, call_id, profile_id),
        )
    except Exception:
        pass

    _create_call_log(call, profile_id, "rejected")
    return {"ok": True, "call": get_call(call_id)}


def cancel_call(call_id, profile_id):
    call_id = _uuid(call_id)
    profile_id = _uuid(profile_id)
    call = get_call(call_id)
    if not call:
        return {"ok": False, "error": "not_found"}

    try:
        write_query(
            "UPDATE chain_calls SET status = 'cancelled', ended_at = now(), end_reason = 'cancelled', updated_at = now() WHERE id = %s",
            (call_id,),
        )
        write_query(
            """UPDATE chain_call_participants SET status = 'left', left_at = now()
               WHERE (call_id = %s OR call_session_id = %s) AND profile_id = %s""",
            (call_id, call_id, profile_id),
        )
    except Exception:
        pass

    return {"ok": True, "call": get_call(call_id)}


def end_call(call_id, profile_id):
    call_id = _uuid(call_id)
    profile_id = _uuid(profile_id)
    call = get_call(call_id)
    if not call:
        return {"ok": False, "error": "not_found"}

    started = call.get("accepted_at") or call.get("started_at")
    duration = 0
    if started:
        try:
            started_dt = started
            if isinstance(started, str):
                started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            duration = max(0, int((_now() - started_dt).total_seconds()))
        except Exception:
            duration = 0

    try:
        write_query(
            "UPDATE chain_calls SET status = 'ended', ended_at = now(), duration_seconds = %s, end_reason = 'hung_up', updated_at = now() WHERE id = %s",
            (duration, call_id),
        )
        write_query(
            """UPDATE chain_call_participants SET status = 'left', left_at = now()
               WHERE (call_id = %s OR call_session_id = %s) AND profile_id = %s""",
            (call_id, call_id, profile_id),
        )
    except Exception:
        pass

    _create_call_log(call, profile_id, "ended", duration)
    return {"ok": True, "call": get_call(call_id)}


def mark_call_busy(call_id):
    call_id = _uuid(call_id)
    try:
        write_query(
            "UPDATE chain_calls SET status = 'busy', ended_at = now(), end_reason = 'busy', updated_at = now() WHERE id = %s",
            (call_id,),
        )
    except Exception:
        pass
    return {"ok": True}


def mark_call_timeout(call_id):
    call_id = _uuid(call_id)
    call = get_call(call_id)
    if not call:
        return {"ok": False, "error": "not_found"}

    try:
        write_query(
            "UPDATE chain_calls SET status = 'missed', ended_at = now(), end_reason = 'timeout', updated_at = now() WHERE id = %s",
            (call_id,),
        )
        write_query(
            """UPDATE chain_call_participants SET status = 'missed', left_at = now()
               WHERE (call_id = %s OR call_session_id = %s) AND status = 'ringing'""",
            (call_id, call_id),
        )
    except Exception:
        pass

    if call.get("receiver_profile_id"):
        _create_call_log(call, call["receiver_profile_id"], "missed")

    return {"ok": True, "call": get_call(call_id)}


def get_call_participants(call_id):
    call_id = _uuid(call_id)
    if _db_available():
        rows = fast_query(
            """SELECT * FROM chain_call_participants
               WHERE call_id = %s OR call_session_id = %s
               ORDER BY joined_at NULLS LAST""",
            (call_id, call_id),
            timeout_ms=500, default=[],
        )
        result = []
        for r in rows:
            result.append({
                "id": str(r["id"]),
                "call_id": str(r.get("call_id") or r.get("call_session_id") or ""),
                "profile_id": str(r["profile_id"]),
                "role": r.get("role", "participant"),
                "status": r.get("status", "unknown"),
                "joined_at": r["joined_at"].isoformat() if r.get("joined_at") else None,
                "left_at": r["left_at"].isoformat() if r.get("left_at") else None,
                "muted": r.get("muted", False),
                "camera_enabled": r.get("camera_enabled", True),
                "speaker_enabled": r.get("speaker_enabled", True),
                "connection_status": r.get("connection_status", "disconnected"),
            })
        return result
    return []


def add_call_event(call_id, profile_id, event_type, metadata=None):
    call_id = _uuid(call_id)
    profile_id = _uuid(profile_id) if profile_id else None
    try:
        write_query(
            """INSERT INTO chain_call_events (call_session_id, call_id, profile_id, event_type, metadata, payload)
               VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb)""",
            (None, call_id, profile_id, event_type, json.dumps(metadata or {}), json.dumps(metadata or {})),
        )
    except Exception:
        pass
    return {"ok": True}


def _create_call_log(call, profile_id, status, duration=0):
    profile_id = _uuid(profile_id)
    try:
        direction = "outgoing" if str(call.get("caller_profile_id")) == profile_id else "incoming"
        other_id = call.get("receiver_profile_id") if direction == "outgoing" else call.get("caller_profile_id")
        write_query(
            """INSERT INTO chain_call_logs (call_id, profile_id, other_profile_id, direction, call_type, status, duration_seconds)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (call["id"], profile_id, str(other_id) if other_id else None, direction, call.get("call_type", "audio"), status, duration),
        )
    except Exception:
        pass


def create_call_logs(call_id, profile_id, other_profile_id, direction="outgoing", call_type="audio", status="missed", duration=0):
    call_id = _uuid(call_id)
    profile_id = _uuid(profile_id)
    other_profile_id = _uuid(other_profile_id) if other_profile_id else None
    try:
        write_query(
            """INSERT INTO chain_call_logs (call_id, profile_id, other_profile_id, direction, call_type, status, duration_seconds)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (call_id, profile_id, other_profile_id, direction, call_type, status, duration),
        )
    except Exception:
        pass
    return {"ok": True}


def get_call_history(profile_id, limit=50):
    profile_id = _uuid(profile_id)
    if _db_available():
        rows = fast_query(
            """SELECT l.*,
                      p.display_name as other_display_name,
                      p.username as other_username,
                      p.avatar_url as other_avatar_url
               FROM chain_call_logs l
               LEFT JOIN chain_profiles p ON p.id = l.other_profile_id
               WHERE l.profile_id = %s
               ORDER BY l.created_at DESC
               LIMIT %s""",
            (profile_id, limit),
            timeout_ms=700, default=[],
        )
        results = []
        for r in rows:
            results.append({
                "id": str(r["id"]),
                "call_id": str(r["call_id"]) if r.get("call_id") else None,
                "profile_id": str(r["profile_id"]),
                "other_profile_id": str(r["other_profile_id"]) if r.get("other_profile_id") else None,
                "direction": r.get("direction", "outgoing"),
                "call_type": r.get("call_type", "audio"),
                "status": r.get("status", "missed"),
                "duration_seconds": r.get("duration_seconds", 0),
                "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
                "other_display_name": r.get("other_display_name"),
                "other_username": r.get("other_username"),
                "other_avatar_url": r.get("other_avatar_url"),
            })
        return results
    return []


def update_participant_state(call_id, profile_id, **kwargs):
    call_id = _uuid(call_id)
    profile_id = _uuid(profile_id)
    sets = []
    params = []
    for key in ("muted", "camera_enabled", "speaker_enabled", "connection_status", "status"):
        if key in kwargs:
            sets.append(f"{key} = %s")
            params.append(kwargs[key])
    if not sets:
        return {"ok": False, "error": "no_fields"}
    params.extend([call_id, call_id, profile_id])
    try:
        write_query(
            f"UPDATE chain_call_participants SET {', '.join(sets)} WHERE (call_id = %s OR call_session_id = %s) AND profile_id = %s",
            params,
        )
    except Exception:
        pass
    return {"ok": True}


def check_call_timeouts():
    timeout_limit = _now() - timedelta(seconds=30)
    if _db_available():
        stale = fast_query(
            """SELECT id, caller_profile_id, receiver_profile_id, call_type, thread_id
               FROM chain_calls
               WHERE status = 'ringing' AND started_at < %s""",
            (timeout_limit,),
            timeout_ms=2000, default=[],
        )
        for call_row in stale:
            call_id = str(call_row["id"])
            try:
                write_query(
                    "UPDATE chain_calls SET status = 'missed', ended_at = now(), end_reason = 'timeout', updated_at = now() WHERE id = %s",
                    (call_id,),
                )
                write_query(
                    """UPDATE chain_call_participants SET status = 'missed', left_at = now()
                       WHERE (call_id = %s OR call_session_id = %s) AND status = 'ringing'""",
                    (call_id, call_id),
                )
            except Exception:
                pass
            receiver_id = str(call_row["receiver_profile_id"]) if call_row.get("receiver_profile_id") else None
            caller_id = str(call_row["caller_profile_id"]) if call_row.get("caller_profile_id") else None
            if receiver_id:
                emit_to_profile(receiver_id, "call:missed", {"call_id": call_id})
            if caller_id:
                emit_to_profile(caller_id, "call:no-answer", {"call_id": call_id})
            call = _call_dict(call_row)
            if receiver_id:
                _create_call_log(call, receiver_id, "missed")
        return len(stale)
    return 0
