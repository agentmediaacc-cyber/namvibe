import os
from flask import Blueprint, jsonify, session
from services.neon_service import fast_query
from services.profile_service import get_current_profile

dev_bp = Blueprint("dev_diagnostics", __name__, url_prefix="/dev/phase37")

def _enabled():
    return os.getenv("CHAIN_DEV_DIAGNOSTICS") == "1"

@dev_bp.route("/session")
def dev_session():
    if not _enabled():
        return jsonify({"error": "disabled"}), 404
    safe = {k: v for k, v in session.items() if k != "access_token"}
    return jsonify({
        "logged_in": bool(session.get("profile_id")),
        "session_keys": list(session.keys()),
        "profile_id": session.get("profile_id"),
        "username": session.get("username"),
        "auth_user_id": session.get("auth_user_id"),
    })

@dev_bp.route("/profile")
def dev_profile():
    if not _enabled():
        return jsonify({"error": "disabled"}), 404
    profile = get_current_profile()
    if not profile:
        return jsonify({"error": "not_logged_in"}), 401
    return jsonify({
        "id": profile.get("id"),
        "username": profile.get("username"),
        "display_name": profile.get("display_name"),
        "email": profile.get("email"),
        "avatar_url": profile.get("avatar_url"),
        "is_creator": profile.get("is_creator"),
        "profile_fallback": profile.get("profile_fallback"),
    })

@dev_bp.route("/messages/state")
def dev_messages_state():
    if not _enabled():
        return jsonify({"error": "disabled"}), 404
    profile = get_current_profile()
    if not profile:
        return jsonify({"error": "not_logged_in"}), 401
    pid = profile["id"]
    threads = fast_query("""
        SELECT tm.thread_id, t.thread_type, t.updated_at,
               (SELECT COUNT(*) FROM chain_messages m WHERE m.thread_id = tm.thread_id AND m.deleted_at IS NULL) AS msg_count
        FROM chain_thread_members tm
        JOIN chain_message_threads t ON t.id = tm.thread_id
        WHERE tm.profile_id = %s
        ORDER BY t.updated_at DESC NULLS LAST
        LIMIT 10
    """, (pid,), default=[])
    recent = fast_query("""
        SELECT id, body, thread_id, sender_profile_id, created_at
        FROM chain_messages
        WHERE sender_profile_id = %s OR thread_id IN (
            SELECT thread_id FROM chain_thread_members WHERE profile_id = %s
        )
        ORDER BY created_at DESC LIMIT 10
    """, (pid, pid), default=[])
    return jsonify({
        "profile_id": pid,
        "thread_count": len(threads),
        "threads": [{"id": str(r["thread_id"]), "type": r["thread_type"], "msg_count": r["msg_count"]} for r in threads],
        "latest_messages": [{"id": str(r["id"]), "body": (r["body"] or "")[:60], "thread_id": str(r["thread_id"])} for r in recent],
    })

@dev_bp.route("/calls/state")
def dev_calls_state():
    if not _enabled():
        return jsonify({"error": "disabled"}), 404
    profile = get_current_profile()
    if not profile:
        return jsonify({"error": "not_logged_in"}), 401
    pid = profile["id"]
    calls = fast_query("""
        SELECT id, call_type, call_status, caller_profile_id, receiver_profile_id,
               started_at, ended_at, duration_seconds
        FROM chain_call_sessions
        WHERE caller_profile_id = %s OR receiver_profile_id = %s
        ORDER BY started_at DESC LIMIT 10
    """, (pid, pid), default=[])
    return jsonify({
        "profile_id": pid,
        "call_count": len(calls),
        "calls": [{"id": str(r["id"]), "type": r["call_type"], "status": r["call_status"],
                    "duration": r["duration_seconds"]} for r in calls],
    })

@dev_bp.route("/socket/state")
def dev_socket_state():
    if not _enabled():
        return jsonify({"error": "disabled"}), 404
    profile = get_current_profile()
    if not profile:
        return jsonify({"error": "not_logged_in"}), 401
    try:
        from services.socket_events import socketio
        has_socket = True
    except Exception:
        has_socket = False
    return jsonify({
        "profile_id": profile.get("id"),
        "socketio_loaded": has_socket,
        "redis_available": bool(os.getenv("REDIS_URL") or os.getenv("REDIS_URI")),
        "neon_available": True,
    })

@dev_bp.route("/frontend-error", methods=["POST"])
def dev_frontend_error():
    if not _enabled():
        return jsonify({"error": "disabled"}), 404
    from flask import request
    error_data = request.get_json(silent=True) or {}
    print(f"[FRONTEND_ERROR] {error_data}")
    return jsonify({"ok": True})
