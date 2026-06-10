import uuid
from datetime import datetime
import os
from flask import Blueprint, flash, redirect, render_template, request, url_for, session, jsonify
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.messaging_engine import (
    list_threads, get_thread, send_message_realtime, 
    get_or_create_direct_thread, mark_thread_seen, set_typing,
    add_reaction, remove_reaction, delete_message, 
    pin_thread, archive_thread, mute_thread, search_messages,
    move_thread, get_stickers
)
from services.neon_service import fast_query, write_query
from services.rate_limit_service import limiter, user_or_ip_key
from services.supabase_safe import safe_insert
from services import message_feature_service as phase29_messages
from services.thread_security_service import can_access_thread
from services import group_feature_service as phase29_groups
from services.relationship_gate_service import can_message, can_call, is_mutual_follow, relationship_status
from services.socketio_service import emit_to_profile

message_bp = Blueprint("messages", __name__, url_prefix="/messages")

@message_bp.route("/")
@login_required
def inbox():
    profile = get_current_profile()
    folder = request.args.get('folder', 'primary')
    if not profile or not profile.get("id"):
        return render_template("messages/index.html", threads=[], profile=profile, setup_warning=True)
    if profile.get("profile_fallback"):
        return render_template("messages/index.html", threads=[], profile=profile, active_folder=folder, setup_warning=True)
    threads = list_threads(profile["id"], folder=folder)
    return render_template("messages/index.html", threads=threads, profile=profile, active_folder=folder)

@message_bp.route("/thread/<thread_id>")
@message_bp.route("/<thread_id>")
@login_required
def thread_view(thread_id):
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return redirect(url_for("messages.inbox"))
    
    thread = get_thread(thread_id, profile["id"])
    if not thread:
        return redirect(url_for("messages.inbox"))
    
    mark_thread_seen(thread_id, profile["id"])
    return render_template("messages/thread.html", thread=thread, profile=profile)

@message_bp.route("/api/messages/threads")
@login_required
def api_threads():
    profile = get_current_profile()
    folder = request.args.get('folder', 'primary')
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify([]), 200
    if (profile or {}).get("profile_fallback"):
        return jsonify([]), 200
    threads = list_threads(profile_id, folder=folder)
    return jsonify(threads), 200

@message_bp.route("/api/messages/search")
@login_required
def api_search():
    profile = get_current_profile()
    query = request.args.get("q")
    if not profile or not query:
        return jsonify([]), 200
    results = phase29_messages.search_messages(profile["id"], query)
    return jsonify(results), 200

@message_bp.route("/api/messages/<thread_id>")
@login_required
def api_thread(thread_id):
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"error": "Profile setup incomplete"}), 400
    thread = get_thread(thread_id, profile_id)
    if not thread:
        return jsonify({"error": "Thread not found"}), 404
    return jsonify(thread), 200

@message_bp.route("/api/messages/send", methods=["POST"])
@login_required
@limiter.limit("60/minute", key_func=user_or_ip_key)
def api_send():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"error": "Profile setup incomplete"}), 400
    # Premium chat must stay non-blocking when the session already has a
    # profile id but a full profile lookup is slow or unavailable.
    data = request.get_json(silent=True) or {}
    
    thread_id = request.form.get("thread_id") or data.get("thread_id")
    body = request.form.get("body") or data.get("body")
    media_file = request.files.get("media") or request.files.get("file") or request.files.get("attachment")
    client_message_id = request.form.get("client_message_id") or data.get("client_message_id")
    parent_message_id = request.form.get("parent_message_id") or data.get("parent_message_id")
    is_forwarded = request.form.get("is_forwarded") == 'true' or data.get("is_forwarded", False)
    status_id = request.form.get("status_id") or data.get("status_id")
    
    # Dedup check
    if client_message_id:
        from services.neon_service import fast_query
        existing = fast_query(
            "SELECT id, delivery_status FROM chain_messages WHERE sender_profile_id = %s AND client_message_id = %s LIMIT 1",
            (profile_id, client_message_id), default=[]
        )
        if existing:
            return jsonify({"success": True, "id": str(existing[0]["id"]), "delivery_status": existing[0].get("delivery_status", "sent"), "duplicate": True}), 200
    
    # Premium Fields
    sticker_id = request.form.get("sticker_id") or data.get("sticker_id")
    gif_url = request.form.get("gif_url") or data.get("gif_url")
    location = data.get("location")
    contact = data.get("contact")

    body = (body or "").strip()
    if not body and not media_file and not sticker_id and not gif_url and not location and not contact:
        return jsonify({"error": "Message cannot be empty"}), 400
    if not thread_id:
        return jsonify({"error": "Thread is required"}), 400

    from services.neon_service import fast_query as _mq
    other_member = _mq(
        "SELECT profile_id FROM chain_thread_members WHERE thread_id = %s AND profile_id != %s LIMIT 1",
        (thread_id, profile_id), default=[]
    )
    if other_member:
        gate = relationship_status(profile_id, other_member[0]["profile_id"])
        if not gate.get("can_message"):
            return jsonify({"error": gate.get("error", "Cannot send message")}), 403

    if media_file:
        from services.messaging_engine import send_message
        result = send_message(
            thread_id, profile_id, body, media_file,
            client_message_id=client_message_id,
            parent_message_id=parent_message_id,
            is_forwarded=is_forwarded,
            status_id=status_id,
            sticker_id=sticker_id,
            gif_url=gif_url,
            location=location,
            contact=contact
        )
        if result and result.get("success"):
            return jsonify({"success": True, **result}), 200
        return jsonify(result or {"error": "Failed to send message"}), 400

    result = phase29_messages.send_text_message(
        thread_id,
        profile_id,
        body,
        client_event_id=client_message_id,
        parent_message_id=parent_message_id,
        is_forwarded=is_forwarded,
    )
    if result and result.get("ok"):
        return jsonify({"success": True, **result}), 200
    return jsonify(result or {"error": "Failed to send message"}), 400




