from flask import Blueprint, jsonify, request, session

from api_routes.profile_routes import login_required
from services.engagement_service import (
    add_comment,
    delete_comment,
    follow_profile,
    list_comments,
    record_share,
    record_view_count,
    react_to_live,
    react_to_post,
    toggle_like,
    toggle_save,
    unfollow_profile,
)
from services.ai.interaction_service import track_interaction_safe
from services.profile_service import get_current_profile


engagement_bp = Blueprint("engagement", __name__)


def _json_body():
    return request.get_json(silent=True) or {}


def _current_id():
    current = get_current_profile()
    if not current or not current.get("id"):
        return session.get("profile_id")
    return current["id"]


def _response(result, ok_status=200):
    if result.get("success"):
        return jsonify(result), ok_status
    return jsonify(result), 400


@engagement_bp.route("/api/social/<entity_type>/<entity_id>/like", methods=["POST"])
@login_required
def api_toggle_like(entity_type, entity_id):
    profile_id = _current_id()
    if not profile_id:
        return jsonify({"success": False, "error": "Profile setup incomplete."}), 400
    result = toggle_like(profile_id, entity_type, entity_id)
    if result.get("success") and entity_type in {"post", "reel"}:
        track_interaction_safe(
            profile_id,
            entity_type,
            entity_id,
            "like" if result.get("liked") else "unlike",
            source_surface="discover",
        )
    return _response(result)


@engagement_bp.route("/api/social/<entity_type>/<entity_id>/comments", methods=["GET"])
def api_comments(entity_type, entity_id):
    return jsonify({"success": True, "comments": list_comments(entity_type, entity_id, limit=10)}), 200


@engagement_bp.route("/api/social/<entity_type>/<entity_id>/comments", methods=["POST"])
@login_required
def api_add_comment(entity_type, entity_id):
    profile_id = _current_id()
    if not profile_id:
        return jsonify({"success": False, "error": "Profile setup incomplete."}), 400
    body = request.form.get("body") or _json_body().get("body")
    result = add_comment(profile_id, entity_type, entity_id, body)
    if result.get("success") and entity_type in {"post", "reel"}:
        track_interaction_safe(profile_id, entity_type, entity_id, "comment", source_surface="discover")
    return _response(result, ok_status=201)


@engagement_bp.route("/api/social/<entity_type>/comments/<comment_id>", methods=["DELETE", "POST"])
@login_required
def api_delete_comment(entity_type, comment_id):
    profile_id = _current_id()
    if not profile_id:
        return jsonify({"success": False, "error": "Profile setup incomplete."}), 400
    return _response(delete_comment(profile_id, entity_type, comment_id))


@engagement_bp.route("/api/social/profiles/<profile_id>/follow", methods=["POST"])
@login_required
def api_follow(profile_id):
    current_id = _current_id()
    if not current_id:
        return jsonify({"success": False, "error": "Profile setup incomplete."}), 400
    from services.follow_request_service import send_follow_request
    res = send_follow_request(current_id, profile_id)
    return jsonify(res)


@engagement_bp.route("/api/social/profiles/<profile_id>/unfollow", methods=["POST"])
@login_required
def api_unfollow(profile_id):
    current_id = _current_id()
    if not current_id:
        return jsonify({"success": False, "error": "Profile setup incomplete."}), 400
    result = unfollow_profile(current_id, profile_id)
    if result.get("success"):
        track_interaction_safe(current_id, "profile", profile_id, "unfollow", source_surface="discover")
    return _response(result)


@engagement_bp.route("/api/profile/<profile_id>/follow", methods=["POST", "DELETE"])
@login_required
def api_profile_follow(profile_id):
    """JS from namvibe_2026_home.js calls POST to follow, DELETE to unfollow."""
    current_id = _current_id()
    if not current_id:
        return jsonify({"success": False, "error": "Profile setup incomplete."}), 400
    if request.method == "DELETE":
        return _response(unfollow_profile(current_id, profile_id))
    from services.follow_request_service import send_follow_request
    res = send_follow_request(current_id, profile_id)
    return jsonify(res)


