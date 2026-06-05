from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.moderation_engine import (
    report_entity, block_profile, mute_profile, 
    restrict_profile, unrestrict_profile, is_restricted
)
from services.neon_service import fast_query, write_query

safety_bp = Blueprint("safety", __name__, url_prefix="/safety")

@safety_bp.route("/")
@login_required
def index():
    profile = get_current_profile()
    return render_template("safety/index.html", profile=profile)

@safety_bp.route("/blocked")
@login_required
def blocked_users():
    profile = get_current_profile()
    # Fetch blocked users
    sql = """
        SELECT p.id, p.username, p.full_name, p.avatar_url
        FROM chain_blocks b
        JOIN chain_profiles p ON b.blocked_profile_id = p.id
        WHERE b.blocker_profile_id = %s AND b.deleted_at IS NULL
    """
    blocked = fast_query(sql, (profile["id"],))
    return render_template("safety/blocked.html", profile=profile, blocked=blocked)

@safety_bp.route("/unblock/<target_id>", methods=["POST"])
@login_required
def unblock_user(target_id):
    profile = get_current_profile()
    sql = "UPDATE chain_blocks SET deleted_at = now() WHERE blocker_profile_id = %s AND blocked_profile_id = %s"
    write_query(sql, (profile["id"], target_id))
    flash("User unblocked", "success")
    return redirect(url_for("safety.blocked_users"))

@safety_bp.route("/reports")
@login_required
def my_reports():
    profile = get_current_profile()
    sql = """
        SELECT r.*, p.username as target_username
        FROM chain_reports r
        LEFT JOIN chain_profiles p ON r.target_profile_id = p.id
        WHERE r.reporter_profile_id = %s
        ORDER BY r.created_at DESC
    """
    reports = fast_query(sql, (profile["id"],))
    return render_template("safety/reports.html", profile=profile, reports=reports)

@safety_bp.route("/privacy")
@login_required
def privacy_settings():
    profile = get_current_profile()
    # Fetch privacy settings from chain_profiles or a dedicated table if exists
    # For now, let's assume they are in chain_profiles as suggested by the prompt
    return render_template("safety/privacy.html", profile=profile)

@safety_bp.route("/privacy/update", methods=["POST"])
@login_required
def update_privacy():
    profile = get_current_profile()
    # Update privacy settings
    who_can_message = request.form.get("who_can_message")
    who_can_call = request.form.get("who_can_call")
    who_can_see_status = request.form.get("who_can_see_status")
    
    sql = """
        UPDATE chain_profiles 
        SET who_can_message = %s, who_can_call = %s, who_can_see_status = %s 
        WHERE id = %s
    """
    write_query(sql, (who_can_message, who_can_call, who_can_see_status, profile["id"]))
    flash("Privacy settings updated", "success")
    return redirect(url_for("safety.privacy_settings"))

@safety_bp.route("/restrict/<target_id>", methods=["POST"])
@login_required
def restrict(target_id):
    profile = get_current_profile()
    restrict_profile(profile["id"], target_id)
    return jsonify({"success": True})

@safety_bp.route("/unrestrict/<target_id>", methods=["POST"])
@login_required
def unrestrict(target_id):
    profile = get_current_profile()
    unrestrict_profile(profile["id"], target_id)
    return jsonify({"success": True})
