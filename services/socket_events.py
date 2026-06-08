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
from services.push_notification_service import queue_push_event
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
from services.message_delivery_service import (
    update_presence as mds_update_presence,
    set_offline as mds_set_offline,
    mark_thread_seen as mds_mark_thread_seen,
    react_to_message as mds_react,
    edit_message as mds_edit,
    delete_message_for_everyone as mds_delete_everyone,
    get_reactions as mds_get_reactions,
    get_presence as mds_get_presence,
)
from services.webrtc_call_service import (
    get_call as w_get_call,
    get_active_call as w_get_active_call,
    accept_call as w_accept_call,
    reject_call as w_reject_call,
    cancel_call as w_cancel_call,
    end_call as w_end_call,
    mark_call_busy as w_mark_call_busy,
    mark_call_timeout as w_mark_call_timeout,
    update_participant_state as w_update_participant_state,
    add_call_event as w_add_call_event,
)


_SOCKET_STATE_TTL_SECONDS = 180
_EVENT_DEDUPE_TTL_SECONDS = 120


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def _get_profile_id():
    profile_id = session.get("profile_id") or session.get("user_id")
    if profile_id:
        return str(profile_id)
    if "auth_user_id" not in session:
        return None
    profile = get_current_profile()
    return str(profile["id"]) if profile else None


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
        mds_update_presence(profile_id, status="online")
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
            mds_set_offline(profile_id)
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
        profile = {"username": session.get("username") or session.get("email")}
        emit_to_thread(thread_id, "typing:update", {
            "profile_id": profile_id,
            "username": profile.get("username") or "Someone",
            "display_name": profile.get("display_name") or profile.get("username") or "Someone",
            "typing": True,
            "thread_id": thread_id,
        })
        emit_to_thread(thread_id, "user_typing", {
            "profile_id": profile_id,
            "username": profile.get("username") or "Someone",
            "display_name": profile.get("display_name") or profile.get("username") or "Someone",
            "typing": True,
            "thread_id": thread_id,
        })
        emit_to_thread(thread_id, "typing:start", {
            "profile_id": profile_id,
            "username": profile.get("username") or "Someone",
            "display_name": profile.get("display_name") or profile.get("username") or "Someone",
            "typing": True,
            "thread_id": thread_id,
        })
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
        profile = {"username": session.get("username") or session.get("email")}
        emit_to_thread(thread_id, "typing:update", {
            "profile_id": profile_id,
            "username": profile.get("username") or "Someone",
            "display_name": profile.get("display_name") or profile.get("username") or "Someone",
            "typing": False,
            "thread_id": thread_id,
        })
        emit_to_thread(thread_id, "user_typing", {
            "profile_id": profile_id,
            "username": profile.get("username") or "Someone",
            "display_name": profile.get("display_name") or profile.get("username") or "Someone",
            "typing": False,
            "thread_id": thread_id,
        })
        emit_to_thread(thread_id, "typing:stop", {
            "profile_id": profile_id,
            "username": profile.get("username") or "Someone",
            "display_name": profile.get("display_name") or profile.get("username") or "Someone",
            "typing": False,
            "thread_id": thread_id,
        })
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
        sender_profile = get_current_profile()
        sender_name = (sender_profile or {}).get("display_name") or (sender_profile or {}).get("username") or "Someone"
        # Queue push events for other thread participants
        thread_data = get_thread(thread_id, profile_id) if profile_id else None
        if thread_data:
            other_participant = None
            participants = thread_data.get("participants") or thread_data.get("members") or []
            for p in participants:
                pid = p.get("id") if isinstance(p, dict) else p
                if pid and str(pid) != str(profile_id):
                    other_participant = pid if isinstance(pid, str) else (p.get("id") if isinstance(p, dict) else None)
                    break
            if other_participant:
                queue_push_event(
                    other_participant,
                    "message_received",
                    f"New message from {sender_name}",
                    (payload.get("body") or "")[:120],
                    {"url": f"/messages/thread/{thread_id}"},
                )
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
        mds_mark_thread_seen(thread_id, profile_id)
        profile = get_current_profile() or {}
        emit_to_thread(thread_id, "message_seen", {
            "profile_id": profile_id,
            "thread_id": thread_id,
            "username": profile.get("username") or "Someone",
            "seen_at": _utcnow_iso(),
        })
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
        sender_profile = get_current_profile()
        sender_name = (sender_profile or {}).get("display_name") or (sender_profile or {}).get("username") or "Someone"
        queue_push_event(
            target_id,
            "incoming_call",
            f"Incoming {data.get('call_type', 'video')} call",
            f"from {sender_name}",
            {"url": "/calls/recent"},
        )
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
    reason = data.get("reason", "hung_up")
    if profile_id and target_id:
        emit_to_profile(target_id, "call:ended", {
            "call_id": call_id,
            "from_id": profile_id,
            "reason": reason
        })
        if reason == "timeout" or reason == "no_answer":
            caller_profile = get_current_profile()
            caller_name = (caller_profile or {}).get("display_name") or (caller_profile or {}).get("username") or "Someone"
            queue_push_event(
                target_id,
                "missed_call",
                "Missed call",
                f"from {caller_name}",
                {"url": "/calls/recent"},
            )
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
@socketio.on("reaction:new")
def handle_add_reaction(data):
    profile_id = _get_profile_id()
    message_id = (data or {}).get("message_id")
    thread_id = (data or {}).get("thread_id")
    reaction_type = (data or {}).get("reaction_type") or (data or {}).get("reaction")
    if profile_id and message_id and reaction_type:
        add_reaction(message_id, profile_id, reaction_type)
        mds_react(message_id, profile_id, reaction_type)
        reactions = mds_get_reactions(message_id)
        if thread_id:
            payload = {
                "message_id": message_id,
                "thread_id": thread_id,
                "profile_id": profile_id,
                "reaction_type": reaction_type,
                "reaction": reaction_type,
                "added": True,
                "reactions": reactions,
            }
            emit_to_thread(thread_id, "message_reaction", payload)
            emit_to_thread(thread_id, "reaction:new", payload)
        return {"success": True, "reactions": reactions}
    return {"success": False}

