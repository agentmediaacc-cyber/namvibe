"""Stories V2 API routes — follower-only status feed and viewer tracking."""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from services.profile_service import get_current_profile
from services.stories_service import (
    get_stories_feed, get_story_with_views, record_story_view,
    react_to_story, reply_to_story, create_story_poll, vote_story_poll
)
from services.status_service import list_active_statuses, get_status, record_view, can_view_status, list_viewers, delete_status
from services.content_service import get_session_profile_id
from services.story_engagement_service import (
    get_tray as se_get_tray,
    record_view as se_record_view,
    set_reaction as se_set_reaction,
    send_reply as se_send_reply,
    delete_story as se_delete_story,
    get_viewers as se_get_viewers,
)
from services.reel_watch_service import record_watch_event
from services.feed_cursor_service import encode_cursor
import json

stories_bp = Blueprint("stories_v2", __name__, url_prefix="/stories")

@stories_bp.route("")
@stories_bp.route("/")
def index():
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    stories = list_active_statuses(viewer_profile_id=viewer_id)
    return render_template("stories.html",
        stories=stories,
        profile=profile,
        current=profile,
        stories_json=json.dumps(stories or [], default=str)
    )

@stories_bp.route("/<story_id>")
def detail(story_id):
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    allowed, _ = can_view_status(story_id, viewer_id)
    story = get_status(story_id, viewer_profile_id=viewer_id)
    if not story or not allowed:
        return redirect(url_for("stories_v2.index"))
    if viewer_id:
        record_view(story_id, viewer_id)
    return render_template("stories.html",
        stories=[story],
        profile=profile,
        current=profile,
        stories_json=json.dumps([story], default=str)
    )

@stories_bp.route("/api/stories/feed", methods=["GET"])
def api_feed():
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    stories = list_active_statuses(viewer_profile_id=viewer_id)
    return jsonify({"stories": stories}), 200


@stories_bp.route("/api/stories/<story_id>", methods=["GET"])
def api_story_detail(story_id):
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    allowed, reason = can_view_status(story_id, viewer_id)
    if not allowed:
        return jsonify({"error": "Cannot view status", "reason": reason}), 403
    story = get_status(story_id, viewer_profile_id=viewer_id)
    if not story:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"story": story}), 200

@stories_bp.route("/api/stories/<story_id>/view", methods=["POST"])
def api_view(story_id):
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    if not viewer_id:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    reaction = data.get("reaction")
    allowed, reason = can_view_status(story_id, viewer_id)
    if not allowed:
        return jsonify({"error": f"Cannot view status: {reason}", "reason": reason}), 403
    record_view(story_id, viewer_id, reaction=reaction)
    return jsonify({"success": True}), 200

@stories_bp.route("/api/stories/<story_id>/react", methods=["POST"])
def api_react(story_id):
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    if not viewer_id:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    reaction = data.get("reaction", "like")
    react_to_story(story_id, viewer_id, reaction)
    return jsonify({"success": True}), 200

@stories_bp.route("/api/stories/<story_id>/reply", methods=["POST"])
def api_reply(story_id):
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    if not viewer_id:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    reply_text = data.get("reply_text", "")
    reply_to_story(story_id, viewer_id, reply_text)
    return jsonify({"success": True}), 200

@stories_bp.route("/api/stories/<story_id>/poll/vote", methods=["POST"])
def api_poll_vote(story_id):
    profile = get_current_profile()
    user_id = (profile or {}).get("id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    poll_id = data.get("poll_id")
    option_index = int(data.get("option_index", 0))
    if not poll_id:
        return jsonify({"error": "poll_id required"}), 400
    vote_story_poll(poll_id, user_id, option_index)
    return jsonify({"success": True}), 200


@stories_bp.route("/api/status/<status_id>/visible", methods=["GET"])
def api_status_visible(status_id):
    """Check if the current user can view a status. Returns {visible, reason, owner?, viewer_count?}"""
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    from services.status_service import can_view_status, get_status
    allowed, reason = can_view_status(status_id, viewer_id)
    status = get_status(status_id) if allowed else None
    viewer_count = status.get("views_count", 0) if status else 0
    is_owner = bool(viewer_id and status and str(status.get("profile_id")) == str(viewer_id))
    return jsonify({
        "visible": allowed,
        "reason": reason,
        "owner": is_owner,
        "viewer_count": viewer_count,
    }), 200


# =========== PHASE 93: Story Engagement (unique endpoints only) ===========

@stories_bp.route("/api/stories/tray", methods=["GET"])
def api_story_tray():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    if not profile_id:
        return jsonify({"stories": []})
    tray = se_get_tray(profile_id)
    return jsonify({"stories": tray})


@stories_bp.route("/api/stories/<story_id>", methods=["DELETE"])
def api_story_delete(story_id):
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    if not profile_id:
        return jsonify({"error": "Not authenticated"}), 401
    ok = delete_status(story_id, profile_id)
    if ok:
        return jsonify({"ok": True})
    return jsonify({"error": "delete_failed"}), 403


@stories_bp.route("/api/stories/<story_id>/viewers", methods=["GET"])
def api_story_viewers(story_id):
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    viewers = list_viewers(story_id, requesting_profile_id=viewer_id)
    return jsonify({"viewers": viewers})


# =========== PHASE 157: Status Viewer Tracking ===========

@stories_bp.route("/api/status/<status_id>/view", methods=["POST"])
def api_status_view(status_id):
    """Record a view on a status. Body: {reaction?, reply_message?}"""
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    if not viewer_id:
        return jsonify({"error": "Not authenticated"}), 401
    allowed, reason = can_view_status(status_id, viewer_id)
    if not allowed:
        return jsonify({"error": f"Cannot view status: {reason}", "reason": reason}), 403
    data = request.get_json(silent=True) or {}
    reaction = data.get("reaction")
    reply_message = data.get("reply_message")
    record_view(status_id, viewer_id, reaction=reaction, reply_message=reply_message)
    return jsonify({"success": True}), 200


@stories_bp.route("/api/status/<status_id>/viewers", methods=["GET"])
def api_status_viewers(status_id):
    """List viewers of a status. Only owner can see viewer list."""
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    if not viewer_id:
        return jsonify({"error": "Not authenticated"}), 401
    viewers = list_viewers(status_id, requesting_profile_id=viewer_id)
    return jsonify({"viewers": viewers}), 200
