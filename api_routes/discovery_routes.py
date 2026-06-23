import time

from flask import Blueprint, render_template, request, session, jsonify
from services.discovery_service import get_discovery_data, search_profiles
from services.profile_service import get_current_profile
from services.creator_ranking_service import get_trending_creators
from services.trending_service import get_trending_hashtags, get_trending_locations
from services.logging_service import log_info

discovery_bp = Blueprint("discovery", __name__, url_prefix="/discover")

@discovery_bp.route("/")
@discovery_bp.route("/<section>")
def section(section="recommended"):
    start = time.perf_counter()
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    query = request.args.get("q", "").strip()
    viewer = get_current_profile() if session.get("profile_id") else None
    viewer_id = viewer.get("id") if viewer else None
    
    # Handle search queries
    if query:
        data = search_profiles(query, viewer_id=viewer_id, limit=limit, offset=offset)
        data["section"] = section
        data["query"] = query
    else:
        data = get_discovery_data(section, viewer_id=viewer_id, limit=limit, offset=offset)
    
    response = render_template(
        "discover/index.html",
        viewer_id=viewer_id,
        **data
    )
    log_info("discover_page_total", duration_ms=round((time.perf_counter() - start) * 1000, 2), section=section, query=query or None)
    return response

@discovery_bp.route("/live")
def live_discovery():
    return section("live")

@discovery_bp.route("/members")
def members_discovery():
    return section("members")

@discovery_bp.route("/trending")
def trending_discovery():
    return section("trending")


# =========== PHASE 93: Trending APIs ===========

@discovery_bp.route("/api/discover/creators/trending")
def api_trending_creators():
    limit = min(int(request.args.get("limit", 20)), 50)
    offset = int(request.args.get("offset", 0))
    creators = get_trending_creators(limit=limit, offset=offset)
    return jsonify({"creators": creators})


@discovery_bp.route("/api/discover/hashtags/trending")
def api_trending_hashtags():
    limit = min(int(request.args.get("limit", 20)), 50)
    hashtags = get_trending_hashtags(limit=limit)
    return jsonify({"hashtags": hashtags})


@discovery_bp.route("/api/discover/locations/trending")
def api_trending_locations():
    limit = min(int(request.args.get("limit", 20)), 50)
    locations = get_trending_locations(limit=limit)
    return jsonify({"locations": locations})
