"""Phase 59 — Real Feed API + Follow + Like/Save/Share actions."""

from flask import Blueprint, jsonify, request, session
from services.profile_service import get_current_profile
from services.homepage_service import get_feed_tab
from services.engagement_service import follow_profile, unfollow_profile, toggle_like, toggle_save
from services.neon_service import fast_query, is_circuit_open
from api_routes.profile_routes import login_required

homepage_api_bp = Blueprint("homepage_api", __name__)


def _current_profile():
    profile = get_current_profile()
    if profile and profile.get("id"):
        return profile
    pid = session.get("profile_id")
    if pid:
        return {"id": pid}
    return None


def _json_ok(data, status=200):
    return jsonify({"ok": True, **data}), status


def _json_error(message, status=400):
    return jsonify({"ok": False, "error": message}), status


# ================================================================
# GET /api/home/feed — Tab-filtered feed with pagination
# ================================================================
@homepage_api_bp.route("/api/home/feed")
def api_feed():
    tab = request.args.get("tab", "for_you")
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    limit = 20

    profile = _current_profile()
    profile_id = profile.get("id") if profile else None

    try:
        items, has_more = get_feed_tab(profile_id=profile_id, tab=tab, page=page, limit=limit)
    except Exception:
        items, has_more = [], False

    return _json_ok({
        "tab": tab,
        "items": items,
        "page": page,
        "next_page": page + 1 if has_more else None,
        "has_more": has_more,
    })


# ================================================================
# POST /api/home/follow/<profile_id>
# ================================================================
@homepage_api_bp.route("/api/home/follow/<profile_id>", methods=["POST"])
@login_required
def api_follow(profile_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return _json_error("Not authenticated", 401)
    if str(profile["id"]) == str(profile_id):
        return _json_error("Cannot follow yourself")
    result = follow_profile(str(profile["id"]), str(profile_id))
    return _json_ok({"result": result})


# ================================================================
# POST /api/home/unfollow/<profile_id>
# ================================================================
@homepage_api_bp.route("/api/home/unfollow/<profile_id>", methods=["POST"])
@login_required
def api_unfollow(profile_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return _json_error("Not authenticated", 401)
    if str(profile["id"]) == str(profile_id):
        return _json_error("Cannot unfollow yourself")
    result = unfollow_profile(str(profile["id"]), str(profile_id))
    return _json_ok({"result": result})


# ================================================================
# POST /api/home/post/<post_id>/like
# ================================================================
@homepage_api_bp.route("/api/home/post/<post_id>/like", methods=["POST"])
@login_required
def api_like_post(post_id):
    profile = _current_profile()
    if not profile or not profile.get("id"):
        return _json_error("Not authenticated", 401)
    try:
        result = toggle_like(str(profile["id"]), "post", str(post_id))
        return _json_ok({"result": result})
    except Exception as e:
        return _json_error(str(e), 500)


# ================================================================
# POST /api/home/post/<post_id>/save
# ================================================================
@homepage_api_bp.route("/api/home/post/<post_id>/save", methods=["POST"])
@login_required
def api_save_post(post_id):
    profile = _current_profile()
    if not profile or not profile.get("id"):
        return _json_error("Not authenticated", 401)
    try:
        result = toggle_save(str(profile["id"]), "post", str(post_id))
        return _json_ok({"result": result})
    except Exception as e:
        return _json_error(str(e), 500)


# ================================================================
# POST /api/home/post/<post_id>/share
# ================================================================
@homepage_api_bp.route("/api/home/post/<post_id>/share", methods=["POST"])
@login_required
def api_share_post(post_id):
    profile = _current_profile()
    if not profile or not profile.get("id"):
        return _json_error("Not authenticated", 401)
    try:
        from services.engagement_service import _first
        post = _first("chain_posts", {"id": str(post_id)})
        new_count = (post.get("shares_count") or 0) + 1 if post else 1
        from services.supabase_safe import safe_update
        safe_update("chain_posts", {"shares_count": new_count}, {"id": str(post_id)})
        return _json_ok({"shares_count": new_count})
    except Exception as e:
        return _json_error(str(e), 500)
