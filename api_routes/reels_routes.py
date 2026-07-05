import os
import time

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from services.profile_service import get_current_profile
from services.reels_engine import list_reels, get_reel, create_reel, create_reel_full, record_reel_view, share_reel, delete_reel
from services.reels_engine import get_reels_feed, get_reel_detail, get_next_reels, track_reel_watch
from services.reels_engine import get_creator_reel_stats, get_reel_comments_summary
from services.reels_engine import like_reel_v2, unlike_reel, save_reel, unsave_reel, share_reel_v2, note_reel_comment
from services.reels_service import track_reel_event, get_reel_comments, get_reel_feed, batch_is_following, toggle_reel_save, toggle_reel_like
from services.engagement_service import add_comment, toggle_like, toggle_save
from api_routes.profile_routes import login_required
from services.rate_limit_service import limiter, user_or_ip_key
from services.reel_watch_service import record_watch_event as rwe_record_watch
from services.feed_cursor_service import encode_cursor as rwe_encode_cursor
from services.content_service import get_session_profile_id, session_profile_stub
from services.profile_context_service import build_profile_template_context
from services.comments_service import add_comment as reply_to_comment
from services.logging_service import log_info

from services.content_manager_service import get_managed_reels, update_content_status as update_reel_status

reels_bp = Blueprint("reels", __name__, url_prefix="/reels")

@reels_bp.route("/profile/reels")
@login_required
def profile_reels():
    profile = get_current_profile()
    sort = request.args.get("sort", "newest")
    cursor = request.args.get("cursor")
    limit = min(int(request.args.get("limit", 20)), 50)
    data = get_managed_reels(profile['id'], tab=sort, limit=limit, cursor=cursor)
    return render_template(
        "profile/reels_manager.html", 
        profile=profile, 
        reels=data['items'], 
        pagination={'total': data['total'], 'per_page': limit},
        **data
    )

@reels_bp.route("/api/reels")
@login_required
def api_reels():
    profile = get_current_profile()
    tab = request.args.get("tab", "newest")
    cursor = request.args.get("cursor")
    limit = min(int(request.args.get("limit", 20)), 50)
    data = get_managed_reels(profile['id'], tab=tab, limit=limit, cursor=cursor)
    return jsonify(data)


def _render_upload(profile, **extra):
    context = build_profile_template_context(
        profile=profile,
        active_tab="reels",
        extra={"page_title": "Upload Reel", **extra},
    )
    return render_template("reels/upload.html", **context)

@reels_bp.route("/")
def index():
    start = time.perf_counter()
    force_fast_reels = (
        os.getenv("CHAIN_FORCE_FAST_HOME", "").lower() in ("1", "true", "yes", "on")
        or os.getenv("CHAIN_TUNNEL_TESTING", "").lower() in ("1", "true", "yes", "on")
        or "namvibe.com" in request.headers.get("Host", "").lower()
    )
    if force_fast_reels:
        response = render_template("reels.html", reels=[], profile=None, current=None, follow_map={})
        log_info("reels_page_total", duration_ms=round((time.perf_counter() - start) * 1000, 2), reel_count=0, shell=True)
        return response

    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    # Pass viewer_id for visibility filtering (public/followers/private)
    reels = get_reel_feed(limit=15, viewer_id=profile_id)
    if not reels:
        reels = list_reels(limit=12)
    follow_map = {}
    if profile_id and reels:
        creator_ids = {r.get("profile_id") for r in reels if r.get("profile_id")}
        following = batch_is_following(profile_id, creator_ids)
        follow_map = {pid: pid in following for pid in creator_ids}
    response = render_template("reels.html", reels=reels, profile=profile, current=profile, follow_map=follow_map)
    log_info("reels_page_total", duration_ms=round((time.perf_counter() - start) * 1000, 2), reel_count=len(reels or []))
    return response

@reels_bp.route("/upload", methods=["GET", "POST"])
@login_required
@limiter.limit("20/hour", key_func=user_or_ip_key)
def upload():
    if request.method == "POST":
        profile_id = get_session_profile_id()
        profile = get_current_profile() or (session_profile_stub() if profile_id else None)
        if not profile_id:
            return redirect(url_for("auth.login", next=request.path))
        video_file = request.files.get("video")
        thumbnail_file = request.files.get("thumbnail")
        caption = request.form.get("caption", "")
        music_title = request.form.get("music_title", "")
        visibility = request.form.get("visibility", "public")

        if not video_file:
            return _render_upload(profile, error="Video file is required")

        reel_id, error = create_reel(profile_id, caption, video_file, thumbnail_file, music_title=music_title, visibility=visibility)
        if error:
            return _render_upload(profile, error=error)
        
        return redirect(url_for('reels.index'))

    # Phase 156: Redirect to homepage with upload modal open
    return redirect("/?open=upload#upload")

