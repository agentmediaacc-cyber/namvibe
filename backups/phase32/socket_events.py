from datetime import datetime, timezone

from flask import request, session
from flask_socketio import emit, join_room, leave_room

from services.messaging_engine import (
    acknowledge_delivery,
    clear_expired_typing_statuses,
    get_thread,
    mark_thread_seen,
    reconnect_sync as sync_thread_messages,
    recover_thread_messages,
    send_message,
    add_reaction,
    remove_reaction,
    delete_message,
    pin_thread,
    archive_thread,
    mute_thread
)
from services.presence_engine import heartbeat, set_offline, set_online, set_typing
from services.profile_service import get_current_profile
from services.redis_service import (
    delete_key,
    get_json,
    publish,
    set_add,
    set_json,
    set_members,
    set_remove,
)
from services.socketio_service import emit_to_live_room, emit_to_profile, emit_to_thread, live_room, profile_room, socketio, thread_room
from services.wallet_engine import send_gift
from services import message_feature_service as phase30_messages
from services import call_feature_service as phase30_calls


_SOCKET_STATE_TTL_SECONDS = 180
_EVENT_DEDUPE_TTL_SECONDS = 120


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def _get_profile_id():
    if "auth_user_id" not in session:
        return None
    profile = get_current_profile()
    return profile["id"] if profile else None


def _socket_state_key(profile_id):
    return f"socket_state:{profile_id}"


def _socket_event_key(event_name, event_id):
    return f"socket_event:{event_name}:{event_id}"


def _mark_socket_event(event_name, event_id):
    if not event_id:
        return False
    key = _socket_event_key(event_name, event_id)
    if get_json(key):
        return False
    set_json(key, {"seen_at": _utcnow_iso()}, ttl=_EVENT_DEDUPE_TTL_SECONDS)
    return True


def _ignore_duplicate_event(event_name, payload, fallback_key):
    event_id = (payload or {}).get("event_id") or (payload or {}).get("client_event_id") or fallback_key
    return not _mark_socket_event(event_name, event_id)


def _track_joined_room(profile_id, room_name):
    state = get_json(_socket_state_key(profile_id), default={"rooms": []}) or {"rooms": []}
    rooms = set(state.get("rooms") or [])
    rooms.add(room_name)
    set_json(_socket_state_key(profile_id), {"rooms": sorted(rooms), "updated_at": _utcnow_iso()}, ttl=_SOCKET_STATE_TTL_SECONDS)


def _track_left_room(profile_id, room_name):
    state = get_json(_socket_state_key(profile_id), default={"rooms": []}) or {"rooms": []}
    rooms = set(state.get("rooms") or [])
    rooms.discard(room_name)
    set_json(_socket_state_key(profile_id), {"rooms": sorted(rooms), "updated_at": _utcnow_iso()}, ttl=_SOCKET_STATE_TTL_SECONDS)


def _recover_rooms(profile_id):
    state = get_json(_socket_state_key(profile_id), default={"rooms": []}) or {"rooms": []}
    return list(state.get("rooms") or [])


def _record_sid(profile_id):
    if not profile_id:
        return
    set_add(f"profile_sids:{profile_id}", request.sid, ttl=_SOCKET_STATE_TTL_SECONDS)


def _clear_sid(profile_id):
    if not profile_id:
        return
    set_remove(f"profile_sids:{profile_id}", request.sid)


@socketio.on("connect")
def handle_connect():
    profile_id = _get_profile_id()
    if profile_id:
        join_room(profile_room(profile_id))
        set_online(profile_id)
        _record_sid(profile_id)
        for room_name in _recover_rooms(profile_id):
            join_room(room_name)
        emit("socket:recovered", {"rooms": _recover_rooms(profile_id), "sid": request.sid, "success": True})
        print(f"[socket] Profile {profile_id} connected")
    else:
        print("[socket] Anonymous client connected")


@socketio.on("join_profile")
def handle_join_profile(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"joined": False}
    room_name = profile_room(profile_id)
    join_room(room_name)
    _track_joined_room(profile_id, room_name)
    return {"joined": True, "room": room_name}


