from flask import Blueprint, request, jsonify
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.moderation_engine import report_entity, block_profile, mute_profile
from services.moderation_service import create_report, get_reports, restrict_user
from services.blocking_service import block_user, unblock_user, get_blocked_ids
from services.trust_score_service import get_trust_summary
from services.rate_limit_service import limiter, user_or_ip_key
from services.neon_service import fast_query

safety_bp = Blueprint("safety", __name__, url_prefix="/api")

# --- Existing routes preserved under /api/moderation/* ---

@safety_bp.route("/moderation/report", methods=["POST"])
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


@safety_bp.route("/moderation/block", methods=["POST"])
@login_required
def api_block():
    profile = get_current_profile()
    target_id = request.form.get("target_id")
    if block_profile(profile['id'], target_id):
        return jsonify({"success": True}), 200
    return jsonify({"error": "Failed to block user"}), 400


@safety_bp.route("/moderation/mute", methods=["POST"])
@login_required
def api_mute():
    profile = get_current_profile()
    target_id = request.form.get("target_id")
    if mute_profile(profile['id'], target_id):
        return jsonify({"success": True}), 200
    return jsonify({"error": "Failed to mute user"}), 400


# --- Report routes ---

@safety_bp.route("/report/content", methods=["POST"])
@login_required
@limiter.limit("10/hour", key_func=user_or_ip_key)
def api_report_content():
    profile = get_current_profile()
    data = request.json or {}
    content_type = data.get("content_type")
    content_id = data.get("content_id")
    reported_profile_id = data.get("reported_profile_id")
    reason = data.get("reason")
    details = data.get("details")

    valid_types = ("post", "reel", "story", "comment", "message", "call")
    if not content_type or content_type not in valid_types:
        return jsonify({"error": f"Invalid content_type, must be one of {valid_types}"}), 400
    if not reason or not reason.strip():
        return jsonify({"error": "Reason is required"}), 400
    if reported_profile_id == profile["id"]:
        return jsonify({"error": "Cannot report yourself"}), 400

    result = create_report(
        reporter_profile_id=profile["id"],
        reported_profile_id=reported_profile_id,
        content_type=content_type,
        content_id=content_id,
        reason=reason,
        details=details
    )
    if result.get("ok"):
        return jsonify({"success": True, "report": result["report"]}), 200
    return jsonify({"error": "Failed to create report"}), 500


@safety_bp.route("/report/profile", methods=["POST"])
@login_required
@limiter.limit("10/hour", key_func=user_or_ip_key)
def api_report_profile():
    profile = get_current_profile()
    data = request.json or {}
    reported_profile_id = data.get("reported_profile_id")
    reason = data.get("reason")
    details = data.get("details")

    if not reported_profile_id:
        return jsonify({"error": "reported_profile_id is required"}), 400
    if not reason or not reason.strip():
        return jsonify({"error": "Reason is required"}), 400
    if reported_profile_id == profile["id"]:
        return jsonify({"error": "Cannot report yourself"}), 400

    result = create_report(
        reporter_profile_id=profile["id"],
        reported_profile_id=reported_profile_id,
        content_type="profile",
        reason=reason,
        details=details
    )
    if result.get("ok"):
        return jsonify({"success": True, "report": result["report"]}), 200
    return jsonify({"error": "Failed to create report"}), 500


@safety_bp.route("/report/message", methods=["POST"])
@login_required
@limiter.limit("10/hour", key_func=user_or_ip_key)
def api_report_message():
    profile = get_current_profile()
    data = request.json or {}
    content_id = data.get("content_id")
    reported_profile_id = data.get("reported_profile_id")
    reason = data.get("reason")
    details = data.get("details")

    if not content_id:
        return jsonify({"error": "content_id (message id) is required"}), 400
    if not reason or not reason.strip():
        return jsonify({"error": "Reason is required"}), 400
    if reported_profile_id == profile["id"]:
        return jsonify({"error": "Cannot report yourself"}), 400

    result = create_report(
        reporter_profile_id=profile["id"],
        reported_profile_id=reported_profile_id,
        content_type="message",
        content_id=content_id,
        reason=reason,
        details=details
    )
    if result.get("ok"):
        return jsonify({"success": True, "report": result["report"]}), 200
    return jsonify({"error": "Failed to create report"}), 500