@reels_bp.route("/api/reels/<reel_id>/view", methods=["POST"])
def api_view(reel_id):
    try:
        profile = get_current_profile()
        viewer_id = (profile or {}).get("id") if profile else None
        record_reel_view(reel_id, viewer_profile_id=viewer_id)
        return jsonify({"ok": True, "queued": True}), 200
    except Exception:
        return jsonify({"ok": True, "queued": True}), 200

@reels_bp.route("/api/reels/<reel_id>/like", methods=["POST"])
@login_required
def api_like(reel_id):
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"error": "Profile not found"}), 404
    result = toggle_like(profile_id, "reel", reel_id)
    status = 200 if result.get("success") else 400
    return jsonify(result), status

@reels_bp.route("/api/reels/<reel_id>/comment", methods=["POST"])
@login_required
def api_comment(reel_id):
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"error": "Profile not found"}), 404
    data = request.get_json(silent=True) or {}
    result = add_comment("reel", reel_id, profile_id, request.form.get("body") or data.get("body"))
    status = 201 if result.get("success") else 400
    return jsonify(result), status

@reels_bp.route("/api/reels/<reel_id>/save", methods=["POST"])
@login_required
def api_save(reel_id):
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"error": "Profile not found"}), 404
    result = toggle_save(profile_id, "reel", reel_id)
    status = 200 if result.get("success") else 400
    return jsonify(result), status

@reels_bp.route("/api/reels/<reel_id>/share", methods=["POST"])
def api_share(reel_id):
    try:
        share_reel(reel_id)
        return jsonify({"success": True}), 200
    except Exception:
        return jsonify({"success": False, "tracked": False, "message": "Share tracking skipped."}), 200

@reels_bp.route("/api/reels/<reel_id>/delete", methods=["POST"])
@login_required
def api_delete(reel_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"error": "Profile not found"}), 404
    if delete_reel(reel_id, profile['id']):
        return jsonify({"success": True}), 200
    return jsonify({"error": "Failed to delete reel"}), 400

@reels_bp.route("/api/reels/<reel_id>/event", methods=["POST"])
def api_event(reel_id):
    try:
        data = request.get_json(silent=True) or {}
        event_type = data.get("event_type", "view")
        watch_ms = int(data.get("watch_ms", 0))
        user_id = None
        profile = get_current_profile()
        if profile:
            user_id = profile.get("id")
        track_reel_event(reel_id, user_id, event_type, watch_ms)
        return jsonify({"ok": True, "queued": True}), 200
    except Exception:
        return jsonify({"ok": True, "queued": True}), 200

@reels_bp.route("/api/reels/<reel_id>/comments", methods=["GET"])
def api_comments(reel_id):
    comments = get_reel_comments(reel_id, limit=30)
    comments_list = []
    for c in comments:
        comments_list.append({
            "id": c.get("id"),
            "body": c.get("body"),
            "username": c.get("username"),
            "avatar_url": c.get("avatar_url"),
            "created_at": str(c.get("created_at") or ""),
        })
    return jsonify({"comments": comments_list}), 200


# =========== PHASE 93: Reel Watch & Feed ===========

@reels_bp.route("/api/reels/<reel_id>/watch", methods=["POST"])
def api_reel_watch(reel_id):
    try:
        data = request.get_json(silent=True) or {}
        profile = get_current_profile()
        user_id = (profile or {}).get("id")
        rwe_record_watch(
            reel_id=reel_id,
            user_id=user_id,
            session_id=data.get("session_id"),
            watch_seconds=float(data.get("watch_seconds", 0)),
            completion_percent=float(data.get("completion_percent", 0)),
            replay_count=int(data.get("replay_count", 0)),
        )
        return jsonify({"ok": True, "queued": True}), 200
    except Exception:
        return jsonify({"ok": True, "queued": True}), 200


@reels_bp.route("/api/reels/feed", methods=["GET"])
def api_reels_feed():
    from services.reels_service import get_reel_feed as _grf
    cursor = request.args.get("cursor")
    limit = min(int(request.args.get("limit", 20)), 50)
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    # Pass viewer_id for visibility filtering (public/followers/private)
    reels = _grf(limit=limit + 1, viewer_id=viewer_id)
    next_cursor = None
    if len(reels) > limit:
        next_cursor = reels[-1].get("id")
        reels = reels[:limit]
    return jsonify({
        "reels": reels,
        "next_cursor": rwe_encode_cursor(next_cursor) if next_cursor else None,
        "has_more": bool(next_cursor),
    })


# =========== PHASE 93: Batch View Tracking ===========

