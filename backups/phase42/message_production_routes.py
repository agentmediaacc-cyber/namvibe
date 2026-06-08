from flask import Blueprint, jsonify, request, session
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.message_delivery_service import (
    ensure_message_tables,
    get_thread_messages,
    send_message,
    unread_count,
    get_unread_counts_per_thread,
    mark_delivered_for_online_user,
    mark_thread_seen,
    react_to_message,
    remove_reaction,
    get_reactions,
    edit_message,
    delete_message_for_everyone,
    update_presence,
    get_presence,
    set_offline,
)

message_production_bp = Blueprint("message_production", __name__, url_prefix="/messages/api")

@message_production_bp.route("/thread/<thread_id>", methods=["GET"])
@login_required
def api_thread(thread_id):
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "Login required"}), 401
    rows = get_thread_messages(thread_id, profile["id"])
    return jsonify({"ok": True, "thread_id": thread_id, "messages": rows})

@message_production_bp.route("/thread/<thread_id>/send", methods=["POST"])
@login_required
def api_send(thread_id):
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "Login required"}), 401
    data = request.get_json(silent=True) or request.form.to_dict()
    body = (data.get("body") or "").strip()
    if not body and not data.get("media_url"):
        return jsonify({"ok": False, "error": "Message is empty"}), 400
    msg = send_message(
        thread_id=thread_id,
        sender_profile_id=profile["id"],
        body=body,
        message_type=data.get("message_type", "text"),
        media_url=data.get("media_url"),
        reply_to_message_id=data.get("reply_to_message_id"),
    )
    return jsonify({"ok": True, "message": msg})

@message_production_bp.route("/thread/<thread_id>/voice-note", methods=["POST"])
@login_required
def api_voice(thread_id):
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "Login required"}), 401
    seconds = request.form.get("seconds") or "0"
    msg = send_message(
        thread_id=thread_id,
        sender_profile_id=profile["id"],
        body=f"🎙 Voice note • {seconds}s",
        message_type="voice_note",
        voice_duration_seconds=int(float(seconds or 0))
    )
    return jsonify({"ok": True, "message": msg})

@message_production_bp.route("/unread-count", methods=["GET"])
@login_required
def api_unread():
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": True, "unread": 0})
    if profile.get("profile_fallback"):
        return jsonify({"ok": True, "unread": 0})
    return jsonify({"ok": True, "unread": unread_count(profile["id"])})

@message_production_bp.route("/unread-counts", methods=["GET"])
@login_required
def api_unread_counts():
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": True, "counts": {}})
    counts = get_unread_counts_per_thread(profile["id"])
    return jsonify({"ok": True, "counts": counts})

@message_production_bp.route("/online", methods=["POST"])
@login_required
def api_online():
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False}), 401
    if profile.get("profile_fallback"):
        return jsonify({"ok": True, "delivery": "skipped"})
    mark_delivered_for_online_user(profile["id"])
    update_presence(profile["id"], status="online")
    return jsonify({"ok": True, "delivery": "updated"})

@message_production_bp.route("/thread/<thread_id>/seen", methods=["POST"])
@login_required
def api_seen(thread_id):
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "Login required"}), 401
    ok = mark_thread_seen(thread_id, profile["id"])
    return jsonify({"ok": ok})

@message_production_bp.route("/message/<message_id>/react", methods=["POST"])
@login_required
def api_react(message_id):
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "Login required"}), 401
    data = request.get_json(silent=True) or {}
    reaction = data.get("reaction", "").strip()
    if not reaction:
        return jsonify({"ok": False, "error": "Reaction required"}), 400
    ok = react_to_message(message_id, profile["id"], reaction)
    if ok:
        reactions = get_reactions(message_id)
        return jsonify({"ok": True, "reactions": reactions})
    return jsonify({"ok": False, "error": "Failed to add reaction"}), 400

@message_production_bp.route("/message/<message_id>/unreact", methods=["POST"])
@login_required
def api_unreact(message_id):
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "Login required"}), 401
    remove_reaction(message_id, profile["id"])
    reactions = get_reactions(message_id)
    return jsonify({"ok": True, "reactions": reactions})

@message_production_bp.route("/message/<message_id>/reactions", methods=["GET"])
@login_required
def api_get_reactions(message_id):
    reactions = get_reactions(message_id)
    return jsonify({"ok": True, "reactions": reactions})

@message_production_bp.route("/message/<message_id>/edit", methods=["POST"])
@login_required
def api_edit(message_id):
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "Login required"}), 401
    data = request.get_json(silent=True) or {}
    new_body = (data.get("body") or "").strip()
    if not new_body:
        return jsonify({"ok": False, "error": "Body required"}), 400
    ok = edit_message(message_id, profile["id"], new_body)
    if ok:
        return jsonify({"ok": True, "message_id": message_id, "body": new_body, "edited": True})
    return jsonify({"ok": False, "error": "Cannot edit. Not your message or outside 15-min window"}), 400

@message_production_bp.route("/message/<message_id>/delete-everyone", methods=["POST"])
@login_required
def api_delete_everyone(message_id):
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "Login required"}), 401
    ok = delete_message_for_everyone(message_id, profile["id"])
    if ok:
        return jsonify({"ok": True, "message_id": message_id, "deleted": True})
    return jsonify({"ok": False, "error": "Cannot delete. Not your message or outside 24-hour window"}), 400

@message_production_bp.route("/presence/<profile_id>", methods=["GET"])
@login_required
def api_presence(profile_id):
    data = get_presence(profile_id)
    return jsonify({"ok": True, "presence": data})

@message_production_bp.route("/presence", methods=["POST"])
@login_required
def api_update_presence():
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "Login required"}), 401
    data = request.get_json(silent=True) or {}
    status = data.get("status", "online")
    device_type = data.get("device_type")
    update_presence(profile["id"], status=status, device_type=device_type)
    return jsonify({"ok": True, "status": status})

@message_production_bp.route("/presence/offline", methods=["POST"])
@login_required
def api_offline():
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False}), 401
    set_offline(profile["id"])
    return jsonify({"ok": True})