@message_bp.route("/api/stickers")
@login_required
def api_stickers():
    return jsonify(get_stickers()), 200

@message_bp.route("/api/threads/<thread_id>/move", methods=["POST"])
@login_required
def api_move(thread_id):
    data = request.get_json(silent=True) or {}
    folder = data.get("folder", "primary")
    if move_thread(thread_id, folder):
        return jsonify({"success": True}), 200
    return jsonify({"error": "Failed"}), 400

@message_bp.route("/api/messages/<message_id>/reaction", methods=["POST"])
@login_required
def api_reaction(message_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    reaction_type = data.get("reaction") or request.form.get("reaction")
    action = data.get("action", "add")
    
    if not profile or not reaction_type:
        return jsonify({"error": "Missing data"}), 400
        
    if action == "add":
        phase29_messages.add_reaction(message_id, profile["id"], reaction_type)
    else:
        remove_reaction(message_id, profile["id"], reaction_type)
        
    return jsonify({"success": True}), 200




@message_bp.route("/api/messages/<message_id>/delete", methods=["POST"])
@login_required
def api_delete_msg(message_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    for_everyone = data.get("for_everyone", False)
    
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
        
    result = phase29_messages.delete_message(message_id, profile["id"], for_everyone=for_everyone)
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/messages/<message_id>/delete-for-me", methods=["POST"])
@login_required
def api_delete_for_me(message_id):
    profile_id = session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "success": False, "error": "Unauthorized"}), 401
    result = phase29_messages.delete_message(message_id, profile_id, for_everyone=False)
    return jsonify({"ok": bool(result.get("ok")), "success": bool(result.get("ok")), **result}), 200 if result.get("ok") else 400


@message_bp.route("/api/messages/<message_id>/info", methods=["GET"])
@login_required
def api_message_info(message_id):
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    result = phase29_messages.get_message_info(message_id, profile_id)
    return jsonify(result), 200