@reels_bp.route("/api/reels/view/batch", methods=["POST"])
def api_reels_view_batch():
    """Batch endpoint for tracking reel views. Accepts either a list or {views: [...]} format."""
    try:
        data = request.get_json(silent=True) or {}
        # Support both formats: direct list or {views: [...]}
        views = data if isinstance(data, list) else data.get("views", [])
        if not views:
            return jsonify({"ok": True, "tracked": 0}), 200
        
        profile = get_current_profile()
        viewer_id = (profile or {}).get("id")
        
        tracked = 0
        for view in views:
            reel_id = view.get("reel_id") or view.get("id")
            watch_ms = int(view.get("watch_ms") or view.get("watch_seconds", 0) or 0)
            completed = view.get("completed", False)
            if reel_id:
                try:
                    record_reel_view(reel_id, viewer_profile_id=viewer_id)
                    tracked += 1
                except Exception:
                    pass
        
        return jsonify({"ok": True, "tracked": tracked}), 200
    except Exception:
        return jsonify({"ok": True, "tracked": 0}), 200


# =========== API: Reel Upload ===========

@reels_bp.route("/api/reels/create", methods=["POST"])
@login_required
def api_create_reel():
    """API endpoint for creating reels with video upload."""
    profile_id = get_session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    
    video_file = request.files.get("video")
    if not video_file:
        return jsonify({"ok": False, "error": "Video file is required"}), 400
    
    from services.redis_service import cache_get, cache_set
    dedup_key = f"reel_upload:{profile_id}:{video_file.filename}:{video_file.content_length}"
    if cache_get(dedup_key):
        return jsonify({"ok": False, "error": "Duplicate upload detected"}), 429
    cache_set(dedup_key, True, ttl=30)
    
    max_size = 500 * 1024 * 1024
    if video_file.content_length and video_file.content_length > max_size:
        return jsonify({"ok": False, "error": "Video exceeds 500MB limit"}), 400
    
    caption = request.form.get("caption", "")
    music_title = request.form.get("music_title", "")
    music_url = request.form.get("music_url", "")
    music_artist = request.form.get("music_artist", "")
    music_start_seconds = request.form.get("music_start_seconds", 0)
    music_duration_seconds = request.form.get("music_duration_seconds", 0)
    music_file = request.files.get("music_file")
    visibility = request.form.get("visibility", "public")
    
    if music_file and music_file.filename:
        try:
            from services.supabase_storage_service import upload_media_to_supabase
            result = upload_media_to_supabase(music_file, "reels", profile_id)
            if result.get("ok"):
                music_url = music_url or result["url"]
                if not music_title:
                    music_title = music_file.filename.rsplit(".", 1)[0]
        except Exception:
            pass
    
    # Normalize visibility
    visibility = request.form.get("audience") or visibility
    visibility = visibility.lower() if visibility else "public"
    if visibility not in ("public", "followers", "private"):
        visibility = "public"
    
    reel, error = create_reel_full(profile_id, caption, video_file, None, music_title=music_title, visibility=visibility,
                                   music_url=music_url, music_artist=music_artist,
                                   music_start_seconds=music_start_seconds, music_duration_seconds=music_duration_seconds)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    if reel:
        try:
            from services.video_processing_service import create_processing_job
            video_url = reel.get("video_url") or reel.get("media_url") or ""
            if video_url:
                create_processing_job("reel", reel.get("id"), profile_id, video_url)
        except Exception:
            pass
        return jsonify({"ok": True, "reel_id": reel.get("id"), "video_url": reel.get("video_url"), "media_url": reel.get("media_url")}), 201
    return jsonify({"ok": False, "error": "Failed to create reel"}), 400


# =========== PHASE 4: Reels Engine Premium Endpoints ===========

@reels_bp.route("/api/reels/<reel_id>/detail", methods=["GET"])
def api_reel_detail(reel_id):
    """Get reel detail with viewer interaction state."""
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    reel = get_reel_detail(viewer_id, reel_id)
    if not reel:
        return jsonify({"error": "Reel not found"}), 404
    return jsonify({"reel": reel}), 200


@reels_bp.route("/api/reels/<reel_id>/next", methods=["GET"])
def api_next_reels(reel_id):
    """Get next reels for continuous play."""
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    limit = min(int(request.args.get("limit", 5)), 20)
    reels = get_next_reels(viewer_id, reel_id, limit=limit)
    return jsonify({"reels": reels}), 200


