from flask import Blueprint, render_template, request, jsonify
from services.profile_service import get_current_profile
from services.feed_engine import build_feed, trending_feed
from services.rate_limit_service import limiter
from services.viral_feed_service import (
    score_for_you_posts, score_following_feed,
    score_trending_feed, score_nearby_feed,
)
from services.feed_cursor_service import encode_cursor

feed_bp = Blueprint("feed", __name__)


@feed_bp.route("/feed/")
def index_legacy():
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


@feed_bp.route("/api/feed/check")
def api_feed_check():
    return jsonify({
        "ok": True,
        "has_new": False,
        "checked": False,
    }), 200


# =========== PHASE 93: Viral Feed API Endpoints ===========

@feed_bp.route("/api/feed/for-you")
def api_feed_for_you():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    cursor = request.args.get("cursor")
    limit = min(int(request.args.get("limit", 20)), 50)
    posts, next_cursor = score_for_you_posts(
        profile_id=profile_id, cursor=cursor, limit=limit
    )
    return jsonify({
        "posts": posts,
        "next_cursor": encode_cursor(next_cursor) if next_cursor else None,
        "has_more": bool(next_cursor),
    })


@feed_bp.route("/api/feed/following")
def api_feed_following():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    if not profile_id:
        return jsonify({"posts": [], "next_cursor": None, "has_more": False})
    cursor = request.args.get("cursor")
    limit = min(int(request.args.get("limit", 20)), 50)
    posts, next_cursor = score_following_feed(
        profile_id=profile_id, cursor=cursor, limit=limit
    )
    return jsonify({
        "posts": posts,
        "next_cursor": encode_cursor(next_cursor) if next_cursor else None,
        "has_more": bool(next_cursor),
    })


@feed_bp.route("/api/feed/trending")
def api_feed_trending():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    cursor = request.args.get("cursor")
    limit = min(int(request.args.get("limit", 20)), 50)
    posts, next_cursor = score_trending_feed(
        profile_id=profile_id, cursor=cursor, limit=limit
    )
    return jsonify({
        "posts": posts,
        "next_cursor": encode_cursor(next_cursor) if next_cursor else None,
        "has_more": bool(next_cursor),
    })


@feed_bp.route("/api/feed/nearby")
def api_feed_nearby():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    cursor = request.args.get("cursor")
    limit = min(int(request.args.get("limit", 20)), 50)
    posts, next_cursor = score_nearby_feed(
        profile_id=profile_id, cursor=cursor, limit=limit
    )
    return jsonify({
        "posts": posts,
        "next_cursor": encode_cursor(next_cursor) if next_cursor else None,
        "has_more": bool(next_cursor),
    })
