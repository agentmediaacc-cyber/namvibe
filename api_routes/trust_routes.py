from flask import Blueprint, jsonify
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.trust_score_service import get_trust_summary

trust_bp = Blueprint("trust", __name__, url_prefix="/api")


@trust_bp.route("/trust/summary", methods=["GET"])
@login_required
def api_trust_summary():
    profile = get_current_profile()
    summary = get_trust_summary(profile["id"])
    return jsonify(summary), 200
