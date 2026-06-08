from flask import Blueprint, flash, redirect, render_template, request, url_for, jsonify, session
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile, get_profile_by_id, get_lightweight_profile
from engines.cache_engine import cache_key, get_cache, set_cache
from services.logging_service import log_info
from services.call_service import (
    start_call, answer_call, end_call, list_recent_calls,
    add_participant, record_call_event, update_participant_status
)
from services import call_feature_service as phase29_calls
from services.webrtc_call_service import (
    create_call as w_create_call,
    accept_call as w_accept_call,
    reject_call as w_reject_call,
    cancel_call as w_cancel_call,
    end_call as w_end_call,
    get_call as w_get_call,
    get_active_call as w_get_active_call,
    get_call_history as w_get_call_history,
    update_participant_state as w_update_participant_state,
    get_call_participants as w_get_call_participants,
    add_call_event as w_add_call_event,
    invite_participant as w_invite_participant,
    leave_participant as w_leave_participant,
    mark_call_reconnecting as w_mark_call_reconnecting,
    mark_call_failed as w_mark_call_failed,
    get_missed_call_count as w_get_missed_call_count,
    get_call_notifications as w_get_call_notifications,
    mark_notifications_seen as w_mark_notifications_seen,
    get_call_logs as w_get_call_logs,
    get_participants_with_profiles as w_get_participants_with_profiles,
)
from services.webrtc_turn_service import get_webrtc_ice_config

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


# =========== PHASE 40: WebRTC Calling API ===========

@call_bp.route("/api/start", methods=["POST"])
@login_required
def api_webrtc_start():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    receiver_id = data.get("receiver_id")
    thread_id = data.get("thread_id")
    call_type = data.get("call_type", "audio")
    if not receiver_id:
        return jsonify({"ok": False, "error": "receiver_required"}), 400
    result = w_create_call(profile["id"], receiver_id, thread_id=thread_id, call_type=call_type)
    if result.get("ok"):
        return jsonify({"ok": True, "call": result["call"]}), 200
    if result.get("status") == "busy":
        return jsonify({"ok": False, "error": result.get("error", "busy"), "status": "busy"}), 409
    return jsonify({"ok": False, "error": result.get("error", "failed")}), 500


