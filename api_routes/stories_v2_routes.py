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
from services.stories_engine import (
    get_story_feed, get_grouped_stories, get_story_detail,
    get_stories_by_creator, record_story_view_v2, react_to_story_v2,
    reply_to_story_v2, record_story_analytics_event, can_view_story_v2,
    get_story_viewers, get_story_analytics, get_creator_story_stats,
    create_story_v2, delete_story_v2, create_highlight, get_highlights,
    get_highlight_detail, update_highlight, delete_highlight,
    reorder_highlights, add_stories_to_highlight, remove_story_from_highlight,
    add_close_friend, remove_close_friend, get_close_friends,
    hide_story_from, unhide_story_from, get_hidden_users,
)
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


# =========== PHASE 5: Stories 2.0 Premium Endpoints ===========

@stories_bp.route("/api/stories/feed-v2", methods=["GET"])
def api_stories_feed_v2():
    """Enhanced story feed with grouped stories, highlights, viewer state."""
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    groups = get_grouped_stories(viewer_id)
    stories = get_story_feed(viewer_id)
    return jsonify({"groups": groups, "stories": stories}), 200


@stories_bp.route("/api/stories/<story_id>/view-v2", methods=["POST"])
def api_story_view_v2(story_id):
    """Enhanced view tracking with optional reaction/reply."""
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    if not viewer_id:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    reaction = data.get("reaction")
    reply_text = data.get("reply_text")
    allowed, reason = can_view_story_v2(story_id, viewer_id)
    if not allowed:
        return jsonify({"error": reason}), 403
    record_story_view_v2(story_id, viewer_id, reaction=reaction, reply_text=reply_text)
    return jsonify({"success": True}), 200


@stories_bp.route("/api/stories/<story_id>/react-v2", methods=["POST"])
def api_story_react_v2(story_id):
    """Set emoji reaction on a story."""
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    if not viewer_id:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    reaction = data.get("reaction", "❤️")
    react_to_story_v2(story_id, viewer_id, reaction)
    return jsonify({"success": True}), 200


@stories_bp.route("/api/stories/<story_id>/reply-v2", methods=["POST"])
def api_story_reply_v2(story_id):
    """Reply to a story (private message thread)."""
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    if not viewer_id:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    reply_text = data.get("reply_text", "")
    if not reply_text.strip():
        return jsonify({"error": "reply_text required"}), 400
    reply_to_story_v2(story_id, viewer_id, reply_text)
    return jsonify({"success": True}), 200


@stories_bp.route("/api/stories/<story_id>/analytics-event", methods=["POST"])
def api_story_analytics_event(story_id):
    """Record granular analytics event (forward, back, exit)."""
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    data = request.get_json(silent=True) or {}
    event_type = data.get("event_type", "view")
    record_story_analytics_event(story_id, viewer_id, event_type)
    return jsonify({"success": True}), 200


@stories_bp.route("/api/stories/<story_id>/detail-v2", methods=["GET"])
def api_story_detail_v2(story_id):
    """Get story detail with viewer interaction state."""
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    allowed, reason = can_view_story_v2(story_id, viewer_id)
    if not allowed:
        return jsonify({"error": reason}), 403
    story = get_story_detail(story_id, viewer_id)
    if not story:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"story": story}), 200


@stories_bp.route("/api/stories/<story_id>/analytics", methods=["GET"])
def api_story_analytics(story_id):
    """Get analytics for a story (owner only)."""
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    if not viewer_id:
        return jsonify({"error": "Not authenticated"}), 401
    analytics = get_story_analytics(story_id, viewer_id)
    if analytics is None:
        return jsonify({"error": "Not found or unauthorized"}), 404
    return jsonify(analytics), 200


@stories_bp.route("/api/stories/<story_id>/creator-stats", methods=["GET"])
def api_story_creator_stats(story_id):
    """Get creator story stats (own stats only)."""
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    story = fast_query(
        "SELECT profile_id FROM chain_status_posts WHERE id = %s", (story_id,), default=[]
    )
    if not story:
        return jsonify({"error": "Not found"}), 404
    creator_id = story[0][0] if isinstance(story[0], (list, tuple)) else story[0]["profile_id"]
    stats = get_creator_story_stats(creator_id, requesting_profile_id=viewer_id)
    return jsonify(stats), 200


@stories_bp.route("/api/stories/<story_id>/delete-v2", methods=["POST"])
def api_story_delete_v2(story_id):
    """Delete a story (owner only)."""
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    if not profile_id:
        return jsonify({"error": "Not authenticated"}), 401
    ok = delete_story_v2(story_id, profile_id)
    if ok:
        return jsonify({"ok": True}), 200
    return jsonify({"error": "Not found or unauthorized"}), 404


# ── Highlights ──

@stories_bp.route("/api/highlights", methods=["GET"])
def api_highlights_list():
    """Get highlights for current user's profile."""
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    target_id = request.args.get("profile_id", profile_id)
    viewer_id = (profile or {}).get("id")
    highlights = get_highlights(target_id, viewer_id=viewer_id)
    return jsonify({"highlights": highlights}), 200


@stories_bp.route("/api/highlights/<highlight_id>", methods=["GET"])
def api_highlight_detail(highlight_id):
    """Get highlight with its stories."""
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    hl = get_highlight_detail(highlight_id, viewer_id=viewer_id)
    if not hl:
        return jsonify({"error": "Not found"}), 404
    return jsonify(hl), 200


