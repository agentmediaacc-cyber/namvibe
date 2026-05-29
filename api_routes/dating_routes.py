from flask import Blueprint, render_template
from api_routes.profile_routes import login_required
from services.matching_service import get_discover_profiles

dating_bp = Blueprint("dating", __name__, url_prefix="/dating")

@dating_bp.route("/discover")
@login_required
def discover():
    profiles, current = get_discover_profiles()
    return render_template("dating/discover.html", items=profiles, current=current)