@socketio.on("disconnect")
def handle_disconnect():
    profile_id = _get_profile_id()
    if profile_id:
        _clear_sid(profile_id)
        if not set_members(f"profile_sids:{profile_id}"):
            set_offline(profile_id)
            delete_key(_socket_state_key(profile_id))
        print(f"[socket] Profile {profile_id} disconnected")


@socketio.on("room:join")
def handle_room_join(data):
    profile_id = _get_profile_id()
    room_name = (data or {}).get("room")
    event_id = (data or {}).get("event_id")
    if not profile_id or not room_name or not _mark_socket_event("room:join", event_id or f"{profile_id}:{room_name}"):
        return {"joined": False}
    join_room(room_name)
    _track_joined_room(profile_id, room_name)
    return {"joined": True, "room": room_name}


@socketio.on("room:leave")
def handle_room_leave(data):
    profile_id = _get_profile_id()
    room_name = (data or {}).get("room")
    event_id = (data or {}).get("event_id")
    if not room_name or (event_id and not _mark_socket_event("room:leave", event_id)):
        return {"left": False}
    leave_room(room_name)
    if profile_id:
        _track_left_room(profile_id, room_name)
    return {"left": True, "room": room_name}


@socketio.on("join_thread")
def handle_join_thread(data):
    thread_id = (data or {}).get("thread_id")
    profile_id = _get_profile_id()
    if profile_id and thread_id and get_thread(thread_id, profile_id):
        room_name = thread_room(thread_id)
        join_room(room_name)
        _track_joined_room(profile_id, room_name)
        emit("thread:joined", {"thread_id": thread_id, "room": room_name})
        return {"thread_id": thread_id, "room": room_name, "joined": True}
    return {"joined": False}


@socketio.on("leave_thread")
def handle_leave_thread(data):
    thread_id = (data or {}).get("thread_id")
    profile_id = _get_profile_id()
    if thread_id:
        room_name = thread_room(thread_id)
        leave_room(room_name)
        if profile_id:
            _track_left_room(profile_id, room_name)
        emit("thread:left", {"thread_id": thread_id, "room": room_name})
        return {"thread_id": thread_id, "room": room_name, "left": True}
    return {"left": False}


@socketio.on("join_live_room")
def handle_join_live(data):
    room_id = (data or {}).get("room_id")
    profile_id = _get_profile_id()
    if room_id:
        room_name = live_room(room_id)
        join_room(room_name)
        if profile_id:
            _track_joined_room(profile_id, room_name)
        set_add(f"live_viewers:{room_id}", request.sid, ttl=_SOCKET_STATE_TTL_SECONDS)
        viewer_count = len(set_members(f"live_viewers:{room_id}"))
        emit_to_live_room(room_id, "live:viewers", {"count": viewer_count})
        return {"joined": True, "room_id": room_id, "viewer_count": viewer_count}
    return {"joined": False}


@socketio.on("leave_live_room")
def handle_leave_live(data):
    room_id = (data or {}).get("room_id")
    profile_id = _get_profile_id()
    if room_id:
        room_name = live_room(room_id)
        leave_room(room_name)
        if profile_id:
            _track_left_room(profile_id, room_name)
        set_remove(f"live_viewers:{room_id}", request.sid)
        viewer_count = len(set_members(f"live_viewers:{room_id}"))
        emit_to_live_room(room_id, "live:viewers", {"count": viewer_count})
        return {"left": True, "room_id": room_id, "viewer_count": viewer_count}
    return {"left": False}


@socketio.on("typing:start")
@socketio.on("typing_start")
def handle_typing_start(data):
    profile_id = _get_profile_id()
    thread_id = (data or {}).get("thread_id")
    if _ignore_duplicate_event("typing_start", data, f"{profile_id}:{thread_id}:start"):
        return {"typing": True, "duplicate": True, "thread_id": thread_id}
    if profile_id and thread_id:
        set_typing(profile_id, thread_id)
        emit_to_thread(thread_id, "typing:update", {"profile_id": profile_id, "typing": True})
        return {"typing": True, "thread_id": thread_id}
    return {"typing": False}


