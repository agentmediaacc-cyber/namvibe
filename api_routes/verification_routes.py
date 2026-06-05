from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from services.profile_service import get_current_profile
from services.verification_engine import submit_verification, get_verification_status
from api_routes.profile_routes import login_required

verification_bp = Blueprint("verification", __name__, url_prefix="/verification")

@verification_bp.route("/")
@login_required
def index():
    profile = get_current_profile()
    status = get_verification_status(profile['id'])
    return render_template("verification/index.html", profile=profile, status=status)

@verification_bp.route("/", methods=["POST"])
@login_required
def submit():
    profile = get_current_profile()
    file = request.files.get("document")
    request_type = request.form.get("request_type", "creator")
    notes = request.form.get("notes")

    request_id, error = submit_verification(profile['id'], file=file, request_type=request_type, notes=notes)
    if error:
        return render_template("verification/index.html", profile=profile, error=error)
    
    return redirect(url_for('verification.index'))

@verification_bp.route("/api/verification/status")
@login_required
def api_status():
    profile = get_current_profile()
    status = get_verification_status(profile['id'])
    return jsonify(status), 200
