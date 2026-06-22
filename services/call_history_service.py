from datetime import datetime, timezone

from services.neon_service import fast_query, write_query
from services.socketio_service import emit_to_profile
from services.webrtc_call_service import get_call as w_get_call


def _uuid(value):
    import uuid
    if value:
        try:
            return str(uuid.UUID(str(value)))
        except (TypeError, ValueError):
            pass
    return None


def get_call_history(profile_id, limit=50, offset=0):
    profile_id = _uuid(profile_id)
    if not profile_id:
        return []

    rows = fast_query(
        """SELECT l.id, l.call_id, l.profile_id, l.other_profile_id,
                  l.direction, l.call_type, l.status,
                  l.duration_seconds, l.created_at,
                  l.started_at, l.accepted_at, l.ended_at,
                  l.missed_at, l.rejected_at, l.busy_at,
                  l.failure_reason,
                  p.display_name as other_display_name,
                  p.username as other_username,
                  p.avatar_url as other_avatar_url
           FROM chain_call_logs l
           LEFT JOIN chain_profiles p ON p.id = l.other_profile_id
           WHERE l.profile_id = %s
           ORDER BY l.created_at DESC
           LIMIT %s OFFSET %s""",
        (profile_id, limit, offset),
        timeout_ms=1000, default=[],
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
            "started_at": r["started_at"].isoformat() if r.get("started_at") else None,
            "accepted_at": r["accepted_at"].isoformat() if r.get("accepted_at") else None,
            "ended_at": r["ended_at"].isoformat() if r.get("ended_at") else None,
            "missed_at": r["missed_at"].isoformat() if r.get("missed_at") else None,
            "rejected_at": r["rejected_at"].isoformat() if r.get("rejected_at") else None,
            "busy_at": r["busy_at"].isoformat() if r.get("busy_at") else None,
            "failure_reason": r.get("failure_reason"),
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
            "other_display_name": r.get("other_display_name"),
            "other_username": r.get("other_username"),
            "other_avatar_url": r.get("other_avatar_url"),
        })
    return results


def create_call_log(call_id, profile_id, other_profile_id, direction, call_type, status, duration=0):
    call_id = _uuid(call_id)
    profile_id = _uuid(profile_id)
    other_profile_id = _uuid(other_profile_id)

    now_iso = datetime.now(timezone.utc).isoformat()
    col = None
    if status == "accepted":
        col = "accepted_at"
    elif status == "rejected":
        col = "rejected_at"
    elif status == "missed":
        col = "missed_at"
    elif status == "busy":
        col = "busy_at"
    elif status in ("ended", "completed", "failed"):
        col = "ended_at"

    try:
        write_query(
            f"""INSERT INTO chain_call_logs
                (call_id, profile_id, other_profile_id, direction, call_type, status, duration_seconds,
                 started_at, {col if col else 'created_at'}, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, now(), now(), now())""",
            (call_id, profile_id, other_profile_id, direction, call_type, status, duration),
        )
    except Exception:
        pass

    emit_to_profile(profile_id, "calls:history:update", {
        "call_id": call_id,
        "other_profile_id": other_profile_id,
        "direction": direction,
        "call_type": call_type,
        "status": status,
        "duration_seconds": duration,
    })
    return {"ok": True}


def delete_call_log(log_id, profile_id):
    log_id = _uuid(log_id)
    profile_id = _uuid(profile_id)
    if not log_id or not profile_id:
        return {"ok": False, "error": "invalid_id"}

    try:
        write_query(
            "DELETE FROM chain_call_logs WHERE id = %s AND profile_id = %s",
            (log_id, profile_id),
        )
    except Exception:
        return {"ok": False, "error": "delete_failed"}
    return {"ok": True}


def get_missed_call_count(profile_id):
    profile_id = _uuid(profile_id)
    if not profile_id:
        return 0
    try:
        rows = fast_query(
            "SELECT COUNT(*) as cnt FROM chain_call_logs WHERE other_profile_id = %s AND status = 'missed'",
            (profile_id,),
            default=[{"cnt": 0}],
        )
        return rows[0]["cnt"] if rows else 0
    except Exception:
        return 0