@socketio.on("message:reaction:remove")
def handle_remove_reaction(data):
    profile_id = _get_profile_id()
    message_id = (data or {}).get("message_id")
    thread_id = (data or {}).get("thread_id")
    reaction_type = (data or {}).get("reaction_type") or (data or {}).get("reaction")
    if profile_id and message_id and reaction_type:
        remove_reaction(message_id, profile_id, reaction_type)
        from services.message_delivery_service import remove_reaction as mds_remove_react
        mds_remove_react(message_id, profile_id)
        reactions = mds_get_reactions(message_id)
        if thread_id:
            payload = {
                "message_id": message_id,
                "thread_id": thread_id,
                "profile_id": profile_id,
                "reaction_type": reaction_type,
                "reaction": reaction_type,
                "removed": True,
                "reactions": reactions,
            }
            emit_to_thread(thread_id, "message_reaction", payload)
            emit_to_thread(thread_id, "reaction:new", payload)
        return {"success": True}
    return {"success": False}

@socketio.on("message:delete")
def handle_message_delete(data):
    profile_id = _get_profile_id()
    message_id = (data or {}).get("message_id")
    thread_id = (data or {}).get("thread_id")
    for_everyone = bool((data or {}).get("for_everyone", False))
    if profile_id and message_id:
        if delete_message(message_id, profile_id, for_everyone=for_everyone):
            if for_everyone:
                mds_delete_everyone(message_id, profile_id)
            if thread_id:
                payload = {
                    "message_id": message_id,
                    "thread_id": thread_id,
                    "profile_id": profile_id,
                    "for_everyone": for_everyone,
                }
                emit_to_thread(thread_id, "message_deleted", payload)
                emit_to_thread(thread_id, "message:deleted", payload)
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
    thread_id = (data or {}).get("thread_id")
    body = (data or {}).get("body")
    if profile_id and message_id and body:
        phase30_messages.edit_message(message_id, profile_id, body)
        mds_edit(message_id, profile_id, body)
        if thread_id:
            emit_to_thread(thread_id, "message_edited", {
                "message_id": message_id,
                "thread_id": thread_id,
                "profile_id": profile_id,
                "body": body,
                "edited": True,
            })
        return {"ok": True, "message_id": message_id, "body": body, "edited": True}
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


# =========== PHASE 40: Premium WebRTC Call Signaling ===========

@socketio.on("call:start")
def handle_webrtc_call_start(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False, "error": "unauthorized"}
    target_id = (data or {}).get("target_id")
    thread_id = (data or {}).get("thread_id")
    call_type = (data or {}).get("call_type", "audio")
    if not target_id:
        return {"ok": False, "error": "target_required"}
    from services.webrtc_call_service import create_call
    result = create_call(profile_id, target_id, thread_id=thread_id, call_type=call_type)
    if result.get("ok"):
        call = result["call"]
        join_room(f"call:{call['id']}")
        emit_to_profile(target_id, "call:incoming", {
            "call_id": call["id"],
            "caller_id": profile_id,
            "call_type": call["call_mode"],
            "call_mode": call["call_mode"],
        })
        return {"ok": True, "call": call}
    if result.get("status") == "busy":
        emit("call:busy", {"reason": result.get("error", "busy")})
    return {"ok": False, "error": result.get("error", "failed")}


