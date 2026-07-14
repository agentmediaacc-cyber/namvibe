"""NamVibe Live API routes."""

import html
import os
import re
import time
import uuid

from flask import Blueprint, jsonify, request, session

from services.ai.interaction_service import track_interaction_safe
from services.livekit_service import (
    create_guest_token,
    create_ingress_token,
    create_viewer_token,
    get_livekit_server_info,
    check_livekit_health,
    livekit_configured,
    sanitize_room_name,
)
from services.neon_service import (
    execute,
    fetch_all,
    fetch_one,
    get_cached_table_columns,
    table_exists,
)
from services.turn_service import get_turn_config, get_turn_status
from services.wallet_engine import send_gift


live_bp = Blueprint("live_nvc", __name__, url_prefix="/api/live")

_VALID_STATUSES = {"scheduled", "starting", "live", "ended", "cancelled", "failed"}
_VALID_PRIVACY = {"public", "private", "premium", "followers"}
_VALID_SURFACES = {"live"}
_MAX_CHAT_LENGTH = 500


def _profile_id():
    pid = session.get("profile_id")
    if pid:
        return str(pid)
    try:
        from services.profile_service import get_current_profile

        profile = get_current_profile()
        if profile and profile.get("id"):
            return str(profile["id"])
    except Exception:
        pass
    auth_id = session.get("auth_user_id")
    return str(auth_id) if auth_id else None


def _columns(table_name):
    try:
        return set(get_cached_table_columns(table_name) or [])
    except Exception:
        return set()


def _owner_column(room_columns):
    for key in ("profile_id", "host_profile_id", "host_id", "creator_id"):
        if key in room_columns:
            return key
    return None


def _status_column_filter():
    return "r.deleted_at IS NULL AND COALESCE(r.is_live, FALSE) = TRUE AND COALESCE(r.status, 'live') IN ('live', 'starting')"


def _scheduled_filter():
    return "r.deleted_at IS NULL AND COALESCE(r.status, '') = 'scheduled'"


def _room_select_columns():
    room_cols = _columns("chain_live_rooms")
    profile_cols = _columns("chain_profiles")
    owner_col = _owner_column(room_cols)

    cols = ["r.id"]
    for name in [
        owner_col,
        "title",
        "description",
        "category",
        "status",
        "is_live",
        "viewer_count",
        "peak_viewer_count",
        "cover_url",
        "thumbnail_url",
        "created_at",
        "updated_at",
        "ended_at",
        "scheduled_at",
        "access_type",
        "visibility",
        "stream_mode",
        "allow_camera",
        "allow_microphone",
        "comments_enabled",
        "gifts_enabled",
        "private_mode",
        "webrtc_room_id",
        "replay_url",
    ]:
        if name and name in room_cols:
            cols.append(f"r.{name}")

    if "display_name" in profile_cols:
        cols.append("p.display_name")
    if "username" in profile_cols:
        cols.append("p.username")
    if "avatar_url" in profile_cols:
        cols.append("p.avatar_url")
    if "is_verified" in profile_cols:
        cols.append("p.is_verified")
    if "verified" in profile_cols:
        cols.append("p.verified")
    if "deleted_at" in profile_cols:
        cols.append("p.deleted_at AS profile_deleted_at")
    if "profile_visibility" in profile_cols:
        cols.append("p.profile_visibility")

    return cols, owner_col


def _normalize_room(row):
    if not row:
        return None
    room = dict(row)
    owner_id = room.get("profile_id") or room.get("host_profile_id") or room.get("host_id") or room.get("creator_id")
    room["owner_profile_id"] = owner_id
    room["host_name"] = room.get("display_name") or room.get("username") or "Host"
    room["host_username"] = room.get("username") or ""
    room["host_avatar"] = room.get("avatar_url") or ""
    room["is_verified"] = bool(room.get("is_verified") or room.get("verified"))
    room["status"] = _normalize_status(room.get("status"), room.get("is_live"))
    room["privacy"] = (room.get("access_type") or room.get("visibility") or ("private" if room.get("private_mode") else "public") or "public").lower()
    room["viewer_count"] = int(room.get("viewer_count") or 0)
    room["stream_mode"] = (room.get("stream_mode") or "camera").lower()
    room["type"] = "audio" if room["stream_mode"] == "audio" else "video"
    return room


def _normalize_status(value, is_live=False):
    raw = str(value or "").strip().lower()
    if raw in _VALID_STATUSES:
        return raw
    return "live" if is_live else "scheduled"


def _fetch_room(room_id):
    cols, owner_col = _room_select_columns()
    if not cols or not owner_col:
        return None
    sql = f"""
        SELECT {", ".join(cols)}
        FROM chain_live_rooms r
        JOIN chain_profiles p ON p.id = r.{owner_col}
        WHERE r.id = %s
        LIMIT 1
    """
    try:
        row = fetch_one(sql, (room_id,))
        return _normalize_room(row)
    except Exception:
        return None


