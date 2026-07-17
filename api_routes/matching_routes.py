from flask import Blueprint, render_template, redirect, url_for, request
from services.matching_service import (
    get_discover_profiles,
    like_target,
    pass_target,
    super_like_target,
    get_matches,
    get_liked_me,
)
from api_routes.profile_routes import login_required

matching_bp = Blueprint("matching", __name__, url_prefix="/matching")


@matching_bp.route("/")
@login_required
def discover():
    profiles, current = get_discover_profiles()
    return render_template("matching/discover.html", profiles=profiles, current=current)


@matching_bp.route("/like/<target_id>", methods=["GET", "POST"])
@login_required
def like(target_id):
    if request.method == "GET":
        return redirect(url_for("matching.discover"))
    ok, result = like_target(target_id)
    if result == "match":
        return redirect(url_for("matching.matches"))
    return redirect(url_for("matching.discover"))

@matching_bp.route("/pass/<target_id>", methods=["GET", "POST"])
@login_required
def pass_profile(target_id):
    if request.method == "GET":
        return redirect(url_for("matching.discover"))
    pass_target(target_id)
    return redirect(url_for("matching.discover"))

@matching_bp.route("/super-like/<target_id>", methods=["GET", "POST"])
@login_required
def super_like(target_id):
    if request.method == "GET":
        return redirect(url_for("matching.discover"))
    super_like_target(target_id)
    return redirect(url_for("matching.discover"))


@matching_bp.route("/matches")
@login_required
def matches():
    profiles, current = get_matches()
    return render_template("matching/matches.html", profiles=profiles, current=current)


@matching_bp.route("/likes")
@login_required
def likes():
    profiles, current = get_liked_me()
    return render_template("matching/likes.html", profiles=profiles, current=current)
