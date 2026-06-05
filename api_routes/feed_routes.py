from flask import Blueprint, render_template, request, jsonify
from services.profile_service import get_current_profile
from services.feed_engine import build_feed, trending_feed
from services.rate_limit_service import limiter

feed_bp = Blueprint("feed", __name__)

@feed_bp.route("/feed/")
def index():
    profile = get_current_profile()
    tab = request.args.get("tab", "for_you")
    limit = int(request.args.get("limit", 30))
    
    if tab == "following" and profile:
        feed = build_feed(profile_id=profile['id'], limit=limit, feed_type="following")
    elif tab == "trending":
        feed = build_feed(profile_id=profile['id'] if profile else None, limit=limit, feed_type="trending")
    else:
        feed = build_feed(profile_id=profile['id'] if profile else None, limit=limit, feed_type="explore")
        
    return render_template("feed/index.html", feed=feed, tab=tab, profile=profile)

@feed_bp.route("/api/feed")
@limiter.limit("120/minute")
def api_feed():
    profile = get_current_profile()
    tab = request.args.get("tab", "for_you")
    limit = int(request.args.get("limit", 30))
    
    feed = build_feed(profile_id=profile['id'] if profile else None, limit=limit, feed_type=tab)
    return jsonify(feed), 200