@socketio.on("typing:stop")
@socketio.on("typing_stop")
def handle_typing_stop(data):
    profile_id = _get_profile_id()
    thread_id = (data or {}).get("thread_id")
    if _ignore_duplicate_event("typing_stop", data, f"{profile_id}:{thread_id}:stop"):
        return {"typing": False, "duplicate": True, "thread_id": thread_id}
    if profile_id and thread_id:
        clear_expired_typing_statuses(thread_id, [profile_id])
        emit_to_thread(thread_id, "typing:update", {"profile_id": profile_id, "typing": False})
        return {"typing": False, "thread_id": thread_id}
    return {"typing": False}


@socketio.on("message:send")
@socketio.on("send_message")
def handle_message_send(data):
    profile_id = _get_profile_id()
    payload = data or {}
    thread_id = payload.get("thread_id")
    if not profile_id or not thread_id:
        return {"success": False, "error": "missing_thread"}
    
    # Check for voice note / audio
    media_file = None # Usually handled via REST API, but placeholder if binary is sent
    
    if _ignore_duplicate_event("send_message", payload, f"{profile_id}:{thread_id}:{payload.get('client_event_id') or payload.get('client_message_id')}"):
        result = send_message(
            thread_id,
            profile_id,
            body=payload.get("body"),
            file=None,
            client_message_id=payload.get("client_event_id") or payload.get("client_message_id"),
            sticker_id=payload.get("sticker_id"),
            gif_url=payload.get("gif_url"),
            location=payload.get("location"),
            contact=payload.get("contact"),
            parent_message_id=payload.get("parent_message_id")
        )
        if result and result.get("success"):
            result["duplicate"] = True
            return result
            
    result = send_message(
        thread_id,
        profile_id,
        body=payload.get("body"),
        file=None,
        client_message_id=payload.get("client_event_id") or payload.get("client_message_id"),
        sticker_id=payload.get("sticker_id"),
        gif_url=payload.get("gif_url"),
        location=payload.get("location"),
        contact=payload.get("contact"),
        parent_message_id=payload.get("parent_message_id")
    )
    if result and not result.get("error"):
        emit("message:ack", result)
        # Handle message requests - move to request folder if not contacts
        # This is a placeholder for actual contact check logic
        # move_thread_to_requests_if_needed(thread_id, profile_id, target_id)
        return result
    return {"success": False, **(result or {"error": "send_failed"})}


@socketio.on("message:delivered")
@socketio.on("delivered")
def handle_message_delivered(data):
    profile_id = _get_profile_id()
    message_id = (data or {}).get("message_id")
    thread_id = (data or {}).get("thread_id")
    if profile_id and message_id:
        ack_payload = acknowledge_delivery(message_id, profile_id)
        if thread_id:
            emit_to_thread(thread_id, "message:delivered", ack_payload)
        return {"ok": True, **ack_payload}
    return {"ok": False}


@socketio.on("message:seen")
@socketio.on("message_seen")
@socketio.on("seen")
def handle_message_seen(data):
    profile_id = _get_profile_id()
    thread_id = (data or {}).get("thread_id")
    if profile_id and thread_id:
        mark_thread_seen(thread_id, profile_id)
        return {"success": True, "thread_id": thread_id}
    return {"success": False}

@socketio.on("call:offer")
def handle_call_offer(data):
    profile_id = _get_profile_id()
    target_id = (data or {}).get("target_id")
    if profile_id and target_id:
        emit_to_profile(target_id, "call:offer", {
            "sender_id": profile_id,
            "sdp": data.get("sdp"),
            "call_id": data.get("call_id"),
            "call_type": data.get("call_type", "video")
        })
        emit_to_profile(profile_id, "call:ringing", {"call_id": data.get("call_id")})
        return {"success": True}
    return {"success": False}

@socketio.on("call:answer")
def handle_call_answer(data):
    profile_id = _get_profile_id()
    target_id = (data or {}).get("target_id")
    if profile_id and target_id:
        emit_to_profile(target_id, "call:answer", {
            "sender_id": profile_id,
            "sdp": data.get("sdp"),
            "call_id": data.get("call_id")
        })
        emit_to_profile(target_id, "call:accepted", {"call_id": data.get("call_id"), "by": profile_id})
        return {"success": True}
    return {"success": False}

