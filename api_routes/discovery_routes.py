from flask import Blueprint, render_template, request, session
from services.discovery_service import get_discovery_data
from services.profile_service import get_current_profile

discovery_bp = Blueprint("discovery", __name__, url_prefix="/discover")

@discovery_bp.route("/")
@discovery_bp.route("/<section>")
def section(section="recommended"):
    limit = request.args.get("limit", 50, type=int)
    viewer = get_current_profile() if session.get("profile_id") else None
    viewer_id = viewer.get("id") if viewer else None
    data = get_discovery_data(section, viewer_id=viewer_id, limit=limit)
    return render_template(
        "discover/index.html",
        viewer_id=viewer_id,
        **data
    )

@discovery_bp.route("/live")
def live_discovery():
    return section("live")

@discovery_bp.route("/members")
def members_discovery():
    return section("members")

@discovery_bp.route("/trending")
def trending_discovery():
    return section("trending")
