from flask import Blueprint, jsonify, request, session

from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.e2ee_service import (
    get_encryption_status,
    rotate_encryption_session,
    get_thread_encryption_status,
    get_group_encryption_status,
    rotate_group_encryption_key,
    ensure_encryption_session,
    create_group_encryption_key,
)

encryption_bp = Blueprint("encryption", __name__, url_prefix="/encryption")


@encryption_bp.route("/api/status", methods=["GET"])
@login_required
def api_encryption_status():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    status = get_encryption_status(profile["id"])
    return jsonify(status), 200


@encryption_bp.route("/api/rotate", methods=["POST"])
@login_required
def api_rotate_key():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    data = request.json or {}
    peer_profile_id = data.get("peer_profile_id")
    thread_id = data.get("thread_id")
    result = rotate_encryption_session(profile["id"], peer_profile_id=peer_profile_id, thread_id=thread_id)
    if result.get("ok"):
        return jsonify(result), 200
    return jsonify(result), 500


@encryption_bp.route("/api/thread/<thread_id>/status", methods=["GET"])
@login_required
def api_thread_encryption(thread_id):
    status = get_thread_encryption_status(thread_id)
    return jsonify(status), 200


@encryption_bp.route("/api/thread/<thread_id>/activate", methods=["POST"])
@login_required
def api_thread_rotate(thread_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    result = rotate_encryption_session(profile["id"], thread_id=thread_id)
    if result.get("ok"):
        extra = {"thread_id": thread_id}
        extra.update(result)
        return jsonify(extra), 200
    return jsonify(result), 500


@encryption_bp.route("/api/group/<group_id>/status", methods=["GET"])
@login_required
def api_group_encryption(group_id):
    status = get_group_encryption_status(group_id)
    return jsonify(status), 200


@encryption_bp.route("/api/group/<group_id>/rotate", methods=["POST"])
@login_required
def api_group_rotate(group_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    data = request.json or {}
    reason = data.get("reason", "manual")
    result = rotate_group_encryption_key(group_id=group_id, reason=reason)
    if result.get("ok"):
        extra = {"group_id": group_id}
        extra.update(result)
        return jsonify(extra), 200
    return jsonify(result), 500


@encryption_bp.route("/api/history", methods=["GET"])
@login_required
def api_encryption_history():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    from services.e2ee_service import get_encryption_status, is_encryption_enabled_for_thread
    status = get_encryption_status(profile["id"])
    return jsonify({"ok": True, "history": [], "status": status}), 200