@reels_bp.route("/api/reels/<reel_id>/watch-v2", methods=["POST"])
def api_watch_v2(reel_id):
    """Enhanced watch tracking with completed/replayed signals."""
    try:
        data = request.get_json(silent=True) or {}
        profile = get_current_profile()
        viewer_id = (profile or {}).get("id")
        watch_ms = int(data.get("watch_ms", data.get("watch_seconds", 0)) * 1000)
        completed = bool(data.get("completed", False))
        replayed = bool(data.get("replayed", False))
        track_reel_watch(viewer_id, reel_id, watch_ms, completed=completed, replayed=replayed)
        return jsonify({"ok": True}), 200
    except Exception:
        return jsonify({"ok": True}), 200


@reels_bp.route("/api/reels/<reel_id>/like-v2", methods=["POST"])
@login_required
def api_like_v2(reel_id):
    """Like/unlike a reel with state tracking."""
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    if not profile_id:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    action = data.get("action", "toggle")
    if action == "unlike":
        success, liked = unlike_reel(profile_id, reel_id)
    else:
        success, liked = like_reel_v2(profile_id, reel_id)
    if not success:
        return jsonify({"error": "Action failed"}), 400
    return jsonify({"success": True, "liked": liked}), 200


@reels_bp.route("/api/reels/<reel_id>/save-v2", methods=["POST"])
@login_required
def api_save_v2(reel_id):
    """Save/unsave a reel with state tracking."""
    profile = get_current_profile()
    profile_id = (profile or {}).get("id")
    if not profile_id:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    action = data.get("action", "toggle")
    if action == "unsave":
        success, saved = unsave_reel(profile_id, reel_id)
    else:
        success, saved = save_reel(profile_id, reel_id)
    if not success:
        return jsonify({"error": "Action failed"}), 400
    return jsonify({"success": True, "saved": saved}), 200


@reels_bp.route("/api/reels/<reel_id>/share-v2", methods=["POST"])
def api_share_v2(reel_id):
    """Enhanced share tracking."""
    try:
        profile = get_current_profile()
        profile_id = (profile or {}).get("id")
        data = request.get_json(silent=True) or {}
        target = data.get("target", "link")
        share_reel_v2(reel_id, profile_id, target=target)
        return jsonify({"success": True}), 200
    except Exception:
        return jsonify({"success": False}), 200


@reels_bp.route("/api/reels/<reel_id>/creator-stats", methods=["GET"])
def api_creator_stats(reel_id):
    """Get creator's reel analytics (own reels only)."""
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    try:
        reel = fast_query("SELECT profile_id FROM chain_reels WHERE id = %s", (reel_id,))
        if not reel:
            return jsonify({"error": "Reel not found"}), 404
        creator_id = reel[0][0]
        stats = get_creator_reel_stats(creator_id, requesting_profile_id=viewer_id)
        return jsonify(stats), 200
    except Exception:
        return jsonify({"error": "Failed to load stats"}), 500


@reels_bp.route("/api/reels/<reel_id>/comments-summary", methods=["GET"])
def api_comments_summary(reel_id):
    """Get comment count + latest commenters."""
    summary = get_reel_comments_summary(reel_id)
    return jsonify(summary), 200


@reels_bp.route("/api/reels/feed-v2", methods=["GET"])
def api_feed_v2():
    """Enhanced cursor-based feed with ranking."""
    feed_type = request.args.get("type", "for_you")
    cursor = request.args.get("cursor")
    limit = min(int(request.args.get("limit", 10)), 50)
    profile = get_current_profile()
    viewer_id = (profile or {}).get("id")
    reels, next_cursor = get_reels_feed(viewer_id, feed_type=feed_type, cursor=cursor, limit=limit)

    # Add viewer interaction states
    if viewer_id and reels:
        try:
            from services.reels_service import batch_is_following
            creator_ids = [r["profile_id"] for r in reels if r.get("profile_id")]
            following = batch_is_following(viewer_id, creator_ids) if creator_ids else set()
            for r in reels:
                pid = r.get("profile_id")
                r["viewer_follows_creator"] = pid in following if pid else False
        except Exception:
            pass

    return jsonify({
        "reels": reels,
        "next_cursor": next_cursor,
        "has_more": bool(next_cursor),
    })


@reels_bp.route("/api/reels/track", methods=["POST"])
def api_track_activity():
    """Generic activity tracking endpoint for client-side events."""
    try:
        data = request.get_json(silent=True) or {}
        profile = get_current_profile()
        profile_id = (profile or {}).get("id")
        verb = data.get("verb", "reel_viewed")
        reel_id = data.get("reel_id")
        if reel_id and verb and profile_id:
            try:
                from services.reels_engine import _emit_reel_activity
                _emit_reel_activity(profile_id, reel_id, verb, data.get("extra"))
            except Exception:
                pass
        return jsonify({"ok": True}), 200
    except Exception:
        return jsonify({"ok": True}), 200
