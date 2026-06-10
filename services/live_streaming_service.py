import os
import re
from datetime import datetime, timezone
from flask import session
from services.profile_service import get_current_profile
from services.supabase_safe import safe_count, safe_insert, safe_select, safe_update, safe_delete
from services.live_service import get_room, get_live_rooms, end_live, join_room, add_comment

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

def _safe_number(value, default=0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default

def _load_profile_map(profile_ids):
    ids = [pid for pid in profile_ids if pid]
    if not ids:
        return {}
    profiles = safe_select("chain_profiles", limit=len(ids), filters={"id": ("in", ids)}, order_by=None)
    return {p["id"]: p for p in profiles}

# ─── Participants / Multi-host ───

def add_participant(room_id, profile_id, role="viewer"):
    existing = safe_select("chain_live_participants", filters={"room_id": room_id, "profile_id": profile_id}, limit=1, order_by=None)
    if existing:
        safe_update("chain_live_participants", {"is_active": True, "role": role}, eq={"id": existing[0]["id"]})
        return existing[0]
    payload = {"room_id": room_id, "profile_id": profile_id, "role": role, "joined_at": _utcnow_iso()}
    return safe_insert("chain_live_participants", payload)

def remove_participant(room_id, profile_id):
    safe_update("chain_live_participants", {"is_active": False}, eq={"room_id": room_id, "profile_id": profile_id})

def get_participants(room_id):
    rows = safe_select("chain_live_participants", limit=100, filters={"room_id": room_id, "is_active": True})
    profile_ids = [r.get("profile_id") for r in rows]
    profiles = _load_profile_map(profile_ids)
    result = []
    for r in rows:
        p = profiles.get(r.get("profile_id")) or {}
        result.append({**r, "display_name": p.get("full_name") or p.get("username") or "Member", "avatar_url": p.get("avatar_url")})
    return result

def get_hosts(room_id):
    return safe_select("chain_live_participants", limit=10, filters={"room_id": room_id, "role": ("in", ["host","co-host"]), "is_active": True})

def promote_cohost(room_id, profile_id, actor_profile_id):
    room = get_room(room_id)
    if not room:
        return False, "Room not found"
    if str(room.get("host_profile_id")) != str(actor_profile_id):
        return False, "Only the host can promote co-hosts"
    add_participant(room_id, profile_id, "co-host")
    return True, "Co-host added"

def demote_participant(room_id, profile_id, actor_profile_id):
    room = get_room(room_id)
    if not room:
        return False, "Room not found"
    if str(room.get("host_profile_id")) != str(actor_profile_id):
        return False, "Only the host can demote"
    remove_participant(room_id, profile_id)
    return True, "Removed"

# ─── Premium Gifts ───

def get_gift_catalog(include_inactive=False):
    filters = {} if include_inactive else {"is_active": True}
    return safe_select("chain_gift_catalog", limit=50, filters=filters, order_by="sort_order", desc=False)

def send_premium_gift(room_id, sender_profile_id, gift_id, quantity=1):
    gift_rows = safe_select("chain_gift_catalog", filters={"id": gift_id, "is_active": True}, limit=1, order_by=None)
    if not gift_rows:
        return False, "Gift not found"
    gift = gift_rows[0]
    total_coins = _safe_number(gift.get("coin_price"), 0) * quantity
    room = get_room(room_id)
    if not room:
        return False, "Room not found"
    from services.wallet_engine import deduct_coins
    ok, err = deduct_coins(sender_profile_id, int(total_coins), "live_gift", room_id)
    if not ok:
        return False, err or "Insufficient coins"
    gift_payload = {
        "room_id": room_id,
        "sender_profile_id": sender_profile_id,
        "gift_name": gift.get("gift_name"),
        "gift_icon": gift.get("gift_icon", "🎁"),
        "amount": total_coins,
        "created_at": _utcnow_iso(),
    }
    inserted = safe_insert("chain_live_gifts", gift_payload)
    host_id = room.get("host_profile_id") or room.get("profile_id")
    if host_id:
        safe_insert("chain_live_earnings", {
            "profile_id": host_id,
            "room_id": room_id,
            "source_type": "gift",
            "source_id": inserted[0].get("id") if inserted else None,
            "amount": total_coins,
            "currency": "coins",
            "status": "pending",
            "created_at": _utcnow_iso(),
        })
    _update_room_gift_total(room_id)
    _check_goals(room_id, total_coins)
    return True, "Gift sent"

def _update_room_gift_total(room_id):
    gifts = safe_select("chain_live_gifts", limit=500, filters={"room_id": room_id})
    total = sum(_safe_number(g.get("amount"), 0) for g in gifts)
    safe_update("chain_live_rooms", {"gift_total_earned": total}, eq={"id": room_id})

# ─── Raids ───

def create_raid(source_room_id, target_room_id, host_profile_id, viewer_count=0):
    payload = {
        "source_room_id": source_room_id,
        "target_room_id": target_room_id,
        "host_profile_id": host_profile_id,
        "viewer_count": int(viewer_count),
        "status": "pending",
        "created_at": _utcnow_iso(),
    }
    return safe_insert("chain_live_raids", payload)

def activate_raid(raid_id):
    safe_update("chain_live_raids", {"status": "active"}, eq={"id": raid_id})

def complete_raid(raid_id):
    safe_update("chain_live_raids", {"status": "completed", "completed_at": _utcnow_iso()}, eq={"id": raid_id})

def cancel_raid(raid_id):
    safe_update("chain_live_raids", {"status": "cancelled"}, eq={"id": raid_id})

def get_raids_for_room(room_id):
    return safe_select("chain_live_raids", limit=20, filters={"source_room_id": room_id}, order_by="created_at", desc=True)

def get_incoming_raids(room_id):
    return safe_select("chain_live_raids", limit=10, filters={"target_room_id": room_id, "status": "active"})

def raid_target_options(exclude_room_id, limit=10):
    rooms = get_live_rooms(limit=20)
    return [r for r in rooms if r.get("id") != exclude_room_id][:limit]

# ─── Stream Goals ───

def create_goal(room_id, title, target_amount, goal_type="gifts"):
    payload = {
        "room_id": room_id,
        "title": title,
        "target_amount": _safe_number(target_amount, 100),
        "current_amount": 0,
        "goal_type": goal_type,
        "is_active": True,
        "created_at": _utcnow_iso(),
    }
    return safe_insert("chain_live_goals", payload)

def get_active_goals(room_id):
    return safe_select("chain_live_goals", limit=10, filters={"room_id": room_id, "is_active": True}, order_by="created_at", desc=False)

def update_goal_progress(goal_id, amount):
    goal = safe_select("chain_live_goals", filters={"id": goal_id}, limit=1, order_by=None)
    if not goal:
        return
    g = goal[0]
    new_current = _safe_number(g.get("current_amount"), 0) + _safe_number(amount, 0)
    update = {"current_amount": new_current}
    if new_current >= _safe_number(g.get("target_amount"), 0) and not g.get("reached_at"):
        update["reached_at"] = _utcnow_iso()
    safe_update("chain_live_goals", update, eq={"id": goal_id})

def _check_goals(room_id, amount):
    goals = get_active_goals(room_id)
    for g in goals:
        if g.get("goal_type") == "gifts":
            update_goal_progress(g["id"], amount)

def complete_goal(goal_id):
    safe_update("chain_live_goals", {"is_active": False, "reached_at": _utcnow_iso()}, eq={"id": goal_id})

# ─── Chat Moderation ───

def ban_user(room_id, profile_id, banned_by, reason=None, duration_minutes=0):
    payload = {
        "room_id": room_id,
        "profile_id": profile_id,
        "banned_by": banned_by,
        "reason": reason or "",
        "duration_minutes": int(duration_minutes),
        "expires_at": None,
        "created_at": _utcnow_iso(),
    }
    if duration_minutes > 0:
        from datetime import timedelta
        payload["expires_at"] = (datetime.now(timezone.utc) + timedelta(minutes=int(duration_minutes))).isoformat()
    return safe_insert("chain_live_chat_bans", payload)

def unban_user(room_id, profile_id):
    rows = safe_select("chain_live_chat_bans", filters={"room_id": room_id, "profile_id": profile_id}, limit=1, order_by=None)
    if rows:
        safe_delete("chain_live_chat_bans", eq={"id": rows[0]["id"]})

def is_banned(room_id, profile_id):
    rows = safe_select("chain_live_chat_bans", filters={"room_id": room_id, "profile_id": profile_id}, limit=1, order_by=None)
    if not rows:
        return False
    ban = rows[0]
    if ban.get("expires_at"):
        try:
            expires = datetime.fromisoformat(ban["expires_at"].replace("Z", "+00:00"))
            if expires < datetime.now(timezone.utc):
                safe_delete("chain_live_chat_bans", eq={"id": ban["id"]})
                return False
        except (ValueError, TypeError):
            pass
    return True

def get_bans(room_id):
    return safe_select("chain_live_chat_bans", limit=100, filters={"room_id": room_id}, order_by="created_at", desc=True)

def get_moderators(room_id):
    return safe_select("chain_live_participants", limit=20, filters={"room_id": room_id, "role": ("in", ["host","co-host","moderator"]), "is_active": True})

def add_moderator(room_id, profile_id, actor_profile_id):
    room = get_room(room_id)
    if not room:
        return False, "Room not found"
    if str(room.get("host_profile_id")) != str(actor_profile_id):
        return False, "Only the host can add moderators"
    add_participant(room_id, profile_id, "moderator")
    return True, "Moderator added"

# ─── Earnings ───

def get_earnings(profile_id, status=None):
    filters = {"profile_id": profile_id}
    if status:
        filters["status"] = status
    return safe_select("chain_live_earnings", limit=200, filters=filters, order_by="created_at", desc=True)

def get_earnings_summary(profile_id):
    rows = get_earnings(profile_id)
    total = sum(_safe_number(r.get("amount"), 0) for r in rows)
    pending = sum(_safe_number(r.get("amount"), 0) for r in rows if r.get("status") == "pending")
    available = sum(_safe_number(r.get("amount"), 0) for r in rows if r.get("status") == "available")
    return {"total": total, "pending": pending, "available": available, "count": len(rows)}

def withdraw_earnings(profile_id, amount):
    rows = safe_select("chain_live_earnings", limit=200, filters={"profile_id": profile_id, "status": "available"})
    available = sum(_safe_number(r.get("amount"), 0) for r in rows)
    if _safe_number(amount, 0) > available:
        return False, "Insufficient available earnings"
    withdraw_amount = _safe_number(amount, 0)
    remaining = withdraw_amount
    for r in rows:
        if remaining <= 0:
            break
        r_amount = _safe_number(r.get("amount"), 0)
        if r_amount <= remaining:
            safe_update("chain_live_earnings", {"status": "withdrawn"}, eq={"id": r["id"]})
            remaining -= r_amount
        else:
            safe_update("chain_live_earnings", {"amount": r_amount - remaining}, eq={"id": r["id"]})
            remaining = 0
    return True, f"Withdrew {withdraw_amount} coins"

# ─── Dashboard ───

def get_dashboard_stats(profile_id):
    my_rooms = safe_select("chain_live_rooms", limit=50, filters={"host_profile_id": profile_id}, order_by="created_at", desc=True)
    active_rooms = [r for r in my_rooms if r.get("is_live") or r.get("status") in ("live", "active")]
    total_viewers = sum(_safe_number(r.get("viewer_count"), 0) for r in my_rooms)
    total_gifts = sum(_safe_number(r.get("gift_total_earned"), _safe_number(r.get("gift_total"), 0)) for r in my_rooms)
    earnings_data = get_earnings_summary(profile_id)
    return {
        "total_rooms": len(my_rooms),
        "active_rooms": len(active_rooms),
        "total_viewers": total_viewers,
        "total_gifts": total_gifts,
        "earnings": earnings_data,
        "recent_rooms": my_rooms[:10],
    }

# ─── Room discovery ───

def get_featured_rooms(limit=6):
    rooms = safe_select("chain_live_rooms", limit=limit, filters={"is_featured": True, "is_live": True}, order_by="viewer_count", desc=True)
    if not rooms:
        rooms = get_live_rooms(limit=limit)
    return rooms

def get_rooms_by_category(category, limit=12):
    return safe_select("chain_live_rooms", limit=limit, filters={"category": category, "is_live": True}, order_by="viewer_count", desc=True)

def get_premium_rooms(limit=12):
    return safe_select("chain_live_rooms", limit=limit, filters={"access_type": "premium", "is_live": True}, order_by="created_at", desc=True)

# ─── Metadata helpers ───

def get_room_metadata(room_id):
    room = get_room(room_id)
    if not room:
        return None
    participants = get_participants(room_id)
    goals = get_active_goals(room_id)
    hosts = [p for p in participants if p.get("role") in ("host", "co-host")]
    viewer_count = _safe_number(room.get("viewer_count"), 0)
    return {
        "room": room,
        "hosts": hosts,
        "participant_count": len(participants),
        "goals": goals,
        "viewer_count": viewer_count,
        "gift_total": room.get("gift_total_earned") or room.get("gift_total") or 0,
        "is_premium": room.get("access_type") == "premium",
        "is_mature": room.get("is_mature", False),
        "tags": room.get("tags") or [],
    }
