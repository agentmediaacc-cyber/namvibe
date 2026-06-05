from flask import Blueprint, jsonify, request, session

from api_routes.profile_routes import login_required
from services.engagement_service import (
    add_comment,
    delete_comment,
    follow_profile,
    list_comments,
    react_to_live,
    react_to_post,
    toggle_like,
    toggle_save,
    unfollow_profile,
)
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
    return _response(toggle_like(profile_id, entity_type, entity_id))


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
    return _response(add_comment(profile_id, entity_type, entity_id, body), ok_status=201)


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
    return _response(follow_profile(current_id, profile_id))


@engagement_bp.route("/api/social/profiles/<profile_id>/unfollow", methods=["POST"])
@login_required
def api_unfollow(profile_id):
    current_id = _current_id()
    if not current_id:
        return jsonify({"success": False, "error": "Profile setup incomplete."}), 400
    return _response(unfollow_profile(current_id, profile_id))


@engagement_bp.route("/api/social/<item_type>/<item_id>/save", methods=["POST"])
@login_required
def api_toggle_save(item_type, item_id):
    profile_id = _current_id()
    if not profile_id:
        return jsonify({"success": False, "error": "Profile setup incomplete."}), 400
    return _response(toggle_save(profile_id, item_type, item_id))


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
