import os, uuid, time
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from services.profile_service import get_current_profile, get_profile_by_username, get_profile_by_id
from services.rpromo_service import (
    get_promo_videos, get_promo_video, upload_promo_video,
    delete_promo_video, record_view, toggle_like, count_promo_videos
)
from services.content_service import get_session_profile_id
from services.rate_limit_service import limiter
from api_routes.profile_routes import login_required

rpromo_bp = Blueprint("rpromo", __name__, url_prefix="/rpromo")


def _ensure_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


@rpromo_bp.route("/<username>")
def view_promo(username):
    profile = get_profile_by_username(username)
    if not profile:
        return render_template("errors/404.html"), 404
    viewer_id = get_session_profile_id()
    videos = get_promo_videos(profile["id"], viewer_id=viewer_id)
    is_owner = viewer_id and str(profile["id"]) == str(viewer_id)
    return render_template(
        "rpromo/index.html",
        profile=profile,
        videos=videos,
        is_owner=is_owner,
        video_count=len(videos),
    )


@rpromo_bp.route("/api/<profile_id>/videos")
def api_videos(profile_id):
    viewer_id = get_session_profile_id()
    videos = get_promo_videos(profile_id, viewer_id=viewer_id)
    return jsonify({"videos": videos, "count": len(videos)})


@rpromo_bp.route("/api/upload", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
def api_upload():
    profile = get_current_profile()
    if not profile:
        return jsonify({"error": "Not authenticated."}), 401
    profile_id = profile["id"]
    current_count = count_promo_videos(profile_id)
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    video_file = request.files.get("video")
    if not video_file:
        return jsonify({"error": "No video file provided."}), 400
    if not title:
        return jsonify({"error": "Title is required."}), 400
    result = _save_video_file(video_file, profile_id)
    if not result.get("success"):
        return jsonify({"error": result.get("error", "Upload failed.")}), 500
    video_url = result["url"]
    thumbnail_url = result.get("thumbnail_url", "")
    r = upload_promo_video(profile_id, title, description, video_url, thumbnail_url)
    if not r.get("success"):
        return jsonify({"error": r.get("error", "Failed to save promo video.")}), 500
    return jsonify({"success": True, "video": r.get("video"), "count": current_count + 1})


@rpromo_bp.route("/api/video/<video_id>/delete", methods=["POST"])
@login_required
def api_delete(video_id):
    profile = get_current_profile()
    if not profile:
        return jsonify({"error": "Not authenticated."}), 401
    r = delete_promo_video(video_id, profile["id"])
    if not r.get("success"):
        return jsonify({"error": r.get("error", "Delete failed.")}), 400
    return jsonify({"success": True})


@rpromo_bp.route("/api/video/<video_id>/view", methods=["POST"])
def api_view(video_id):
    profile_id = get_session_profile_id()
    record_view(video_id, profile_id=profile_id)
    return jsonify({"success": True})


@rpromo_bp.route("/api/video/<video_id>/like", methods=["POST"])
@login_required
def api_like(video_id):
    profile = get_current_profile()
    if not profile:
        return jsonify({"error": "Not authenticated."}), 401
    r = toggle_like(video_id, profile["id"])
    if not r.get("success"):
        return jsonify({"error": r.get("error", "Like failed.")}), 400
    return jsonify({"success": True, "liked": r.get("liked"), "likes_count": r.get("likes_count")})


def _save_video_file(file_obj, profile_id):
    upload_dir = os.path.join("static", "uploads", "rpromo")
    os.makedirs(upload_dir, exist_ok=True)
    ext = os.path.splitext(file_obj.filename or ".mp4")[1] or ".mp4"
    safe_name = "promo_{}_{}{}".format(profile_id[:8], int(time.time()), ext)
    save_path = os.path.join(upload_dir, safe_name)
    file_obj.save(save_path)
    url = "/" + save_path
    result = {"success": True, "url": url, "thumbnail_url": ""}
    return result
