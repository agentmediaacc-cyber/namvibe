from flask import Blueprint, jsonify, request, session

from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.neon_service import fast_query, write_query
from services.thread_security_service import can_access_thread
from services.message_media_service import upload_message_media, validate_message_attachment
from services.message_receipt_service import mark_message_delivered, mark_message_seen, mark_thread_seen
from services.message_thread_service import (
    add_group_member,
    create_group,
    latest_messages,
    leave_group,
    older_messages,
    remove_group_member,
    unread_count,
)


messaging_api_bp = Blueprint("messaging_api", __name__, url_prefix="/api/messages")


def _profile_id():
    profile = get_current_profile()
    return (profile or {}).get("id") or session.get("profile_id")


def _json_or_form():
    return request.get_json(silent=True) or request.form.to_dict() or {}


def _message_thread(message_id):
    rows = fast_query(
        "SELECT id, thread_id, sender_profile_id FROM chain_messages WHERE id = %s LIMIT 1",
        (message_id,),
        default=[],
    )
    return rows[0] if rows else None


def _blocked(profile_id, thread_id):
    try:
        rows = fast_query(
            """
            SELECT 1
            FROM chain_blocks b
            JOIN chain_thread_members tm ON tm.profile_id IN (b.blocker_profile_id, b.blocked_profile_id)
            WHERE tm.thread_id = %s
              AND %s IN (b.blocker_profile_id, b.blocked_profile_id)
            LIMIT 1
            """,
            (thread_id, profile_id),
            default=[],
        )
        return bool(rows)
    except Exception:
        return False


@messaging_api_bp.get("/thread/<thread_id>/latest")
@login_required
def api_thread_latest(thread_id):
    profile_id = _profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    result = latest_messages(
        thread_id,
        profile_id,
        limit=request.args.get("limit", 50, type=int),
        since=request.args.get("since"),
    )
    return jsonify(result), 200 if result.get("ok") else 404


@messaging_api_bp.get("/thread/<thread_id>/older")
@login_required
def api_thread_older(thread_id):
    profile_id = _profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    result = older_messages(
        thread_id,
        profile_id,
        limit=request.args.get("limit", 50, type=int),
        before=request.args.get("before"),
    )
    return jsonify(result), 200 if result.get("ok") else 404


@messaging_api_bp.post("/send")
@login_required
def api_send_message():
    profile_id = _profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = _json_or_form()
    thread_id = data.get("thread_id")
    body = (data.get("body") or "").strip()
    client_temp_id = data.get("client_temp_id") or data.get("client_event_id")
    reply_to_message_id = data.get("reply_to_message_id")
    if not thread_id:
        return jsonify({"ok": False, "error": "thread_id_required"}), 400
    if not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "thread_not_found"}), 404
    if _blocked(profile_id, thread_id):
        return jsonify({"ok": False, "error": "blocked"}), 403
    file_obj = request.files.get("file") or request.files.get("media")
    if not body and not file_obj and not data.get("media_url"):
        return jsonify({"ok": False, "error": "message_empty"}), 400

    from services.messaging_engine import send_message

    result = send_message(
        thread_id=thread_id,
        sender_profile_id=profile_id,
        body=body,
        file=file_obj,
        client_message_id=client_temp_id,
        parent_message_id=reply_to_message_id,
        is_forwarded=bool(data.get("forwarded_from_message_id")),
    )
    if not result.get("success"):
        return jsonify({"ok": False, "error": result.get("error", "send_failed"), "client_temp_id": client_temp_id}), 400

    message_id = result.get("message_id") or result.get("id")
    if message_id:
        try:
            write_query(
                """
                UPDATE chain_messages
                SET status = 'sent',
                    client_temp_id = COALESCE(client_temp_id, %s),
                    reply_to_message_id = COALESCE(reply_to_message_id, %s),
                    forwarded_from_message_id = COALESCE(forwarded_from_message_id, %s)
                WHERE id = %s
                """,
                (client_temp_id, reply_to_message_id, data.get("forwarded_from_message_id"), message_id),
            )
        except Exception:
            pass
    try:
        from services.socketio_service import emit_to_profile, emit_to_thread
        emit_to_thread(thread_id, "inbox:update", {"thread_id": thread_id, "sender_profile_id": profile_id})
        emit_to_thread(thread_id, "unread:update", {"thread_id": thread_id, "profile_id": profile_id})
    except Exception:
        pass
    return jsonify({"ok": True, "message": result, "status": "sent", "client_temp_id": client_temp_id})


@messaging_api_bp.post("/<message_id>/delivered")
@login_required
def api_message_delivered(message_id):
    profile_id = _profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    result = mark_message_delivered(message_id, profile_id)
    return jsonify(result), 200 if result.get("ok") else 404


@messaging_api_bp.post("/<message_id>/seen")
@login_required
def api_message_seen(message_id):
    profile_id = _profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    result = mark_message_seen(message_id, profile_id)
    return jsonify(result), 200 if result.get("ok") else 404


