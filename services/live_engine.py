import time
import uuid
from datetime import datetime, timezone
from functools import wraps

from services.live_service import (
    create_live_room as _legacy_create_room,
    get_live_rooms as _legacy_get_rooms,
    get_room as _legacy_get_room,
    join_room as _legacy_join_room,
    room_activity as _legacy_room_activity,
    add_comment as _legacy_add_comment,
    send_gift as _legacy_send_gift,
    end_live as _legacy_end_live,
    request_cohost as _legacy_request_cohost,
    get_cohost_requests as _legacy_get_cohost_requests,
    update_cohost_status as _legacy_update_cohost_status,
)
from services.live_streaming_service import (
    add_participant as _ls_add_participant,
    remove_participant as _ls_remove_participant,
    get_participants as _ls_get_participants,
    get_hosts as _ls_get_hosts,
    promote_cohost as _ls_promote_cohost,
    demote_participant as _ls_demote_participant,
    get_gift_catalog as _ls_get_gift_catalog,
    send_premium_gift as _ls_send_premium_gift,
    ban_user as _ls_ban_user,
    unban_user as _ls_unban_user,
    is_banned as _ls_is_banned,
)
from services.live_feature_service import (
    moderation_action as _lf_moderation_action,
    request_guest as _lf_request_guest,
    update_guest_request as _lf_update_guest_request,
)
from services.profile_service import get_current_profile
from services.socketio_service import emit_to_live_room, emit_to_profile
from services.relationship_gate_service import is_blocked
from services.performance_monitor import track_timing
from services.supabase_safe import safe_select, safe_insert, safe_update, safe_count

_LIVE_ACTIVITY_EVENTS = frozenset({
    "live_started", "live_ended", "live_joined", "live_left",
    "live_chat_sent", "live_chat_deleted", "live_reaction",
    "live_gift_sent", "live_guest_requested", "live_guest_approved",
    "live_guest_rejected", "live_cohost_added", "live_cohost_removed",
    "live_moderated", "live_viewer_count",
})


def _now():
    return datetime.now(timezone.utc).isoformat()


def _uuid(value):
    if value:
        try:
            return str(uuid.UUID(str(value)))
        except (TypeError, ValueError):
            pass
    return str(uuid.uuid4())


def _get_current_user():
    return get_current_profile()


def _can_moderate(room, profile_id):
    if not profile_id or not room:
        return False
    host_id = room.get("host_profile_id") or room.get("profile_id")
    if str(host_id) == str(profile_id):
        return True
    mods = _ls_get_participants(room.get("id"))
    for mod in mods:
        if str(mod.get("profile_id")) == str(profile_id) and mod.get("role") in ("host", "co-host", "moderator"):
            return True
    return False


def _track_op(name):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                track_timing(f"live.{name}", round((time.perf_counter() - start) * 1000, 2))
                return result
            except Exception as e:
                track_timing(f"live.{name}.error", round((time.perf_counter() - start) * 1000, 2))
                return {"ok": False, "error": str(e)}
        return wrapper
    return decorator


def _emit_activity(actor_id, event_type, target_type=None, target_id=None, recipient_id=None, metadata=None):
    try:
        from services.activity_engine import emit_activity
        if event_type in _LIVE_ACTIVITY_EVENTS:
            emit_activity(
                actor_profile_id=actor_id,
                event_type=event_type,
                target_type=target_type or "live_room",
                target_id=target_id,
                recipient_profile_id=recipient_id,
                metadata=metadata,
            )
    except Exception:
        pass


def _create_notification(recipient_id, actor_id, event_type, title, body=None, entity_type="live_room", entity_id=None, action_url=None):
    if not recipient_id:
        return None
    try:
        from services.notification_center_service import create_notification as _notif
        return _notif(
            recipient_profile_id=recipient_id,
            notification_type=event_type,
            title=title,
            body=body,
            actor_profile_id=actor_id,
            target_type=entity_type,
            target_id=entity_id,
            action_url=action_url,
        )
    except Exception:
        try:
            from services.notification_engine import create_notification as _notif
            return _notif(
                recipient_profile_id=recipient_id,
                event_type=event_type,
                title=title,
                body=body,
                actor_profile_id=actor_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action_url=action_url,
            )
        except Exception:
            return None


def _wallet_available():
    try:
        from services.wallet_engine import deduct_coins
        return True
    except Exception:
        return False