@stories_bp.route("/api/highlights/create", methods=["POST"])
def api_highlight_create():
    """Create a new highlight."""
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    if not profile_id:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    title = data.get("title", "Highlights")
    cover_url = data.get("cover_url")
    story_ids = data.get("story_ids", [])
    hl = create_highlight(profile_id, title, cover_url=cover_url, story_ids=story_ids)
    if hl:
        return jsonify(hl), 201
    return jsonify({"error": "Failed to create"}), 400


@stories_bp.route("/api/highlights/<highlight_id>/update", methods=["POST"])
def api_highlight_update(highlight_id):
    """Update highlight title/cover."""
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    if not profile_id:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    cover_url = data.get("cover_url")
    ok = update_highlight(highlight_id, title=title, cover_url=cover_url)
    if ok:
        return jsonify({"ok": True}), 200
    return jsonify({"error": "Failed to update"}), 400


@stories_bp.route("/api/highlights/<highlight_id>/delete", methods=["POST"])
def api_highlight_delete(highlight_id):
    """Delete a highlight."""
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    if not profile_id:
        return jsonify({"error": "Not authenticated"}), 401
    ok = delete_highlight(highlight_id, profile_id)
    if ok:
        return jsonify({"ok": True}), 200
    return jsonify({"error": "Not found or unauthorized"}), 404


@stories_bp.route("/api/highlights/reorder", methods=["POST"])
def api_highlights_reorder():
    """Reorder highlights."""
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    if not profile_id:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    highlight_ids = data.get("highlight_ids", [])
    ok = reorder_highlights(profile_id, highlight_ids)
    if ok:
        return jsonify({"ok": True}), 200
    return jsonify({"error": "Failed to reorder"}), 400


@stories_bp.route("/api/highlights/<highlight_id>/stories/add", methods=["POST"])
def api_highlight_add_stories(highlight_id):
    """Add stories to a highlight."""
    data = request.get_json(silent=True) or {}
    story_ids = data.get("story_ids", [])
    ok = add_stories_to_highlight(highlight_id, story_ids)
    if ok:
        return jsonify({"ok": True}), 200
    return jsonify({"error": "Failed to add stories"}), 400


@stories_bp.route("/api/highlights/<highlight_id>/stories/<story_id>/remove", methods=["POST"])
def api_highlight_remove_story(highlight_id, story_id):
    """Remove a story from a highlight."""
    ok = remove_story_from_highlight(highlight_id, story_id)
    if ok:
        return jsonify({"ok": True}), 200
    return jsonify({"error": "Failed to remove"}), 400


# ── Close Friends ──

@stories_bp.route("/api/close-friends", methods=["GET"])
def api_close_friends_list():
    """Get close friends list."""
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    if not profile_id:
        return jsonify({"error": "Not authenticated"}), 401
    friends = get_close_friends(profile_id)
    return jsonify({"close_friends": friends}), 200


@stories_bp.route("/api/close-friends/add", methods=["POST"])
def api_close_friend_add():
    """Add a close friend."""
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    if not profile_id:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    friend_id = data.get("friend_id")
    if not friend_id:
        return jsonify({"error": "friend_id required"}), 400
    add_close_friend(profile_id, friend_id)
    return jsonify({"ok": True}), 200


@stories_bp.route("/api/close-friends/remove", methods=["POST"])
def api_close_friend_remove():
    """Remove a close friend."""
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    if not profile_id:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    friend_id = data.get("friend_id")
    if not friend_id:
        return jsonify({"error": "friend_id required"}), 400
    remove_close_friend(profile_id, friend_id)
    return jsonify({"ok": True}), 200


# ── Hidden Users ──

@stories_bp.route("/api/stories/hidden-users", methods=["GET"])
def api_hidden_users_list():
    """Get hidden users list."""
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    if not profile_id:
        return jsonify({"error": "Not authenticated"}), 401
    hidden = get_hidden_users(profile_id)
    return jsonify({"hidden_users": hidden}), 200


@stories_bp.route("/api/stories/hide-from", methods=["POST"])
def api_hide_from_user():
    """Hide stories from a user."""
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    if not profile_id:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    hidden_user_id = data.get("user_id")
    if not hidden_user_id:
        return jsonify({"error": "user_id required"}), 400
    hide_story_from(profile_id, hidden_user_id)
    return jsonify({"ok": True}), 200


@stories_bp.route("/api/stories/unhide-from", methods=["POST"])
def api_unhide_from_user():
    """Stop hiding stories from a user."""
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    if not profile_id:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    hidden_user_id = data.get("user_id")
    if not hidden_user_id:
        return jsonify({"error": "user_id required"}), 400
    unhide_story_from(profile_id, hidden_user_id)
    return jsonify({"ok": True}), 200


# ── Create Story (Phase 5) ──

@stories_bp.route("/api/stories/create-v2", methods=["POST"])
def api_story_create_v2():
    """Create a story with full metadata."""
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    if not profile_id:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    media_type = data.get("media_type", "image")
    media_url = data.get("media_url")
    caption = data.get("caption", "")
    visibility = data.get("visibility", "public")
    duration_seconds = int(data.get("duration_seconds", 10))
    background_color = data.get("background_color")
    text_content = data.get("text_content")
    music_title = data.get("music_title")
    music_url = data.get("music_url")
    location_name = data.get("location_name")
    mentions = data.get("mentions")
    hashtags = data.get("hashtags")
    link_url = data.get("link_url")

    story, error = create_story_v2(
        profile_id, media_type=media_type, media_url=media_url,
        caption=caption, visibility=visibility,
        duration_seconds=duration_seconds, background_color=background_color,
        text_content=text_content, music_title=music_title, music_url=music_url,
        location_name=location_name, mentions=mentions, hashtags=hashtags,
        link_url=link_url,
    )
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"ok": True, "story": story}), 201
