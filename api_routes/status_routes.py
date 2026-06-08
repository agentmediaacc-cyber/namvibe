from flask import Blueprint, flash, redirect, render_template, request, url_for, session, jsonify
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.status_service import create_status, list_active_statuses, get_status, delete_status, record_view, list_viewers
from services.content_service import get_session_profile_id, session_profile_stub

status_bp = Blueprint("status", __name__, url_prefix="/status")

@status_bp.route("/")
def index():
    profile = get_current_profile()
    statuses = list_active_statuses(viewer_profile_id=(profile.get("id") if profile else None))
    return render_template("status/index.html", statuses=statuses, profile=profile)

@status_bp.route("/stories")
@status_bp.route("/stories/")
def stories_redirect():
    return redirect(url_for("status.index"))

@status_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        profile_id = get_session_profile_id()
        profile = session_profile_stub() if profile_id else None
        if not profile_id:
            return redirect(url_for("auth.login", next=request.path))
        caption = request.form.get("caption")
        media_file = request.files.get("media")
        visibility = request.form.get("visibility") or "public"
        media_type = request.form.get("media_type", "image")
        
        status = create_status(profile_id, caption, media_file, visibility=visibility, media_type=media_type)
        if status:
            flash("Status posted successfully!", "success")
            return redirect(url_for("status.index"))
        
        flash("Could not post status.", "error")

    profile = get_current_profile() or (session_profile_stub() if get_session_profile_id() else None)
    if not profile or not profile.get("id"):
        from api_routes.profile_routes import _session_profile_stub
        profile = _session_profile_stub()
        return render_template("status/create.html", profile=profile, setup_warning=True)

    return render_template("status/create.html", profile=profile)

@status_bp.route("/<status_id>")
def detail(status_id):
    status = get_status(status_id)
    if not status:
        return redirect(url_for("status.index"))
    
    profile = get_current_profile()
    if profile and profile.get("id"):
        record_view(status_id, profile["id"])
        
    can_delete = bool(profile and profile.get("id") == status.get("profile_id"))
    viewers = list_viewers(status_id) if can_delete else []
    
    return render_template("status/detail.html", status=status, profile=profile, can_delete=can_delete, viewers=viewers)


@status_bp.route("/<status_id>/delete", methods=["POST"])
@login_required
def delete(status_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        flash("Profile not found.", "error")
        return redirect(url_for("status.index"))
    if delete_status(status_id, profile["id"]):
        flash("Story deleted.", "success")
    else:
        flash("Story could not be deleted.", "error")
    return redirect(url_for("status.index"))

@status_bp.route("/api/status/create", methods=["POST"])
@login_required
def api_create():
    profile_id = get_session_profile_id()
    if not profile_id:
        return jsonify({"error": "Unauthorized"}), 401
    
    caption = request.form.get("caption")
    media_file = request.files.get("media")
    visibility = request.form.get("visibility", "public")
    media_type = request.form.get("media_type", "image")
    
    status = create_status(profile_id, caption, media_file, visibility=visibility, media_type=media_type)
    if status:
        return jsonify({"success": True, "status_id": status["id"]}), 201
    return jsonify({"error": "Failed to create"}), 400
