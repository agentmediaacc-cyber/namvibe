from flask import Blueprint, jsonify, request, session, render_template

from api_routes.profile_routes import login_required
from services.admin_auth_service import require_admin
from services.profile_service import get_current_profile
from services.trust_score_service import get_trust_summary
from services.moderation_service import (
    create_report, get_reports, resolve_report, get_moderation_queue,
    assign_moderation_item, review_moderation_item, take_moderation_action,
    warn_user, restrict_user, unrestrict_user,
)
from services.creator_verification_service import (
    submit_verification_request, get_creator_verification_status,
    approve_creator_verification, reject_creator_verification, list_verification_requests,
)
from services.fraud_detection_service import get_fraud_summary
from services.spam_detection_service import get_spam_summary
from services.safety_rate_limit_service import check_action_rate_limit

safety_bp = Blueprint("safety", __name__)


def _profile_id():
    if session.get("profile_id"):
        return session.get("profile_id")
    profile = get_current_profile() or {}
    return profile.get("id")


def _admin_id():
    return session.get("profile_id") or session.get("auth_user_id")


@safety_bp.route("/safety/trust")
@login_required
def trust_page():
    return render_template("safety/trust_summary.html")


@safety_bp.route("/safety/report")
@login_required
def report_page():
    return render_template("safety/report.html")


@safety_bp.route("/safety/creator-verification")
@login_required
def creator_verification_page():
    return render_template("safety/creator_verification.html")


@safety_bp.route("/admin/safety")
@require_admin
def admin_safety_dashboard():
    return render_template("admin/safety_dashboard.html")


@safety_bp.route("/admin/safety/moderation-queue")
@require_admin
def admin_moderation_queue_page():
    return render_template("admin/moderation_queue.html")


@safety_bp.route("/admin/safety/fraud-events")
@require_admin
def admin_fraud_events_page():
    return render_template("admin/fraud_events.html")


@safety_bp.route("/admin/safety/spam-events")
@require_admin
def admin_spam_events_page():
    return render_template("admin/spam_events.html")


@safety_bp.route("/admin/safety/creator-verification")
@require_admin
def admin_creator_verification_page():
    return render_template("admin/creator_verification.html")


@safety_bp.route("/safety/api/report", methods=["POST"])
@login_required
def api_report():
    pid = _profile_id()
    rate = check_action_rate_limit(pid, "report")
    if rate.get("blocked"):
        return jsonify({"ok": False, "error": "rate_limited"}), 429
    data = request.json or request.form or {}
    result = create_report(
        pid,
        reported_profile_id=data.get("reported_profile_id"),
        content_type=data.get("content_type"),
        content_id=data.get("content_id"),
        reason=data.get("reason", "other"),
        details=data.get("details"),
        severity=data.get("severity", "medium"),
    )
    return jsonify(result), 200


@safety_bp.route("/safety/api/my-reports")
@login_required
def api_my_reports():
    return jsonify({"ok": True, "reports": get_reports(profile_id=_profile_id())}), 200


@safety_bp.route("/safety/api/trust-summary")
@login_required
def api_trust_summary():
    return jsonify(get_trust_summary(_profile_id())), 200


@safety_bp.route("/safety/api/creator-verification/request", methods=["POST"])
@login_required
def api_creator_verification_request():
    pid = _profile_id()
    rate = check_action_rate_limit(pid, "creator_verification")
    if rate.get("blocked"):
        return jsonify({"ok": False, "error": "rate_limited"}), 429
    return jsonify(submit_verification_request(pid, request.json or {})), 200


@safety_bp.route("/safety/api/creator-verification/status")
@login_required
def api_creator_verification_status():
    return jsonify(get_creator_verification_status(_profile_id())), 200


@safety_bp.route("/admin/safety/api/reports")
@require_admin
def admin_reports():
    return jsonify({"ok": True, "reports": get_reports(status=request.args.get("status"))}), 200


@safety_bp.route("/admin/safety/api/reports/<report_id>/resolve", methods=["POST"])
@require_admin
def admin_resolve_report(report_id):
    data = request.json or {}
    return jsonify(resolve_report(report_id, _admin_id(), data.get("status", "resolved"), data.get("resolution_note"))), 200


@safety_bp.route("/admin/safety/api/moderation-queue")
@require_admin
def admin_queue():
    return jsonify({"ok": True, "queue": get_moderation_queue(status=request.args.get("status", "pending"))}), 200


@safety_bp.route("/admin/safety/api/moderation-queue/<item_id>/assign", methods=["POST"])
@require_admin
def admin_assign_queue(item_id):
    return jsonify(assign_moderation_item(item_id, _admin_id())), 200


@safety_bp.route("/admin/safety/api/moderation-queue/<item_id>/review", methods=["POST"])
@require_admin
def admin_review_queue(item_id):
    data = request.json or {}
    return jsonify(review_moderation_item(item_id, _admin_id(), data.get("status", "reviewed"), data.get("note"))), 200


@safety_bp.route("/admin/safety/api/actions/warn", methods=["POST"])
@require_admin
def admin_warn():
    data = request.json or {}
    return jsonify(warn_user(data.get("profile_id"), data.get("reason", ""), _admin_id())), 200


@safety_bp.route("/admin/safety/api/actions/restrict", methods=["POST"])
@require_admin
def admin_restrict():
    data = request.json or {}
    return jsonify(restrict_user(data.get("profile_id"), data.get("reason", ""), data.get("duration_minutes"), _admin_id())), 200


@safety_bp.route("/admin/safety/api/actions/unrestrict", methods=["POST"])
@require_admin
def admin_unrestrict():
    data = request.json or {}
    return jsonify(unrestrict_user(data.get("profile_id"), _admin_id(), data.get("reason", ""))), 200


@safety_bp.route("/admin/safety/api/fraud-events")
@require_admin
def admin_fraud_events():
    return jsonify(get_fraud_summary()), 200


@safety_bp.route("/admin/safety/api/spam-events")
@require_admin
def admin_spam_events():
    return jsonify(get_spam_summary()), 200


@safety_bp.route("/admin/safety/api/trust-scores")
@require_admin
def admin_trust_scores():
    return jsonify({"ok": True, "trust_scores": []}), 200


@safety_bp.route("/admin/safety/api/creator-verification")
@require_admin
def admin_creator_verification():
    return jsonify({"ok": True, "requests": list_verification_requests(status=request.args.get("status"))}), 200


@safety_bp.route("/admin/safety/api/creator-verification/<request_id>/approve", methods=["POST"])
@require_admin
def admin_approve_verification(request_id):
    data = request.json or {}
    return jsonify(approve_creator_verification(request_id, _admin_id(), data.get("note"))), 200


@safety_bp.route("/admin/safety/api/creator-verification/<request_id>/reject", methods=["POST"])
@require_admin
def admin_reject_verification(request_id):
    data = request.json or {}
    return jsonify(reject_creator_verification(request_id, _admin_id(), data.get("note"))), 200


@safety_bp.route("/admin/safety/api/actions/moderate", methods=["POST"])
@require_admin
def admin_take_action():
    data = request.json or {}
    return jsonify(take_moderation_action(
        data.get("action_type", "note"),
        target_profile_id=data.get("target_profile_id"),
        moderator_profile_id=_admin_id(),
        content_type=data.get("content_type"),
        content_id=data.get("content_id"),
        reason=data.get("reason", ""),
        duration_minutes=data.get("duration_minutes"),
        metadata=data.get("metadata") or {},
    )), 200