@messaging_api_bp.post("/thread/<thread_id>/seen")
@login_required
def api_thread_seen(thread_id):
    profile_id = _profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    result = mark_thread_seen(thread_id, profile_id)
    return jsonify(result), 200 if result.get("ok") else 404


@messaging_api_bp.post("/<message_id>/delete-for-me")
@login_required
def api_delete_for_me(message_id):
    profile_id = _profile_id()
    message = _message_thread(message_id)
    if not profile_id or not message or not can_access_thread(profile_id, message["thread_id"]):
        return jsonify({"ok": False, "error": "message_not_found"}), 404
    write_query(
        "UPDATE chain_messages SET deleted_for_sender = TRUE WHERE id = %s AND sender_profile_id = %s",
        (message_id, profile_id),
    )
    return jsonify({"ok": True, "message_id": message_id, "deleted_for_me": True})


@messaging_api_bp.post("/<message_id>/delete-for-everyone")
@login_required
def api_delete_for_everyone(message_id):
    profile_id = _profile_id()
    message = _message_thread(message_id)
    if not profile_id or not message or not can_access_thread(profile_id, message["thread_id"]):
        return jsonify({"ok": False, "error": "message_not_found"}), 404
    if str(message["sender_profile_id"]) != str(profile_id):
        return jsonify({"ok": False, "error": "sender_only"}), 403
    write_query(
        """
        UPDATE chain_messages
        SET deleted_for_everyone_at = COALESCE(deleted_for_everyone_at, now()),
            body = NULL,
            media_url = NULL
        WHERE id = %s
        """,
        (message_id,),
    )
    try:
        from services.socketio_service import emit_to_thread
        emit_to_thread(message["thread_id"], "message:deleted", {"message_id": message_id, "for_everyone": True})
    except Exception:
        pass
    return jsonify({"ok": True, "message_id": message_id, "deleted_for_everyone": True, "body": "This message was deleted"})


@messaging_api_bp.post("/<message_id>/forward")
@login_required
def api_forward(message_id):
    profile_id = _profile_id()
    data = _json_or_form()
    target_thread_id = data.get("target_thread_id") or data.get("thread_id")
    source = _message_thread(message_id)
    if not profile_id or not source or not target_thread_id:
        return jsonify({"ok": False, "error": "message_not_found"}), 404
    if not can_access_thread(profile_id, source["thread_id"]) or not can_access_thread(profile_id, target_thread_id):
        return jsonify({"ok": False, "error": "thread_not_found"}), 404
    original = fast_query(
        "SELECT body, media_url, media_type FROM chain_messages WHERE id = %s LIMIT 1",
        (message_id,),
        default=[],
    )
    body = (original[0] or {}).get("body") if original else ""
    from services.messaging_engine import send_message
    result = send_message(target_thread_id, profile_id, body=body or "", client_message_id=data.get("client_temp_id"), is_forwarded=True)
    new_id = result.get("message_id") or result.get("id")
    if new_id:
        write_query("UPDATE chain_messages SET forwarded_from_message_id = %s WHERE id = %s", (message_id, new_id))
    return jsonify({"ok": True, "message": result, "forwarded_from_message_id": message_id})


@messaging_api_bp.post("/upload")
@login_required
def api_upload():
    profile_id = _profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    file_obj = request.files.get("file") or request.files.get("media")
    result = upload_message_media(file_obj, profile_id, voice=request.form.get("media_type") == "voice")
    return jsonify(result), 200 if result.get("ok") else 400


@messaging_api_bp.post("/validate-upload")
@login_required
def api_validate_upload():
    file_obj = request.files.get("file") or request.files.get("media")
    result = validate_message_attachment(file_obj)
    return jsonify(result), 200 if result.get("ok") else 400


@messaging_api_bp.get("/unread-count")
@login_required
def api_unread_count():
    profile_id = _profile_id()
    if not profile_id:
        return jsonify({"ok": True, "unread_count": 0})
    return jsonify({"ok": True, "unread_count": unread_count(profile_id)})


@messaging_api_bp.post("/group/create")
@login_required
def api_group_create():
    profile_id = _profile_id()
    data = _json_or_form()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    result = create_group(profile_id, data.get("title") or data.get("name"), data.get("member_ids") or [])
    return jsonify(result)


@messaging_api_bp.post("/group/<thread_id>/members/add")
@login_required
def api_group_member_add(thread_id):
    profile_id = _profile_id()
    data = _json_or_form()
    result = add_group_member(thread_id, profile_id, data.get("member_id") or data.get("profile_id"))
    return jsonify(result), 200 if result.get("ok") else 404


@messaging_api_bp.post("/group/<thread_id>/members/remove")
@login_required
def api_group_member_remove(thread_id):
    profile_id = _profile_id()
    data = _json_or_form()
    result = remove_group_member(thread_id, profile_id, data.get("member_id") or data.get("profile_id"))
    return jsonify(result), 200 if result.get("ok") else 404


@messaging_api_bp.post("/group/<thread_id>/leave")
@login_required
def api_group_leave(thread_id):
    profile_id = _profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    return jsonify(leave_group(thread_id, profile_id))
