from flask import Blueprint, flash, redirect, render_template, request, url_for, jsonify
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile, get_profile_by_id
from services.call_service import (
    start_call, answer_call, end_call, list_recent_calls,
    add_participant, record_call_event, update_participant_status
)
from services import call_feature_service as phase29_calls

call_bp = Blueprint("calls_v2", __name__, url_prefix="/calls")

@call_bp.route("/recent")
@login_required
def recent_calls():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return render_template("calls/recent.html", calls=[], profile=profile)
    if profile.get("profile_fallback"):
        return render_template("calls/recent.html", calls=[], profile=profile, setup_warning=True)
    calls = phase29_calls.recent_calls(profile["id"]) or list_recent_calls(profile["id"])
    return render_template("calls/recent.html", calls=calls, profile=profile)

@call_bp.route("/start", methods=["POST"])
@login_required
def init_call():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        flash("Profile setup incomplete. Please finish onboarding first.", "error")
        return redirect(url_for("profile.onboarding"))
    if profile.get("profile_fallback"):
        flash("Profile setup incomplete. Please finish onboarding first.", "error")
        return redirect(url_for("profile.onboarding"))
    conversation_id = request.form.get("conversation_id")
    receiver_id = request.form.get("receiver_id")
    call_type = request.form.get("call_type", "video")
    
    result = phase29_calls.start_call(profile["id"], receiver_id, call_type=call_type, conversation_id=conversation_id)
    if result.get("ok"):
        return render_template("calls/video.html", call=result["call"], profile=profile, role='caller')
    if result.get("status") == "busy":
        flash("User is busy on another call.", "error")
        return redirect(request.referrer or url_for("messages.inbox"))
    
    flash("Could not start call.", "error")
    return redirect(request.referrer or url_for("messages.inbox"))

