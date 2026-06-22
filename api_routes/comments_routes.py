"""Unified comments API — Facebook-level nested comments for posts, reels, stories, live."""
from flask import Blueprint, request, jsonify
from services.profile_service import get_current_profile
from services.comments_service import (
    get_comments, get_replies_for_comments, add_comment,
    react_to_comment, pin_comment, edit_comment, delete_comment
)

comments_bp = Blueprint("comments", __name__, url_prefix="/api/comments")

@comments_bp.route("/<content_type>/<content_id>", methods=["GET"])
def api_list(content_type, content_id):
    limit = request.args.get("limit", 30, type=int)
    comments = get_comments(content_type, content_id, limit=limit)
    replies_by_parent = get_replies_for_comments([c["id"] for c in comments], limit_per_comment=5)
    result = []
    for c in comments:
        replies = replies_by_parent.get(str(c["id"]), [])
        result.append({
            "id": c["id"],
            "body": c["body"],
            "user_id": c["user_id"],
            "username": c.get("username"),
            "avatar_url": c.get("avatar_url"),
            "is_verified": c.get("is_verified", False),
            "is_pinned": c.get("is_pinned", False),
            "media_url": c.get("media_url"),
            "gif_url": c.get("gif_url"),
            "reaction_count": c.get("reaction_count", 0),
            "created_at": str(c.get("created_at", "")),
            "replies": [{
                "id": r["id"],
                "body": r["body"],
                "user_id": r["user_id"],
                "username": r.get("username"),
                "avatar_url": r.get("avatar_url"),
                "is_verified": r.get("is_verified", False),
                "created_at": str(r.get("created_at", "")),
            } for r in replies],
        })
    return jsonify({"comments": result}), 200

@comments_bp.route("/<content_type>/<content_id>", methods=["POST"])
def api_add(content_type, content_id):
    profile = get_current_profile()
    user_id = (profile or {}).get("id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    body = data.get("body", "")
    media_url = data.get("media_url")
    gif_url = data.get("gif_url")
    parent_id = data.get("parent_id")
    comment_id = add_comment(content_type, content_id, user_id, body, media_url, gif_url, parent_id)
    if comment_id:
        return jsonify({"success": True, "comment_id": comment_id}), 201
    return jsonify({"error": "Could not add comment"}), 400

@comments_bp.route("/<comment_id>/reply", methods=["POST"])
def api_reply(comment_id):
    profile = get_current_profile()
    user_id = (profile or {}).get("id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    body = data.get("body", "")
    comment_id = add_comment("reply", comment_id, user_id, body, parent_id=comment_id)
    if comment_id:
        return jsonify({"success": True, "comment_id": comment_id}), 201
    return jsonify({"error": "Could not reply"}), 400

@comments_bp.route("/<comment_id>/react", methods=["POST"])
def api_react(comment_id):
    profile = get_current_profile()
    user_id = (profile or {}).get("id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    reaction_type = data.get("reaction_type", "like")
    result = react_to_comment(comment_id, user_id, reaction_type)
    return jsonify(result), 200

@comments_bp.route("/<comment_id>", methods=["PATCH"])
def api_edit(comment_id):
    profile = get_current_profile()
    user_id = (profile or {}).get("id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    body = data.get("body", "")
    if edit_comment(comment_id, user_id, body):
        return jsonify({"success": True}), 200
    return jsonify({"error": "Could not edit"}), 400

@comments_bp.route("/<comment_id>", methods=["DELETE"])
def api_delete(comment_id):
    profile = get_current_profile()
    user_id = (profile or {}).get("id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    is_admin = profile.get("is_admin", False) or profile.get("role") == "admin"
    delete_comment(comment_id, user_id, is_admin=is_admin)
    return jsonify({"success": True}), 200

@comments_bp.route("/<comment_id>/pin", methods=["POST"])
def api_pin(comment_id):
    profile = get_current_profile()
    user_id = (profile or {}).get("id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    pin_comment(comment_id, user_id)
    return jsonify({"success": True}), 200
