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
from services.live_streaming_service import (
    add_participant,
    get_participants,
    get_hosts,
    promote_cohost,
    demote_participant,
    get_gift_catalog,
    send_premium_gift,
    create_raid,
    activate_raid,
    complete_raid,
    cancel_raid,
    get_raids_for_room,
    get_incoming_raids,
    raid_target_options,
    create_goal,
    get_active_goals,
    complete_goal,
    ban_user,
    unban_user,
    is_banned,
    get_bans,
    get_moderators,
    add_moderator,
    get_earnings,
    get_earnings_summary,
    withdraw_earnings,
    get_dashboard_stats,
    get_featured_rooms,
    get_rooms_by_category,
    get_premium_rooms,
    get_room_metadata,
)

live_bp = Blueprint("live", __name__, url_prefix="/live")

# ─── Index / Dashboard ───

@live_bp.route("/")
def live_channels():
    profile = get_current_profile()
    rooms = phase29_live.list_live_rooms(limit=8) or get_live_rooms_public(limit=8, allow_query=False)
    return render_template("live/channels.html", rooms=rooms, profile=profile)

@live_bp.route("/dashboard")
def live_dashboard():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return redirect(url_for("live.live_channels"))
    stats = get_dashboard_stats(profile["id"])
    gift_catalog = get_gift_catalog()
    featured = get_featured_rooms(limit=6)
    return render_template("live/index.html", profile=profile, stats=stats, gift_catalog=gift_catalog, featured=featured)

# ─── Studio ───

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
        add_participant(room["id"], profile["id"], "host")
        return redirect(url_for("live.watch_room", room_id=room["id"]))
    return render_template("live/studio.html", profile=profile)

# ─── Watch / Room ───

@live_bp.route("/room/<room_id>")
def watch_room(room_id):
    profile = get_current_profile()
    room = get_room(room_id)
    if not room:
        return "Live room not found", 404

    phase29_live.join_live(room_id, profile.get("id") if profile else None, request.args.get("name"))
    if profile and profile.get("id"):
        add_participant(room_id, profile["id"], "viewer")

    gift_catalog = safe_select("chain_gift_catalog", filters={"is_active": True}, limit=8, order_by="coin_price", desc=False)
    metadata = get_room_metadata(room_id)
    goals = get_active_goals(room_id)
    return render_template("live/watch.html", room=room, activity=room_activity(room_id), gift_catalog=gift_catalog, profile=profile, metadata=metadata, goals=goals)

@live_bp.route("/room/<room_id>/activity")
def activity(room_id):
    return jsonify(room_activity(room_id))

# ─── Comment ───

@live_bp.route("/room/<room_id>/comment", methods=["POST"])
def comment(room_id):
    profile = get_current_profile()
    if profile and profile.get("id") and is_banned(room_id, profile["id"]):
        return jsonify({"error": "You are banned from this room"}), 403
    phase29_live.comment_live(room_id, (profile or {}).get("id"), request.form.get("body") or request.form.get("comment"), request.form.get("display_name"))
    if request.is_json:
        return jsonify({"status": "ok"})
    return redirect(url_for("live.watch_room", room_id=room_id))

@live_bp.route("/api/live/<room_id>/comment", methods=["POST"])
@login_required
def api_comment(room_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"error": "Unauthorized"}), 401
    if is_banned(room_id, profile["id"]):
        return jsonify({"error": "You are banned from this room"}), 403
    data = request.get_json(silent=True) or {}
    add_comment(room_id, data.get("body"), data.get("display_name"))
    return jsonify({"status": "ok"})

# ─── Gift ───

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

