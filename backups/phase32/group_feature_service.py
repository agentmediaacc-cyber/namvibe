import os
import uuid
from datetime import datetime, timezone
import json

from services.neon_service import fast_query, get_pool_status, write_query
from services.socketio_service import emit_to_thread

_GROUPS = {}
_REQUESTS = {}
_POSTS = {}
_ROLES = {}
_ANNOUNCEMENTS = {}
_ADVERTS = {}
_ANALYTICS = {}
_VERIFICATIONS = {}
_GROUP_LIVE = {}
_GROUP_REELS = {}
_MARKET = {}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _uuid(value=None):
    if value:
        try:
            return str(uuid.UUID(str(value)))
        except (TypeError, ValueError):
            pass
    return str(uuid.uuid4())


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _write(sql, params=(), timeout_ms=900):
    if not _db_available():
        raise RuntimeError("db_unavailable")
    return write_query(sql, params, timeout_ms=timeout_ms)


def create_group(owner_profile_id, name, visibility="public", **settings):
    owner_profile_id = _uuid(owner_profile_id)
    group_id = str(uuid.uuid4())
    invite_code = uuid.uuid4().hex[:16]
    visibility = visibility if visibility in {"public", "private"} else "public"
    payload = {
        "id": group_id,
        "owner_profile_id": owner_profile_id,
        "name": (name or "CHAIN Group").strip(),
        "visibility": visibility,
        "access_type": settings.get("access_type") or visibility,
        "join_fee": float(settings.get("join_fee") or 0),
        "premium_only": bool(settings.get("premium_only")),
        "paid_access": bool(settings.get("paid_access") or float(settings.get("join_fee") or 0) > 0),
        "invite_code": invite_code,
        "allow_typing": bool(settings.get("allow_typing", True)),
        "allow_replies": bool(settings.get("allow_replies", True)),
        "allow_comments": bool(settings.get("allow_comments", True)),
        "allow_adverts": bool(settings.get("allow_adverts", False)),
        "allow_group_calls": bool(settings.get("allow_group_calls", True)),
        "allow_member_invites": bool(settings.get("allow_member_invites", True)),
        "created_at": _now(),
    }
    try:
        _write(
            """
            INSERT INTO chain_groups
            (id, owner_profile_id, name, visibility, access_type, join_fee, premium_only, invite_code,
             allow_typing, allow_replies, allow_comments, allow_adverts, allow_group_calls, allow_member_invites)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            tuple(payload[key] for key in ["id", "owner_profile_id", "name", "visibility", "access_type", "join_fee", "premium_only", "invite_code", "allow_typing", "allow_replies", "allow_comments", "allow_adverts", "allow_group_calls", "allow_member_invites"]),
        )
        _write("INSERT INTO chain_group_members (group_id, profile_id, role, status) VALUES (%s, %s, 'admin', 'active') ON CONFLICT DO NOTHING", (group_id, owner_profile_id))
    except Exception:
        _GROUPS[group_id] = payload
    return {"ok": True, "group": payload, "invite_link": f"/messages/groups/join/{invite_code}"}


def join_public_group(group_id, profile_id):
    group_id = _uuid(group_id)
    profile_id = _uuid(profile_id)
    group = get_group(group_id)
    if group and group.get("visibility") == "private":
        return request_join(group_id, profile_id)
    try:
        _write("INSERT INTO chain_group_members (group_id, profile_id, role, status) VALUES (%s, %s, 'member', 'active') ON CONFLICT DO NOTHING", (group_id, profile_id))
    except Exception:
        _GROUPS.setdefault(group_id, {"id": group_id, "members": []}).setdefault("members", []).append(profile_id)
    return {"ok": True, "status": "joined", "group_id": group_id}


def request_join(group_id, profile_id):
    group_id = _uuid(group_id)
    profile_id = _uuid(profile_id)
    try:
        _write("INSERT INTO chain_group_join_requests (group_id, profile_id, status) VALUES (%s, %s, 'pending') ON CONFLICT DO UPDATE SET status = 'pending', updated_at = now()", (group_id, profile_id))
    except Exception:
        _REQUESTS[(group_id, profile_id)] = {"status": "pending", "created_at": _now()}
    return {"ok": True, "status": "pending", "group_id": group_id}


def get_group(group_id):
    group_id = _uuid(group_id)
    rows = fast_query("SELECT * FROM chain_groups WHERE id = %s LIMIT 1", (group_id,), timeout_ms=500, default=[]) if _db_available() else []
    return rows[0] if rows else _GROUPS.get(group_id)


def create_group_post(group_id, profile_id, body, post_type="message"):
    group_id = _uuid(group_id)
    profile_id = _uuid(profile_id)
    post_id = str(uuid.uuid4())
    post = {"id": post_id, "group_id": group_id, "profile_id": profile_id, "body": body or "", "post_type": post_type, "created_at": _now()}
    try:
        _write("INSERT INTO chain_group_posts (id, group_id, profile_id, post_type, body) VALUES (%s, %s, %s, %s, %s)", (post_id, group_id, profile_id, post_type, body))
    except Exception:
        _POSTS.setdefault(group_id, []).append(post)
    emit_to_thread(group_id, "group:post", post)
    return {"ok": True, "post": post}


def set_role(group_id, profile_id, role, assigned_by_profile_id=None):
    group_id = _uuid(group_id)
    profile_id = _uuid(profile_id)
    assigned_by_profile_id = _uuid(assigned_by_profile_id) if assigned_by_profile_id else None
    role = role if role in {"admin", "moderator", "co_host", "member"} else "member"
    payload = {"group_id": group_id, "profile_id": profile_id, "role": role, "assigned_by_profile_id": assigned_by_profile_id}
    try:
        _write(
            "INSERT INTO chain_group_roles (group_id, profile_id, role, assigned_by_profile_id) VALUES (%s, %s, %s, %s)",
            (group_id, profile_id, role, assigned_by_profile_id),
        )
        _write("UPDATE chain_group_members SET role = %s WHERE group_id = %s AND profile_id = %s", (role, group_id, profile_id), timeout_ms=500)
    except Exception:
        _ROLES[(group_id, profile_id)] = payload
    return {"ok": True, "role": payload}


def create_announcement(group_id, profile_id, title, body):
    return _insert_group_record("chain_group_announcements", _ANNOUNCEMENTS, group_id, profile_id, {"title": title, "body": body}, "announcement")


def create_advert(group_id, profile_id, title, body=None, media_url=None):
    return _insert_group_record("chain_group_adverts", _ADVERTS, group_id, profile_id, {"title": title, "body": body, "media_url": media_url}, "advert")


def record_analytics(group_id, metric_name, metric_value=0, **metadata):
    group_id = _uuid(group_id)
    record = {"id": str(uuid.uuid4()), "group_id": group_id, "metric_name": metric_name, "metric_value": float(metric_value or 0), "metadata": metadata}
    try:
        _write(
            "INSERT INTO chain_group_analytics (id, group_id, metric_name, metric_value, metadata) VALUES (%s, %s, %s, %s, %s::jsonb)",
            (record["id"], group_id, metric_name, record["metric_value"], json.dumps(metadata)),
        )
    except Exception:
        _ANALYTICS.setdefault(group_id, []).append(record)
    return {"ok": True, "analytics": record}


def request_group_verification(group_id, profile_id, note=None):
    group_id = _uuid(group_id)
    profile_id = _uuid(profile_id)
    record = {"id": str(uuid.uuid4()), "group_id": group_id, "profile_id": profile_id, "status": "pending", "note": note}
    try:
        _write("INSERT INTO chain_group_verification (id, group_id, profile_id, status, note) VALUES (%s, %s, %s, 'pending', %s)", (record["id"], group_id, profile_id, note))
    except Exception:
        _VERIFICATIONS[record["id"]] = record
    return {"ok": True, "verification": record}


def create_group_live_room(group_id, profile_id, title=None, room_id=None):
    group_id = _uuid(group_id)
    profile_id = _uuid(profile_id)
    room_id = _uuid(room_id) if room_id else None
    record = {"id": str(uuid.uuid4()), "group_id": group_id, "room_id": room_id, "profile_id": profile_id, "title": title or "Group live", "status": "scheduled"}
    try:
        _write("INSERT INTO chain_group_live_rooms (id, group_id, room_id, profile_id, title, status) VALUES (%s, %s, %s, %s, %s, %s)", (record["id"], group_id, room_id, profile_id, record["title"], record["status"]))
    except Exception:
        _GROUP_LIVE[record["id"]] = record
    return {"ok": True, "group_live": record}


def create_group_reel(group_id, profile_id, caption=None, reel_id=None):
    group_id = _uuid(group_id)
    profile_id = _uuid(profile_id)
    reel_id = _uuid(reel_id) if reel_id else None
    record = {"id": str(uuid.uuid4()), "group_id": group_id, "profile_id": profile_id, "reel_id": reel_id, "caption": caption}
    try:
        _write("INSERT INTO chain_group_reels (id, group_id, profile_id, reel_id, caption) VALUES (%s, %s, %s, %s, %s)", (record["id"], group_id, profile_id, reel_id, caption))
    except Exception:
        _GROUP_REELS[record["id"]] = record
    return {"ok": True, "group_reel": record}


def create_marketplace_item(group_id, profile_id, title, description=None, price_coins=0):
    group_id = _uuid(group_id)
    profile_id = _uuid(profile_id)
    record = {"id": str(uuid.uuid4()), "group_id": group_id, "profile_id": profile_id, "title": title, "description": description, "price_coins": float(price_coins or 0), "status": "active"}
    try:
        _write("INSERT INTO chain_group_marketplace_items (id, group_id, profile_id, title, description, price_coins) VALUES (%s, %s, %s, %s, %s, %s)", (record["id"], group_id, profile_id, title, description, record["price_coins"]))
    except Exception:
        _MARKET[record["id"]] = record
    return {"ok": True, "item": record}


def invite_link(group_id):
    group_id = _uuid(group_id)
    group = get_group(group_id) or {}
    code = group.get("invite_code") or uuid.uuid4().hex[:16]
    return {"ok": True, "invite_code": code, "invite_link": f"/messages/groups/join/{code}"}


def _insert_group_record(table, store, group_id, profile_id, data, key):
    group_id = _uuid(group_id)
    profile_id = _uuid(profile_id)
    record = {"id": str(uuid.uuid4()), "group_id": group_id, "profile_id": profile_id, **data}
    try:
        columns = ["id", "group_id", "profile_id", *data.keys()]
        placeholders = ", ".join(["%s"] * len(columns))
        _write(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(record[column] for column in columns),
        )
    except Exception:
        store.setdefault(group_id, []).append(record)
    emit_to_thread(group_id, f"group:{key}", record)
    return {"ok": True, key: record}