def _active_room_for_host(profile_id):
    room_cols = _columns("chain_live_rooms")
    owner_col = _owner_column(room_cols)
    if not owner_col:
        return None
    where = ["r.%s = %%s" % owner_col]
    if "deleted_at" in room_cols:
        where.append("r.deleted_at IS NULL")
    if "status" in room_cols and "is_live" in room_cols:
        where.append("(COALESCE(r.is_live, FALSE) = TRUE OR COALESCE(r.status, '') IN ('live', 'starting', 'scheduled'))")
    elif "is_live" in room_cols:
        where.append("COALESCE(r.is_live, FALSE) = TRUE")
    elif "status" in room_cols:
        where.append("COALESCE(r.status, '') IN ('live', 'starting', 'scheduled')")

    sql = f"""
        SELECT r.id, r.title, r.status, COALESCE(r.is_live, FALSE) AS is_live
        FROM chain_live_rooms r
        WHERE {" AND ".join(where)}
        ORDER BY COALESCE(r.created_at, NOW()) DESC
        LIMIT 1
    """
    try:
        row = fetch_one(sql, (profile_id,))
        return dict(row) if row else None
    except Exception:
        return None


def _calculate_viewer_count(room):
    participant_cols = _columns("chain_live_participants")
    room_cols = _columns("chain_live_rooms")
    owner_id = (room or {}).get("owner_profile_id")
    room_id = (room or {}).get("id")
    if not room_id or not participant_cols or not table_exists("chain_live_participants"):
        return int((room or {}).get("viewer_count") or 0)

    clauses = ["room_id = %s"]
    params = [room_id]
    if "is_active" in participant_cols:
        clauses.append("COALESCE(is_active, TRUE) = TRUE")
    if "left_at" in participant_cols:
        clauses.append("left_at IS NULL")
    if "profile_id" in participant_cols and owner_id:
        clauses.append("profile_id <> %s")
        params.append(owner_id)
    distinct_expr = "COUNT(DISTINCT profile_id) AS cnt" if "profile_id" in participant_cols else "COUNT(*) AS cnt"
    try:
        row = fetch_one(f"SELECT {distinct_expr} FROM chain_live_participants WHERE {' AND '.join(clauses)}", tuple(params))
        return int((row or {}).get("cnt") or 0)
    except Exception:
        return int((room or {}).get("viewer_count") or 0)


def _sync_viewer_count(room):
    viewer_count = _calculate_viewer_count(room)
    room_cols = _columns("chain_live_rooms")
    updates = []
    params = []
    if "viewer_count" in room_cols:
        updates.append("viewer_count = %s")
        params.append(viewer_count)
    if "peak_viewer_count" in room_cols:
        updates.append("peak_viewer_count = GREATEST(COALESCE(peak_viewer_count, 0), %s)")
        params.append(viewer_count)
    if updates and room and room.get("id"):
        try:
            execute(f"UPDATE chain_live_rooms SET {', '.join(updates)} WHERE id = %s", tuple(params + [room["id"]]))
        except Exception:
            pass
    return viewer_count


def _room_access_allowed(room, profile_id):
    if not room:
        return False, "room_not_found"
    if room.get("status") in {"ended", "cancelled", "failed"} or room.get("is_live") is False and room.get("status") != "scheduled":
        return False, "stream_ended"
    if room.get("privacy") in {"private", "followers", "premium"} and not profile_id:
        return False, "auth_required"
    owner_id = room.get("owner_profile_id")
    if profile_id and owner_id:
        try:
            from services.blocking_service import is_blocked_any

            if is_blocked_any(str(profile_id), str(owner_id)):
                return False, "blocked"
        except Exception:
            pass
    return True, None


def _sanitize_chat_text(value):
    text = html.escape((value or "").strip())
    text = re.sub(r"\s+", " ", text)
    return text[:_MAX_CHAT_LENGTH]


def _validated_title(value):
    title = (value or "").strip()
    return title[:100] if title else "Untitled Stream"


def _validated_category(value):
    category = (value or "").strip().lower()
    return category[:64] if category else "entertainment"


def _validated_privacy(data):
    privacy = str((data or {}).get("live_type") or (data or {}).get("access_type") or (data or {}).get("visibility") or "public").strip().lower()
    return privacy if privacy in _VALID_PRIVACY else "public"


def _validated_status(data):
    requested = str((data or {}).get("status") or "live").strip().lower()
    requested = "scheduled" if requested == "schedule" else requested
    return requested if requested in _VALID_STATUSES else "live"


