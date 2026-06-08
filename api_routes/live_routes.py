from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from services.live_service import (
    create_live_room,
    get_live_rooms,
    get_live_rooms_public,
    get_room,
    join_room,
    room_activity,
    add_comment,
    send_gift,
    end_live,
    request_cohost,
    get_cohost_requests,
    update_cohost_status,
    prime_live_rooms_public_cache,
)
from services.realtime_service import track_live_reaction
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.push_notification_service import queue_push_event
from services.supabase_safe import safe_select
from services import live_feature_service as phase29_live

live_bp = Blueprint("live", __name__, url_prefix="/live")

@live_bp.route("/api/react/<room_id>", methods=["POST"])
@login_required
def react_api(room_id):
    current = get_current_profile()
    if not current or not current.get("id"):
        return jsonify({"error": "Profile setup incomplete"}), 400
    data = request.json or {}
    r_type = data.get("type", "heart")
    track_live_reaction(room_id, current["id"], r_type)
    return jsonify({"status": "ok"})


@live_bp.route("/")
def live_channels():
    profile = get_current_profile()
    rooms = phase29_live.list_live_rooms(limit=8) or get_live_rooms_public(limit=8, allow_query=False)
    return render_template("live/channels.html", rooms=rooms, profile=profile)


@live_bp.route("/studio", methods=["GET", "POST"])
@login_required
def studio():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        from api_routes.profile_routes import _session_profile_stub
        profile = _session_profile_stub()
        return render_template("live/studio.html", profile=profile, setup_warning=True)

    if request.method == "POST":
        room_result = phase29_live.start_live(profile["id"], request.form.get("title"), host_name=profile.get("full_name") or profile.get("username"), allow_comments=request.form.get("allow_comments", "on") != "off")
        room = room_result.get("room") if room_result.get("ok") else create_live_room(request.form, request.files)
        if not room:
            return render_template("live/studio.html", profile=profile, error="We could not save this live room with the current Supabase schema.")
        return redirect(url_for("live.watch_room", room_id=room["id"]))
    return render_template("live/studio.html", profile=profile)


@live_bp.route("/room/<room_id>")
def watch_room(room_id):
    profile = get_current_profile()
    room = get_room(room_id)
    if not room:
        return "Live room not found", 404

    phase29_live.join_live(room_id, profile.get("id") if profile else None, request.args.get("name"))
    gift_catalog = safe_select("chain_gift_catalog", filters={"is_active": True}, limit=8, order_by="coin_price", desc=False)
    return render_template("live/watch.html", room=room, activity=room_activity(room_id), gift_catalog=gift_catalog, profile=profile)


@live_bp.route("/room/<room_id>/activity")
def activity(room_id):
    return jsonify(room_activity(room_id))


@live_bp.route("/room/<room_id>/request-cohost", methods=["POST"])
def cohost_request(room_id):
    request_cohost(room_id, request.form.get("display_name"))
    return jsonify({"status": "requested"})


@live_bp.route("/room/<room_id>/cohost/<request_id>/<status>", methods=["POST"])
def cohost_status(room_id, request_id, status):
    update_cohost_status(request_id, status)
    return jsonify({"status": status})


@live_bp.route("/room/<room_id>/comment", methods=["POST"])
def comment(room_id):
    phase29_live.comment_live(room_id, (get_current_profile() or {}).get("id"), request.form.get("body") or request.form.get("comment"), request.form.get("display_name"))
    return redirect(url_for("live.watch_room", room_id=room_id))


@live_bp.route("/room/<room_id>/gift", methods=["POST"])
def gift(room_id):
    send_gift(
        room_id,
        request.form.get("gift_icon") or request.form.get("emoji"),
        request.form.get("gift_name"),
        request.form.get("amount") or request.form.get("coins"),
        request.form.get("display_name"),
    )
    return redirect(url_for("live.watch_room", room_id=room_id))