def _deduct_coins_wallet(profile_id, amount, tx_type, ref_id):
    try:
        from services.wallet_engine import deduct_coins
        ok, err = deduct_coins(profile_id, int(amount), tx_type, ref_id)
        if ok:
            return {"ok": True}
        return {"ok": False, "error": err or "wallet_error"}
    except Exception:
        return {"ok": False, "error": "wallet_disabled"}


# ─── Room Lifecycle ───

@_track_op("create_room")
def create_live_room(form_data, files=None):
    room = _legacy_create_room(form_data, files)
    if not room:
        return {"ok": False, "error": "room_creation_failed"}
    _emit_activity(
        actor_id=room.get("host_profile_id") or room.get("profile_id"),
        event_type="live_started",
        target_id=room.get("id"),
        metadata={"title": room.get("title")},
    )
    _notify_followers_live_started(room)
    emit_to_live_room(room.get("id"), "live:started", room)
    return {"ok": True, "room": room}


@_track_op("get_room")
def get_live_room(room_id):
    room = _legacy_get_room(room_id)
    if not room:
        return {"ok": False, "error": "not_found"}
    return {"ok": True, "room": room}


@_track_op("list_rooms")
def get_live_rooms(limit=30):
    rooms = _legacy_get_rooms(limit=limit)
    return {"ok": True, "rooms": rooms}


@_track_op("trending_rooms")
def get_trending_live_rooms(limit=12):
    rooms = safe_select(
        "chain_live_rooms",
        limit=limit,
        filters={"is_live": True},
        order_by="viewer_count",
        desc=True,
    )
    if not rooms:
        rooms = safe_select(
            "chain_live_rooms",
            limit=limit,
            filters={"status": "live"},
            order_by="viewer_count",
            desc=True,
        )
    return {"ok": True, "rooms": rooms}


@_track_op("start_room")
def start_live_room(profile_id, title, host_name=None):
    try:
        from services.live_feature_service import start_live
        result = start_live(profile_id, title, host_name)
        if result.get("ok"):
            room = result.get("room")
            _emit_activity(profile_id, "live_started", target_id=room.get("id"), metadata={"title": title})
            _notify_followers_live_started(room)
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


@_track_op("end_room")
def end_live_room(room_id, profile_id=None):
    try:
        from services.live_feature_service import end_live as _lf_end
        result = _lf_end(room_id, profile_id)
        if result.get("ok"):
            _legacy_end_live(room_id)
            _emit_activity(profile_id, "live_ended", target_id=room_id)
            emit_to_live_room(room_id, "live:ended", {"room_id": room_id, "ended_at": _now()})
        return result
    except Exception as e:
        _legacy_end_live(room_id)
        return {"ok": True, "room_id": room_id}


def _notify_followers_live_started(room):
    host_id = room.get("host_profile_id") or room.get("profile_id")
    room_id = room.get("id")
    if not host_id or not room_id:
        return
    followers = safe_select("chain_follows", columns="follower_profile_id", filters={"following_profile_id": host_id}, limit=100, order_by=None)
    if not followers:
        return
    title = room.get("title") or "Live"
    for f in followers:
        recipient_id = f.get("follower_profile_id")
        if not recipient_id:
            continue
        _create_notification(
            recipient_id=recipient_id,
            actor_id=host_id,
            event_type="live_started",
            title="Live started",
            body=f"{room.get('host_name') or 'A creator'} is live: {title}",
            entity_id=room_id,
            action_url=f"/live/room/{room_id}",
        )


# ─── Viewer Management ───

@_track_op("join_room")
def join_live_room(room_id, display_name=None):
    profile = _get_current_user()
    profile_id = profile.get("id") if profile else None

    if profile_id:
        blocked = is_blocked(profile_id, profile_id)
        if blocked:
            return {"ok": False, "error": "blocked"}

    room_resp = get_live_room(room_id)
    if not room_resp.get("ok"):
        return {"ok": False, "error": "room_not_found"}

    room = room_resp.get("room")
    if room.get("is_live") is False or room.get("status") == "ended":
        return {"ok": False, "error": "room_ended"}

    _legacy_join_room(room_id, display_name)
    if profile_id:
        _ls_add_participant(room_id, profile_id, "viewer")

    _emit_activity(profile_id, "live_joined", target_id=room_id, recipient_id=room.get("host_profile_id"))
    emit_to_live_room(room_id, "live:joined", {"profile_id": profile_id, "room_id": room_id})

    count_resp = get_live_viewers(room_id)
    if count_resp.get("ok"):
        update_viewer_count(room_id, count_resp["viewer_count"])

    return {"ok": True, "room": room}