@socketio.on("call:reject")
def handle_call_reject(data):
    profile_id = _get_profile_id()
    target_id = (data or {}).get("target_id")
    call_id = (data or {}).get("call_id")
    if profile_id and target_id:
        emit_to_profile(target_id, "call:rejected", {
            "call_id": call_id,
            "from_id": profile_id,
            "reason": "declined"
        })
        return {"success": True}
    return {"success": False}

@socketio.on("call:ice-candidate")
def handle_call_ice_candidate(data):
    profile_id = _get_profile_id()
    target_id = (data or {}).get("target_id")
    if profile_id and target_id:
        emit_to_profile(target_id, "call:ice-candidate", {
            "sender_id": profile_id,
            "candidate": data.get("candidate"),
            "call_id": data.get("call_id")
        })
        return {"success": True}
    return {"success": False}

@socketio.on("call:end")
def handle_call_end(data):
    profile_id = _get_profile_id()
    target_id = (data or {}).get("target_id")
    call_id = (data or {}).get("call_id")
    if profile_id and target_id:
        emit_to_profile(target_id, "call:ended", {
            "call_id": call_id,
            "from_id": profile_id,
            "reason": data.get("reason", "hung_up")
        })
        return {"success": True}
    return {"success": False}

@socketio.on("call:media-state")
def handle_call_media_state(data):
    profile_id = _get_profile_id()
    target_id = (data or {}).get("target_id")
    if profile_id and target_id:
        emit_to_profile(target_id, "call:media-state", {
            "from_id": profile_id,
            "audio": data.get("audio"),
            "video": data.get("video")
        })
        return {"success": True}
    return {"success": False}

@socketio.on("call:reconnect")
def handle_call_reconnect(data):
    profile_id = _get_profile_id()
    target_id = (data or {}).get("target_id")
    if profile_id and target_id:
        emit_to_profile(target_id, "call:reconnect", {"from_id": profile_id})
        return {"success": True}
    return {"success": False}


@socketio.on("message:recover")
def handle_message_recover(data):
    profile_id = _get_profile_id()
    payload = data or {}
    thread_id = payload.get("thread_id")
    if profile_id and thread_id:
        messages = recover_thread_messages(thread_id, profile_id, since_iso=payload.get("since"))
        emit("message:recovery", {"thread_id": thread_id, "messages": messages})
        return {"ok": True, "count": len(messages)}
    return {"ok": False}


@socketio.on("reconnect_sync")
def handle_reconnect_sync(data):
    profile_id = _get_profile_id()
    payload = data or {}
    thread_id = payload.get("thread_id")
    if not profile_id or not thread_id:
        return {"success": False, "messages": []}
    messages = sync_thread_messages(
        thread_id,
        profile_id,
        last_seen_message_id=payload.get("last_seen_message_id"),
        last_seen_at=payload.get("last_seen_at"),
        limit=min(int(payload.get("limit") or 100), 100),
    )
    return {"success": True, "thread_id": thread_id, "messages": messages}


@socketio.on("live_chat_message")
def handle_live_chat(data):
    room_id = (data or {}).get("room_id")
    message = (data or {}).get("message")
    profile_id = _get_profile_id()
    if _ignore_duplicate_event("live_chat_message", data, f"{profile_id}:{room_id}:{message}"):
        return {"ok": True, "duplicate": True}
    if room_id and message:
        payload = {
            "profile_id": profile_id,
            "username": session.get("username", "Anonymous"),
            "message": message,
            "timestamp": _utcnow_iso(),
        }
        emit_to_live_room(room_id, "live:chat", payload)


