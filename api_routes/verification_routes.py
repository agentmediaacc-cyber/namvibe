"""Full identity verification API routes — multi-step wizard flow."""
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from services.profile_service import get_current_profile
from api_routes.profile_routes import login_required
from services.verification_service import (
    COUNTRIES, DOCUMENT_TYPES,
    get_or_create_verification_request, save_step_country, save_step_document_type,
    save_step_upload, save_step_selfie, save_step_auto_checks,
    get_my_verification, get_profile_verification_status,
)

verification_bp = Blueprint("verification", __name__, url_prefix="/verification")


@verification_bp.route("/")
def index_redirect():
    return redirect(url_for("verification.center"))

@verification_bp.route("/center")
@login_required
def center():
    profile = get_current_profile()
    status = get_profile_verification_status(profile["id"])
    my_req = get_my_verification(profile["id"])
    return render_template(
        "verification/center.html",
        profile=profile,
        status=status,
        request=my_req,
        countries=COUNTRIES,
        doc_types=DOCUMENT_TYPES,
    )


@verification_bp.route("/api/status")
@login_required
def api_status():
    profile = get_current_profile()
    status = get_profile_verification_status(profile["id"])
    my_req = get_my_verification(profile["id"])
    return jsonify({"ok": True, "status": status, "request": my_req})


@verification_bp.route("/api/step/country", methods=["POST"])
@login_required
def api_step_country():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    country = data.get("country")
    if not country:
        return jsonify({"ok": False, "error": "Country is required"}), 400
    result = save_step_country(profile["id"], country)
    return jsonify(result)


@verification_bp.route("/api/step/document-type", methods=["POST"])
@login_required
def api_step_document_type():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    doc_type = data.get("document_type")
    if not doc_type:
        return jsonify({"ok": False, "error": "Document type is required"}), 400
    result = save_step_document_type(profile["id"], doc_type)
    return jsonify(result)


@verification_bp.route("/api/step/upload", methods=["POST"])
@login_required
def api_step_upload():
    profile = get_current_profile()
    front_url = request.form.get("front_url")
    back_url = request.form.get("back_url")
    if not front_url:
        return jsonify({"ok": False, "error": "Front image is required"}), 400
    result = save_step_upload(profile["id"], front_url, back_url)
    return jsonify(result)


@verification_bp.route("/api/step/selfie", methods=["POST"])
@login_required
def api_step_selfie():
    profile = get_current_profile()
    selfie_url = request.form.get("selfie_url")
    liveness = request.form.get("liveness_data")
    import json
    liveness_data = json.loads(liveness) if liveness else {}
    if not selfie_url:
        return jsonify({"ok": False, "error": "Selfie is required"}), 400
    result = save_step_selfie(profile["id"], selfie_url, liveness_data)
    return jsonify(result)


@verification_bp.route("/api/step/submit", methods=["POST"])
@login_required
def api_step_submit():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    checks = data.get("auto_checks", {})
    risk = data.get("risk_indicators", [])
    if not checks:
        checks = {
            "expiry_valid": True,
            "format_valid": True,
            "name_consistent": True,
            "dob_match": True,
            "security_features": True,
            "duplicate_doc": False,
            "duplicate_face": False,
            "blacklist": False,
        }
    result = save_step_auto_checks(profile["id"], checks, risk)
    return jsonify(result)


@verification_bp.route("/api/acceptable-docs")
@login_required
def api_acceptable_docs():
    country = request.args.get("country")
    from services.verification_service import get_acceptable_docs
    docs, requires_back = get_acceptable_docs(country or "")
    return jsonify({"ok": True, "docs": docs, "requires_back_photo": requires_back})