@_track_op("leave_room")
def leave_live_room(room_id, profile_id=None):
    if profile_id:
        _ls_remove_participant(room_id, profile_id)
        try:
            from services.supabase_safe import safe_update
            safe_update("chain_live_viewers", {"left_at": _now()}, eq={"room_id": room_id, "profile_id": profile_id})
        except Exception:
            pass
    _emit_activity(profile_id, "live_left", target_id=room_id)
    emit_to_live_room(room_id, "live:left", {"profile_id": profile_id, "room_id": room_id})

    count_resp = get_live_viewers(room_id)
    if count_resp.get("ok"):
        update_viewer_count(room_id, count_resp["viewer_count"])

    return {"ok": True}


@_track_op("get_viewers")
def get_live_viewers(room_id):
    viewers = _ls_get_participants(room_id)
    count = len(viewers)
    return {"ok": True, "viewers": viewers, "viewer_count": count}


@_track_op("update_viewer_count")
def update_viewer_count(room_id, count):
    try:
        safe_update("chain_live_rooms", {"viewer_count": count}, eq={"id": room_id})
    except Exception:
        pass
    emit_to_live_room(room_id, "live:viewer_count", {"room_id": room_id, "count": count})


# ─── Guest Management ───

@_track_op("request_guest")
def request_guest_slot(room_id, profile_id, note=None):
    result = _lf_request_guest(room_id, profile_id, note)
    if result.get("ok"):
        room = _legacy_get_room(room_id)
        _emit_activity(profile_id, "live_guest_requested", target_id=room_id, recipient_id=room.get("host_profile_id") if room else None)
        host_id = room.get("host_profile_id") if room else None
        if host_id:
            _create_notification(
                recipient_id=host_id,
                actor_id=profile_id,
                event_type="live_guest_request",
                title="Guest request",
                body="Someone wants to be a guest in your live room",
                entity_id=room_id,
                action_url=f"/live/room/{room_id}",
            )
    return result


@_track_op("approve_guest")
def approve_guest_request(request_id):
    result = _lf_update_guest_request(request_id, "accepted")
    return result


@_track_op("reject_guest")
def reject_guest_request(request_id):
    result = _lf_update_guest_request(request_id, "rejected")
    return result


@_track_op("remove_guest")
def remove_guest(room_id, profile_id):
    try:
        safe_update("chain_live_guest_requests", {"status": "removed", "updated_at": _now()}, eq={"room_id": room_id, "profile_id": profile_id})
    except Exception:
        pass
    _ls_remove_participant(room_id, profile_id)
    return {"ok": True}


# ─── Cohost Management ───

@_track_op("add_cohost")
def add_cohost(room_id, profile_id, actor_profile_id):
    ok, msg = _ls_promote_cohost(room_id, profile_id, actor_profile_id)
    if ok:
        _emit_activity(actor_profile_id, "live_cohost_added", target_id=room_id, recipient_id=profile_id)
        _create_notification(
            recipient_id=profile_id,
            actor_id=actor_profile_id,
            event_type="live_cohost_added",
            title="You're now co-host",
            body="You have been promoted to co-host",
            entity_id=room_id,
            action_url=f"/live/room/{room_id}",
        )
    return {"ok": ok, "message": msg}


@_track_op("remove_cohost")
def remove_cohost(room_id, profile_id, actor_profile_id):
    ok, msg = _ls_demote_participant(room_id, profile_id, actor_profile_id)
    if ok:
        _emit_activity(actor_profile_id, "live_cohost_removed", target_id=room_id, recipient_id=profile_id)
    return {"ok": ok, "message": msg}


@_track_op("get_cohosts")
def get_cohosts(room_id):
    hosts = _ls_get_hosts(room_id)
    return {"ok": True, "cohosts": hosts}


# ─── Chat ───