@call_bp.route("/api/<call_id>/accept", methods=["POST"])
@login_required
def api_webrtc_accept(call_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    result = w_accept_call(call_id, profile["id"])
    if result.get("ok"):
        return jsonify({"ok": True, "call": result["call"]}), 200
    return jsonify({"ok": False, "error": result.get("error", "not_found")}), 404


@call_bp.route("/api/<call_id>/reject", methods=["POST"])
@login_required
def api_webrtc_reject(call_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    result = w_reject_call(call_id, profile["id"])
    if result.get("ok"):
        return jsonify({"ok": True, "call": result["call"]}), 200
    return jsonify({"ok": False, "error": result.get("error", "not_found")}), 404


@call_bp.route("/api/<call_id>/cancel", methods=["POST"])
@login_required
def api_webrtc_cancel(call_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    result = w_cancel_call(call_id, profile["id"])
    if result.get("ok"):
        return jsonify({"ok": True, "call": result["call"]}), 200
    return jsonify({"ok": False, "error": result.get("error", "not_found")}), 404


@call_bp.route("/api/<call_id>/end", methods=["POST"])
@login_required
def api_webrtc_end(call_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    result = w_end_call(call_id, profile["id"])
    if result.get("ok"):
        return jsonify({"ok": True, "call": result["call"]}), 200
    return jsonify({"ok": False, "error": result.get("error", "not_found")}), 404


@call_bp.route("/api/<call_id>/mute", methods=["POST"])
@login_required
def api_webrtc_mute(call_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    muted = data.get("muted", True)
    result = w_update_participant_state(call_id, profile["id"], muted=bool(muted))
    w_add_call_event(call_id, profile["id"], "mute_toggle", {"muted": muted})
    return jsonify({"ok": True, "muted": bool(muted)})


@call_bp.route("/api/<call_id>/camera", methods=["POST"])
@login_required
def api_webrtc_camera(call_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    enabled = data.get("enabled", True)
    result = w_update_participant_state(call_id, profile["id"], camera_enabled=bool(enabled))
    w_add_call_event(call_id, profile["id"], "camera_toggle", {"enabled": enabled})
    return jsonify({"ok": True, "camera_enabled": bool(enabled)})


@call_bp.route("/api/<call_id>/speaker", methods=["POST"])
@login_required
def api_webrtc_speaker(call_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    enabled = data.get("enabled", True)
    result = w_update_participant_state(call_id, profile["id"], speaker_enabled=bool(enabled))
    w_add_call_event(call_id, profile["id"], "speaker_toggle", {"enabled": enabled})
    return jsonify({"ok": True, "speaker_enabled": bool(enabled)})


@call_bp.route("/api/active")
@login_required
def api_webrtc_active():
    profile_id = session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    cached = get_cache(cache_key("active_call", profile_id))
    if cached is not None:
        return jsonify({"ok": True, "call": cached})
    active = w_get_active_call(profile_id)
    set_cache(cache_key("active_call", profile_id), active, ttl=10)
    return jsonify({"ok": True, "call": active})


@call_bp.route("/api/history")
@login_required
def api_webrtc_history():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    limit = request.args.get("limit", 50, type=int)
    history = w_get_call_history(profile["id"], limit=limit)
    return jsonify({"ok": True, "history": history})


@call_bp.route("/api/<call_id>")
@login_required
def api_webrtc_get_call(call_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    call = w_get_call(call_id)
    if not call:
        return jsonify({"ok": False, "error": "not_found"}), 404
    participants = w_get_call_participants(call_id)
    return jsonify({"ok": True, "call": call, "participants": participants})


@call_bp.route("/api/ice-servers")
def api_webrtc_ice_servers():
    config = get_webrtc_ice_config()
    return jsonify(config)


# =========== Compat aliases under /messages/api/calls ===========
messages_call_bp = Blueprint("messages_calls_v2", __name__, url_prefix="/messages/api/calls")


@messages_call_bp.route("/start", methods=["POST"])
@login_required
def msg_api_call_start():
    return api_webrtc_start()


@messages_call_bp.route("/<call_id>/accept", methods=["POST"])
@login_required
def msg_api_call_accept(call_id):
    return api_webrtc_accept(call_id)


@messages_call_bp.route("/<call_id>/reject", methods=["POST"])
@login_required
def msg_api_call_reject(call_id):
    return api_webrtc_reject(call_id)


@messages_call_bp.route("/<call_id>/cancel", methods=["POST"])
@login_required
def msg_api_call_cancel(call_id):
    return api_webrtc_cancel(call_id)


@messages_call_bp.route("/<call_id>/end", methods=["POST"])
@login_required
def msg_api_call_end(call_id):
    return api_webrtc_end(call_id)


@messages_call_bp.route("/<call_id>/mute", methods=["POST"])
@login_required
def msg_api_call_mute(call_id):
    return api_webrtc_mute(call_id)


@messages_call_bp.route("/<call_id>/camera", methods=["POST"])
@login_required
def msg_api_call_camera(call_id):
    return api_webrtc_camera(call_id)


@messages_call_bp.route("/<call_id>/speaker", methods=["POST"])
@login_required
def msg_api_call_speaker(call_id):
    return api_webrtc_speaker(call_id)


@messages_call_bp.route("/active", methods=["GET"])
@login_required
def msg_api_call_active():
    return api_webrtc_active()


@messages_call_bp.route("/history", methods=["GET"])
@login_required
def msg_api_call_history():
    return api_webrtc_history()


@messages_call_bp.route("/<call_id>", methods=["GET"])
@login_required
def msg_api_call_get(call_id):
    return api_webrtc_get_call(call_id)


@messages_call_bp.route("/ice-servers")
def msg_api_call_ice_servers():
    return api_webrtc_ice_servers()


# =========== PHASE 41: Mobile Call Reliability Endpoints ===========

@call_bp.route("/api/<call_id>/invite", methods=["POST"])
@login_required
def api_phase41_invite(call_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    target_profile_id = data.get("profile_id")
    if not target_profile_id:
        return jsonify({"ok": False, "error": "profile_id_required"}), 400
    result = w_invite_participant(call_id, profile["id"], target_profile_id)
    if result.get("ok"):
        return jsonify({"ok": True, "call_id": call_id, "profile_id": target_profile_id}), 200
    return jsonify({"ok": False, "error": result.get("error", "invite_failed")}), 400


@call_bp.route("/api/<call_id>/leave", methods=["POST"])
@login_required
def api_phase41_leave(call_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    result = w_leave_participant(call_id, profile["id"])
    return jsonify(result), 200


@call_bp.route("/api/<call_id>/reconnect", methods=["POST"])
@login_required
def api_phase41_reconnect(call_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    result = w_mark_call_reconnecting(call_id, profile["id"])
    return jsonify({"ok": True, "reconnecting": True}), 200


@call_bp.route("/api/<call_id>/failed", methods=["POST"])
@login_required
def api_phase41_failed(call_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "network_error")
    result = w_mark_call_failed(call_id, profile["id"], reason=reason)
    if result.get("ok"):
        return jsonify({"ok": True, "call": result.get("call")}), 200
    return jsonify({"ok": False, "error": result.get("error", "failed")}), 500


@call_bp.route("/api/logs")
@login_required
def api_phase41_logs():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    limit = request.args.get("limit", 50, type=int)
    logs = w_get_call_logs(profile["id"], limit=limit)
    return jsonify({"ok": True, "logs": logs}), 200


@call_bp.route("/api/missed-count")
@login_required
def api_phase41_missed_count():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    count = w_get_missed_call_count(profile["id"])
    return jsonify({"ok": True, "count": count}), 200


@call_bp.route("/api/mark-missed-seen", methods=["POST"])
@login_required
def api_phase41_mark_missed_seen():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    ntype = data.get("notification_type")
    result = w_mark_notifications_seen(profile["id"], notification_type=ntype)
    return jsonify({"ok": True, **result}), 200


@call_bp.route("/api/notifications")
@login_required
def api_phase41_notifications():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    limit = request.args.get("limit", 50, type=int)
    notifs = w_get_call_notifications(profile["id"], limit=limit)
    return jsonify({"ok": True, "notifications": notifs}), 200


@call_bp.route("/api/<call_id>/participants")
@login_required
def api_phase41_participants(call_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    participants = w_get_participants_with_profiles(call_id)
    return jsonify({"ok": True, "participants": participants}), 200
