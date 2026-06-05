from flask import Blueprint, jsonify, request
from services.profile_service import get_current_profile
from services.feed_service import get_personalized_feed
from services.supabase_safe import safe_select
from api_routes.profile_routes import login_required

mobile_api_bp = Blueprint("mobile_api", __name__, url_prefix="/api/mobile/v1")

def _compact_profile(p):
    """Compact serializer for mobile payloads"""
    return {
        "id": p.get("id"),
        "u": p.get("username"),
        "n": p.get("full_name") or p.get("display_name"),
        "a": p.get("avatar_url"),
        "v": bool(p.get("is_verified")),
        "p": bool(p.get("is_premium"))
    }

@mobile_api_bp.route("/feed")
@login_required
def mobile_feed():
    current = get_current_profile()
    limit = request.args.get("limit", 20, type=int)
    feed = get_personalized_feed(current["id"], limit=limit)
    
    # Transform feed for mobile optimization
    compact_feed = []
    for item in feed:
        data = item["data"]
        compact_item = {
            "t": item["type"],
            "id": data.get("id"),
            "title": data.get("title") or data.get("caption"),
            "media": data.get("video_url") or data.get("media_url") or data.get("cover_url"),
            "creator": _compact_profile(data.get("creator", {})) if "creator" in data else None
        }
        if item["type"] == "live_room":
            compact_item["v"] = data.get("viewer_count", 0)
        compact_feed.append(compact_item)
        
    return jsonify({"feed": compact_feed})

@mobile_api_bp.route("/me")
@login_required
def mobile_me():
    current = get_current_profile()
    return jsonify({"profile": _compact_profile(current)})

@mobile_api_bp.route("/auth/status")
def mobile_auth_status():
    """Simple check for mobile app session validation"""
    current = get_current_profile()
    if current:
        return jsonify({"authenticated": True, "p_id": current["id"]})
    return jsonify({"authenticated": False}), 401

@mobile_api_bp.route("/reels")
@login_required
def mobile_reels():
    from services.reels_engine import list_reels
    limit = request.args.get("limit", 10, type=int)
    reels = list_reels(limit=limit)
    return jsonify({"reels": reels})

@mobile_api_bp.route("/stories")
@login_required
def mobile_stories():
    from services.status_service import get_active_statuses
    stories = get_active_statuses()
    return jsonify({"stories": stories})

@mobile_api_bp.route("/messages")
@login_required
def mobile_messages():
    from services.messaging_engine import list_threads
    current = get_current_profile()
    threads = list_threads(current["id"])
    return jsonify({"threads": threads})

@mobile_api_bp.route("/wallet")
@login_required
def mobile_wallet():
    from services.wallet_service import get_wallet_data
    current = get_current_profile()
    wallet = get_wallet_data(current["id"])
    return jsonify({"wallet": wallet})

@mobile_api_bp.route("/dating/discover")
@login_required
def mobile_dating():
    from services.matching_service import get_discover_profiles
    profiles, _ = get_discover_profiles(limit=20)
    return jsonify({"profiles": profiles})