@message_bp.route("/api/messages/<message_id>/edit", methods=["POST"])
@login_required
def api_edit_msg(message_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    body = data.get("body") or request.form.get("body")
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    result = phase29_messages.edit_message(message_id, profile["id"], body)
    return jsonify({"success": bool(result.get("ok")), **result}), 200 if result.get("ok") else 400


@message_bp.route("/api/messages/<message_id>/star", methods=["POST"])
@login_required
def api_star_msg(message_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    starred = data.get("starred", True)
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    result = phase29_messages.star_message(message_id, profile["id"], starred=starred)
    return jsonify({"success": True, **result}), 200


@message_bp.route("/api/messages/<message_id>/pin", methods=["POST"])
@login_required
def api_pin_msg(message_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    result = phase29_messages.pin_message(message_id, profile["id"], pinned=data.get("pinned", True))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/messages/forward", methods=["POST"])
@login_required
def api_forward_messages():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    result = phase29_messages.forward_messages(profile["id"], data.get("message_ids") or [], data.get("to_thread_ids") or [])
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/messages/multi-select", methods=["POST"])
@login_required
def api_multi_select_messages():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    result = phase29_messages.multi_select_action(profile["id"], data.get("message_ids") or [], data.get("action"), to_thread_ids=data.get("to_thread_ids") or [])
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/threads/<thread_id>/draft", methods=["POST"])
@login_required
def api_thread_draft(thread_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    result = phase29_messages.save_draft(thread_id, profile["id"], data.get("body") or "", attachments=data.get("attachments"), voice_note=data.get("voice_note"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/threads/<thread_id>/schedule", methods=["POST"])
@login_required
def api_schedule_message(thread_id):
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    data = request.get_json(silent=True) or {}
    if not profile_id:
        return jsonify({"error": "Unauthorized"}), 401
    if not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    result = phase29_messages.schedule_message(thread_id, profile_id, data.get("body") or "", data.get("scheduled_for"), message_type=data.get("message_type", "text"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/threads/<thread_id>/wallpaper", methods=["POST"])
@login_required
def api_thread_wallpaper(thread_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    result = phase29_messages.save_wallpaper(thread_id, profile["id"], data.get("wallpaper_key"), data.get("wallpaper_url"), **(data.get("settings") or {}))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/threads/<thread_id>/shared")
@login_required
def api_shared_items(thread_id):
    return jsonify(phase29_messages.list_shared_items(thread_id, request.args.get("type"))), 200


@message_bp.route("/api/threads/<thread_id>/shared", methods=["POST"])
@login_required
def api_save_shared_item(thread_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    result = phase29_messages.save_shared_item(thread_id, data.get("message_id"), profile["id"], data.get("item_type", "link"), title=data.get("title"), url=data.get("url"), mime_type=data.get("mime_type"), metadata=data.get("metadata") or {})
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/settings/autodownload", methods=["POST"])
@login_required
def api_autodownload_settings():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    result = phase29_messages.save_autodownload_settings(profile["id"], **data)
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/threads/<thread_id>/encryption", methods=["POST"])
@login_required
def api_encryption_status(thread_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_messages.save_encryption_status(thread_id, (profile or {}).get("id"), data.get("status", "transport_protected"), provider=data.get("provider", "chain"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/threads/<thread_id>/voice-draft", methods=["POST"])
@login_required
def api_voice_draft(thread_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    result = phase29_messages.save_voice_note_draft(thread_id, profile["id"], **data)
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/messages/<message_id>/voice", methods=["POST"])
@login_required
def api_voice_metadata(message_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    result = phase29_messages.save_voice_note(message_id, profile["id"], audio_url=data.get("audio_url"), duration_seconds=data.get("duration_seconds"), waveform=data.get("waveform"), mime_type=data.get("mime_type"), file_size=data.get("file_size"), playback_speed=data.get("playback_speed"), draft_state=data.get("draft_state"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/messages/<message_id>/voice/playback", methods=["POST"])
@login_required
def api_voice_playback(message_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    if not profile:
        return jsonify({"error": "Unauthorized"}), 401
    result = phase29_messages.save_voice_playback_state(message_id, profile["id"], data.get("playback_speed", 1), data.get("played", False), data.get("position_seconds", 0))
    return jsonify({"success": bool(result.get("ok")), **result}), 200

@message_bp.route("/api/threads/<thread_id>/pin", methods=["POST"])
@login_required
def api_pin(thread_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    pinned = data.get("pinned", True)
    if pin_thread(thread_id, profile["id"], pinned):
        return jsonify({"success": True}), 200
    return jsonify({"error": "Failed"}), 400

@message_bp.route("/api/threads/<thread_id>/archive", methods=["POST"])
@login_required
def api_archive(thread_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    archived = data.get("archived", True)
    if archive_thread(thread_id, profile["id"], archived):
        return jsonify({"success": True}), 200
    return jsonify({"error": "Failed"}), 400

@message_bp.route("/api/threads/<thread_id>/mute", methods=["POST"])
@login_required
def api_mute(thread_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    muted = data.get("muted", True)
    if mute_thread(thread_id, profile["id"], muted):
        return jsonify({"success": True}), 200
    return jsonify({"error": "Failed"}), 400

@message_bp.route("/api/block", methods=["POST"])
@login_required
def api_block():
    from services.profile_service import block_profile
    current = get_current_profile()
    if not current:
        return jsonify({"error": "Not authenticated"}), 400
    data = request.get_json(silent=True) or {}
    username = data.get("username") or data.get("target") or data.get("user")
    if not username:
        return jsonify({"error": "Username required"}), 400
    blocked = block_profile(username)
    if blocked:
        return jsonify({"success": True, "message": "User blocked"}), 200
    return jsonify({"error": "Failed to block user"}), 400

@message_bp.route("/api/messages/<thread_id>/seen", methods=["POST"])
@login_required
def api_seen(thread_id):
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"success": False}), 400
    phase29_messages.mark_seen(thread_id, profile_id)
    return jsonify({"success": True}), 200





@message_bp.route("/api/messages/<thread_id>/delivered", methods=["POST"])
@login_required
def api_delivered(thread_id):
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"success": False}), 400
    result = phase29_messages.mark_delivered(thread_id, profile_id)
    return jsonify({"success": True, **result}), 200

@message_bp.route("/api/group/create", methods=["POST"])
@login_required
def api_group_create():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"error": "Profile setup incomplete"}), 400
    name = request.form.get("name") or (request.get_json(silent=True) or {}).get("name")
    visibility = request.form.get("visibility") or (request.get_json(silent=True) or {}).get("visibility") or "public"
    result = phase29_groups.create_group(profile_id, name or "New Group", visibility=visibility)
    group = result["group"]
    thread_result = phase29_messages.create_direct_thread(profile_id, profile_id)
    thread_id = thread_result.get("thread_id") or group["id"]
    return jsonify({"success": True, "group": group, "thread_id": thread_id, "invite_link": result.get("invite_link")}), 201


@message_bp.route("/api/groups/<group_id>/join", methods=["POST"])
@login_required
def api_group_join(group_id):
    profile = get_current_profile()
    result = phase29_groups.join_public_group(group_id, profile["id"])
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/groups/<group_id>/request", methods=["POST"])
@login_required
def api_group_request(group_id):
    profile = get_current_profile()
    result = phase29_groups.request_join(group_id, profile["id"])
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/groups/<group_id>/post", methods=["POST"])
@login_required
def api_group_post(group_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or request.form
    result = phase29_groups.create_group_post(group_id, profile["id"], data.get("body"), post_type=data.get("post_type", "message"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/groups/<group_id>/roles", methods=["POST"])
@login_required
def api_group_role(group_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_groups.set_role(group_id, data.get("profile_id") or profile["id"], data.get("role", "member"), profile["id"])
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/groups/<group_id>/announcement", methods=["POST"])
@login_required
def api_group_announcement(group_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_groups.create_announcement(group_id, profile["id"], data.get("title"), data.get("body"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/groups/<group_id>/advert", methods=["POST"])
@login_required
def api_group_advert(group_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_groups.create_advert(group_id, profile["id"], data.get("title"), data.get("body"), data.get("media_url"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/groups/<group_id>/analytics", methods=["POST"])
@login_required
def api_group_analytics(group_id):
    data = request.get_json(silent=True) or {}
    result = phase29_groups.record_analytics(group_id, data.get("metric_name", "activity"), data.get("metric_value", 0), **(data.get("metadata") or {}))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/groups/<group_id>/verification", methods=["POST"])
@login_required
def api_group_verification(group_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_groups.request_group_verification(group_id, profile["id"], data.get("note"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/groups/<group_id>/live", methods=["POST"])
@login_required
def api_group_live(group_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_groups.create_group_live_room(group_id, profile["id"], data.get("title"), data.get("room_id"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/groups/<group_id>/reel", methods=["POST"])
@login_required
def api_group_reel(group_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_groups.create_group_reel(group_id, profile["id"], data.get("caption"), data.get("reel_id"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/api/groups/<group_id>/marketplace", methods=["POST"])
@login_required
def api_group_marketplace(group_id):
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = phase29_groups.create_marketplace_item(group_id, profile["id"], data.get("title") or "Group item", data.get("description"), data.get("price_coins", 0))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@message_bp.route("/start/<profile_id>", methods=["GET", "POST"])
@login_required
def start_direct_message_from_profile(profile_id):
    """
    Create or open a direct message thread between current user and target profile.
    Used by profile Message buttons.
    """
    import uuid
    from flask import redirect, url_for, flash
    from services.profile_service import get_current_profile
    from services.neon_service import fast_query, write_query

    viewer = get_current_profile()
    if not viewer or not viewer.get("id"):
        return redirect("/auth/login")

    viewer_id = str(viewer["id"])
    target_id = str(profile_id)

    if viewer_id == target_id:
        flash("You cannot message yourself.", "info")
        return redirect("/messages/")

    # Make sure target exists
    target_rows = fast_query(
        "SELECT id FROM chain_profiles WHERE id = %s AND deleted_at IS NULL LIMIT 1",
        (target_id,),
        default=[]
    )
    if not target_rows:
        flash("Profile not found.", "error")
        return redirect("/messages/")

    # Reuse existing direct thread between both users
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
        return redirect(f"/messages/{existing[0]['thread_id']}")

    # Create new direct thread
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

    return redirect(f"/messages/{thread_id}")


@message_bp.route("/@<username>", methods=["GET", "POST"])
@login_required
def start_direct_message_by_username(username):
    from flask import redirect, flash
    from services.neon_service import fast_query

    rows = fast_query(
        "SELECT id FROM chain_profiles WHERE username = %s AND deleted_at IS NULL LIMIT 1",
        (username,),
        default=[]
    )
    if not rows:
        flash("Profile not found.", "error")
        return redirect("/messages/")
    return redirect(f"/messages/start/{rows[0]['id']}")


# =========== CALL + MESSAGE SCALE HARDENING ===========

@message_bp.route("/api/retry/<message_id>", methods=["POST"])
@login_required
def api_retry_message(message_id):
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    from services.message_delivery_service import retry_message
    result = retry_message(message_id, profile_id)
    if result.get("ok"):
        return jsonify({"ok": True, "message": result["message"]}), 200
    return jsonify({"ok": False, "error": result.get("error", "retry_failed")}), 400


# =========== PHASE 53 — PREMIUM MESSAGING ===========

def _session_profile_id():
    profile = get_current_profile()
    return (profile or {}).get("id") or session.get("profile_id")


def _message_thread_id_for_access(message_id):
    return phase29_messages.message_thread_id(message_id)


@message_bp.route("/api/messages/<message_id>/transcribe", methods=["POST"])
@login_required
def api_transcribe(message_id):
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    thread_id = _message_thread_id_for_access(message_id)
    if thread_id and not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    result = phase29_messages.transcribe_voice_note(message_id, profile_id)
    return jsonify(result), 200

@message_bp.route("/api/messages/send-hd", methods=["POST"])
@login_required
def api_send_hd():
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    thread_id = data.get("thread_id")
    media_url = data.get("media_url")
    quality = data.get("quality", "standard")
    file_size = data.get("file_size", 0)
    file_name = data.get("file_name", "")
    if not thread_id or not media_url:
        return jsonify({"ok": False, "error": "thread_id and media_url required"}), 400
    if not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    result = phase29_messages.send_hd_media(thread_id, profile_id, media_url, quality, file_size, file_name)
    return jsonify(result), 200

@message_bp.route("/api/poll/create", methods=["POST"])
@login_required
def api_poll_create():
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    thread_id = data.get("thread_id")
    question = data.get("question")
    options = data.get("options", [])
    if not thread_id or not question or len(options) < 2:
        return jsonify({"ok": False, "error": "thread_id, question, and at least 2 options required"}), 400
    if not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    result = phase29_messages.create_poll(thread_id, profile_id, question, options, data.get("allow_multiple", False))
    return jsonify(result), 200

@message_bp.route("/api/poll/<poll_id>/vote", methods=["POST"])
@login_required
def api_poll_vote(poll_id):
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    option_id = data.get("option_id")
    if not option_id:
        return jsonify({"ok": False, "error": "option_id required"}), 400
    thread_id = phase29_messages.get_poll_thread_id(poll_id)
    if not thread_id or not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    result = phase29_messages.vote_poll(poll_id, option_id, profile_id)
    return jsonify(result), 200

@message_bp.route("/api/poll/<poll_id>/results", methods=["GET"])
@login_required
def api_poll_results(poll_id):
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    thread_id = phase29_messages.get_poll_thread_id(poll_id)
    if not thread_id or not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    result = phase29_messages.get_poll_results(poll_id)
    return jsonify(result), 200

@message_bp.route("/api/location/share", methods=["POST"])
@login_required
def api_location_share():
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    thread_id = data.get("thread_id")
    lat = data.get("latitude")
    lng = data.get("longitude")
    duration = data.get("duration_minutes", 15)
    if not thread_id or lat is None or lng is None:
        return jsonify({"ok": False, "error": "thread_id, latitude, longitude required"}), 400
    if not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    result = phase29_messages.share_live_location(thread_id, profile_id, lat, lng, duration)
    return jsonify(result), 200

@message_bp.route("/api/location/stop", methods=["POST"])
@login_required
def api_location_stop():
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    share_id = data.get("share_id")
    if not share_id:
        return jsonify({"ok": False, "error": "share_id required"}), 400
    if not phase29_messages.verify_location_owner(share_id, profile_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    result = phase29_messages.stop_live_location(share_id, profile_id)
    return jsonify(result), 200

@message_bp.route("/api/thread/<thread_id>/disappearing", methods=["POST"])
@login_required
def api_disappearing(thread_id):
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    if not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    data = request.get_json(silent=True) or {}
    timer_seconds = data.get("timer_seconds", 0)
    result = phase29_messages.set_disappearing_timer(thread_id, profile_id, timer_seconds)
    return jsonify(result), 200

@message_bp.route("/api/thread/<thread_id>/disappearing/settings", methods=["GET"])
@login_required
def api_disappearing_settings(thread_id):
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    if not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    result = phase29_messages.get_disappearing_settings(thread_id)
    return jsonify(result), 200

@message_bp.route("/api/chat/ai/summarize", methods=["POST"])
@login_required
def api_ai_summarize():
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    thread_id = data.get("thread_id")
    if not thread_id:
        return jsonify({"ok": False, "error": "thread_id required"}), 400
    if not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    result = phase29_messages.ai_summarize(thread_id, profile_id)
    return jsonify(result), 200

@message_bp.route("/api/chat/ai/find-important", methods=["POST"])
@login_required
def api_ai_find_important():
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    thread_id = data.get("thread_id")
    if not thread_id:
        return jsonify({"ok": False, "error": "thread_id required"}), 400
    if not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    result = phase29_messages.ai_find_important(thread_id, profile_id)
    return jsonify(result), 200

@message_bp.route("/api/chat/ai/suggest-reply", methods=["POST"])
@login_required
def api_ai_suggest_reply():
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    thread_id = data.get("thread_id")
    context = data.get("context", "")
    if not thread_id:
        return jsonify({"ok": False, "error": "thread_id required"}), 400
    if not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    result = phase29_messages.ai_suggest_reply(thread_id, profile_id, context)
    return jsonify(result), 200

@message_bp.route("/api/chat/ai/translate", methods=["POST"])
@login_required
def api_ai_translate():
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    message_id = data.get("message_id")
    target = data.get("target_language", "en")
    if not message_id:
        return jsonify({"ok": False, "error": "message_id required"}), 400
    thread_id = _message_thread_id_for_access(message_id)
    if thread_id and not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    result = phase29_messages.ai_translate(message_id, target)
    return jsonify(result), 200

@message_bp.route("/api/chat/ai/unread-summary", methods=["POST"])
@login_required
def api_ai_unread_summary():
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    thread_id = data.get("thread_id")
    if not thread_id:
        return jsonify({"ok": False, "error": "thread_id required"}), 400
    if not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    result = phase29_messages.ai_summarize_unread(thread_id, profile_id)
    return jsonify(result), 200

@message_bp.route("/api/wallet/send", methods=["POST"])
@login_required
def api_wallet_send():
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    thread_id = data.get("thread_id")
    if not thread_id or not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    result = phase29_messages.wallet_send(
        thread_id, profile_id, data.get("recipient_profile_id"),
        data.get("amount"), data.get("note", ""))
    return jsonify(result), 200

@message_bp.route("/api/wallet/request", methods=["POST"])
@login_required
def api_wallet_request():
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    thread_id = data.get("thread_id")
    if not thread_id or not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    result = phase29_messages.wallet_request(
        thread_id, profile_id, data.get("recipient_profile_id"),
        data.get("amount"), data.get("note", ""))
    return jsonify(result), 200

@message_bp.route("/api/wallet/tip", methods=["POST"])
@login_required
def api_wallet_tip():
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    thread_id = data.get("thread_id")
    if not thread_id or not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    result = phase29_messages.wallet_tip(
        thread_id, profile_id, data.get("recipient_profile_id"),
        data.get("amount"), data.get("note", ""))
    return jsonify(result), 200

@message_bp.route("/api/wallet/split", methods=["POST"])
@login_required
def api_wallet_split():
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    thread_id = data.get("thread_id")
    if not thread_id or not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    result = phase29_messages.wallet_split(
        thread_id, profile_id, data.get("amount"), data.get("participants"))
    return jsonify(result), 200

@message_bp.route("/api/thread/<thread_id>/search", methods=["GET"])
@login_required
def api_thread_search(thread_id):
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    if not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    query = request.args.get("q", "")
    result = phase29_messages.search_thread_messages(thread_id, profile_id, query)
    return jsonify(result), 200


@message_bp.route("/api/threads/<thread_id>/scheduled", methods=["GET"])
@login_required
def api_scheduled_list(thread_id):
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    if not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    return jsonify(phase29_messages.list_scheduled_messages(thread_id, profile_id)), 200


@message_bp.route("/api/scheduled/<scheduled_id>/edit", methods=["POST"])
@login_required
def api_scheduled_edit(scheduled_id):
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    result = phase29_messages.update_scheduled_message(
        scheduled_id,
        profile_id,
        scheduled_for=data.get("scheduled_for"),
        body=data.get("body"),
    )
    return jsonify(result), 200


@message_bp.route("/api/scheduled/<scheduled_id>/cancel", methods=["POST"])
@login_required
def api_scheduled_cancel(scheduled_id):
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    result = phase29_messages.cancel_scheduled_message(scheduled_id, profile_id, data.get("reason", "cancelled_by_sender"))
    return jsonify(result), 200


@message_bp.route("/api/messages/<message_id>/share/<surface>", methods=["POST"])
@login_required
def api_share_message_surface(message_id, surface):
    profile_id = _session_profile_id()
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    thread_id = _message_thread_id_for_access(message_id)
    if thread_id and not can_access_thread(profile_id, thread_id):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    return jsonify(phase29_messages.share_message_to_surface(message_id, profile_id, surface)), 200

@message_bp.route("/api/debug/inbox")
@login_required
def api_debug_inbox():
    profile = get_current_profile()
    diag = {
        "profile_id": str(profile.get("id")) if profile else None,
        "thread_count": 0,
        "folder": request.args.get('folder', 'primary'),
        "timestamp": datetime.utcnow().isoformat(),
        "duplicate_check": None,
    }
    if profile and profile.get("id"):
        profile_id = profile["id"]
        from services.neon_service import fast_query
        rows = fast_query(
            "SELECT t.id, t.thread_type, t.folder_type, COUNT(*) as member_count, "
            "(SELECT COUNT(*) FROM chain_thread_members tm2 WHERE tm2.thread_id = t.id) as total_members "
            "FROM chain_message_threads t "
            "JOIN chain_thread_members tm ON t.id = tm.thread_id "
            "WHERE tm.profile_id = %s AND t.deleted_at IS NULL "
            "GROUP BY t.id ORDER BY t.updated_at DESC LIMIT 30",
            (profile_id,), default=[]
        )
        diag["threads"] = rows
        diag["thread_count"] = len(rows)
        # Check for duplicate threads (same pair of users)
        dup_check = fast_query(
            "SELECT array_agg(t.id) as thread_ids, array_agg(t.updated_at::text) as updated_ats, "
            "string_agg(DISTINCT p1.id::text, ',') as members "
            "FROM chain_message_threads t "
            "JOIN chain_thread_members tm1 ON t.id = tm1.thread_id AND tm1.profile_id = %s "
            "JOIN chain_thread_members tm2 ON t.id = tm2.thread_id AND tm2.profile_id != %s "
            "JOIN chain_profiles p1 ON tm2.profile_id = p1.id "
            "WHERE t.thread_type = 'direct' AND t.deleted_at IS NULL "
            "GROUP BY t.id HAVING COUNT(DISTINCT tm2.profile_id) = 1",
            (profile_id, profile_id), default=[]
        )
        diag["duplicate_check"] = {
            "total_direct": len(dup_check),
            "note": "Check if multiple threads exist for the same conversation partner"
        }
    return jsonify(diag), 200


@message_bp.route("/api/socket-diagnostics")
@login_required
def api_socket_diagnostics():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    diag = {
        "redis_configured": bool(os.environ.get("REDIS_URL") or os.environ.get("REDIS_TLS_URL")),
        "socket_rate_limits": len(getattr(__import__('services.socket_events', fromlist=['_SOCKET_RATE_LIMITS']), '_SOCKET_RATE_LIMITS', {})),
        "timestamp": datetime.utcnow().isoformat(),
    }
    return jsonify({"ok": True, "diagnostics": diag}), 200


@message_bp.route("/api/relationship/<profile_id>")
@login_required
def api_relationship_status(profile_id):
    current = get_current_profile()
    current_id = (current or {}).get("id") or session.get("profile_id")
    if not current_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    rs = relationship_status(current_id, profile_id)
    return jsonify({"ok": True, "status": rs}), 200


@message_bp.route("/api/thread/<profile_id>")
@login_required
def api_get_or_create_thread(profile_id):
    current = get_current_profile()
    current_id = (current or {}).get("id") or session.get("profile_id")
    if not current_id:
        return jsonify({"error": "unauthorized"}), 401
    if current_id == profile_id:
        return jsonify({"error": "Cannot start thread with yourself"}), 400
    gate = relationship_status(current_id, profile_id)
    if not gate.get("can_message"):
        return jsonify({"error": gate.get("error", "Cannot message this user"), "status": gate.get("status")}), 403
    thread_id = get_or_create_direct_thread(current_id, profile_id)
    if thread_id:
        return jsonify({"id": thread_id}), 200
    return jsonify({"error": "Could not create thread"}), 500


@message_bp.route("/api/threads/start", methods=["POST"])
@login_required
def api_start_thread():
    current = get_current_profile()
    current_id = (current or {}).get("id") or session.get("profile_id")
    if not current_id:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    target_profile_id = data.get("profile_id") or data.get("target_id")
    if not target_profile_id:
        return jsonify({"error": "profile_id required"}), 400
    if current_id == target_profile_id:
        return jsonify({"error": "Cannot start thread with yourself"}), 400
    gate = relationship_status(current_id, target_profile_id)
    if not gate.get("can_message"):
        return jsonify({"error": gate.get("error", "Cannot message this user"), "status": gate.get("status")}), 403
    if gate.get("needs_request"):
        req_resp = fast_query(
            """SELECT id, status FROM chain_message_requests WHERE from_profile_id = %s AND to_profile_id = %s LIMIT 1""",
            (current_id, target_profile_id), default=[]
        )
        if not req_resp or req_resp[0].get("status") != "pending":
            return jsonify({"ok": False, "needs_request": True, "message": "Send a message request first"}), 403
    thread_id = get_or_create_direct_thread(current_id, target_profile_id)
    if thread_id:
        return jsonify({"thread_id": thread_id}), 200
    return jsonify({"error": "Could not create thread"}), 500


@message_bp.route("/api/friends")
@login_required
def api_friends():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    friends = fast_query(
        """
        SELECT p.id, p.username, p.full_name, p.avatar_url,
               p.is_verified, p.bio, p.is_online
        FROM chain_follows f1
        JOIN chain_follows f2
            ON f1.follower_profile_id = f2.following_profile_id
           AND f1.following_profile_id = f2.follower_profile_id
        JOIN chain_profiles p ON f1.following_profile_id = p.id
        WHERE f1.follower_profile_id = %s
        ORDER BY p.is_online DESC, p.full_name ASC
        """,
        (profile_id,), default=[]
    )
    return jsonify({"ok": True, "friends": friends}), 200


@message_bp.route("/api/message-request/send", methods=["POST"])
@login_required
def api_send_message_request():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    to_profile_id = data.get("to_profile_id")
    message_body = (data.get("body") or "").strip()
    if not to_profile_id:
        return jsonify({"ok": False, "error": "recipient_required"}), 400
    if profile_id == to_profile_id:
        return jsonify({"ok": False, "error": "Cannot send request to yourself"}), 400

    gate = can_message(profile_id, to_profile_id)
    if not gate.get("ok"):
        return jsonify({"ok": False, "error": gate.get("error", "Cannot message")}), 403

    existing = fast_query(
        "SELECT id, status FROM chain_message_requests WHERE from_profile_id = %s AND to_profile_id = %s LIMIT 1",
        (profile_id, to_profile_id), default=[]
    )
    if existing:
        existing_status = existing[0]["status"]
        if existing_status == "pending":
            return jsonify({"ok": False, "error": "Request already pending"}), 409
        if existing_status == "accepted":
            return jsonify({"ok": True, "message": "Already connected"}), 200
        write_query(
            "UPDATE chain_message_requests SET status = 'pending', updated_at = now() WHERE id = %s",
            (existing[0]["id"],)
        )
        request_id = existing[0]["id"]
    else:
        request_id = str(uuid.uuid4())
        write_query(
            "INSERT INTO chain_message_requests (id, from_profile_id, to_profile_id, status, message_body, created_at, updated_at) VALUES (%s, %s, %s, 'pending', %s, now(), now())",
            (request_id, profile_id, to_profile_id, message_body)
        )

    try:
        sender = fast_query(
            "SELECT username, full_name FROM chain_profiles WHERE id = %s LIMIT 1",
            (profile_id,), default=[]
        )
        sender_name = sender[0].get("full_name") or sender[0].get("username") if sender else "Someone"
        emit_to_profile(to_profile_id, "message_request:new", {
            "request_id": request_id,
            "from_profile_id": profile_id,
            "from_name": sender_name,
        })
    except Exception:
        pass

    return jsonify({"ok": True, "request_id": request_id}), 200


@message_bp.route("/api/message-requests/inbox")
@login_required
def api_message_request_inbox():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    requests = fast_query(
        """
        SELECT mr.id, mr.from_profile_id, mr.status, mr.message_body, mr.created_at,
               p.username, p.full_name, p.avatar_url, p.online_status, p.is_verified
        FROM chain_message_requests mr
        JOIN chain_profiles p ON mr.from_profile_id = p.id
        WHERE mr.to_profile_id = %s AND mr.status = 'pending'
        ORDER BY mr.created_at DESC
        """,
        (profile_id,), default=[]
    )
    return jsonify({"ok": True, "requests": requests}), 200


@message_bp.route("/api/message-requests/<request_id>/accept", methods=["POST"])
@login_required
def api_accept_message_request(request_id):
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    req = fast_query(
        "SELECT * FROM chain_message_requests WHERE id = %s AND to_profile_id = %s LIMIT 1",
        (request_id, profile_id), default=[]
    )
    if not req:
        return jsonify({"ok": False, "error": "Request not found"}), 404
    if req[0]["status"] != "pending":
        return jsonify({"ok": False, "error": "Request already processed"}), 400

    from_profile_id = req[0]["from_profile_id"]
    thread_id = str(uuid.uuid4())
    try:
        write_query(
            "INSERT INTO chain_message_threads (id, created_by_profile_id, thread_type, folder_type, created_at, updated_at) VALUES (%s, %s, 'direct', 'primary', now(), now())",
            (thread_id, profile_id),
        )
        write_query(
            "INSERT INTO chain_thread_members (thread_id, profile_id) VALUES (%s, %s), (%s, %s)",
            (thread_id, profile_id, thread_id, from_profile_id),
        )
        write_query(
            "UPDATE chain_message_requests SET status = 'accepted', thread_id = %s, updated_at = now() WHERE id = %s",
            (thread_id, request_id),
        )
        return jsonify({"ok": True, "thread_id": thread_id}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@message_bp.route("/api/message-requests/<request_id>/decline", methods=["POST"])
@login_required
def api_decline_message_request(request_id):
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    req = fast_query(
        "SELECT id FROM chain_message_requests WHERE id = %s AND to_profile_id = %s LIMIT 1",
        (request_id, profile_id), default=[]
    )
    if not req:
        return jsonify({"ok": False, "error": "Request not found"}), 404
    write_query(
        "UPDATE chain_message_requests SET status = 'declined', updated_at = now() WHERE id = %s",
        (request_id,)
    )
    return jsonify({"ok": True}), 200
