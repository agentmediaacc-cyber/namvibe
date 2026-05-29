from flask import Blueprint, flash, redirect, render_template, request, url_for
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.status_service import create_status, list_active_statuses

status_bp = Blueprint("status", __name__, url_prefix="/status")

@status_bp.route("/")
def index():
    profile = get_current_profile()
    statuses = list_active_statuses()
    return render_template("status/index.html", statuses=statuses, profile=profile)

@status_bp.route("/stories")
@status_bp.route("/stories/")
def stories_redirect():
    return redirect(url_for("status.index"))

@status_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        from api_routes.profile_routes import _session_profile_stub
        profile = _session_profile_stub()
        if request.method == "POST":
            flash("Profile setup is finishing. Please try again in a moment.", "warning")
            return render_template("status/create.html", profile=profile, setup_warning=True)
        return render_template("status/create.html", profile=profile, setup_warning=True)

    if request.method == "POST":
        caption = request.form.get("caption")
        media_file = request.files.get("media")
        music_file = request.files.get("music")
        
        status = create_status(profile["id"], caption, media_file, music_file)
        if status:
            flash("Status posted successfully!", "success")
            return redirect(url_for("status.index"))
        
        flash("Could not post status.", "error")
        
    return render_template("status/create.html", profile=profile)

@status_bp.route("/<status_id>")
def detail(status_id):
    from services.supabase_safe import safe_select
    status = safe_select("chain_status_posts", filters={"id": status_id}, limit=1)
    if not status:
        return redirect(url_for("status.index"))
    
    return render_template("status/detail.html", status=status[0])
