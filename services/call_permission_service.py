from services.neon_service import fast_query
from services.profile_service import get_current_profile


def can_start_call(caller_profile_id, receiver_profile_id):
    if not caller_profile_id or not receiver_profile_id:
        return {"ok": False, "error": "missing_profile"}

    if str(caller_profile_id) == str(receiver_profile_id):
        return {"ok": False, "error": "self_call"}

    profile = _get_profile_or_none(caller_profile_id)
    if not profile:
        return {"ok": False, "error": "caller_not_found"}

    target = _get_profile_or_none(receiver_profile_id)
    if not target:
        return {"ok": False, "error": "receiver_not_found"}

    if _is_blocked(caller_profile_id, receiver_profile_id):
        return {"ok": False, "error": "blocked"}

    if _is_muted(caller_profile_id, receiver_profile_id):
        return {"ok": False, "error": "you_are_muted"}

    return {"ok": True}


def can_access_call_log(profile_id, log_profile_id):
    return str(profile_id) == str(log_profile_id)


def can_end_call(call, profile_id):
    if not call:
        return False
    caller = call.get("caller_profile_id")
    receiver = call.get("receiver_profile_id")
    return str(profile_id) in (str(caller), str(receiver))


def _get_profile_or_none(profile_id):
    try:
        rows = fast_query(
            "SELECT id FROM chain_profiles WHERE id = %s AND deleted_at IS NULL LIMIT 1",
            (profile_id,), timeout_ms=5000, default=[],
        )
        return rows[0] if rows else None
    except Exception:
        return None


def _is_blocked(a, b):
    try:
        rows = fast_query(
            "SELECT id FROM chain_blocks WHERE (blocker_profile_id = %s AND blocked_profile_id = %s AND deleted_at IS NULL) OR (blocker_profile_id = %s AND blocked_profile_id = %s AND deleted_at IS NULL) LIMIT 1",
            (b, a, a, b), timeout_ms=5000, default=[],
        )
        return bool(rows)
    except Exception:
        return False


def _is_muted(caller, receiver):
    try:
        rows = fast_query(
            "SELECT id FROM chain_muted_users WHERE muter_profile_id = %s AND muted_profile_id = %s LIMIT 1",
            (receiver, caller), timeout_ms=5000, default=[],
        )
        return bool(rows)
    except Exception:
        return False