@call_bp.route("/<call_id>/answer", methods=["POST"])
@login_required
def answer(call_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return redirect(url_for("profile.onboarding"))
    result = phase29_calls.answer_call(call_id, profile["id"])
    if not result.get("ok"):
        flash(result.get("error", "Could not answer call."), "error")
        return redirect(url_for("messages.inbox"))
    return render_template("calls/video.html", call=result["call"], profile=profile, role='receiver')

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
    phase29_calls.end_call(call_id, profile["id"])
    return redirect(url_for("calls_v2.recent_calls"))

@call_bp.route("/api/calls/<call_id>/event", methods=["POST"])
@login_required
def api_event(call_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    event_type = data.get("event_type")
    payload = data.get("payload")
    
    if phase29_calls.record_event(call_id, profile["id"], event_type, payload).get("ok"):
        return jsonify({"success": True}), 200
    return jsonify({"error": "Failed"}), 400

@call_bp.route("/api/calls/<call_id>/status", methods=["POST"])
@login_required
def api_status(call_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    
    if status in {"ended", "missed", "rejected"}:
        result = phase29_calls.end_call(call_id, profile["id"], status=status)
    else:
        result = phase29_calls.record_event(call_id, profile["id"], f"status:{status}", {"status": status})
    if result.get("ok"):
        return jsonify({"success": True}), 200
    return jsonify({"error": "Failed"}), 400


@call_bp.route("/api/calls/group", methods=["POST"])
@login_required
def api_group_call():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    if not profile or not profile.get("id"):
        return jsonify({"error": "Profile setup incomplete"}), 400
    result = phase29_calls.start_group_call(profile["id"], data.get("participant_ids") or [], call_type=data.get("call_type", "video"), conversation_id=data.get("conversation_id"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200 if result.get("ok") else 409


@call_bp.route("/api/calls/<call_id>/participants", methods=["POST"])
@login_required
def api_add_participant(call_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    participant_id = data.get("profile_id")
    if not profile or not participant_id:
        return jsonify({"error": "Missing participant"}), 400
    result = phase29_calls.add_participant(call_id, participant_id, data.get("status", "invited"))
    phase29_calls.record_event(call_id, profile["id"], "participant:add", {"profile_id": participant_id})
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@call_bp.route("/api/calls/<call_id>/quality", methods=["POST"])
@login_required
def api_quality_event(call_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_calls.record_quality_event(call_id, (profile or {}).get("id"), data.get("event_type", "quality"), data.get("quality_score"), data.get("payload") or {})
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@call_bp.route("/api/calls/device-settings", methods=["POST"])
@login_required
def api_device_settings():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    result = phase29_calls.save_device_settings(profile["id"], **data)
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@call_bp.route("/api/calls/recording-settings", methods=["POST"])
@login_required
def api_recording_settings():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    result = phase29_calls.save_recording_setting(profile["id"], allow_recording=data.get("allow_recording", False))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@call_bp.route("/api/calls/<call_id>/waiting", methods=["POST"])
@login_required
def api_call_waiting(call_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    result = phase29_calls.record_call_waiting(call_id, profile["id"], data.get("incoming_profile_id"), data.get("payload") or {})
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@call_bp.route("/start/<profile_id>/<call_type>", methods=["GET", "POST"])
@login_required
def start_direct_call_from_profile(profile_id, call_type):
    """
    Start an audio/video call directly from a user profile.
    Creates/reuses a direct message thread first, then starts call session.
    """
    import uuid
    from flask import redirect, flash
    from services.profile_service import get_current_profile
    from services.neon_service import fast_query, write_query
    from services.call_service import start_call

    viewer = get_current_profile()
    if not viewer or not viewer.get("id"):
        return redirect("/auth/login")

    viewer_id = str(viewer["id"])
    target_id = str(profile_id)
    call_type = "audio" if call_type == "audio" else "video"

    if viewer_id == target_id:
        flash("You cannot call yourself.", "info")
        return redirect("/calls/recent")

    # Make sure target exists
    target_rows = fast_query(
        "SELECT id FROM chain_profiles WHERE id = %s AND deleted_at IS NULL LIMIT 1",
        (target_id,),
        default=[]
    )
    if not target_rows:
        flash("Profile not found.", "error")
        return redirect("/calls/recent")

    # Reuse or create direct thread
    existing = fast_query(
        """
        SELECT tm1.thread_id
        FROM chain_thread_members tm1
        JOIN chain_thread_members tm2 ON tm1.thread_id = tm2.thread_id
        JOIN chain_message_threads t ON t.id = tm1.thread_id
        WHERE tm1.profile_id = %s
          AND tm2.profile_id = %s
          AND t.thread_type = 'direct'
        LIMIT 1
        """,
        (viewer_id, target_id),
        default=[]
    )

    if existing:
        thread_id = str(existing[0]["thread_id"])
    else:
        thread_id = str(uuid.uuid4())
        write_query(
            """
            INSERT INTO chain_message_threads
                (id, created_by_profile_id, thread_type, folder_type, created_at, updated_at)
            VALUES
                (%s, %s, 'direct', 'primary', now(), now())
            """,
            (thread_id, viewer_id)
        )
        write_query(
            """
            INSERT INTO chain_thread_members (thread_id, profile_id)
            VALUES (%s, %s), (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (thread_id, viewer_id, thread_id, target_id)
        )

    call = start_call(thread_id, viewer_id, target_id, call_type)
    if not call:
        flash("Could not start call.", "error")
        return redirect("/calls/recent")

    return redirect(f"/calls/{call['id']}/view")


@call_bp.route("/audio/@<username>", methods=["GET", "POST"])
@login_required
def start_direct_audio_by_username(username):
    from flask import redirect, flash
    from services.neon_service import fast_query

    rows = fast_query(
        "SELECT id FROM chain_profiles WHERE username = %s AND deleted_at IS NULL LIMIT 1",
        (username,),
        default=[]
    )
    if not rows:
        flash("Profile not found.", "error")
        return redirect("/calls/recent")
    return redirect(f"/calls/start/{rows[0]['id']}/audio")


@call_bp.route("/video/@<username>", methods=["GET", "POST"])
@login_required
def start_direct_video_by_username(username):
    from flask import redirect, flash
    from services.neon_service import fast_query

    rows = fast_query(
        "SELECT id FROM chain_profiles WHERE username = %s AND deleted_at IS NULL LIMIT 1",
        (username,),
        default=[]
    )
    if not rows:
        flash("Profile not found.", "error")
        return redirect("/calls/recent")
    return redirect(f"/calls/start/{rows[0]['id']}/video")