@socketio.on("call:ringing")
def handle_webrtc_call_ringing(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    call_id = (data or {}).get("call_id")
    if call_id:
        join_room(f"call:{call_id}")
        target_id = (data or {}).get("target_id")
        if target_id:
            emit_to_profile(target_id, "call:ringing", {"call_id": call_id, "from_id": profile_id})
        w_add_call_event(call_id, profile_id, "ringing")
        return {"ok": True}
    return {"ok": False}


@socketio.on("call:accept")
def handle_webrtc_call_accept(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    call_id = (data or {}).get("call_id")
    if not call_id:
        return {"ok": False}
    result = w_accept_call(call_id, profile_id)
    if result.get("ok"):
        call = result.get("call") or {}
        join_room(f"call:{call_id}")
        caller_id = call.get("caller_profile_id") or (data or {}).get("target_id")
        if caller_id and caller_id != profile_id:
            emit_to_profile(caller_id, "call:accepted", {"call_id": call_id, "profile_id": profile_id})
        w_add_call_event(call_id, profile_id, "accepted")
        return {"ok": True, "call": call}
    return {"ok": False, "error": result.get("error")}


@socketio.on("call:reject")
def handle_webrtc_call_reject(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    call_id = (data or {}).get("call_id")
    if not call_id:
        return {"ok": False}
    w_reject_call(call_id, profile_id)
    target_id = (data or {}).get("target_id") or (data or {}).get("caller_id")
    if target_id:
        emit_to_profile(target_id, "call:rejected", {"call_id": call_id, "from_id": profile_id, "reason": "declined"})
    w_add_call_event(call_id, profile_id, "rejected")
    return {"ok": True}


@socketio.on("call:cancel")
def handle_webrtc_call_cancel(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    call_id = (data or {}).get("call_id")
    if not call_id:
        return {"ok": False}
    w_cancel_call(call_id, profile_id)
    target_id = (data or {}).get("target_id") or (data or {}).get("receiver_id")
    if target_id:
        emit_to_profile(target_id, "call:cancelled", {"call_id": call_id, "from_id": profile_id})
    w_add_call_event(call_id, profile_id, "cancelled")
    return {"ok": True}


@socketio.on("call:end")
def handle_webrtc_call_end(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    call_id = (data or {}).get("call_id")
    if not call_id:
        return {"ok": False}
    reason = data.get("reason", "hung_up")
    w_end_call(call_id, profile_id)
    target_id = (data or {}).get("target_id")
    if target_id:
        emit_to_profile(target_id, "call:ended", {"call_id": call_id, "from_id": profile_id, "reason": reason})
    w_add_call_event(call_id, profile_id, "ended", {"reason": reason})
    return {"ok": True}


@socketio.on("call:busy")
def handle_webrtc_call_busy(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    call_id = (data or {}).get("call_id")
    if call_id:
        w_mark_call_busy(call_id)
        w_add_call_event(call_id, profile_id, "busy")
    return {"ok": True}


@socketio.on("call:timeout")
def handle_webrtc_call_timeout(data):
    profile_id = _get_profile_id()
    call_id = (data or {}).get("call_id")
    if call_id:
        w_mark_call_timeout(call_id)
        w_add_call_event(call_id, profile_id, "timeout")
    return {"ok": True}


@socketio.on("call:offer")
def handle_webrtc_call_offer(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    target_id = (data or {}).get("target_id")
    call_id = (data or {}).get("call_id")
    if profile_id and target_id:
        join_room(f"call:{call_id}")
        emit_to_profile(target_id, "call:offer", {
            "sender_id": profile_id,
            "sdp": data.get("sdp"),
            "call_id": call_id,
            "call_type": data.get("call_type", "audio"),
        })
        w_add_call_event(call_id, profile_id, "offer")
        return {"ok": True}
    return {"ok": False}


@socketio.on("call:answer")
def handle_webrtc_call_answer(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    target_id = (data or {}).get("target_id")
    call_id = (data or {}).get("call_id")
    if profile_id and target_id:
        join_room(f"call:{call_id}")
        emit_to_profile(target_id, "call:answer", {
            "sender_id": profile_id,
            "sdp": data.get("sdp"),
            "call_id": call_id,
        })
        w_add_call_event(call_id, profile_id, "answer")
        return {"ok": True}
    return {"ok": False}


@socketio.on("call:ice-candidate")
def handle_webrtc_call_ice(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    target_id = (data or {}).get("target_id")
    call_id = (data or {}).get("call_id")
    if profile_id and target_id:
        emit_to_profile(target_id, "call:ice-candidate", {
            "sender_id": profile_id,
            "candidate": data.get("candidate"),
            "call_id": call_id,
        })
        return {"ok": True}
    return {"ok": False}


@socketio.on("call:reconnecting")
def handle_webrtc_call_reconnecting(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    call_id = (data or {}).get("call_id")
    target_id = (data or {}).get("target_id")
    if call_id:
        w_update_participant_state(call_id, profile_id, connection_status="reconnecting")
        if target_id:
            emit_to_profile(target_id, "call:reconnecting", {"call_id": call_id, "profile_id": profile_id})
    return {"ok": True}


@socketio.on("call:reconnected")
def handle_webrtc_call_reconnected(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    call_id = (data or {}).get("call_id")
    target_id = (data or {}).get("target_id")
    if call_id:
        w_update_participant_state(call_id, profile_id, connection_status="connected")
        if target_id:
            emit_to_profile(target_id, "call:reconnected", {"call_id": call_id, "profile_id": profile_id})
    return {"ok": True}


@socketio.on("call:failed")
def handle_webrtc_call_failed(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    call_id = (data or {}).get("call_id")
    target_id = (data or {}).get("target_id")
    if call_id:
        w_update_participant_state(call_id, profile_id, connection_status="failed")
        if target_id:
            emit_to_profile(target_id, "call:failed", {"call_id": call_id, "profile_id": profile_id})
        w_add_call_event(call_id, profile_id, "failed", {"reason": data.get("reason")})
    return {"ok": True}


@socketio.on("call:mute")
def handle_webrtc_call_mute(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    call_id = (data or {}).get("call_id")
    target_id = (data or {}).get("target_id")
    muted = bool((data or {}).get("muted", True))
    if call_id:
        w_update_participant_state(call_id, profile_id, muted=muted)
        w_add_call_event(call_id, profile_id, "mute", {"muted": muted})
        if target_id:
            emit_to_profile(target_id, "call:mute_state", {"call_id": call_id, "profile_id": profile_id, "muted": muted})
    return {"ok": True}


@socketio.on("call:camera-toggle")
def handle_webrtc_call_camera(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    call_id = (data or {}).get("call_id")
    target_id = (data or {}).get("target_id")
    enabled = bool((data or {}).get("enabled", True))
    if call_id:
        w_update_participant_state(call_id, profile_id, camera_enabled=enabled)
        w_add_call_event(call_id, profile_id, "camera_toggle", {"enabled": enabled})
        if target_id:
            emit_to_profile(target_id, "call:camera_state", {"call_id": call_id, "profile_id": profile_id, "enabled": enabled})
    return {"ok": True}


@socketio.on("call:speaker-toggle")
def handle_webrtc_call_speaker(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    call_id = (data or {}).get("call_id")
    target_id = (data or {}).get("target_id")
    enabled = bool((data or {}).get("enabled", True))
    if call_id:
        w_update_participant_state(call_id, profile_id, speaker_enabled=enabled)
        w_add_call_event(call_id, profile_id, "speaker_toggle", {"enabled": enabled})
        if target_id:
            emit_to_profile(target_id, "call:speaker_state", {"call_id": call_id, "profile_id": profile_id, "enabled": enabled})
    return {"ok": True}


# =========== PHASE 41: Mobile Call Reliability Events ===========

@socketio.on("call:invite")
def handle_phase41_call_invite(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False, "error": "unauthorized"}
    call_id = (data or {}).get("call_id")
    target_profile_id = (data or {}).get("target_profile_id") or (data or {}).get("target_id")
    if not call_id or not target_profile_id:
        return {"ok": False, "error": "missing_params"}
    from services.webrtc_call_service import invite_participant
    result = invite_participant(call_id, profile_id, target_profile_id)
    if result.get("ok"):
        emit_to_profile(target_profile_id, "call:invite", {
            "call_id": call_id,
            "from_id": profile_id,
            "call_type": data.get("call_type", "audio"),
        })
        sender_profile = get_current_profile()
        sender_name = (sender_profile or {}).get("display_name") or (sender_profile or {}).get("username") or "Someone"
        queue_push_event(
            target_profile_id,
            "call_invite",
            f"Call invitation",
            f"{sender_name} invited you to a call",
            {"url": "/calls/recent"},
        )
        emit_to_profile(target_profile_id, "call:notification", {
            "type": "call_invite",
            "call_id": call_id,
            "title": "Call invitation",
            "body": f"{sender_name} invited you to a call",
        })
        return {"ok": True, "call_id": call_id}
    return {"ok": False, "error": result.get("error", "invite_failed")}


@socketio.on("call:participant-joined")
def handle_phase41_participant_joined(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    call_id = (data or {}).get("call_id")
    if call_id:
        from services.webrtc_call_service import get_call_participants
        participants = get_call_participants(call_id)
        emit_to_profile(profile_id, "call:participant-joined", {
            "call_id": call_id,
            "participants": participants,
            "profile_id": profile_id,
        })
        return {"ok": True}
    return {"ok": False}


@socketio.on("call:participant-left")
def handle_phase41_participant_left(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    call_id = (data or {}).get("call_id")
    if call_id:
        from services.webrtc_call_service import leave_participant, get_call_participants
        leave_participant(call_id, profile_id)
        participants = get_call_participants(call_id)
        emit_to_profile(profile_id, "call:participant-left", {
            "call_id": call_id,
            "participants": participants,
            "profile_id": profile_id,
        })
        return {"ok": True}
    return {"ok": False}


@socketio.on("call:quality-warning")
def handle_phase41_quality_warning(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    call_id = (data or {}).get("call_id")
    quality_status = (data or {}).get("quality_status", "weak")
    ice_state = (data or {}).get("ice_state")
    connection_state = (data or {}).get("connection_state")
    if call_id:
        from services.webrtc_call_service import add_call_quality_event
        add_call_quality_event(call_id, profile_id, quality_status, ice_state, connection_state)
        target_id = (data or {}).get("target_id")
        if target_id:
            emit_to_profile(target_id, "call:quality-warning", {
                "call_id": call_id,
                "quality_status": quality_status,
                "ice_state": ice_state,
                "connection_state": connection_state,
                "from_id": profile_id,
            })
        return {"ok": True}
    return {"ok": False}


@socketio.on("call:network-weak")
def handle_phase41_network_weak(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    call_id = (data or {}).get("call_id")
    target_id = (data or {}).get("target_id")
    if call_id:
        from services.webrtc_call_service import add_call_quality_event
        add_call_quality_event(call_id, profile_id, "weak", connection_state="weak")
        if target_id:
            emit_to_profile(target_id, "call:network-weak", {
                "call_id": call_id,
                "from_id": profile_id,
            })
        return {"ok": True}
    return {"ok": False}


@socketio.on("call:log-update")
def handle_phase41_log_update(data):
    profile_id = _get_profile_id()
    if profile_id:
        from services.webrtc_call_service import get_call_history
        history = get_call_history(profile_id, limit=10)
        emit_to_profile(profile_id, "call:log-update", {
            "history": history,
        })
        return {"ok": True, "count": len(history)}
    return {"ok": False}


@socketio.on("call:notification")
def handle_phase41_notification(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    call_id = (data or {}).get("call_id")
    notification_type = (data or {}).get("type") or (data or {}).get("notification_type", "info")
    title = (data or {}).get("title")
    body = (data or {}).get("body")
    if call_id:
        from services.webrtc_call_service import _create_call_notification
        _create_call_notification(profile_id, call_id, notification_type, title, body)
        return {"ok": True}
    if title or body:
        from services.webrtc_call_service import _create_call_notification
        _create_call_notification(profile_id, None, notification_type, title, body)
        return {"ok": True}
    return {"ok": False}


@socketio.on("call:speaking-toggle")
def handle_phase41_speaking_toggle(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    call_id = (data or {}).get("call_id")
    speaking = bool((data or {}).get("speaking", True))
    target_id = (data or {}).get("target_id")
    if call_id:
        from services.webrtc_call_service import update_participant_speaking
        update_participant_speaking(call_id, profile_id, speaking)
        if target_id:
            emit_to_profile(target_id, "call:speaking_state", {
                "call_id": call_id,
                "profile_id": profile_id,
                "speaking": speaking,
            })
        return {"ok": True}
    return {"ok": False}


# ---------- PHASE 44: Group Calling Socket Events ----------

def _get_group_call_room(call_id):
    return f"group_call:{call_id}"


@socketio.on("group-call:create")
def handle_group_call_create(data):
    profile = get_current_profile()
    if not profile:
        return {"ok": False}
    profile_id = profile["id"]
    from services.group_call_service import create_group_call
    room_name = (data or {}).get("room_name", "")
    call_type = (data or {}).get("call_type", "audio")
    thread_id = (data or {}).get("thread_id")
    call = create_group_call(profile_id, room_name=room_name, call_type=call_type, thread_id=thread_id)
    if not call:
        return {"ok": False}
    room = _get_group_call_room(call["id"])
    join_room(room)
    emit("group-call:created", {"call": call, "profile_id": profile_id}, room=room)
    return {"ok": True, "call": call}


@socketio.on("group-call:join")
def handle_group_call_join(data):
    profile = get_current_profile()
    if not profile:
        return {"ok": False}
    profile_id = profile["id"]
    call_id = (data or {}).get("call_id")
    if not call_id:
        return {"ok": False}
    from services.group_call_service import join_group_call
    ok = join_group_call(call_id, profile_id)
    if not ok:
        return {"ok": False}
    room = _get_group_call_room(call_id)
    join_room(room)
    emit("group-call:participant-joined", {"profile_id": profile_id, "call_id": call_id}, room=room)
    return {"ok": True}


@socketio.on("group-call:leave")
def handle_group_call_leave(data):
    profile = get_current_profile()
    if not profile:
        return {"ok": False}
    profile_id = profile["id"]
    call_id = (data or {}).get("call_id")
    if not call_id:
        return {"ok": False}
    from services.group_call_service import leave_group_call
    leave_group_call(call_id, profile_id)
    room = _get_group_call_room(call_id)
    leave_room(room)
    emit("group-call:participant-left", {"profile_id": profile_id, "call_id": call_id}, room=room)
    return {"ok": True}


@socketio.on("group-call:invite")
def handle_group_call_invite(data):
    profile = get_current_profile()
    if not profile:
        return {"ok": False}
    profile_id = profile["id"]
    call_id = (data or {}).get("call_id")
    invited_id = (data or {}).get("target_id")
    if not call_id or not invited_id:
        return {"ok": False}
    from services.group_call_service import invite_participant
    invite_participant(call_id, invited_id, profile_id)
    emit_to_profile(invited_id, "group-call:invite", {"call_id": call_id, "invited_by": profile_id})
    return {"ok": True}


@socketio.on("group-call:mute")
def handle_group_call_mute(data):
    profile = get_current_profile()
    if not profile:
        return {"ok": False}
    profile_id = profile["id"]
    call_id = (data or {}).get("call_id")
    target_id = (data or {}).get("target_id", profile_id)
    if not call_id:
        return {"ok": False}
    from services.group_call_service import mute_participant
    mute_participant(call_id, target_id)
    room = _get_group_call_room(call_id)
    emit("group-call:muted", {"profile_id": target_id, "call_id": call_id}, room=room)
    return {"ok": True}


@socketio.on("group-call:unmute")
def handle_group_call_unmute(data):
    profile = get_current_profile()
    if not profile:
        return {"ok": False}
    profile_id = profile["id"]
    call_id = (data or {}).get("call_id")
    target_id = (data or {}).get("target_id", profile_id)
    if not call_id:
        return {"ok": False}
    from services.group_call_service import unmute_participant
    unmute_participant(call_id, target_id)
    room = _get_group_call_room(call_id)
    emit("group-call:unmuted", {"profile_id": target_id, "call_id": call_id}, room=room)
    return {"ok": True}


@socketio.on("group-call:raise-hand")
def handle_group_call_raise_hand(data):
    profile = get_current_profile()
    if not profile:
        return {"ok": False}
    profile_id = profile["id"]
    call_id = (data or {}).get("call_id")
    if not call_id:
        return {"ok": False}
    from services.group_call_service import raise_hand
    raise_hand(call_id, profile_id)
    room = _get_group_call_room(call_id)
    emit("group-call:hand-raised", {"profile_id": profile_id, "call_id": call_id}, room=room)
    return {"ok": True}


@socketio.on("group-call:lower-hand")
def handle_group_call_lower_hand(data):
    profile = get_current_profile()
    if not profile:
        return {"ok": False}
    profile_id = profile["id"]
    call_id = (data or {}).get("call_id")
    if not call_id:
        return {"ok": False}
    from services.group_call_service import lower_hand
    lower_hand(call_id, profile_id)
    room = _get_group_call_room(call_id)
    emit("group-call:hand-lowered", {"profile_id": profile_id, "call_id": call_id}, room=room)
    return {"ok": True}


@socketio.on("group-call:camera-toggle")
def handle_group_call_camera(data):
    profile = get_current_profile()
    if not profile:
        return {"ok": False}
    profile_id = profile["id"]
    call_id = (data or {}).get("call_id")
    enabled = bool((data or {}).get("enabled", True))
    if not call_id:
        return {"ok": False}
    from services.group_call_service import update_camera_status
    update_camera_status(call_id, profile_id, enabled)
    room = _get_group_call_room(call_id)
    emit("group-call:camera-toggled", {"profile_id": profile_id, "call_id": call_id, "enabled": enabled}, room=room)
    return {"ok": True}


@socketio.on("group-call:screen-share")
def handle_group_call_screen_share(data):
    profile = get_current_profile()
    if not profile:
        return {"ok": False}
    profile_id = profile["id"]
    call_id = (data or {}).get("call_id")
    sharing = bool((data or {}).get("sharing", True))
    if not call_id:
        return {"ok": False}
    from services.group_call_service import update_screen_share_status
    update_screen_share_status(call_id, profile_id, sharing)
    room = _get_group_call_room(call_id)
    emit("group-call:screen-shared", {"profile_id": profile_id, "call_id": call_id, "sharing": sharing}, room=room)
    return {"ok": True}


@socketio.on("group-call:speaking")
def handle_group_call_speaking(data):
    profile = get_current_profile()
    if not profile:
        return {"ok": False}
    profile_id = profile["id"]
    call_id = (data or {}).get("call_id")
    speaking = bool((data or {}).get("speaking", True))
    if not call_id:
        return {"ok": False}
    from services.group_call_service import update_speaking_status
    update_speaking_status(call_id, profile_id, speaking)
    room = _get_group_call_room(call_id)
    emit("group-call:speaking-status", {"profile_id": profile_id, "call_id": call_id, "speaking": speaking}, room=room)
    return {"ok": True}


@socketio.on("group-call:host-transfer")
def handle_group_call_host_transfer(data):
    profile = get_current_profile()
    if not profile:
        return {"ok": False}
    profile_id = profile["id"]
    call_id = (data or {}).get("call_id")
    target_id = (data or {}).get("target_id")
    if not call_id or not target_id:
        return {"ok": False}
    from services.group_call_service import transfer_host
    transfer_host(call_id, target_id)
    room = _get_group_call_room(call_id)
    emit("group-call:host-transferred", {"from_id": profile_id, "to_id": target_id, "call_id": call_id}, room=room)
    return {"ok": True}


@socketio.on("group-call:end")
def handle_group_call_end(data):
    profile = get_current_profile()
    if not profile:
        return {"ok": False}
    profile_id = profile["id"]
    call_id = (data or {}).get("call_id")
    if not call_id:
        return {"ok": False}
    from services.group_call_service import get_group_call, end_group_call
    call = get_group_call(call_id)
    if not call or call["host_profile_id"] != profile_id:
        return {"ok": False}
    end_group_call(call_id)
    room = _get_group_call_room(call_id)
    emit("group-call:ended", {"call_id": call_id, "ended_by": profile_id}, room=room)
    return {"ok": True}


# ---------- PHASE 45: Push Notification Socket Events ----------


@socketio.on("notification:new")
def handle_notification_new(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    payload = data or {}
    notification_type = payload.get("type", "info")
    title = payload.get("title", "")
    body = payload.get("body", "")
    from services.push_notification_service import send_push_notification
    result = send_push_notification(
        profile_id, title, body, {"_notification_type": notification_type, "url": payload.get("url")},
    )
    if result.get("ok"):
        emit_to_profile(profile_id, "notification:new", {
            "profile_id": profile_id,
            "type": notification_type,
            "title": title,
            "body": body,
            "ts": _utcnow_iso(),
        })
        return {"ok": True}
    return {"ok": False}


@socketio.on("notification:read")
def handle_notification_read(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    notification_id = (data or {}).get("notification_id")
    if notification_id:
        try:
            from services.neon_service import write_query
            write_query(
                "UPDATE chain_notification_queue SET status = 'read' WHERE id = %s AND profile_id = %s",
                (notification_id, profile_id),
            )
        except Exception:
            pass
        emit_to_profile(profile_id, "notification:read", {
            "notification_id": notification_id, "profile_id": profile_id,
        })
        return {"ok": True}
    return {"ok": False}


@socketio.on("notification:deleted")
def handle_notification_deleted(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    notification_id = (data or {}).get("notification_id")
    if notification_id:
        try:
            from services.neon_service import write_query
            write_query(
                "DELETE FROM chain_notification_queue WHERE id = %s AND profile_id = %s",
                (notification_id, profile_id),
            )
        except Exception:
            pass
        emit_to_profile(profile_id, "notification:deleted", {
            "notification_id": notification_id, "profile_id": profile_id,
        })
        return {"ok": True}
    return {"ok": False}


@socketio.on("notification:call")
def handle_notification_call(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    payload = data or {}
    target_id = payload.get("target_id")
    caller_name = payload.get("caller_name") or "Someone"
    call_type = payload.get("call_type", "audio")
    call_id = payload.get("call_id")
    if target_id and call_id:
        from services.push_notification_service import send_call_notification, send_missed_call_notification
        send_call_notification(target_id, caller_name, call_type)
        emit_to_profile(target_id, "notification:call", {
            "call_id": call_id,
            "caller_name": caller_name,
            "call_type": call_type,
            "profile_id": profile_id,
        })
        return {"ok": True}
    return {"ok": False}


@socketio.on("notification:message")
def handle_notification_message(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    payload = data or {}
    target_id = payload.get("target_id")
    sender_name = payload.get("sender_name") or "Someone"
    message_preview = payload.get("body") or ""
    thread_id = payload.get("thread_id")
    if target_id and thread_id:
        from services.push_notification_service import send_message_notification
        send_message_notification(target_id, sender_name, message_preview, thread_id)
        emit_to_profile(target_id, "notification:message", {
            "thread_id": thread_id,
            "sender_name": sender_name,
            "body": message_preview[:120],
            "profile_id": profile_id,
        })
        return {"ok": True}
    return {"ok": False}


@socketio.on("notification:security")
def handle_notification_security(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    payload = data or {}
    target_id = payload.get("target_id")
    event_type = payload.get("event_type", "security_alert")
    title = payload.get("title", "Security Alert")
    body = payload.get("body", "A security event was detected.")
    if target_id:
        from services.push_notification_service import send_security_notification
        send_security_notification(target_id, event_type, title, body)
        emit_to_profile(target_id, "notification:security", {
            "event_type": event_type,
            "title": title,
            "body": body,
            "profile_id": profile_id,
        })
        return {"ok": True}
    return {"ok": False}


@socketio.on("notification:group-call")
def handle_notification_group_call(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    payload = data or {}
    target_id = payload.get("target_id")
    invited_by_name = payload.get("invited_by_name") or "Someone"
    call_id = payload.get("call_id")
    room_name = payload.get("room_name", "")
    if target_id and call_id:
        from services.push_notification_service import send_group_call_invite
        send_group_call_invite(target_id, invited_by_name, call_id, room_name)
        emit_to_profile(target_id, "notification:group-call", {
            "call_id": call_id,
            "invited_by_name": invited_by_name,
            "room_name": room_name,
            "profile_id": profile_id,
        })
        return {"ok": True}
    return {"ok": False}


# ---------- PHASE 46: E2EE Socket Events ----------


@socketio.on("encryption:status")
def handle_encryption_status(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    from services.e2ee_service import get_encryption_status
    status = get_encryption_status(profile_id)
    emit_to_profile(profile_id, "encryption:status", status)
    return status


@socketio.on("encryption:key-rotated")
def handle_encryption_key_rotated(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    payload = data or {}
    peer_profile_id = payload.get("peer_profile_id")
    thread_id = payload.get("thread_id")
    from services.e2ee_service import rotate_encryption_session, record_key_rotation_event
    result = rotate_encryption_session(profile_id, peer_profile_id=peer_profile_id, thread_id=thread_id)
    if result.get("ok"):
        record_key_rotation_event(
            profile_id=profile_id, thread_id=thread_id,
            old_key_version=0, new_key_version=result.get("session", {}).get("session_key_id", "1"),
            reason="manual",
        )
        room = thread_id if thread_id else profile_id
        emit("encryption:key-rotated", {
            "profile_id": profile_id,
            "peer_profile_id": peer_profile_id,
            "thread_id": thread_id,
            "ts": _utcnow_iso(),
        }, room=room)
        return {"ok": True}
    return {"ok": False}


@socketio.on("encryption:thread-secured")
def handle_encryption_thread_secured(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    thread_id = (data or {}).get("thread_id")
    if thread_id:
        from services.neon_service import write_query
        try:
            write_query("UPDATE chain_message_threads SET is_e2ee = TRUE, e2ee_activated_at = now() WHERE id = %s", (thread_id,))
        except Exception:
            pass
        emit_to_profile(profile_id, "encryption:thread-secured", {
            "thread_id": thread_id,
            "profile_id": profile_id,
            "ts": _utcnow_iso(),
        })
        return {"ok": True}
    return {"ok": False}


@socketio.on("encryption:group-key-rotated")
def handle_encryption_group_key_rotated(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    payload = data or {}
    group_id = payload.get("group_id")
    thread_id = payload.get("thread_id")
    reason = payload.get("reason", "manual")
    if group_id or thread_id:
        from services.e2ee_service import rotate_group_encryption_key
        result = rotate_group_encryption_key(group_id=group_id, thread_id=thread_id, reason=reason)
        if result.get("ok"):
            emit_to_profile(profile_id, "encryption:group-key-rotated", {
                "group_id": group_id,
                "thread_id": thread_id,
                "key_version": result.get("key_version"),
                "reason": reason,
                "ts": _utcnow_iso(),
            })
            return {"ok": True}
    return {"ok": False}


@socketio.on("encryption:message-secured")
def handle_encryption_message_secured(data):
    profile_id = _get_profile_id()
    if not profile_id:
        return {"ok": False}
    payload = data or {}
    thread_id = payload.get("thread_id")
    message_id = payload.get("message_id")
    if thread_id and message_id:
        from services.e2ee_service import mark_message_encrypted
        mark_message_encrypted(message_id)
        emit_to_profile(profile_id, "encryption:message-secured", {
            "thread_id": thread_id,
            "message_id": message_id,
            "ts": _utcnow_iso(),
        })
        return {"ok": True}
    return {"ok": False}


@socketio.on("safety:report-created")
def handle_safety_report_created(data):
    emit_to_profile(_get_profile_id(), "safety:report-created", data or {})
    return {"ok": True}


@socketio.on("safety:warning-issued")
def handle_safety_warning_issued(data):
    emit_to_profile(_get_profile_id(), "safety:warning-issued", data or {})
    return {"ok": True}


@socketio.on("safety:user-restricted")
def handle_safety_user_restricted(data):
    emit_to_profile(_get_profile_id(), "safety:user-restricted", data or {})
    return {"ok": True}


@socketio.on("safety:user-unrestricted")
def handle_safety_user_unrestricted(data):
    emit_to_profile(_get_profile_id(), "safety:user-unrestricted", data or {})
    return {"ok": True}


@socketio.on("safety:moderation-updated")
def handle_safety_moderation_updated(data):
    emit_to_profile(_get_profile_id(), "safety:moderation-updated", data or {})
    return {"ok": True}


@socketio.on("safety:fraud-alert")
def handle_safety_fraud_alert(data):
    emit_to_profile(_get_profile_id(), "safety:fraud-alert", data or {})
    return {"ok": True}


@socketio.on("safety:spam-alert")
def handle_safety_spam_alert(data):
    emit_to_profile(_get_profile_id(), "safety:spam-alert", data or {})
    return {"ok": True}


@socketio.on("safety:verification-updated")
def handle_safety_verification_updated(data):
    emit_to_profile(_get_profile_id(), "safety:verification-updated", data or {})
    return {"ok": True}


@socketio.on("trust:score-updated")
def handle_trust_score_updated(data):
    emit_to_profile(_get_profile_id(), "trust:score-updated", data or {})
    return {"ok": True}