def _create_room_row(profile_id, data):
    room_cols = _columns("chain_live_rooms")
    owner_col = _owner_column(room_cols)
    if not room_cols or not owner_col:
        raise RuntimeError("live_room_schema_unavailable")

    room_id = str(uuid.uuid4())
    status = _validated_status(data)
    privacy = _validated_privacy(data)
    stream_mode = "audio" if str((data or {}).get("room_type") or "").strip().lower() == "audio" else "camera"
    base = {
        "id": room_id,
        owner_col: profile_id,
        "title": _validated_title((data or {}).get("title")),
        "description": str((data or {}).get("description") or "").strip()[:500],
        "category": _validated_category((data or {}).get("category")),
        "status": "scheduled" if status == "scheduled" else "starting",
        "is_live": False if status == "scheduled" else False,
        "viewer_count": 0,
        "peak_viewer_count": 0,
        "stream_mode": stream_mode,
        "visibility": privacy,
        "access_type": privacy,
        "allow_camera": stream_mode != "audio",
        "allow_microphone": True,
        "comments_enabled": True,
        "gifts_enabled": True,
        "private_mode": privacy == "private",
    }
    if "host_profile_id" in room_cols:
        base["host_profile_id"] = profile_id
    if "scheduled_at" in room_cols and status == "scheduled":
        base["scheduled_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    payload = {key: value for key, value in base.items() if key in room_cols}

    cols = list(payload.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    sql = f"INSERT INTO chain_live_rooms ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id"
    row = fetch_one(sql, tuple(payload[col] for col in cols))
    return room_id if not row else str(row["id"])


def _finalize_room_start(room_id, status, provider_mode=None, provider_room_name=None):
    room_cols = _columns("chain_live_rooms")
    updates = []
    params = []
    if "status" in room_cols:
        updates.append("status = %s")
        params.append(status)
    if "is_live" in room_cols:
        updates.append("is_live = %s")
        params.append(status == "live")
    if provider_room_name and "webrtc_room_id" in room_cols:
        updates.append("webrtc_room_id = %s")
        params.append(provider_room_name)
    if "updated_at" in room_cols:
        updates.append("updated_at = NOW()")
    if updates:
        execute(f"UPDATE chain_live_rooms SET {', '.join(updates)} WHERE id = %s", tuple(params + [room_id]))


def _mark_room_failed(room_id):
    room_cols = _columns("chain_live_rooms")
    updates = []
    if "status" in room_cols:
        updates.append("status = 'failed'")
    if "is_live" in room_cols:
        updates.append("is_live = FALSE")
    if updates:
        try:
            execute(f"UPDATE chain_live_rooms SET {', '.join(updates)} WHERE id = %s", (room_id,))
        except Exception:
            pass


def _delete_room_if_safe(room_id):
    room_cols = _columns("chain_live_rooms")
    try:
        if "deleted_at" in room_cols:
            execute("UPDATE chain_live_rooms SET deleted_at = NOW() WHERE id = %s", (room_id,))
        else:
            execute("DELETE FROM chain_live_rooms WHERE id = %s", (room_id,))
    except Exception:
        pass


def _build_livekit_room_name(room_id):
    return sanitize_room_name(f"live-{room_id}")


def _gift_catalog_table():
    if table_exists("chain_live_gift_catalog"):
        return "chain_live_gift_catalog"
    if table_exists("chain_live_gifts"):
        return "chain_live_gifts"
    return ""


@live_bp.route("/wallet/balance", methods=["GET"])
def wallet_balance():
    pid = _profile_id()
    if not pid:
        return jsonify({"ok": False}), 401
    if not table_exists("chain_nvc_wallet"):
        return jsonify({"ok": True, "balance": 0, "lifetime_earned": 0, "lifetime_spent": 0})
    try:
        execute(
            "INSERT INTO chain_nvc_wallet (profile_id, balance) VALUES (%s, 0) ON CONFLICT (profile_id) DO NOTHING",
            (pid,),
        )
        row = fetch_one(
            "SELECT balance, lifetime_earned, lifetime_spent FROM chain_nvc_wallet WHERE profile_id = %s",
            (pid,),
        )
    except Exception:
        row = None
    return jsonify({
        "ok": True,
        "balance": float((row or {}).get("balance") or 0),
        "lifetime_earned": float((row or {}).get("lifetime_earned") or 0),
        "lifetime_spent": float((row or {}).get("lifetime_spent") or 0),
    })


@live_bp.route("/wallet/transactions", methods=["GET"])
def wallet_transactions():
    pid = _profile_id()
    if not pid:
        return jsonify({"ok": False}), 401
    if not table_exists("chain_nvc_transactions"):
        return jsonify({"transactions": []})
    limit = min(int(request.args.get("limit", 20)), 50)
    try:
        rows = fetch_all(
            "SELECT * FROM chain_nvc_transactions WHERE profile_id = %s ORDER BY created_at DESC LIMIT %s",
            (pid, limit),
        )
    except Exception:
        rows = []
    transactions = []
    for row in rows:
        transactions.append({
            "id": row.get("id"),
            "type": row.get("type", ""),
            "amount": float(row.get("amount", 0) or 0),
            "balance_after": float(row.get("balance_after", 0) or 0),
            "reference_type": row.get("reference_type", ""),
            "description": row.get("description", ""),
            "created_at": row.get("created_at").isoformat() if row.get("created_at") else "",
        })
    return jsonify({"transactions": transactions})


@live_bp.route("/wallet/purchase", methods=["POST"])
def purchase_coins():
    pid = _profile_id()
    if not pid:
        return jsonify({"ok": False}), 401
    if not table_exists("chain_nvc_packages") or not table_exists("chain_nvc_wallet"):
        return jsonify({"ok": False, "error": "wallet_unavailable"}), 503
    data = request.get_json(silent=True) or {}
    package_id = data.get("package_id")
    if not package_id:
        return jsonify({"ok": False, "error": "Missing package_id"}), 400
    try:
        pkg = fetch_one("SELECT * FROM chain_nvc_packages WHERE id = %s", (package_id,))
        if not pkg:
            return jsonify({"ok": False, "error": "Package not found"}), 404
        total_coins = float(pkg.get("coins", 0) or 0) + float(pkg.get("bonus_coins", 0) or 0)
        execute("INSERT INTO chain_nvc_wallet (profile_id, balance) VALUES (%s, 0) ON CONFLICT (profile_id) DO NOTHING", (pid,))
        wallet = fetch_one("SELECT balance FROM chain_nvc_wallet WHERE profile_id = %s", (pid,)) or {}
        new_balance = float(wallet.get("balance", 0) or 0) + total_coins
        execute(
            "UPDATE chain_nvc_wallet SET balance = %s, lifetime_earned = COALESCE(lifetime_earned, 0) + %s, updated_at = NOW() WHERE profile_id = %s",
            (new_balance, total_coins, pid),
        )
        execute(
            "INSERT INTO chain_nvc_transactions (profile_id, type, amount, balance_after, reference_type, reference_id, description) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (pid, "purchase", total_coins, new_balance, "package", str(package_id), f"Purchased {pkg.get('name', 'package')}"),
        )
        return jsonify({"ok": True, "coins_added": total_coins, "package_name": pkg.get("name", ""), "new_balance": new_balance})
    except Exception:
        return jsonify({"ok": False, "error": "purchase_failed"}), 503


@live_bp.route("/wallet/packages", methods=["GET"])
def get_packages():
    if not table_exists("chain_nvc_packages"):
        return jsonify({"packages": []})
    try:
        rows = fetch_all("SELECT * FROM chain_nvc_packages ORDER BY sort_order ASC", ())
    except Exception:
        rows = []
    packages = []
    for row in rows:
        coins = float(row.get("coins", 0) or 0)
        bonus = float(row.get("bonus_coins", 0) or 0)
        packages.append({
            "id": row.get("id"),
            "name": row.get("name", ""),
            "coins": coins,
            "bonus_coins": bonus,
            "total_coins": coins + bonus,
            "price": float(row.get("price", 0) or 0),
            "currency": row.get("currency", "NAD"),
            "is_popular": bool(row.get("is_popular")),
            "badge": row.get("badge", ""),
        })
    return jsonify({"packages": packages})


@live_bp.route("/rooms", methods=["GET"])
def get_rooms():
    category = (request.args.get("category") or "all").strip().lower()
    limit = min(int(request.args.get("limit", 12)), 50)
    pid = _profile_id()
    cols, owner_col = _room_select_columns()
    if not cols or not owner_col:
        return jsonify({"rooms": [], "count": 0})

    params = []
    where = [_status_column_filter()]
    joins = [f"JOIN chain_profiles p ON p.id = r.{owner_col}"]

    if category == "friends" and pid and table_exists("chain_follows"):
        joins.append("JOIN chain_follows f ON f.following_profile_id = r.%s" % owner_col)
        where.append("f.follower_profile_id = %s")
        params.append(pid)
    elif category == "scheduled":
        where = [_scheduled_filter()]
    elif category not in {"all", "featured", "trending", "new", "friends"}:
        where.append("LOWER(COALESCE(r.category, '')) = %s")
        params.append(category)

    order = "COALESCE(r.viewer_count, 0) DESC, COALESCE(r.created_at, NOW()) DESC"
    if category == "new":
        order = "COALESCE(r.created_at, NOW()) DESC"
    elif category == "scheduled":
        order = "COALESCE(r.scheduled_at, r.created_at, NOW()) ASC"

    sql = f"""
        SELECT {", ".join(cols)}
        FROM chain_live_rooms r
        {' '.join(joins)}
        WHERE {" AND ".join(where)}
        ORDER BY {order}
        LIMIT %s
    """
    params.append(limit)
    try:
        rows = fetch_all(sql, tuple(params))
    except Exception:
        rows = []

    rooms = []
    for row in rows:
        room = _normalize_room(row)
        if not room:
            continue
        room["viewer_count"] = _calculate_viewer_count(room)
        rooms.append({
            "id": room["id"],
            "title": room.get("title", ""),
            "category": room.get("category", ""),
            "status": room.get("status", "live"),
            "viewer_count": room.get("viewer_count", 0),
            "host_name": room.get("host_name", "Host"),
            "host_username": room.get("host_username", ""),
            "host_avatar": room.get("host_avatar", ""),
            "is_verified": bool(room.get("is_verified")),
            "thumbnail_url": room.get("cover_url") or room.get("thumbnail_url") or "",
            "watch_url": f"/live/{room['id']}",
            "is_featured": False,
        })
    return jsonify({"rooms": rooms, "count": len(rooms)})


@live_bp.route("/gifts", methods=["GET"])
def get_gift_catalog():
    table = _gift_catalog_table()
    if not table:
        return jsonify({"gifts": [], "count": 0})
    tier = (request.args.get("tier") or "").strip().lower()
    try:
        if tier and "tier" in _columns(table):
            rows = fetch_all(f"SELECT * FROM {table} WHERE tier = %s ORDER BY sort_order ASC, price_nvc ASC", (tier,))
        else:
            rows = fetch_all(f"SELECT * FROM {table} ORDER BY sort_order ASC, price_nvc ASC", ())
    except Exception:
        rows = []
    gifts = []
    for gift in rows:
        gifts.append({
            "id": gift.get("id"),
            "name": gift.get("name", ""),
            "emoji": gift.get("emoji") or gift.get("gift_icon") or "🎁",
            "price_nvc": float(gift.get("price_nvc", gift.get("amount", 0)) or 0),
            "tier": gift.get("tier", "bronze"),
            "animation_class": gift.get("animation_class", ""),
            "is_premium": bool(gift.get("is_premium")),
            "is_featured": bool(gift.get("is_featured")),
        })
    return jsonify({"gifts": gifts, "count": len(gifts)})


@live_bp.route("/<room_id>/gift", methods=["POST"])
def send_live_gift(room_id):
    pid = _profile_id()
    if not pid:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    room = _fetch_room(room_id)
    allowed, error = _room_access_allowed(room, pid)
    if not allowed:
        status = 403 if error == "blocked" else 404 if error == "room_not_found" else 400
        return jsonify({"ok": False, "error": error}), status

    owner_id = room.get("owner_profile_id")
    if not owner_id:
        return jsonify({"ok": False, "error": "invalid_room"}), 400

    data = request.get_json(silent=True) or {}
    gift_name = str(data.get("gift_name") or "Gift").strip()[:80]
    gift_emoji = str(data.get("gift_emoji") or "🎁").strip()[:16] or "🎁"
    try:
        amount = int(float(data.get("amount", 0) or 0))
    except Exception:
        amount = 0
    if amount <= 0:
        return jsonify({"ok": False, "error": "invalid_amount"}), 400

    ok, result = send_gift(pid, str(owner_id), gift_name, amount, entity_type="live_room", entity_id=room_id)
    if not ok:
        error_text = str(result or "gift_failed")
        if "Insufficient balance" in error_text:
            return jsonify({"ok": False, "error": "Insufficient NVC coins"}), 400
        return jsonify({"ok": False, "error": "gift_failed"}), 503

    if table_exists("chain_live_gifts"):
        cols = _columns("chain_live_gifts")
        payload = {}
        if "room_id" in cols:
            payload["room_id"] = room_id
        if "sender_profile_id" in cols:
            payload["sender_profile_id"] = pid
        if "host_profile_id" in cols:
            payload["host_profile_id"] = owner_id
        if "gift_name" in cols:
            payload["gift_name"] = gift_name
        if "emoji" in cols:
            payload["emoji"] = gift_emoji
        if "coins" in cols:
            payload["coins"] = amount
        if "amount" in cols:
            payload["amount"] = amount
        if payload:
            try:
                fields = list(payload.keys())
                execute(
                    f"INSERT INTO chain_live_gifts ({', '.join(fields)}) VALUES ({', '.join(['%s'] * len(fields))})",
                    tuple(payload[field] for field in fields),
                )
            except Exception:
                pass

    try:
        from services.socketio_service import emit_to_live_room

        emit_to_live_room(room_id, "live:gift", {
            "room_id": room_id,
            "sender_id": pid,
            "gift_name": gift_name,
            "gift_emoji": gift_emoji,
            "amount": amount,
        })
    except Exception:
        pass

    new_balance = result.get("sender_balance") if isinstance(result, dict) else None
    return jsonify({
        "ok": True,
        "gift_name": gift_name,
        "gift_emoji": gift_emoji,
        "amount": amount,
        "new_balance": new_balance,
    })


@live_bp.route("/start", methods=["POST"])
def start_live():
    pid = _profile_id()
    if not pid:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    data = request.get_json(silent=True) or {}
    existing = _active_room_for_host(pid)
    if existing and existing.get("status") in {"live", "starting", "scheduled"}:
        return jsonify({
            "ok": True,
            "room_id": existing.get("id"),
            "join_url": f"/live/{existing.get('id')}",
            "status": existing.get("status"),
            "reused": True,
            "provider": "livekit" if livekit_configured() else "webrtc_fallback",
        })

    room_id = None
    try:
        room_id = _create_room_row(pid, data)
        requested_status = _validated_status(data)
        provider = "livekit" if livekit_configured() else "webrtc_fallback"
        provider_room_name = _build_livekit_room_name(room_id)
        host_token = None
        if requested_status != "scheduled" and provider == "livekit":
            host_token = create_ingress_token(f"profile:{pid}", provider_room_name)
            if not host_token:
                raise RuntimeError("livekit_setup_failed")
        final_status = "scheduled" if requested_status == "scheduled" else "live"
        _finalize_room_start(room_id, final_status, provider_mode=provider, provider_room_name=provider_room_name)
        track_interaction_safe(pid, "live", room_id, "open", source_surface="live")
        payload = {
            "ok": True,
            "room_id": room_id,
            "join_url": f"/live/{room_id}",
            "status": final_status,
            "provider": provider,
        }
        if provider == "livekit" and host_token:
            payload["livekit"] = {
                "enabled": True,
                "room_name": provider_room_name,
                "ws_url": get_livekit_server_info().get("ws_url", ""),
                "token": host_token,
            }
        else:
            payload["livekit"] = {"enabled": False}
        return jsonify(payload)
    except Exception:
        if room_id:
            _mark_room_failed(room_id)
            _delete_room_if_safe(room_id)
        return jsonify({"ok": False, "error": "Failed to create room"}), 503


@live_bp.route("/scheduled", methods=["GET"])
def get_scheduled():
    limit = min(int(request.args.get("limit", 12)), 50)
    cols, owner_col = _room_select_columns()
    if not cols or not owner_col:
        return jsonify({"rooms": [], "count": 0})
    sql = f"""
        SELECT {", ".join(cols)}
        FROM chain_live_rooms r
        JOIN chain_profiles p ON p.id = r.{owner_col}
        WHERE {_scheduled_filter()}
        ORDER BY COALESCE(r.scheduled_at, r.created_at, NOW()) ASC
        LIMIT %s
    """
    try:
        rows = fetch_all(sql, (limit,))
    except Exception:
        rows = []
    rooms = []
    for row in rows:
        room = _normalize_room(row)
        if not room:
            continue
        rooms.append({
            "id": room["id"],
            "title": room.get("title", ""),
            "category": room.get("category", ""),
            "status": "scheduled",
            "host_name": room.get("host_name", "Host"),
            "host_avatar": room.get("host_avatar", ""),
            "is_verified": bool(room.get("is_verified")),
            "thumbnail_url": room.get("cover_url") or room.get("thumbnail_url") or "",
        })
    return jsonify({"rooms": rooms, "count": len(rooms)})


@live_bp.route("/<room_id>/end", methods=["POST"])
def end_live(room_id):
    pid = _profile_id()
    if not pid:
        return jsonify({"ok": False}), 401
    room = _fetch_room(room_id)
    owner_id = (
        (room or {}).get("owner_profile_id")
        or (room or {}).get("profile_id")
        or (room or {}).get("host_profile_id")
        or (room or {}).get("host_id")
    )
    if not room or str(owner_id) != str(pid):
        return jsonify({"ok": False, "error": "Not authorized"}), 403

    room_cols = _columns("chain_live_rooms")
    updates = []
    if "is_live" in room_cols:
        updates.append("is_live = FALSE")
    if "status" in room_cols:
        updates.append("status = 'ended'")
    if "ended_at" in room_cols:
        updates.append("ended_at = NOW()")
    if "viewer_count" in room_cols:
        updates.append("viewer_count = 0")
    if updates:
        try:
            execute(f"UPDATE chain_live_rooms SET {', '.join(updates)} WHERE id = %s", (room_id,))
        except Exception:
            return jsonify({"ok": False, "error": "end_failed"}), 503

    if table_exists("chain_live_participants"):
        participant_cols = _columns("chain_live_participants")
        changes = []
        if "is_active" in participant_cols:
            changes.append("is_active = FALSE")
        if "left_at" in participant_cols:
            changes.append("left_at = NOW()")
        if "last_seen_at" in participant_cols:
            changes.append("last_seen_at = NOW()")
        if changes:
            try:
                execute(f"UPDATE chain_live_participants SET {', '.join(changes)} WHERE room_id = %s", (room_id,))
            except Exception:
                pass

    try:
        from services.socketio_service import emit_to_live_room

        emit_to_live_room(room_id, "live:room_ended", {"room_id": room_id, "ended": True})
    except Exception:
        pass
    return jsonify({"ok": True})


@live_bp.route("/<room_id>/chat", methods=["GET", "POST"])
def chat(room_id):
    room = _fetch_room(room_id)
    pid = _profile_id()
    allowed, reason = _room_access_allowed(room, pid)
    if request.method == "POST":
        if not pid:
            return jsonify({"ok": False, "error": "auth_required"}), 401
        if not allowed:
            return jsonify({"ok": False, "error": reason or "join_not_allowed"}), 403
        data = request.get_json(silent=True) or {}
        body = _sanitize_chat_text(data.get("body"))
        if not body:
            return jsonify({"ok": False, "error": "Empty message"}), 400
        display_name = None
        try:
            profile = fetch_one("SELECT display_name, username FROM chain_profiles WHERE id = %s", (pid,))
            display_name = (profile or {}).get("display_name") or (profile or {}).get("username") or "User"
        except Exception:
            display_name = "User"

        message = {
            "sender_name": display_name,
            "body": body,
            "message_type": "text",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if table_exists("chain_live_chat_messages"):
            cols = _columns("chain_live_chat_messages")
            payload = {}
            if "room_id" in cols:
                payload["room_id"] = room_id
            if "profile_id" in cols:
                payload["profile_id"] = pid
            if "display_name" in cols:
                payload["display_name"] = display_name
            if "body" in cols:
                payload["body"] = body
            if payload:
                try:
                    fields = list(payload.keys())
                    row = fetch_one(
                        f"INSERT INTO chain_live_chat_messages ({', '.join(fields)}) VALUES ({', '.join(['%s'] * len(fields))}) RETURNING id, created_at",
                        tuple(payload[field] for field in fields),
                    )
                    if row:
                        message["id"] = row.get("id")
                        if row.get("created_at"):
                            message["created_at"] = row["created_at"].isoformat()
                except Exception:
                    pass
        try:
            from services.socketio_service import emit_to_live_room

            emit_to_live_room(room_id, "live:chat", message)
        except Exception:
            pass
        return jsonify({"ok": True, "message": message})

    if not allowed and reason == "stream_ended":
        return jsonify({"messages": [], "count": 0})
    if not table_exists("chain_live_chat_messages"):
        return jsonify({"messages": [], "count": 0})
    after = request.args.get("after")
    limit = min(int(request.args.get("limit", 50)), 100)
    cols = _columns("chain_live_chat_messages")
    where = ["room_id = %s"]
    params = [room_id]
    if after and "id" in cols:
        where.append("id::text > %s")
        params.append(str(after))
    try:
        rows = fetch_all(
            f"SELECT id, profile_id, display_name, body, created_at, COALESCE(is_pinned, FALSE) AS is_pinned FROM chain_live_chat_messages WHERE {' AND '.join(where)} ORDER BY created_at ASC LIMIT %s",
            tuple(params + [limit]),
        )
    except Exception:
        rows = []
    messages = []
    for row in rows:
        messages.append({
            "id": row.get("id"),
            "sender_name": row.get("display_name", "User"),
            "body": row.get("body", ""),
            "is_pinned": bool(row.get("is_pinned")),
            "created_at": row.get("created_at").isoformat() if row.get("created_at") else "",
            "message_type": "text",
        })
    return jsonify({"messages": messages, "count": len(messages)})


@live_bp.route("/<room_id>/participants", methods=["GET"])
def get_participants(room_id):
    room = _fetch_room(room_id)
    limit = min(int(request.args.get("limit", 50)), 100)
    if not room or not table_exists("chain_live_participants"):
        return jsonify({"participants": [], "count": 0})
    participant_cols = _columns("chain_live_participants")
    where = ["lp.room_id = %s"]
    params = [room_id]
    if "is_active" in participant_cols:
        where.append("COALESCE(lp.is_active, TRUE) = TRUE")
    if "left_at" in participant_cols:
        where.append("lp.left_at IS NULL")
    try:
        rows = fetch_all(
            f"""
            SELECT lp.profile_id, lp.role, lp.joined_at,
                   COALESCE(p.display_name, p.username, 'User') AS display_name,
                   p.username, p.avatar_url
            FROM chain_live_participants lp
            JOIN chain_profiles p ON p.id = lp.profile_id
            WHERE {' AND '.join(where)}
            ORDER BY lp.joined_at ASC
            LIMIT %s
            """,
            tuple(params + [limit]),
        )
    except Exception:
        rows = []
    participants = []
    seen = set()
    for row in rows:
        key = str(row.get("profile_id"))
        if key in seen:
            continue
        seen.add(key)
        participants.append({
            "id": row.get("profile_id"),
            "display_name": row.get("display_name", "User"),
            "username": row.get("username", ""),
            "avatar_url": row.get("avatar_url", ""),
            "role": row.get("role", "viewer"),
        })
    return jsonify({"participants": participants, "count": len(participants)})


@live_bp.route("/<room_id>/polls", methods=["GET"])
def get_polls(room_id):
    if not table_exists("chain_live_polls"):
        return jsonify({"polls": []})
    try:
        rows = fetch_all(
            "SELECT * FROM chain_live_polls WHERE room_id = %s AND status = 'active' ORDER BY created_at DESC LIMIT 5",
            (room_id,),
        )
    except Exception:
        rows = []
    polls = []
    for row in rows:
        options = row.get("options") or []
        votes = row.get("votes") or {}
        polls.append({
            "id": row.get("id"),
            "question": row.get("question", ""),
            "options": options if isinstance(options, list) else [],
            "votes": votes if isinstance(votes, (dict, list)) else {},
            "status": row.get("status", "active"),
        })
    return jsonify({"polls": polls})


@live_bp.route("/<room_id>/vote", methods=["POST"])
def vote(room_id):
    pid = _profile_id()
    if not pid:
        return jsonify({"ok": False}), 401
    if not table_exists("chain_live_polls"):
        return jsonify({"ok": False, "error": "polls_unavailable"}), 503
    data = request.get_json(silent=True) or {}
    poll_id = data.get("poll_id")
    option = data.get("option")
    if poll_id is None or option is None:
        return jsonify({"ok": False, "error": "Missing poll_id or option"}), 400
    try:
        poll = fetch_one("SELECT votes FROM chain_live_polls WHERE id = %s AND room_id = %s", (poll_id, room_id))
        if not poll:
            return jsonify({"ok": False, "error": "Poll not found"}), 404
        import json as _json

        votes = poll.get("votes") or {}
        if isinstance(votes, str):
            votes = _json.loads(votes)
        key = str(option)
        votes[key] = (votes.get(key, 0) if isinstance(votes, dict) else 0) + 1
        execute("UPDATE chain_live_polls SET votes = %s WHERE id = %s", (_json.dumps(votes), poll_id))
        return jsonify({"ok": True})
    except Exception:
        return jsonify({"ok": False, "error": "vote_failed"}), 503


@live_bp.route("/<room_id>/products", methods=["GET"])
def get_products(room_id):
    if not table_exists("chain_live_products"):
        return jsonify({"products": []})
    try:
        rows = fetch_all("SELECT * FROM chain_live_products WHERE room_id = %s ORDER BY sort_order ASC LIMIT 20", (room_id,))
    except Exception:
        rows = []
    products = []
    for row in rows:
        products.append({
            "id": row.get("id"),
            "title": row.get("title", ""),
            "price": float(row.get("price", 0) or 0),
            "currency": row.get("currency", "NAD"),
            "image_url": row.get("image_url", ""),
            "discount_pct": row.get("discount_pct", 0),
        })
    return jsonify({"products": products})


@live_bp.route("/<room_id>/stats", methods=["GET"])
def get_stats(room_id):
    room = _fetch_room(room_id)
    if not room:
        return jsonify({"viewer_count": 0, "peak_viewers": 0, "like_count": 0, "gift_value": 0, "participant_count": 0})
    viewer_count = _sync_viewer_count(room)
    participant_count = viewer_count
    if table_exists("chain_live_participants"):
        participant_cols = _columns("chain_live_participants")
        clauses = ["room_id = %s"]
        params = [room_id]
        if "is_active" in participant_cols:
            clauses.append("COALESCE(is_active, TRUE) = TRUE")
        if "left_at" in participant_cols:
            clauses.append("left_at IS NULL")
        try:
            row = fetch_one(f"SELECT COUNT(*) AS cnt FROM chain_live_participants WHERE {' AND '.join(clauses)}", tuple(params))
            participant_count = int((row or {}).get("cnt") or 0)
        except Exception:
            participant_count = viewer_count
    return jsonify({
        "viewer_count": viewer_count,
        "peak_viewers": int(room.get("peak_viewer_count") or viewer_count),
        "like_count": int(room.get("likes_count") or 0),
        "gift_value": float(room.get("reaction_count") or 0),
        "participant_count": participant_count,
    })


@live_bp.route("/webrtc-config", methods=["GET"])
def webrtc_config():
    return jsonify(get_turn_config())


@live_bp.route("/livekit-token", methods=["POST"])
def request_livekit_token():
    pid = _profile_id()
    if not pid:
        return jsonify({"ok": False}), 401
    if not livekit_configured():
        return jsonify({"ok": False, "error": "LiveKit not configured"}), 503
    data = request.get_json(silent=True) or {}
    room_id = str(data.get("room_id") or "").strip()
    role = str(data.get("role") or "viewer").strip().lower()
    room = _fetch_room(room_id) if room_id else None
    if not room:
        return jsonify({"ok": False, "error": "room_not_found"}), 404
    allowed, reason = _room_access_allowed(room, pid)
    if not allowed:
        return jsonify({"ok": False, "error": reason or "join_not_allowed"}), 403
    room_name = _build_livekit_room_name(room["id"])
    identity = f"profile:{pid}"
    token = None
    if role == "host" and str(room.get("owner_profile_id")) == str(pid):
        token = create_ingress_token(identity, room_name)
    elif role == "guest":
        token = create_guest_token(identity, room_name)
    else:
        token = create_viewer_token(identity, room_name)
    if not token:
        return jsonify({"ok": False, "error": "livekit_unavailable"}), 503
    return jsonify({"ok": True, "token": token, "ws_url": get_livekit_server_info().get("ws_url", ""), "room_name": room_name})


@live_bp.route("/livekit-status", methods=["GET"])
def livekit_status():
    info = get_livekit_server_info()
    health = check_livekit_health()
    return jsonify({**info, **health})


@live_bp.route("/turn-status", methods=["GET"])
def turn_status():
    return jsonify(get_turn_status())


@live_bp.route("/infra-health", methods=["GET"])
def infra_health():
    from services.neon_service import get_neon_health
    from services.redis_service import get_redis_health

    neon = get_neon_health()
    redis_health = get_redis_health()
    livekit = check_livekit_health()
    turn = get_turn_status()
    all_ok = neon.get("status") in ("ok", "disabled", "skipped") and livekit.get("status") in ("ok", "not_configured")
    return jsonify({
        "ok": all_ok,
        "neon": {"status": neon.get("status"), "connected": neon.get("connected", False)},
        "redis": {"available": redis_health.get("available", False), "status": redis_health.get("status")},
        "livekit": {"status": livekit.get("status"), "configured": get_livekit_server_info().get("configured", False)},
        "turn": {"configured": turn.get("configured", False)},
    })


def register_live_routes(app):
    app.register_blueprint(live_bp)
    print("[live] Live API routes registered (NVC + WebRTC + LiveKit + coturn)")
