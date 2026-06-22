import os
import time
from datetime import datetime, timezone

from services.neon_service import fast_query, write_query
from services.socketio_service import emit_to_profile, emit_to_thread
from services.profile_service import get_current_profile
from services.webrtc_call_service import (
    get_call as w_get_call,
    get_active_call as w_get_active_call,
    create_call as w_create_call,
    accept_call as w_accept_call,
    reject_call as w_reject_call,
    cancel_call as w_cancel_call,
    end_call as w_end_call,
    mark_call_busy as w_mark_call_busy,
    mark_call_timeout as w_mark_call_timeout,
    update_participant_state,
    add_call_event,
)


CALL_RING_TIMEOUT = int(os.getenv("CALL_RING_TIMEOUT_SECONDS", "15"))


def _now():
    return datetime.now(timezone.utc)


def _check_self_call(caller_id, receiver_id):
    return caller_id == receiver_id


def _check_blocked(caller_id, receiver_id):
    try:
        rows = fast_query(
            "SELECT id FROM chain_blocks WHERE (blocker_profile_id = %s AND blocked_profile_id = %s AND deleted_at IS NULL) OR (blocker_profile_id = %s AND blocked_profile_id = %s AND deleted_at IS NULL) LIMIT 1",
            (receiver_id, caller_id, caller_id, receiver_id),
            timeout_ms=300, default=[],
        )
        return bool(rows)
    except Exception:
        return False


def start_call(caller_profile_id, receiver_profile_id, thread_id=None, call_type="audio"):
    if _check_self_call(caller_profile_id, receiver_profile_id):
        return {"ok": False, "error": "self_call"}

    if _check_blocked(caller_profile_id, receiver_profile_id):
        return {"ok": False, "error": "blocked"}

    active = w_get_active_call(receiver_profile_id)
    if active:
        return {"ok": False, "error": "receiver_busy", "status": "busy"}

    active_self = w_get_active_call(caller_profile_id)
    if active_self:
        return {"ok": False, "error": "caller_busy", "status": "busy"}

    result = w_create_call(caller_profile_id, receiver_profile_id, thread_id=thread_id, call_type=call_type)
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error", "start_failed"), "status": result.get("status")}

    call = result.get("call")
    if call:
        emit_to_profile(receiver_profile_id, "call:incoming", {
            "call_id": call["id"],
            "caller_profile_id": caller_profile_id,
            "call_type": call_type,
            "thread_id": thread_id,
        })
        emit_to_profile(caller_profile_id, "call:ringing", {
            "call_id": call["id"],
            "status": "ringing",
        })

    return {"ok": True, "call": call}


def accept_call(call_id, profile_id):
    call = w_get_call(call_id)
    if not call:
        return {"ok": False, "error": "call_not_found"}
    if call["status"] != "ringing":
        return {"ok": False, "error": "call_not_ringing"}

    result = w_accept_call(call_id, profile_id)
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error", "accept_failed")}

    caller = call.get("caller_profile_id")
    if caller and caller != profile_id:
        emit_to_profile(caller, "call:accepted", {
            "call_id": call_id,
            "profile_id": profile_id,
            "accepted_at": _now().isoformat(),
        })

    updated = result.get("call", {})
    _update_call_log_timestamps(call_id, profile_id, "accepted")
    return {"ok": True, "call": updated}


def reject_call(call_id, profile_id):
    call = w_get_call(call_id)
    if not call:
        return {"ok": False, "error": "call_not_found"}

    result = w_reject_call(call_id, profile_id)
    caller = call.get("caller_profile_id")
    if caller and caller != profile_id:
        emit_to_profile(caller, "call:rejected", {
            "call_id": call_id,
            "profile_id": profile_id,
            "rejected_at": _now().isoformat(),
        })

    _update_call_log_timestamps(call_id, profile_id, "rejected")
    return {"ok": True, "call": result.get("call")}


def cancel_call(call_id, profile_id):
    call = w_get_call(call_id)
    if not call:
        return {"ok": False, "error": "call_not_found"}

    result = w_cancel_call(call_id, profile_id)
    receiver = call.get("receiver_profile_id")
    if receiver and receiver != profile_id:
        emit_to_profile(receiver, "call:cancelled", {
            "call_id": call_id,
            "profile_id": profile_id,
            "cancelled_at": _now().isoformat(),
        })

    return {"ok": True, "call": result.get("call")}