@engagement_bp.route("/api/social/<item_type>/<item_id>/save", methods=["POST"])
@login_required
def api_toggle_save(item_type, item_id):
    profile_id = _current_id()
    if not profile_id:
        return jsonify({"success": False, "error": "Profile setup incomplete."}), 400
    result = toggle_save(profile_id, item_type, item_id)
    if result.get("success") and item_type in {"post", "reel"}:
        track_interaction_safe(
            profile_id,
            item_type,
            item_id,
            "save" if result.get("saved") else "unsave",
            source_surface="discover",
        )
    return _response(result)


@engagement_bp.route("/api/media/<entity_id>/like", methods=["POST"])
@login_required
def api_media_like(entity_id):
    profile_id = _current_id()
    entity_type = request.args.get("type", "post")
    return _response(toggle_like(profile_id, entity_type, entity_id))


@engagement_bp.route("/api/media/<entity_id>/comment", methods=["POST"])
@login_required
def api_media_comment(entity_id):
    profile_id = _current_id()
    entity_type = request.args.get("type", "post")
    body = request.form.get("body") or _json_body().get("body")
    return _response(add_comment(profile_id, entity_type, entity_id, body), ok_status=201)


@engagement_bp.route("/api/media/<entity_id>/share", methods=["POST"])
@login_required
def api_media_share(entity_id):
    profile_id = _current_id()
    entity_type = request.args.get("type", "post")
    result = record_share(profile_id, entity_type, entity_id)
    if result.get("success") and entity_type in {"post", "reel"}:
        track_interaction_safe(profile_id, entity_type, entity_id, "share", source_surface="discover")
    return _response(result)


@engagement_bp.route("/api/media/<entity_id>/view", methods=["POST"])
def api_media_view(entity_id):
    profile_id = _current_id()
    entity_type = request.args.get("type", "post")
    result = record_view_count(profile_id, entity_type, entity_id)
    if result.get("success") and profile_id and entity_type in {"post", "reel", "story"}:
        track_interaction_safe(profile_id, entity_type, entity_id, "view", source_surface="discover")
    return _response(result)


@engagement_bp.route("/follow/<profile_id>", methods=["POST"])
@login_required
def follow(profile_id):
    return api_follow(profile_id)


@engagement_bp.route("/unfollow/<profile_id>", methods=["POST"])
@login_required
def unfollow(profile_id):
    return api_unfollow(profile_id)


@engagement_bp.route("/posts/<post_id>/react", methods=["POST"])
@login_required
def post_react(post_id):
    profile_id = _current_id()
    if not profile_id:
        return jsonify({"success": False, "error": "Profile setup incomplete."}), 400
    return _response(react_to_post(profile_id, post_id, "like"))


@engagement_bp.route("/posts/<post_id>/comment", methods=["POST"])
@login_required
def post_comment(post_id):
    profile_id = _current_id()
    if not profile_id:
        return jsonify({"success": False, "error": "Profile setup incomplete."}), 400
    body = request.form.get("body") or _json_body().get("body")
    return _response(add_comment(profile_id, "post", post_id, body), ok_status=201)


@engagement_bp.route("/live/<room_id>/react", methods=["POST"])
@login_required
def live_react(room_id):
    profile_id = _current_id()
    if not profile_id:
        return jsonify({"success": False, "error": "Profile setup incomplete."}), 400
    return _response(react_to_live(room_id, profile_id, "like"))


@engagement_bp.route("/live/<room_id>/comment", methods=["POST"])
@login_required
def live_comment_route(room_id):
    profile_id = _current_id()
    if not profile_id:
        return jsonify({"success": False, "error": "Profile setup incomplete."}), 400
    body = request.form.get("body") or _json_body().get("body")
    return _response(add_comment(profile_id, "live_room", room_id, body), ok_status=201)


@engagement_bp.route("/save-item", methods=["POST"])
@login_required
def bookmark_item():
    profile_id = _current_id()
    if not profile_id:
        return jsonify({"success": False, "error": "Profile setup incomplete."}), 400
    data = _json_body()
    return _response(toggle_save(profile_id, data.get("item_type"), data.get("item_id")))