@live_bp.route("/api/live/<room_id>/gift", methods=["POST"])
@login_required
def api_live_gift(room_id):
    current = get_current_profile()
    if not current or not current.get("id"):
        return jsonify({"error": "Profile setup incomplete"}), 400
    gift_type = request.form.get("gift_type")
    coin_value = request.form.get("coin_value", 0)
    
    from services.wallet_engine import send_gift as send_wallet_gift
    room = get_room(room_id)
    if not room:
        return jsonify({"error": "Room not found"}), 404
        
    ok, error = send_wallet_gift(
        sender_profile_id=current['id'],
        receiver_profile_id=room['profile_id'],
        gift_type=gift_type,
        coin_value=coin_value,
        entity_type='live_room',
        entity_id=room_id
    )
    
    if ok:
        return jsonify({"success": True}), 200
    return jsonify({"error": error}), 400


@live_bp.route("/room/<room_id>/end", methods=["GET", "POST"])
def end(room_id):
    phase29_live.end_live(room_id, (get_current_profile() or {}).get("id"))
    return redirect(url_for("live.live_channels"))


@live_bp.route("/api/live/<room_id>/guest-request", methods=["POST"])
@login_required
def api_guest_request(room_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or request.form
    result = phase29_live.request_guest(room_id, profile["id"], data.get("note"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@live_bp.route("/api/live/guest-request/<request_id>", methods=["POST"])
@login_required
def api_guest_request_status(request_id):
    data = request.get_json(silent=True) or request.form
    result = phase29_live.update_guest_request(request_id, data.get("status", "pending"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@live_bp.route("/api/live/<room_id>/poll", methods=["POST"])
@login_required
def api_create_poll(room_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_live.create_poll(room_id, profile["id"], data.get("question") or "Live poll", data.get("options") or [])
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@live_bp.route("/api/live/poll/<poll_id>/vote", methods=["POST"])
@login_required
def api_vote_poll(poll_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_live.vote_poll(poll_id, profile["id"], data.get("option"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@live_bp.route("/api/live/<room_id>/battle", methods=["POST"])
@login_required
def api_battle(room_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_live.create_battle(room_id, host_profile_id=profile["id"], challenger_room_id=data.get("challenger_room_id"), challenger_profile_id=data.get("challenger_profile_id"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@live_bp.route("/api/live/<room_id>/moderation", methods=["POST"])
@login_required
def api_moderation(room_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_live.moderation_action(room_id, profile["id"], data.get("action_type", "mute"), data.get("target_profile_id"), data.get("reason"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@live_bp.route("/api/live/<room_id>/replay", methods=["POST"])
@login_required
def api_replay(room_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_live.save_replay(room_id, profile["id"], data.get("replay_url"), data.get("duration_seconds", 0), **(data.get("metadata") or {}))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@live_bp.route("/api/live/<room_id>/clip", methods=["POST"])
@login_required
def api_clip(room_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_live.create_clip(room_id, profile["id"], data.get("clip_url"), data.get("start_seconds", 0), data.get("duration_seconds", 0), data.get("title"), **(data.get("metadata") or {}))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@live_bp.route("/api/live/<room_id>/shopping", methods=["POST"])
@login_required
def api_shopping(room_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_live.add_shopping_item(room_id, profile["id"], data.get("title") or "Live item", data.get("price_coins", 0), data.get("url"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@live_bp.route("/api/live/<room_id>/leaderboard", methods=["POST"])
@login_required
def api_leaderboard(room_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_live.upsert_leaderboard(room_id, data.get("profile_id") or profile["id"], data.get("score", 0), data.get("rank"), **(data.get("metadata") or {}))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@live_bp.route("/api/live/<room_id>/stream-settings", methods=["POST"])
@login_required
def api_stream_settings(room_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_live.save_stream_settings(room_id, profile["id"], **data)
    return jsonify({"success": bool(result.get("ok")), **result}), 200