def end_call(call_id, profile_id, end_reason="hung_up"):
    call = w_get_call(call_id)
    if not call:
        return {"ok": False, "error": "call_not_found"}

    other_id = call.get("caller_profile_id") if call.get("receiver_profile_id") == profile_id else call.get("receiver_profile_id")
    result = w_end_call(call_id, profile_id, end_reason=end_reason)
    if result.get("ok") and other_id:
        emit_to_profile(other_id, "call:ended", {
            "call_id": call_id,
            "profile_id": profile_id,
            "end_reason": end_reason,
        })

    return {"ok": True, "call": result.get("call")}


def handle_timeout(call_id):
    call = w_get_call(call_id)
    if not call:
        return {"ok": False, "error": "call_not_found"}

    w_mark_call_timeout(call_id)
    caller = call.get("caller_profile_id")
    receiver = call.get("receiver_profile_id")

    if caller:
        emit_to_profile(caller, "call:missed", {
            "call_id": call_id,
            "receiver_profile_id": receiver,
            "reason": "not_answered",
        })
    if receiver:
        emit_to_profile(receiver, "call:missed", {
            "call_id": call_id,
            "caller_profile_id": caller,
            "reason": "not_answered",
        })

    _update_call_log_timestamps(call_id, None, "missed")
    return {"ok": True}


def handle_busy(call_id):
    call = w_get_call(call_id)
    if not call:
        return {"ok": False, "error": "call_not_found"}

    w_mark_call_busy(call_id)
    caller = call.get("caller_profile_id")
    if caller:
        emit_to_profile(caller, "call:busy", {
            "call_id": call_id,
            "profile_id": call.get("receiver_profile_id"),
        })

    _update_call_log_timestamps(call_id, None, "busy")
    return {"ok": True}


def toggle_mute(call_id, profile_id, muted=True):
    update_participant_state(call_id, profile_id, muted=bool(muted))
    other = _get_other_participant(call_id, profile_id)
    if other:
        emit_to_profile(other, "call:mute-state", {
            "call_id": call_id,
            "profile_id": profile_id,
            "muted": bool(muted),
        })
    return {"ok": True, "muted": bool(muted)}


def toggle_camera(call_id, profile_id, enabled=True):
    update_participant_state(call_id, profile_id, camera_enabled=bool(enabled))
    other = _get_other_participant(call_id, profile_id)
    if other:
        emit_to_profile(other, "call:camera-state", {
            "call_id": call_id,
            "profile_id": profile_id,
            "camera_enabled": bool(enabled),
        })
    return {"ok": True, "camera_enabled": bool(enabled)}


def toggle_speaker(call_id, profile_id, enabled=True):
    update_participant_state(call_id, profile_id, speaker_enabled=bool(enabled))
    return {"ok": True, "speaker_enabled": bool(enabled)}


def handle_reconnect(call_id, profile_id):
    from services.webrtc_call_service import mark_call_reconnecting
    mark_call_reconnecting(call_id, profile_id)
    other = _get_other_participant(call_id, profile_id)
    if other:
        emit_to_profile(other, "call:reconnecting", {
            "call_id": call_id,
            "profile_id": profile_id,
        })
    return {"ok": True}


def handle_reconnected(call_id, profile_id):
    update_participant_state(call_id, profile_id, connection_status="connected")
    other = _get_other_participant(call_id, profile_id)
    if other:
        emit_to_profile(other, "call:reconnected", {
            "call_id": call_id,
            "profile_id": profile_id,
        })
    return {"ok": True}


def handle_reconnect_failed(call_id, profile_id):
    from services.webrtc_call_service import mark_call_failed
    mark_call_failed(call_id, profile_id, reason="reconnect_failed")
    other = _get_other_participant(call_id, profile_id)
    if other:
        emit_to_profile(other, "call:reconnect_failed", {
            "call_id": call_id,
            "profile_id": profile_id,
        })
    return {"ok": True}


def _get_other_participant(call_id, profile_id):
    call = w_get_call(call_id)
    if not call:
        return None
    caller = call.get("caller_profile_id")
    receiver = call.get("receiver_profile_id")
    if caller and caller != profile_id:
        return caller
    if receiver and receiver != profile_id:
        return receiver
    return None


def _update_call_log_timestamps(call_id, profile_id, status):
    now_iso = _now().isoformat()
    col_map = {
        "accepted": "accepted_at",
        "rejected": "rejected_at",
        "missed": "missed_at",
        "busy": "busy_at",
        "ended": "ended_at",
        "failed": "ended_at",
    }
    col = col_map.get(status)
    if col:
        try:
            write_query(
                f"UPDATE chain_call_logs SET {col} = %s, updated_at = now() WHERE call_id = %s",
                (now_iso, call_id),
            )
        except Exception:
            pass
