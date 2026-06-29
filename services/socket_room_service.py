from services.socketio_service import socketio, _emit_async, _json_safe_payload
from services.neon_service import fast_query


def user_room(profile_id):
    return f"profile:{profile_id}"


def thread_room(thread_id):
    return f"thread:{thread_id}"


def call_room(call_id):
    return f"call:{call_id}"


def notification_room(profile_id):
    return f"profile:{profile_id}"


def _is_thread_member(profile_id, thread_id):
    try:
        rows = fast_query(
            "SELECT id FROM chain_thread_members WHERE thread_id = %s AND profile_id = %s LIMIT 1",
            (thread_id, profile_id), default=[]
        )
        return bool(rows)
    except Exception:
        return True


def _is_call_participant(profile_id, call_id):
    try:
        rows = fast_query(
            """SELECT id FROM chain_call_participants
               WHERE (call_id = %s OR call_session_id = %s) AND profile_id = %s LIMIT 1""",
            (call_id, call_id, profile_id), default=[]
        )
        return bool(rows)
    except Exception:
        return True


def safe_emit_to_user(profile_id, event, payload):
    _emit_async(event, _json_safe_payload(payload), room=user_room(profile_id))


def safe_emit_to_thread(thread_id, event, payload, exclude_profile_id=None):
    _emit_async(event, _json_safe_payload(payload), room=thread_room(thread_id))


def safe_emit_to_call(call_id, event, payload):
    _emit_async(event, _json_safe_payload(payload), room=call_room(call_id))


def safe_emit_typing(profile_id, thread_id, typing_state):
    if not _is_thread_member(profile_id, thread_id):
        return
    safe_emit_to_thread(thread_id, "chat:typing", {
        "profile_id": profile_id,
        "thread_id": thread_id,
        "typing": typing_state,
    })
