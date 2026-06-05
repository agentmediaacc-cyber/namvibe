from flask import Blueprint, request, jsonify
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.moderation_engine import report_entity, block_profile, mute_profile
from services.rate_limit_service import limiter, user_or_ip_key

moderation_bp = Blueprint("moderation", __name__, url_prefix="/api/moderation")

@moderation_bp.route("/report", methods=["POST"])
@login_required
@limiter.limit("20/hour", key_func=user_or_ip_key)
def api_report():
    profile = get_current_profile()
    data = request.form
    target_id = data.get("target_id")
    entity_type = data.get("entity_type")
    entity_id = data.get("entity_id")
    reason = data.get("reason")
    details = data.get("details")

    if not reason:
        return jsonify({"error": "Reason is required"}), 400

    report_id = report_entity(profile['id'], entity_type, entity_id, reason, details, target_profile_id=target_id)
    if report_id:
        return jsonify({"success": True, "report_id": report_id}), 200
    return jsonify({"error": "Failed to create report"}), 500

@moderation_bp.route("/block", methods=["POST"])
@login_required
def api_block():
    profile = get_current_profile()
    target_id = request.form.get("target_id")
    if block_profile(profile['id'], target_id):
        return jsonify({"success": True}), 200
    return jsonify({"error": "Failed to block user"}), 400

@moderation_bp.route("/mute", methods=["POST"])
@login_required
def api_mute():
    profile = get_current_profile()
    target_id = request.form.get("target_id")
    if mute_profile(profile['id'], target_id):
        return jsonify({"success": True}), 200
    return jsonify({"error": "Failed to mute user"}), 400