@live_bp.route("/api/live/<room_id>/gift/premium", methods=["POST"])
@login_required
def api_premium_gift(room_id):
    current = get_current_profile()
    if not current or not current.get("id"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    gift_id = data.get("gift_id")
    quantity = int(data.get("quantity", 1))
    if not gift_id:
        return jsonify({"error": "gift_id required"}), 400
    ok, msg = send_premium_gift(room_id, current["id"], gift_id, quantity)
    if ok:
        return jsonify({"success": True, "message": msg}), 200
    return jsonify({"error": msg}), 400

# ─── Co-host ───

@live_bp.route("/room/<room_id>/request-cohost", methods=["POST"])
def cohost_request(room_id):
    request_cohost(room_id, request.form.get("display_name"))
    return jsonify({"status": "requested"})

@live_bp.route("/room/<room_id>/cohost/<request_id>/<status>", methods=["POST"])
def cohost_status(room_id, request_id, status):
    update_cohost_status(request_id, status)
    return jsonify({"status": status})

@live_bp.route("/api/live/<room_id>/cohost/promote", methods=["POST"])
@login_required
def api_promote_cohost(room_id):
    current = get_current_profile()
    if not current or not current.get("id"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    profile_id = data.get("profile_id")
    if not profile_id:
        return jsonify({"error": "profile_id required"}), 400
    ok, msg = promote_cohost(room_id, profile_id, current["id"])
    if ok:
        return jsonify({"success": True, "message": msg}), 200
    return jsonify({"error": msg}), 400

@live_bp.route("/api/live/<room_id>/participant/demote", methods=["POST"])
@login_required
def api_demote_participant(room_id):
    current = get_current_profile()
    if not current or not current.get("id"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    profile_id = data.get("profile_id")
    if not profile_id:
        return jsonify({"error": "profile_id required"}), 400
    ok, msg = demote_participant(room_id, profile_id, current["id"])
    if ok:
        return jsonify({"success": True, "message": msg}), 200
    return jsonify({"error": msg}), 400

@live_bp.route("/api/live/<room_id>/participants")
def api_participants(room_id):
    participants = get_participants(room_id)
    return jsonify({"participants": participants})

# ─── End ───

@live_bp.route("/room/<room_id>/end", methods=["GET", "POST"])
def end(room_id):
    phase29_live.end_live(room_id, (get_current_profile() or {}).get("id"))
    return redirect(url_for("live.live_channels"))

# ─── React ───

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

# ─── Guest Requests ───

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

# ─── Polls ───

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

# ─── Battles ───

@live_bp.route("/api/live/<room_id>/battle", methods=["POST"])
@login_required
def api_battle(room_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_live.create_battle(room_id, host_profile_id=profile["id"], challenger_room_id=data.get("challenger_room_id"), challenger_profile_id=data.get("challenger_profile_id"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200

# ─── Moderation ───

@live_bp.route("/api/live/<room_id>/moderation", methods=["POST"])
@login_required
def api_moderation(room_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_live.moderation_action(room_id, profile["id"], data.get("action_type", "mute"), data.get("target_profile_id"), data.get("reason"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200

@live_bp.route("/api/live/<room_id>/ban", methods=["POST"])
@login_required
def api_ban_user(room_id):
    current = get_current_profile()
    if not current or not current.get("id"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    profile_id = data.get("profile_id")
    if not profile_id:
        return jsonify({"error": "profile_id required"}), 400
    result = ban_user(room_id, profile_id, current["id"], data.get("reason"), int(data.get("duration_minutes", 0)))
    return jsonify({"success": bool(result)}), 200

@live_bp.route("/api/live/<room_id>/unban", methods=["POST"])
@login_required
def api_unban_user(room_id):
    data = request.get_json(silent=True) or {}
    profile_id = data.get("profile_id")
    if not profile_id:
        return jsonify({"error": "profile_id required"}), 400
    unban_user(room_id, profile_id)
    return jsonify({"success": True}), 200

@live_bp.route("/api/live/<room_id>/bans")
@login_required
def api_bans(room_id):
    bans = get_bans(room_id)
    return jsonify({"bans": bans}), 200

@live_bp.route("/api/live/<room_id>/moderators")
def api_moderators(room_id):
    mods = get_moderators(room_id)
    return jsonify({"moderators": mods}), 200

@live_bp.route("/api/live/<room_id>/moderator/add", methods=["POST"])
@login_required
def api_add_moderator(room_id):
    current = get_current_profile()
    if not current or not current.get("id"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    profile_id = data.get("profile_id")
    if not profile_id:
        return jsonify({"error": "profile_id required"}), 400
    ok, msg = add_moderator(room_id, profile_id, current["id"])
    if ok:
        return jsonify({"success": True, "message": msg}), 200
    return jsonify({"error": msg}), 400

# ─── Replay ───

@live_bp.route("/api/live/<room_id>/replay", methods=["POST"])
@login_required
def api_replay(room_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_live.save_replay(room_id, profile["id"], data.get("replay_url"), data.get("duration_seconds", 0), **(data.get("metadata") or {}))
    return jsonify({"success": bool(result.get("ok")), **result}), 200

# ─── Clip ───

@live_bp.route("/api/live/<room_id>/clip", methods=["POST"])
@login_required
def api_clip(room_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_live.create_clip(room_id, profile["id"], data.get("clip_url"), data.get("start_seconds", 0), data.get("duration_seconds", 0), data.get("title"), **(data.get("metadata") or {}))
    return jsonify({"success": bool(result.get("ok")), **result}), 200

# ─── Shopping ───

@live_bp.route("/api/live/<room_id>/shopping", methods=["POST"])
@login_required
def api_shopping(room_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_live.add_shopping_item(room_id, profile["id"], data.get("title") or "Live item", data.get("price_coins", 0), data.get("url"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200

# ─── Leaderboard ───

@live_bp.route("/api/live/<room_id>/leaderboard", methods=["POST"])
@login_required
def api_leaderboard(room_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_live.upsert_leaderboard(room_id, data.get("profile_id") or profile["id"], data.get("score", 0), data.get("rank"), **(data.get("metadata") or {}))
    return jsonify({"success": bool(result.get("ok")), **result}), 200

# ─── Stream Settings ───

@live_bp.route("/api/live/<room_id>/stream-settings", methods=["POST"])
@login_required
def api_stream_settings(room_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_live.save_stream_settings(room_id, profile["id"], **data)
    return jsonify({"success": bool(result.get("ok")), **result}), 200

# ─── Raids ───

@live_bp.route("/api/live/<room_id>/raid", methods=["POST"])
@login_required
def api_create_raid(room_id):
    current = get_current_profile()
    if not current or not current.get("id"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    target_room_id = data.get("target_room_id")
    if not target_room_id:
        return jsonify({"error": "target_room_id required"}), 400
    viewer_count = int(data.get("viewer_count", 0))
    result = create_raid(room_id, target_room_id, current["id"], viewer_count)
    return jsonify({"success": bool(result), "raid": result}), 200

@live_bp.route("/api/live/<room_id>/raids")
def api_raids(room_id):
    raids = get_raids_for_room(room_id)
    incoming = get_incoming_raids(room_id)
    return jsonify({"raids": raids, "incoming": incoming}), 200

@live_bp.route("/api/live/raid/<raid_id>/activate", methods=["POST"])
@login_required
def api_activate_raid(raid_id):
    activate_raid(raid_id)
    return jsonify({"success": True}), 200

@live_bp.route("/api/live/raid/<raid_id>/complete", methods=["POST"])
@login_required
def api_complete_raid(raid_id):
    complete_raid(raid_id)
    return jsonify({"success": True}), 200

@live_bp.route("/api/live/raid/<raid_id>/cancel", methods=["POST"])
@login_required
def api_cancel_raid(raid_id):
    cancel_raid(raid_id)
    return jsonify({"success": True}), 200

@live_bp.route("/api/live/raid/targets/<room_id>")
def api_raid_targets(room_id):
    targets = raid_target_options(room_id)
    return jsonify({"targets": targets}), 200

# ─── Goals ───

@live_bp.route("/api/live/<room_id>/goals", methods=["GET"])
def api_get_goals(room_id):
    goals = get_active_goals(room_id)
    return jsonify({"goals": goals}), 200

@live_bp.route("/api/live/<room_id>/goals", methods=["POST"])
@login_required
def api_create_goal(room_id):
    current = get_current_profile()
    if not current or not current.get("id"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    title = data.get("title", "Stream Goal")
    target = float(data.get("target_amount", 100))
    goal_type = data.get("goal_type", "gifts")
    result = create_goal(room_id, title, target, goal_type)
    return jsonify({"success": bool(result), "goal": result}), 200

@live_bp.route("/api/live/goal/<goal_id>/complete", methods=["POST"])
@login_required
def api_complete_goal(goal_id):
    complete_goal(goal_id)
    return jsonify({"success": True}), 200

# ─── Earnings ───

@live_bp.route("/api/live/earnings")
@login_required
def api_earnings():
    current = get_current_profile()
    if not current or not current.get("id"):
        return jsonify({"error": "Unauthorized"}), 401
    earnings = get_earnings(current["id"])
    summary = get_earnings_summary(current["id"])
    return jsonify({"earnings": earnings, "summary": summary}), 200

@live_bp.route("/api/live/earnings/withdraw", methods=["POST"])
@login_required
def api_withdraw_earnings():
    current = get_current_profile()
    if not current or not current.get("id"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    amount = float(data.get("amount", 0))
    if amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400
    ok, msg = withdraw_earnings(current["id"], amount)
    if ok:
        return jsonify({"success": True, "message": msg}), 200
    return jsonify({"error": msg}), 400

# ─── Gift Catalog ───

@live_bp.route("/api/gift-catalog")
def api_gift_catalog():
    catalog = get_gift_catalog()
    return jsonify({"catalog": catalog}), 200

# ─── Dashboard Stats ───

@live_bp.route("/api/dashboard")
@login_required
def api_dashboard():
    current = get_current_profile()
    if not current or not current.get("id"):
        return jsonify({"error": "Unauthorized"}), 401
    stats = get_dashboard_stats(current["id"])
    return jsonify(stats), 200

# ─── Featured / Discovery ───

@live_bp.route("/api/featured")
def api_featured():
    rooms = get_featured_rooms(limit=6)
    return jsonify({"rooms": rooms}), 200

@live_bp.route("/api/category/<category>")
def api_category(category):
    rooms = get_rooms_by_category(category)
    return jsonify({"rooms": rooms}), 200

@live_bp.route("/api/premium-rooms")
def api_premium_rooms():
    rooms = get_premium_rooms()
    return jsonify({"rooms": rooms}), 200

@live_bp.route("/api/room/<room_id>/metadata")
def api_room_metadata(room_id):
    metadata = get_room_metadata(room_id)
    if not metadata:
        return jsonify({"error": "Room not found"}), 404
    return jsonify(metadata), 200

# ─── Stats ───

@live_bp.route("/api/stats")
def api_stats():
    rooms = get_live_rooms(limit=100)
    total_viewers = sum(r.get("viewer_count", 0) or 0 for r in rooms)
    total_gifts = sum(r.get("gift_total", 0) or 0 for r in rooms)
    return jsonify({"total_viewers": total_viewers, "total_rooms": len(rooms), "total_gifts": total_gifts})
