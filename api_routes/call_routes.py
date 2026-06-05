from flask import Blueprint, flash, redirect, render_template, request, url_for, jsonify
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile, get_profile_by_id
from services.call_service import (
    start_call, answer_call, end_call, list_recent_calls,
    add_participant, record_call_event, update_participant_status
)

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
    return redirect(request.referrer or url_for("messages.inbox"))

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

@call_bp.route("/<call_id>/view")
@login_required
def call_view(call_id):
    profile = get_current_profile()
    from services.supabase_safe import safe_select
    call_rows = safe_select("chain_call_sessions", filters={"id": call_id}, limit=1)
    if not call_rows:
        return redirect(url_for("calls_v2.recent_calls"))
    
    call = call_rows[0]
    role = 'caller' if call['caller_profile_id'] == profile['id'] else 'receiver'
    return render_template("calls/video.html", call=call, profile=profile, role=role)

@call_bp.route("/<call_id>/end", methods=["POST"])
@login_required
def end(call_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return redirect(url_for("calls_v2.recent_calls"))
    end_call(call_id, profile["id"])
    return redirect(url_for("calls_v2.recent_calls"))

@call_bp.route("/api/calls/<call_id>/event", methods=["POST"])
@login_required
def api_event(call_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    event_type = data.get("event_type")
    payload = data.get("payload")
    
    if record_call_event(call_id, profile["id"], event_type, payload):
        return jsonify({"success": True}), 200
    return jsonify({"error": "Failed"}), 400

@call_bp.route("/api/calls/<call_id>/status", methods=["POST"])
@login_required
def api_status(call_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    
    if update_participant_status(call_id, profile["id"], status):
        return jsonify({"success": True}), 200
    return jsonify({"error": "Failed"}), 400
