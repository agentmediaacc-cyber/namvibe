from flask import Blueprint, jsonify
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.blocking_service import block_user, unblock_user, get_blocked_ids

block_bp = Blueprint("block", __name__, url_prefix="/api")


@block_bp.route("/blocked", methods=["GET"])
@login_required
def api_blocked_list():
    profile = get_current_profile()
    blocked_ids = get_blocked_ids(profile["id"])
    return jsonify({"ok": True, "blocked": blocked_ids}), 200


@block_bp.route("/blocked/<profile_id>", methods=["POST"])
@login_required
def api_blocked_add(profile_id):
    profile = get_current_profile()
    result = block_user(profile["id"], profile_id)
    if result.get("ok"):
        return jsonify({"success": True}), 200
    return jsonify({"error": result.get("error", "Failed to block")}), 400


@block_bp.route("/blocked/<profile_id>", methods=["DELETE"])
@login_required
def api_blocked_remove(profile_id):
    profile = get_current_profile()
    result = unblock_user(profile["id"], profile_id)
    if result.get("ok"):
        return jsonify({"success": True}), 200
    return jsonify({"error": result.get("error", "Failed to unblock")}), 400
