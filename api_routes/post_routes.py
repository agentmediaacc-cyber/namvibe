from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.post_service import create_post
from services.content_service import save_media_file

post_bp = Blueprint("posts", __name__, url_prefix="/posts")
media_bp = Blueprint("media_uploads", __name__, url_prefix="/media")

@post_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    profile = get_current_profile()
    if not profile and session.get("profile_id"):
        profile = {
            "id": session.get("profile_id"),
            "username": session.get("username"),
            "full_name": session.get("full_name") or session.get("username") or "CHAIN user",
            "avatar_url": session.get("avatar_url"),
        }
    if request.method == "POST":
        caption = request.form.get("caption") or request.form.get("body") or ""
        media_file = request.files.get("media")
        link_url = request.form.get("link_url") or ""
        town_tag = request.form.get("town_tag") or request.form.get("location") or ""
        visibility = request.form.get("visibility") or "public"
        
        if not caption.strip() and not (media_file and media_file.filename) and not link_url.strip():
            flash("Post cannot be empty.")
            return render_template("posts/create.html", profile=profile)
            
        post, error = create_post(profile["id"], caption, media_file, link_url=link_url, town_tag=town_tag, visibility=visibility)
        if error:
            flash(error)
            return render_template("posts/create.html", profile=profile)
            
        return redirect(url_for("profile.my_profile"))
        
    return render_template("posts/create.html", profile=profile)


@media_bp.route("/upload", methods=["POST"])
@login_required
def upload_media():
    profile = get_current_profile()
    if not profile and session.get("profile_id"):
        profile = {"id": session.get("profile_id")}
    if not profile or not profile.get("id"):
        return jsonify({"success": False, "error": "Profile not found."}), 404
    upload_type = request.form.get("upload_type") or "post"
    media_kind = request.form.get("media_kind") or None
    media_file = request.files.get("media")
    media, error = save_media_file(media_file, upload_type, media_kind=media_kind, profile_id=profile["id"])
    if error:
        return jsonify({"success": False, "error": error}), 400
    return jsonify({"success": True, "media": media}), 201
