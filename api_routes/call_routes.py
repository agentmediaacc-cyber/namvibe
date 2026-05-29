from flask import Blueprint, flash, redirect, render_template, request, url_for
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile, get_profile_by_id
from services.call_service import start_call, answer_call, end_call, list_recent_calls

call_bp = Blueprint("calls_v2", __name__, url_prefix="/calls")

@call_bp.route("/recent")
@login_required
def recent_calls():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return render_template("calls/recent.html", calls=[], profile=profile)
    calls = list_recent_calls(profile["id"])
    return render_template("calls/recent.html", calls=calls, profile=profile)

@call_bp.route("/start", methods=["POST"])
@login_required
def init_call():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        flash("Profile setup incomplete. Please finish onboarding first.", "error")
        return redirect(url_for("profile.onboarding"))
    conversation_id = request.form.get("conversation_id")
    receiver_id = request.form.get("receiver_id")
    call_type = request.form.get("call_type", "video")
    
    call = start_call(conversation_id, profile["id"], receiver_id, call_type)
    if call:
        return render_template("calls/video.html", call=call, profile=profile, role='caller')
    
    flash("Could not start call.", "error")
    return redirect(request.referrer or url_for("chat_v2.inbox"))

@call_bp.route("/<call_id>/answer", methods=["POST"])
@login_required
def answer(call_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return redirect(url_for("profile.onboarding"))
    call, err = answer_call(call_id, profile["id"])
    if err:
        flash(err, "error")
        return redirect(url_for("messages.inbox"))
    
    return render_template("calls/video.html", call=call, profile=profile, role='receiver')

@call_bp.route("/<call_id>/end", methods=["POST"])
@login_required
def end(call_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return redirect(url_for("calls_v2.recent_calls"))
    end_call(call_id, profile["id"])
    return redirect(url_for("calls_v2.recent_calls"))