@socketio.on("live_gift")
def handle_live_gift(data):
    room_id = (data or {}).get("room_id")
    gift_type = (data or {}).get("gift_type")
    amount = int((data or {}).get("amount", 0))
    profile_id = _get_profile_id()
    if _ignore_duplicate_event("live_gift", data, f"{profile_id}:{room_id}:{gift_type}:{amount}"):
        return {"ok": True, "duplicate": True}
    if not profile_id or not room_id or not gift_type or amount <= 0:
        return {"ok": False}

    from services.live_service import get_room

    room = get_room(room_id)
    if not room:
        return {"ok": False, "error": "room_not_found"}
    ok, error = send_gift(profile_id, room["profile_id"], gift_type, amount, entity_type="live_room", entity_id=room_id)
    if ok:
        payload = {
            "sender_id": profile_id,
            "username": session.get("username", "Supporter"),
            "gift_type": gift_type,
            "amount": amount,
        }
        emit_to_live_room(room_id, "live:gift", payload)
        return {"ok": True}
    emit("error", {"message": error})
    return {"ok": False, "error": error}


@socketio.on("presence_heartbeat")
def handle_heartbeat():
    profile_id = _get_profile_id()
    if profile_id:
        heartbeat(profile_id)
        set_json(_socket_state_key(profile_id), {"rooms": _recover_rooms(profile_id), "updated_at": _utcnow_iso()}, ttl=_SOCKET_STATE_TTL_SECONDS)
        return {"ok": True, "sid": request.sid, "heartbeat_ack": True}
    return {"ok": False}


@socketio.on("notification_ack")
def handle_notification_ack(data):
    profile_id = _get_profile_id()
    notification_id = (data or {}).get("notification_id")
    client_event_id = (data or {}).get("client_event_id")
    if not profile_id or not notification_id:
        return {"ok": False}
    if client_event_id and not _mark_socket_event("notification_ack", client_event_id):
        return {"ok": True, "duplicate": True}
    publish(f"notifications:{profile_id}", {"event": "notification:ack", "notification_id": notification_id})
    return {"ok": True, "notification_id": notification_id}

@socketio.on("message:reaction:add")
def handle_add_reaction(data):
    profile_id = _get_profile_id()
    message_id = (data or {}).get("message_id")
    reaction_type = (data or {}).get("reaction_type")
    if profile_id and message_id and reaction_type:
        add_reaction(message_id, profile_id, reaction_type)
        return {"success": True}
    return {"success": False}

@socketio.on("message:reaction:remove")
def handle_remove_reaction(data):
    profile_id = _get_profile_id()
    message_id = (data or {}).get("message_id")
    reaction_type = (data or {}).get("reaction_type")
    if profile_id and message_id and reaction_type:
        remove_reaction(message_id, profile_id, reaction_type)
        return {"success": True}
    return {"success": False}

@socketio.on("message:delete")
def handle_message_delete(data):
    profile_id = _get_profile_id()
    message_id = (data or {}).get("message_id")
    for_everyone = bool((data or {}).get("for_everyone", False))
    if profile_id and message_id:
        if delete_message(message_id, profile_id, for_everyone=for_everyone):
            return {"success": True}
    return {"success": False}

@socketio.on("thread:pin")
def handle_thread_pin(data):
    profile_id = _get_profile_id()
    thread_id = (data or {}).get("thread_id")
    pinned = bool((data or {}).get("pinned", True))
    if profile_id and thread_id:
        pin_thread(thread_id, profile_id, pinned=pinned)
        return {"success": True}
    return {"success": False}

@socketio.on("thread:archive")
def handle_thread_archive(data):
    profile_id = _get_profile_id()
    thread_id = (data or {}).get("thread_id")
    archived = bool((data or {}).get("archived", True))
    if profile_id and thread_id:
        archive_thread(thread_id, profile_id, archived=archived)
        return {"success": True}
    return {"success": False}

@socketio.on("thread:mute")
def handle_thread_mute(data):
    profile_id = _get_profile_id()
    thread_id = (data or {}).get("thread_id")
    muted = bool((data or {}).get("muted", True))
    if profile_id and thread_id:
        mute_thread(thread_id, profile_id, muted=muted)
        return {"success": True}
    return {"success": False}