@_track_op("send_chat")
def send_live_chat(room_id, profile_id, body, display_name=None):
    body = (body or "").strip()
    if not body:
        return {"ok": False, "error": "empty_message"}

    if _ls_is_banned(room_id, profile_id):
        return {"ok": False, "error": "banned"}

    _legacy_add_comment(room_id, body, display_name)

    message = {
        "id": str(uuid.uuid4()),
        "room_id": room_id,
        "profile_id": profile_id,
        "display_name": display_name or "Member",
        "body": body,
        "created_at": _now(),
    }
    emit_to_live_room(room_id, "live:chat", message)
    _emit_activity(profile_id, "live_chat_sent", target_id=room_id)
    return {"ok": True, "message": message}


@_track_op("get_chat")
def get_live_chat_messages(room_id, limit=50):
    messages = safe_select(
        "chain_live_comments",
        limit=limit,
        filters={"room_id": room_id},
        order_by="created_at",
        desc=False,
    )
    return {"ok": True, "messages": messages}


@_track_op("delete_chat")
def delete_live_chat_message(room_id, message_id, profile_id):
    room = _legacy_get_room(room_id)
    if not _can_moderate(room, profile_id):
        return {"ok": False, "error": "unauthorized"}
    try:
        safe_update("chain_live_comments", {"is_deleted": True}, eq={"id": message_id})
    except Exception:
        safe_update("chain_live_comments", {"body": "[deleted]"}, eq={"id": message_id})
    emit_to_live_room(room_id, "live:chat_deleted", {"message_id": message_id, "room_id": room_id})
    _emit_activity(profile_id, "live_chat_deleted", target_id=room_id)
    return {"ok": True}


@_track_op("pin_chat")
def pin_live_chat_message(room_id, message_id, profile_id):
    room = _legacy_get_room(room_id)
    if not _can_moderate(room, profile_id):
        return {"ok": False, "error": "unauthorized"}
    from services.live_service import pin_comment
    ok = pin_comment(room_id, message_id, profile_id)
    return {"ok": ok}


# ─── Reactions ───

@_track_op("send_reaction")
def send_live_reaction(room_id, profile_id, reaction_type="heart"):
    from services.realtime_service import track_live_reaction
    track_live_reaction(room_id, profile_id, reaction_type)

    reaction = {
        "id": str(uuid.uuid4()),
        "room_id": room_id,
        "profile_id": profile_id,
        "reaction_type": reaction_type,
        "created_at": _now(),
    }
    emit_to_live_room(room_id, "live:reaction", reaction)
    _emit_activity(profile_id, "live_reaction", target_id=room_id)
    return {"ok": True, "reaction": reaction}


@_track_op("get_reactions")
def get_live_reactions(room_id, limit=50):
    reactions = safe_select(
        "chain_live_reactions",
        limit=limit,
        filters={"room_id": room_id},
        order_by="created_at",
        desc=True,
    )
    return {"ok": True, "reactions": reactions}


# ─── Gifts ───

@_track_op("send_gift")
def send_live_gift(room_id, sender_profile_id, gift_name=None, gift_icon=None, coins=0, use_wallet=True):
    room = _legacy_get_room(room_id)
    if not room:
        return {"ok": False, "error": "room_not_found"}

    coins = max(0, int(coins))

    if use_wallet and coins > 0:
        wallet_result = _deduct_coins_wallet(sender_profile_id, coins, "live_gift", room_id)
        if not wallet_result.get("ok"):
            if wallet_result.get("error") == "wallet_disabled":
                return {"ok": False, "code": "wallet_disabled", "error": "Wallet system not available"}
            return wallet_result

    _legacy_send_gift(room_id, gift_icon, gift_name or "Gift", coins, None)

    host_id = room.get("host_profile_id") or room.get("profile_id")
    if host_id:
        _create_notification(
            recipient_id=host_id,
            actor_id=sender_profile_id,
            event_type="live_gift_sent",
            title="Gift received!",
            body=f"Received a {gift_name or 'Gift'} worth {coins} coins",
            entity_id=room_id,
            action_url=f"/live/room/{room_id}",
        )

    _emit_activity(sender_profile_id, "live_gift_sent", target_id=room_id, recipient_id=host_id)
    emit_to_live_room(room_id, "live:gift", {
        "sender_profile_id": sender_profile_id,
        "gift_name": gift_name or "Gift",
        "gift_icon": gift_icon or "🎁",
        "coins": coins,
        "room_id": room_id,
    })
    return {"ok": True}


