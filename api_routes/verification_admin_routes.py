"""Admin verification dashboard routes."""
from flask import Blueprint, jsonify, render_template, request
from services.admin_auth_service import require_admin, current_admin
from services.verification_request_service import (
    get_pending_verifications, get_all_verifications, get_verification_detail,
    approve_verification, reject_verification, request_more_info
)
from services.logging_service import log_info

verification_admin_bp = Blueprint("verification_admin", __name__, url_prefix="/admin/verifications")

@verification_admin_bp.route("/")
@require_admin
def dashboard():
    admin = current_admin()
    pending = get_pending_verifications(50)
    all_reqs = get_all_verifications(50)
    return render_template("admin/verifications.html", admin=admin, pending=pending, all=all_reqs)

@verification_admin_bp.route("/api/pending")
@require_admin
def api_pending():
    pending = get_pending_verifications(50)
    return jsonify({"ok": True, "pending": pending})

@verification_admin_bp.route("/api/all")
@require_admin
def api_all():
    all_reqs = get_all_verifications(50)
    return jsonify({"ok": True, "verifications": all_reqs})

@verification_admin_bp.route("/api/detail/<request_id>")
@require_admin
def api_detail(request_id):
    detail = get_verification_detail(request_id)
    if not detail:
        return jsonify({"ok": False, "error": "Not found."}), 404
    return jsonify({"ok": True, "verification": detail})

@verification_admin_bp.route("/api/approve", methods=["POST"])
@require_admin
def api_approve():
    admin = current_admin()
    data = request.get_json(silent=True) or request.form
    request_id = data.get("request_id")
    notes = data.get("notes", "")
    if not request_id:
        return jsonify({"ok": False, "error": "request_id required."}), 400
    result = approve_verification(request_id, admin["id"], notes=notes)
    log_info("admin_verification_approved", request_id=request_id, admin_id=admin["id"])
    return jsonify(result)

@verification_admin_bp.route("/api/reject", methods=["POST"])
@require_admin
def api_reject():
    admin = current_admin()
    data = request.get_json(silent=True) or request.form
    request_id = data.get("request_id")
    notes = data.get("notes", "")
    if not request_id:
        return jsonify({"ok": False, "error": "request_id required."}), 400
    result = reject_verification(request_id, admin["id"], notes=notes)
    log_info("admin_verification_rejected", request_id=request_id, admin_id=admin["id"])
    return jsonify(result)

@verification_admin_bp.route("/api/request-info", methods=["POST"])
@require_admin
def api_request_info():
    admin = current_admin()
    data = request.get_json(silent=True) or request.form
    request_id = data.get("request_id")
    notes = data.get("notes", "")
    if not request_id:
        return jsonify({"ok": False, "error": "request_id required."}), 400
    result = request_more_info(request_id, admin["id"], notes=notes)
    log_info("admin_verification_requested_info", request_id=request_id, admin_id=admin["id"])
    return jsonify(result)