@socketio.on("message:send")
def handle_send_message(data):
    profile_id = _get_profile_id()
    thread_id = (data or {}).get("thread_id")
    body = (data or {}).get("body")
    sticker_id = (data or {}).get("sticker_id")
    gif_url = (data or {}).get("gif_url")
    location = (data or {}).get("location")
    contact = (data or {}).get("contact")
    
    if profile_id and thread_id:
        result = send_message(
            thread_id, profile_id, body=body, 
            sticker_id=sticker_id, gif_url=gif_url, 
            location=location, contact=contact,
            parent_message_id=data.get("parent_message_id")
        )
        return result
    return {"error": "Unauthorized", "success": False}

@socketio.on("message:ack")
def handle_message_ack(data):
    """Client acknowledges message receipt (Delivered Tick)."""
    profile_id = _get_profile_id()
    message_id = (data or {}).get("message_id")
    if profile_id and message_id:
        acknowledge_delivery(message_id, profile_id)
        return {"success": True}
    return {"success": False}

@socketio.on("call:signal")
def handle_call_signal(data):
    """Complete WebRTC signaling (Offer/Answer/ICE)."""
    profile_id = _get_profile_id()
    target_id = (data or {}).get("target_id")
    if profile_id and target_id:
        emit_to_profile(target_id, "call:signal", {
            "sender_id": profile_id,
            "signal": data.get("signal"), # contains SDP or ICE candidate
            "call_id": data.get("call_id"),
            "type": data.get("type") # 'offer', 'answer', 'candidate'
        })
        return {"success": True}
    return {"success": False}

@socketio.on("presence:heartbeat")
def handle_presence_heartbeat(data):
    profile_id = _get_profile_id()
    if profile_id:
        heartbeat(profile_id)
        return {"success": True}
    return {"success": False}

@socketio.on("call:status")
def handle_call_status(data):
    profile_id = _get_profile_id()
    target_id = (data or {}).get("target_id")
    call_id = (data or {}).get("call_id")
    status = (data or {}).get("status")
    if profile_id and target_id and call_id and status:
        emit_to_profile(target_id, "call:status", {
            "call_id": call_id,
            "status": status,
            "from_id": profile_id
        })
        return {"success": True}
    return {"success": False}


@socketio.on("message:edited")
def handle_phase30_message_edited(data):
    profile_id = _get_profile_id()
    message_id = (data or {}).get("message_id")
    body = (data or {}).get("body")
    if profile_id and message_id and body:
        return phase30_messages.edit_message(message_id, profile_id, body)
    return {"ok": False}


@socketio.on("message:pinned")
def handle_phase30_message_pinned(data):
    profile_id = _get_profile_id()
    message_id = (data or {}).get("message_id")
    if profile_id and message_id:
        return phase30_messages.pin_message(message_id, profile_id, bool((data or {}).get("pinned", True)))
    return {"ok": False}


@socketio.on("message:forwarded")
def handle_phase30_message_forwarded(data):
    profile_id = _get_profile_id()
    if profile_id:
        return phase30_messages.forward_messages(profile_id, (data or {}).get("message_ids") or [], (data or {}).get("to_thread_ids") or [])
    return {"ok": False}


@socketio.on("message:draft")
def handle_phase30_message_draft(data):
    profile_id = _get_profile_id()
    thread_id = (data or {}).get("thread_id")
    if profile_id and thread_id:
        return phase30_messages.save_draft(thread_id, profile_id, (data or {}).get("body") or "")
    return {"ok": False}


@socketio.on("call:quality")
def handle_phase30_call_quality(data):
    profile_id = _get_profile_id()
    call_id = (data or {}).get("call_id")
    if profile_id and call_id:
        return phase30_calls.record_quality_event(call_id, profile_id, (data or {}).get("event_type", "quality"), (data or {}).get("quality_score"), (data or {}).get("payload") or {})
    return {"ok": False}


@socketio.on("call:waiting")
def handle_phase30_call_waiting(data):
    profile_id = _get_profile_id()
    call_id = (data or {}).get("call_id")
    if profile_id and call_id:
        return phase30_calls.record_call_waiting(call_id, profile_id, (data or {}).get("incoming_profile_id"), (data or {}).get("payload") or {})
    return {"ok": False}
