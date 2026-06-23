import os
import time

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from services.profile_service import get_current_profile
from services.reels_engine import list_reels, get_reel, create_reel, record_reel_view, share_reel, delete_reel
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
        pagination={'total': data['total']},
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

    profile = get_current_profile() or (session_profile_stub() if get_session_profile_id() else None)
    if not profile or not profile.get("id"):
        return redirect(url_for("auth.login", next=request.path))

    return _render_upload(profile)

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
    result = add_comment(profile_id, "reel", reel_id, request.form.get("body") or data.get("body"))
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
    
    caption = request.form.get("caption", "")
    music_title = request.form.get("music_title", "")
    visibility = request.form.get("visibility", "public")
    
    # Normalize visibility
    visibility = request.form.get("audience") or visibility
    visibility = visibility.lower() if visibility else "public"
    if visibility not in ("public", "followers", "private"):
        visibility = "public"
    
    reel_id, error = create_reel(profile_id, caption, video_file, None, music_title=music_title, visibility=visibility)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    if reel_id:
        return jsonify({"ok": True, "reel_id": reel_id}), 201
    return jsonify({"ok": False, "error": "Failed to create reel"}), 400
