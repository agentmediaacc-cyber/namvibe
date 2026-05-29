from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from services.profile_service import get_current_profile
from services.reels_engine import list_reels, get_reel, create_reel, record_reel_view, like_reel, share_reel, delete_reel
from api_routes.profile_routes import login_required
from services.rate_limit_service import limiter, user_or_ip_key

reels_bp = Blueprint("reels", __name__, url_prefix="/reels")

@reels_bp.route("/")
def index():
    profile = get_current_profile()
    reels = list_reels(limit=20)
    return render_template("reels/index.html", reels=reels, profile=profile, current=profile)

@reels_bp.route("/upload", methods=["GET", "POST"])
@login_required
@limiter.limit("20/hour", key_func=user_or_ip_key)
def upload():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        from api_routes.profile_routes import _session_profile_stub
        profile = _session_profile_stub()
        return render_template("reels/upload.html", profile=profile, current=profile, setup_warning=True)

    if request.method == "POST":
        video_file = request.files.get("video")
        thumbnail_file = request.files.get("thumbnail")
        caption = request.form.get("caption", "")

        if not video_file:
            return render_template("reels/upload.html", error="Video file is required", profile=profile, current=profile)

        reel_id, error = create_reel(profile['id'], caption, video_file, thumbnail_file)
        if error:
            return render_template("reels/upload.html", error=error, profile=profile, current=profile)
        
        return redirect(url_for('reels.index'))

    return render_template("reels/upload.html", profile=profile, current=profile)

@reels_bp.route("/api/reels/<reel_id>/view", methods=["POST"])
def api_view(reel_id):
    record_reel_view(reel_id)
    return jsonify({"success": True}), 200

@reels_bp.route("/api/reels/<reel_id>/like", methods=["POST"])
@login_required
def api_like(reel_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"error": "Profile not found"}), 404
    like_reel(reel_id, profile['id'])
    return jsonify({"success": True}), 200

@reels_bp.route("/api/reels/<reel_id>/share", methods=["POST"])
def api_share(reel_id):
    share_reel(reel_id)
    return jsonify({"success": True}), 200

@reels_bp.route("/api/reels/<reel_id>/delete", methods=["POST"])
@login_required
def api_delete(reel_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"error": "Profile not found"}), 404
    if delete_reel(reel_id, profile['id']):
        return jsonify({"success": True}), 200
    return jsonify({"error": "Failed to delete reel"}), 400
