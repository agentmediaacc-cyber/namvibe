from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from services.profile_service import get_current_profile
from services.reels_engine import list_reels, get_reel, create_reel, record_reel_view, share_reel, delete_reel
from services.reels_service import track_reel_event, get_reel_comments, get_reel_feed, is_following_creator, toggle_reel_save, toggle_reel_like
from services.engagement_service import add_comment, toggle_like, toggle_save
from api_routes.profile_routes import login_required
from services.rate_limit_service import limiter, user_or_ip_key
from services.content_service import get_session_profile_id, session_profile_stub
from services.profile_context_service import build_profile_template_context

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
    profile = get_current_profile()
    reels = get_reel_feed(limit=30)
    if not reels:
        reels = list_reels(limit=20)
    profile_id = (profile or {}).get("id")
    follow_map = {}
    if profile_id and reels:
        for r in reels:
            pid = r.get("profile_id")
            if pid:
                follow_map[pid] = is_following_creator(profile_id, pid)
    return render_template("reels.html", reels=reels, profile=profile, current=profile, follow_map=follow_map)

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
        record_reel_view(reel_id)
        return jsonify({"success": True}), 200
    except Exception as error:
        return jsonify({"success": False, "tracked": False, "message": "View tracking skipped."}), 200

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
        return jsonify({"success": True}), 200
    except Exception:
        return jsonify({"success": False, "tracked": False, "message": "Reel event tracking skipped."}), 200

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