@safety_bp.route("/report/call", methods=["POST"])
@login_required
@limiter.limit("10/hour", key_func=user_or_ip_key)
def api_report_call():
    profile = get_current_profile()
    data = request.json or {}
    room_id = data.get("room_id")
    reported_profile_id = data.get("reported_profile_id")
    reason = data.get("reason")
    details = data.get("details")

    if not room_id:
        return jsonify({"error": "room_id is required"}), 400
    if not reason or not reason.strip():
        return jsonify({"error": "Reason is required"}), 400
    if reported_profile_id == profile["id"]:
        return jsonify({"error": "Cannot report yourself"}), 400

    result = create_report(
        reporter_profile_id=profile["id"],
        reported_profile_id=reported_profile_id,
        content_type="call",
        content_id=room_id,
        reason=reason,
        details=details
    )
    if result.get("ok"):
        return jsonify({"success": True, "report": result["report"]}), 200
    return jsonify({"error": "Failed to create report"}), 500


# --- Block routes ---

@safety_bp.route("/block/list", methods=["GET"])
@login_required
def api_block_list():
    profile = get_current_profile()
    blocked_ids = get_blocked_ids(profile["id"])
    return jsonify({"ok": True, "blocked": blocked_ids}), 200


@safety_bp.route("/block/<profile_id>", methods=["POST"])
@login_required
def api_block_user(profile_id):
    profile = get_current_profile()
    result = block_user(profile["id"], profile_id)
    if result.get("ok"):
        return jsonify({"success": True}), 200
    return jsonify({"error": result.get("error", "Failed to block user")}), 400


@safety_bp.route("/block/<profile_id>", methods=["DELETE"])
@login_required
def api_unblock_user(profile_id):
    profile = get_current_profile()
    result = unblock_user(profile["id"], profile_id)
    if result.get("ok"):
        return jsonify({"success": True}), 200
    return jsonify({"error": result.get("error", "Failed to unblock user")}), 400


# --- Restrict routes ---

@safety_bp.route("/restrict/list", methods=["GET"])
@login_required
def api_restrict_list():
    profile = get_current_profile()
    rows = fast_query(
        "SELECT restricted_profile_id FROM chain_restricted_users WHERE restricter_profile_id = %s",
        (profile["id"],), default=[]
    )
    restricted_ids = [str(r["restricted_profile_id"]) for r in rows if r.get("restricted_profile_id")]
    return jsonify({"ok": True, "restricted": restricted_ids}), 200


@safety_bp.route("/restrict/<profile_id>", methods=["POST"])
@login_required
def api_restrict_user(profile_id):
    profile = get_current_profile()
    if profile_id == profile["id"]:
        return jsonify({"error": "Cannot restrict yourself"}), 400
    result = restrict_user(profile_id, reason="Restricted by admin", moderator_profile_id=profile["id"])
    if result.get("ok"):
        return jsonify({"success": True}), 200
    return jsonify({"error": "Failed to restrict user"}), 500


# --- Trust routes ---

@safety_bp.route("/trust/summary", methods=["GET"])
@login_required
def api_trust_summary():
    profile = get_current_profile()
    summary = get_trust_summary(profile["id"])
    return jsonify(summary), 200


# --- Safety summary routes ---

@safety_bp.route("/safety/reports", methods=["GET"])
@login_required
def api_safety_reports():
    profile = get_current_profile()
    reports = get_reports(profile_id=profile["id"])
    return jsonify({"ok": True, "reports": reports}), 200


@safety_bp.route("/safety/blocked", methods=["GET"])
@login_required
def api_safety_blocked():
    profile = get_current_profile()
    blocked_ids = get_blocked_ids(profile["id"])
    return jsonify({"ok": True, "blocked": blocked_ids}), 200


@safety_bp.route("/safety/restricted", methods=["GET"])
@login_required
def api_safety_restricted():
    profile = get_current_profile()
    rows = fast_query(
        "SELECT restricted_profile_id FROM chain_restricted_users WHERE restricter_profile_id = %s",
        (profile["id"],), default=[]
    )
    restricted_ids = [str(r["restricted_profile_id"]) for r in rows if r.get("restricted_profile_id")]
    return jsonify({"ok": True, "restricted": restricted_ids}), 200

# Backward-compatible export expected by app.py.
# Use a unique Flask blueprint object to avoid duplicate blueprint-name registration.
moderation_bp = Blueprint("moderation", __name__, url_prefix="/api")