@_track_op("gift_leaderboard")
def get_live_gift_leaderboard(room_id, limit=10):
    try:
        from services.live_service import get_room_leaderboard
        data = get_room_leaderboard(room_id, limit=limit)
        return {"ok": True, "leaderboard": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@_track_op("gift_catalog")
def get_live_gift_catalog(include_inactive=False):
    catalog = _ls_get_gift_catalog(include_inactive=include_inactive)
    return {"ok": True, "catalog": catalog}


# ─── Moderation ───

@_track_op("moderate")
def moderate_live_user(room_id, moderator_profile_id, action_type, target_profile_id=None, reason=None):
    room = _legacy_get_room(room_id)
    if not _can_moderate(room, moderator_profile_id):
        return {"ok": False, "error": "unauthorized"}

    actions = {"mute", "unmute", "kick", "ban", "unban", "delete_message", "warn"}

    if action_type not in actions:
        return {"ok": False, "error": f"unknown_action:{action_type}"}

    if action_type == "ban":
        _ls_ban_user(room_id, target_profile_id, moderator_profile_id, reason, duration_minutes=0)
    elif action_type == "unban":
        _ls_unban_user(room_id, target_profile_id)
    elif action_type == "mute":
        from services.live_service import mute_user_live
        mute_user_live(room_id, target_profile_id, duration_minutes=15)
    elif action_type == "unmute":
        from services.redis_service import cache_delete
        try:
            cache_delete(f"live_mute:{room_id}:{target_profile_id}")
        except Exception:
            pass
    elif action_type == "kick":
        from services.live_service import remove_user_live
        remove_user_live(room_id, target_profile_id)

    _lf_moderation_action(room_id, moderator_profile_id, action_type, target_profile_id, reason)
    _emit_activity(moderator_profile_id, "live_moderated", target_id=room_id, metadata={
        "action": action_type,
        "target": target_profile_id,
    })
    emit_to_live_room(room_id, "live:moderation", {
        "action_type": action_type,
        "target_profile_id": target_profile_id,
        "moderator_profile_id": moderator_profile_id,
        "room_id": room_id,
    })
    return {"ok": True}


@_track_op("is_banned")
def is_user_banned(room_id, profile_id):
    banned = _ls_is_banned(room_id, profile_id)
    return {"ok": True, "banned": banned}


# ─── Analytics ───

@_track_op("room_analytics")
def get_live_analytics(room_id):
    room = _legacy_get_room(room_id)
    if not room:
        return {"ok": False, "error": "not_found"}
    activity = _legacy_room_activity(room_id)
    viewer_count = len(activity.get("viewers", []))
    comment_count = len(activity.get("comments", []))
    gift_count = len(activity.get("gifts", []))
    total_coins = sum(g.get("amount") or g.get("coins") or 0 for g in activity.get("gifts", []))
    analytics = {
        "room_id": room_id,
        "viewer_count": viewer_count,
        "comment_count": comment_count,
        "gift_count": gift_count,
        "total_coins": total_coins,
        "peak_viewers": room.get("peak_viewer_count") or viewer_count,
        "duration_minutes": 0,
    }
    created = room.get("created_at")
    if created and room.get("is_live"):
        try:
            if isinstance(created, str):
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            else:
                created_dt = created
            analytics["duration_minutes"] = round((datetime.now(timezone.utc) - created_dt).total_seconds() / 60, 1)
        except Exception:
            pass
    return {"ok": True, "analytics": analytics}


@_track_op("creator_analytics")
def get_creator_live_analytics(profile_id, limit=50):
    rooms = safe_select(
        "chain_live_rooms",
        limit=limit,
        filters={"host_profile_id": profile_id},
        order_by="created_at",
        desc=True,
    )
    total_viewers = 0
    total_gifts = 0
    total_coins = 0
    total_rooms = len(rooms)
    live_rooms = 0
    for room in rooms:
        if room.get("is_live") or room.get("status") == "live":
            live_rooms += 1
        total_viewers += room.get("viewer_count") or 0
        total_gifts += room.get("gift_total") or room.get("gift_total_earned") or 0
        total_coins += room.get("total_gift_coins") or 0
    return {
        "ok": True,
        "analytics": {
            "total_rooms": total_rooms,
            "live_rooms": live_rooms,
            "total_viewers": total_viewers,
            "total_gifts": total_gifts,
            "total_coins": total_coins,
            "avg_viewers": round(total_viewers / max(total_rooms, 1), 1),
        },
    }
