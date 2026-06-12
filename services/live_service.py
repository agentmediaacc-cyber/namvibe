import os
import re
from datetime import datetime, timezone

from flask import session
from werkzeug.utils import secure_filename
from engines.cache_engine import cache_key, get_cache, set_cache
from engines.performance_engine import compact_room
from services.neon_service import (
    fetch_all_with_connection,
    get_cached_table_columns,
    get_connection,
    get_pool_status,
    get_table_columns,
    get_neon_health,
    release_connection,
)
from services.profile_service import get_current_profile
from services.storage_service import upload_live_cover, upload_live_music
from services.supabase_safe import safe_count, safe_insert, safe_select, safe_update


def _invalidate_homepage_cache():
    try:
        from services.homepage_cache_service import invalidate_homepage_cache
        invalidate_homepage_cache()
    except Exception:
        pass


def _notify_followers_live_started(room):
    host_id = room.get("profile_id") or room.get("host_profile_id")
    room_id = room.get("id")
    if not host_id or not room_id:
        return
    followers = safe_select("chain_follows", columns="follower_profile_id", filters={"following_profile_id": host_id}, limit=100, order_by=None)
    if not followers:
        return
    try:
        from services.notification_engine import create_notification

        for follower in followers:
            recipient_id = follower.get("follower_profile_id")
            if not recipient_id:
                continue
            create_notification(
                recipient_profile_id=recipient_id,
                actor_profile_id=host_id,
                event_type="live_started",
                title="Live started",
                body=f"{room.get('host_name') or 'A creator'} is live now.",
                entity_type="live_room",
                entity_id=room_id,
                action_url=f"/live/room/{room_id}",
            )
    except Exception:
        try:
            from services.notification_service import create_notification

            for follower in followers:
                recipient_id = follower.get("follower_profile_id")
                if recipient_id:
                    create_notification(
                        profile_id=recipient_id,
                        actor_profile_id=host_id,
                        title="Live started",
                        body=f"{room.get('host_name') or 'A creator'} is live now.",
                        n_type="live_started",
                        link_url=f"/live/room/{room_id}",
                    )
        except Exception:
            return


def youtube_id(url):
    if not url:
        return None
    patterns = [r"youtu\.be/([^?&/]+)", r"youtube\.com/watch\?v=([^?&/]+)", r"youtube\.com/embed/([^?&/]+)"]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def _safe_number(value, default=0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _viewer_name(display_name=None):
    current = get_current_profile()
    if current:
        return current.get("full_name") or current.get("username") or "NamVibe Member"

    candidate = (display_name or "").strip()
    if candidate:
        return candidate

    username = session.get("username")
    if username:
        return username

    email = session.get("email")
    if email and "@" in email:
        return email.split("@")[0]

    return "Anonymous Viewer"


def _normalize_room(room):
    if not room:
        return None

    normalized = dict(room)
    normalized["host_profile_id"] = normalized.get("host_profile_id") or normalized.get("profile_id")
    normalized["status"] = normalized.get("status") or ("live" if normalized.get("is_live", True) else "ended")
    normalized["viewer_count"] = normalized.get("viewer_count") or 0
    normalized["gift_total"] = normalized.get("gift_total")
    if normalized["gift_total"] is None:
        normalized["gift_total"] = normalized.get("total_gift_coins") or 0
    normalized["host_name"] = normalized.get("host_name") or "NamVibe Host"
    return normalized


def _insert_first(table, payloads):
    for payload in payloads:
        if safe_insert(table, payload) is not None:
            return True
    return False


def _update_room_totals(room_id):
    viewers = safe_count(
        "chain_live_viewers",
        filters={"room_id": room_id, "left_at": ("is", "null")},
    )
    if viewers == 0:
        viewers = safe_count("chain_live_viewers", filters={"room_id": room_id})

    if safe_update("chain_live_rooms", {"viewer_count": viewers}, eq={"id": room_id}) is None:
        safe_update("chain_live_rooms", {"viewer_count": viewers, "is_live": True}, eq={"id": room_id})

    gift_rows = safe_select("chain_live_gifts", limit=200, filters={"room_id": room_id})
    total = 0
    for gift in gift_rows:
        total += _safe_number(gift.get("amount"), _safe_number(gift.get("coins"), 0))

    if safe_update("chain_live_rooms", {"gift_total": total}, eq={"id": room_id}) is None:
        safe_update("chain_live_rooms", {"total_gift_coins": int(total)}, eq={"id": room_id})


def _load_profile_map(profile_ids):
    ids = [profile_id for profile_id in profile_ids if profile_id]
    if not ids:
        return {}

    profiles = safe_select(
        "chain_profiles",
        limit=len(ids),
        filters={"id": ("in", ids)},
        order_by=None,
    )
    return {profile["id"]: profile for profile in profiles}


def _normalize_comments(rows):
    profiles = _load_profile_map([row.get("profile_id") for row in rows])
    comments = []
    for row in rows:
        profile = profiles.get(row.get("profile_id"))
        comments.append({
            **row,
            "body": row.get("body") or row.get("comment") or "",
            "display_name": row.get("display_name")
            or (profile.get("full_name") if profile else None)
            or (profile.get("username") if profile else None)
            or "Member",
        })
    return list(reversed(comments))


def _normalize_gifts(rows):
    profiles = _load_profile_map([row.get("sender_profile_id") for row in rows])
    gifts = []
    for row in rows:
        profile = profiles.get(row.get("sender_profile_id"))
        gifts.append({
            **row,
            "amount": _safe_number(row.get("amount"), _safe_number(row.get("coins"), 0)),
            "gift_icon": row.get("gift_icon") or row.get("emoji") or "🎁",
            "gift_name": row.get("gift_name") or "Gift",
            "display_name": row.get("display_name")
            or (profile.get("full_name") if profile else None)
            or (profile.get("username") if profile else None)
            or "Member",
        })
    return gifts


def _normalize_viewers(rows):
    profiles = _load_profile_map([row.get("profile_id") for row in rows])
    viewers = []
    for row in rows:
        profile = profiles.get(row.get("profile_id"))
        viewers.append({
            **row,
            "display_name": row.get("display_name")
            or (profile.get("full_name") if profile else None)
            or (profile.get("username") if profile else None)
            or "Viewer",
        })
    return viewers


def _normalize_cohost_requests(rows):
    profiles = _load_profile_map([row.get("profile_id") for row in rows])
    requests = []
    for row in rows:
        profile = profiles.get(row.get("profile_id"))
        requests.append({
            **row,
            "display_name": row.get("display_name")
            or (profile.get("full_name") if profile else None)
            or (profile.get("username") if profile else None)
            or "Member",
            "status": row.get("status") or "pending",
        })
    return requests


def create_live_room(form, files=None):
    try:
        current = get_current_profile()
        youtube_url = (form.get("youtube_url") or "").strip()
        video_id = youtube_id(youtube_url)
        
        mp3_url = None
        mp3_filename = None
        mp3_upload_id = None
        
        # Use storage service for MP3
        mp3_file = (files or {}).get("mp3_file") if files else None
        if mp3_file and mp3_file.filename:
            res, err = upload_live_music(current["id"], mp3_file)
            if res:
                mp3_url = res["public_url"]
                mp3_filename = mp3_file.filename
                mp3_upload_id = res["upload_id"]
            else:
                print(f"[live_service] MP3 upload failed: {err}")

        # Use storage service for Cover
        cover_url = None
        cover_upload_id = None
        cover_file = (files or {}).get("cover") if files else None
        if cover_file and cover_file.filename:
            res, err = upload_live_cover(current["id"], cover_file)
            if res:
                cover_url = res["url"]
                cover_upload_id = res["upload_id"]
                cover_metadata = res
            else:
                cover_metadata = None
                print(f"[live_service] Cover upload failed: {err}")
        else:
            cover_metadata = None

        access_type = (form.get("access_type") or "public").strip().lower()
        if access_type not in {"public", "private", "premium"}:
            access_type = "public"

        base_payload = {
            "title": (form.get("title") or "My NamVibe Live Room").strip(),
            "host_name": (current or {}).get("full_name") or (current or {}).get("username") or "NamVibe Host",
            "welcome_message": (form.get("welcome_message") or "").strip() or "Welcome to my NamVibe live room.",
            "category": (form.get("category") or "").strip() or None,
            "youtube_url": youtube_url,
            "youtube_video_id": video_id,
            "youtube_embed_url": f"https://www.youtube.com/embed/{video_id}" if video_id else None,
            "mp3_url": mp3_url,
            "mp3_filename": mp3_filename,
            "background_music_upload_id": mp3_upload_id,
            "cover_url": cover_url,
            "live_cover_upload_id": cover_upload_id,
            "cover_bucket": (cover_metadata or {}).get("bucket"),
            "cover_path": (cover_metadata or {}).get("path"),
            "cover_mime_type": (cover_metadata or {}).get("mime_type"),
            "cover_size_bytes": (cover_metadata or {}).get("size_bytes"),
            "access_type": access_type,
            "entry_fee": _safe_number(form.get("entry_fee"), 0),
            "status": "live",
            "is_live": True,
            "created_at": _utcnow_iso(),
        }

        payloads = [
            {
                **base_payload,
                "host_profile_id": (current or {}).get("id"),
            },
            {
                **base_payload,
                "profile_id": (current or {}).get("id"),
            },
            {
                key: value
                for key, value in base_payload.items()
                if key not in {"category", "youtube_video_id", "mp3_filename", "status"}
            },
        ]

        for payload in payloads:
            inserted = safe_insert("chain_live_rooms", payload)
            if inserted is not None:
                room_id = None
                if inserted:
                    room_id = inserted[0].get("id")
                if room_id:
                    room = get_room(room_id)
                    if room:
                        _notify_followers_live_started(room)
                    _invalidate_homepage_cache()
                    return room

                recent_rooms = get_live_rooms(limit=10)
                for room in recent_rooms:
                    if room.get("title") == payload["title"] and room.get("host_name") == payload["host_name"]:
                        _notify_followers_live_started(room)
                        _invalidate_homepage_cache()
                        return room

        return None
    except Exception as error:
        print(f"[live_service] create_live_room failed: {error}")
        return None


def get_live_rooms(limit=30):
    try:
        room_columns = "id,title,host_name,host_profile_id,profile_id,status,is_live,category,access_type,viewer_count,gift_total,total_gift_coins,welcome_message,cover_url,entry_fee,comments_enabled,gifts_enabled,created_at"
        rooms = safe_select("chain_live_rooms", columns=room_columns, limit=limit, filters={"status": "live"})
        if not rooms:
            rooms = safe_select("chain_live_rooms", columns=room_columns, limit=limit, filters={"is_live": True})
        return [_normalize_room(compact_room(room) or room) for room in rooms]
    except Exception as error:
        print(f"[live_service] get_live_rooms failed: {error}")
        return []


def get_live_rooms_public(limit=12, allow_query=True):
    cached = get_cache(cache_key("chain_live_public_v1", limit))
    if cached is not None:
        return cached

    if not allow_query:
        payload = []
        set_cache(cache_key("chain_live_public_v1", limit), payload, ttl=30)
        return payload

    pool_status = get_pool_status()
    if not pool_status.get("recent_success"):
        payload = []
        set_cache(cache_key("chain_live_public_v1", limit), payload, ttl=30)
        return payload

    columns = set(get_cached_table_columns("chain_live_rooms") or get_table_columns("chain_live_rooms", timeout_ms=150))
    required = {"id", "title", "created_at"}
    if not required.issubset(columns):
        payload = []
        set_cache(cache_key("chain_live_public_v1", limit), payload, ttl=30)
        return payload

    select_columns = [column for column in [
        "id", "profile_id", "title", "status", "is_live", "category",
        "viewer_count", "cover_url", "entry_fee", "created_at"
    ] if column in columns]
    where = ["deleted_at IS NULL"] if "deleted_at" in columns else []
    if "is_live" in columns:
        where.append("is_live = TRUE")
    elif "status" in columns:
        where.append("LOWER(COALESCE(status, '')) IN ('live', 'published', 'active')")
    query = f"SELECT {', '.join(select_columns)} FROM chain_live_rooms"
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY created_at DESC LIMIT %s"
    connection = None
    try:
        connection = get_connection(statement_timeout_ms=200, fast_fail=True)
        rows = fetch_all_with_connection(connection, query, [limit], timeout_ms=200)
    except Exception:
        rows = []
    finally:
        release_connection(connection)
    normalized = []
    for row in rows:
        normalized.append(
            {
                "id": row.get("id"),
                "title": row.get("title") or "",
                "status": row.get("status") or ("live" if row.get("is_live") else "published"),
                "category": row.get("category") or "",
                "viewer_count": row.get("viewer_count"),
                "cover_url": row.get("cover_url"),
                "entry_fee": row.get("entry_fee"),
                "watch_url": f"/live/room/{row.get('id')}",
            }
        )
    set_cache(cache_key("chain_live_public_v1", limit), normalized, ttl=30)
    return normalized


def prime_live_rooms_public_cache(limit=8):
    try:
        get_live_rooms_public(limit=limit, allow_query=True)
    except Exception:
        set_cache(cache_key("chain_live_public_v1", limit), [], ttl=30)


def get_room(room_id):
    try:
        rooms = safe_select("chain_live_rooms", columns="id,title,host_name,host_profile_id,profile_id,status,is_live,category,access_type,viewer_count,gift_total,total_gift_coins,welcome_message,cover_url,youtube_url,youtube_embed_url,entry_fee,comments_enabled,gifts_enabled,mp3_url,created_at", filters={"id": room_id}, limit=1, order_by=None)
        room = _normalize_room(rooms[0]) if rooms else None
        if room and room.get("host_profile_id"):
            profile = _load_profile_map([room["host_profile_id"]]).get(room["host_profile_id"])
            if profile:
                room["host_name"] = room.get("host_name") or profile.get("full_name") or profile.get("username") or "NamVibe Host"
        return room
    except Exception as error:
        print(f"[live_service] get_room failed: {error}")
        return None


def join_room(room_id, display_name):
    try:
        current = get_current_profile()
        viewer_name = _viewer_name(display_name)
        joined_rooms = session.get("joined_live_rooms", [])

        if current:
            existing = safe_select(
                "chain_live_viewers",
                filters={"room_id": room_id, "profile_id": current["id"]},
                limit=1,
                order_by=None,
            )
            if existing:
                safe_update(
                    "chain_live_viewers",
                    {"left_at": None, "joined_at": _utcnow_iso(), "display_name": viewer_name},
                    eq={"id": existing[0]["id"]},
                )
            else:
                _insert_first(
                    "chain_live_viewers",
                    [
                        {"room_id": room_id, "profile_id": current["id"], "display_name": viewer_name, "joined_at": _utcnow_iso()},
                        {"room_id": room_id, "profile_id": current["id"], "joined_at": _utcnow_iso()},
                        {"room_id": room_id, "display_name": viewer_name, "joined_at": _utcnow_iso()},
                        {"room_id": room_id, "display_name": viewer_name},
                    ],
                )
        elif room_id not in joined_rooms:
            existing = safe_select(
                "chain_live_viewers",
                filters={"room_id": room_id, "display_name": viewer_name},
                limit=1,
                order_by=None,
            )
            if existing:
                safe_update(
                    "chain_live_viewers",
                    {"left_at": None, "joined_at": _utcnow_iso()},
                    eq={"id": existing[0]["id"]},
                )
            else:
                _insert_first(
                    "chain_live_viewers",
                    [
                        {"room_id": room_id, "display_name": viewer_name, "joined_at": _utcnow_iso()},
                        {"room_id": room_id, "display_name": viewer_name},
                    ],
                )
            session["joined_live_rooms"] = joined_rooms + [room_id]

        _update_room_totals(room_id)
    except Exception as error:
        print(f"[live_service] join_room failed: {error}")


def room_activity(room_id):
    try:
        comments = _normalize_comments(safe_select("chain_live_comments", limit=50, filters={"room_id": room_id}))
        gifts = _normalize_gifts(safe_select("chain_live_gifts", limit=20, filters={"room_id": room_id}))
        viewers = _normalize_viewers(
            safe_select(
                "chain_live_viewers",
                limit=100,
                filters={"room_id": room_id, "left_at": ("is", "null")},
            )
        )
        if not viewers:
            viewers = _normalize_viewers(safe_select("chain_live_viewers", limit=100, filters={"room_id": room_id}))
        cohost_requests = _normalize_cohost_requests(safe_select("chain_live_cohost_requests", limit=25, filters={"room_id": room_id}))
        return {
            "comments": comments,
            "gifts": gifts,
            "viewers": viewers,
            "cohost_requests": cohost_requests,
        }
    except Exception as error:
        print(f"[live_service] room_activity failed: {error}")
        return {"comments": [], "gifts": [], "viewers": [], "cohost_requests": []}


def add_comment(room_id, body, display_name):
    try:
        current = get_current_profile()
        message = (body or "").strip()
        if not message:
            return

        viewer_name = _viewer_name(display_name)
        _insert_first(
            "chain_live_comments",
            [
                {"room_id": room_id, "profile_id": (current or {}).get("id"), "display_name": viewer_name, "body": message, "created_at": _utcnow_iso()},
                {"room_id": room_id, "profile_id": (current or {}).get("id"), "comment": message, "created_at": _utcnow_iso()},
                {"room_id": room_id, "display_name": viewer_name, "body": message, "created_at": _utcnow_iso()},
                {"room_id": room_id, "display_name": viewer_name, "comment": message, "created_at": _utcnow_iso()},
            ],
        )
    except Exception as error:
        print(f"[live_service] add_comment failed: {error}")


def send_gift(room_id, gift_icon, gift_name, amount, display_name):
    try:
        current = get_current_profile()
        room = get_room(room_id) or {}
        viewer_name = _viewer_name(display_name)
        gift_amount = _safe_number(amount, 0)

        _insert_first(
            "chain_live_gifts",
            [
                {
                    "room_id": room_id,
                    "sender_profile_id": (current or {}).get("id"),
                    "host_profile_id": room.get("host_profile_id"),
                    "gift_name": gift_name or "Gift",
                    "emoji": gift_icon or "🎁",
                    "coins": int(gift_amount),
                    "created_at": _utcnow_iso(),
                },
                {
                    "room_id": room_id,
                    "display_name": viewer_name,
                    "gift_icon": gift_icon or "🎁",
                    "gift_name": gift_name or "Gift",
                    "amount": gift_amount,
                    "created_at": _utcnow_iso(),
                },
            ],
        )

        _update_room_totals(room_id)
    except Exception as error:
        print(f"[live_service] send_gift failed: {error}")


def request_cohost(room_id, display_name):
    try:
        current = get_current_profile()
        viewer_name = _viewer_name(display_name)
        _insert_first(
            "chain_live_cohost_requests",
            [
                {"room_id": room_id, "profile_id": (current or {}).get("id"), "display_name": viewer_name, "status": "pending", "created_at": _utcnow_iso()},
                {"room_id": room_id, "display_name": viewer_name, "status": "pending", "created_at": _utcnow_iso()},
            ],
        )
    except Exception as error:
        print(f"[live_service] request_cohost failed: {error}")


def get_cohost_requests(room_id):
    try:
        rows = safe_select(
            "chain_live_cohost_requests",
            limit=25,
            filters={"room_id": room_id, "status": "pending"},
        )
        return _normalize_cohost_requests(rows)
    except Exception as error:
        print(f"[live_service] get_cohost_requests failed: {error}")
        return []


def update_cohost_status(request_id, status):
    try:
        safe_update("chain_live_cohost_requests", {"status": status}, eq={"id": request_id})
    except Exception as error:
        print(f"[live_service] update_cohost_status failed: {error}")


def create_live_event(profile_id, data):
    """Schedules a new global live event"""
    payload = {
        "creator_profile_id": profile_id,
        "title": data.get("title"),
        "description": data.get("description"),
        "scheduled_start": data.get("scheduled_start"),
        "is_ticketed": data.get("is_ticketed") == 'true',
        "ticket_price_coins": int(data.get("ticket_price_coins", 0)),
        "status": "scheduled",
        "created_at": _utcnow_iso()
    }
    return safe_insert("chain_live_events", payload)

def get_upcoming_events(limit=10):
    """Fetches upcoming scheduled live events"""
    return safe_select("chain_live_events", filters={"status": "scheduled"}, limit=limit, order_by="scheduled_start")

def get_room_leaderboard(room_id, limit=5):
    """Returns top gifters for a live room"""
    sql = """
        SELECT sender_profile_id, SUM(coins) as total_coins, p.username, p.avatar_url
        FROM chain_live_gifts g
        JOIN chain_profiles p ON g.sender_profile_id = p.id
        WHERE room_id = %s
        GROUP BY sender_profile_id, p.username, p.avatar_url
        ORDER BY total_coins DESC
        LIMIT %s
    """
    return fast_query(sql, (room_id, limit))

def add_moderator(room_id, profile_id, permissions=None):
    """Adds a moderator to a live room"""
    payload = {
        "room_id": room_id,
        "profile_id": profile_id,
        "permissions": permissions or ["mute", "remove"]
    }
    return safe_insert("chain_live_moderators", payload)

def is_moderator(room_id, profile_id):
    """Checks if a user is a moderator of a room"""
    room = get_room(room_id)
    if room and room.get("host_profile_id") == profile_id:
        return True
    
    rows = safe_select("chain_live_moderators", filters={"room_id": room_id, "profile_id": profile_id}, limit=1)
    return len(rows) > 0

def pin_comment(room_id, comment_id, profile_id):
    """Pins a comment in a live room"""
    if not is_moderator(room_id, profile_id):
        return False, "Unauthorized"
    
    payload = {
        "room_id": room_id,
        "comment_id": comment_id,
        "profile_id": profile_id
    }
    # Using ON CONFLICT (room_id) UPDATE if supported, otherwise manual
    existing = safe_select("chain_live_pinned_comments", filters={"room_id": room_id}, limit=1)
    if existing:
        return safe_update("chain_live_pinned_comments", payload, eq={"room_id": room_id}) is not None, None
    return safe_insert("chain_live_pinned_comments", payload) is not None, None

def get_pinned_comment(room_id):
    """Gets the pinned comment for a room"""
    sql = """
        SELECT p.*, c.body, c.display_name
        FROM chain_live_pinned_comments p
        JOIN chain_live_comments c ON p.comment_id = c.id
        WHERE p.room_id = %s
        LIMIT 1
    """
    rows = fast_query(sql, (room_id,))
    return rows[0] if rows else None

def mute_user_live(room_id, target_profile_id, duration_minutes=15):
    """Mutes a user in a live stream"""
    # Placeholder for real mute logic, maybe a redis set with TTL
    from services.redis_service import cache_set
    key = f"live_mute:{room_id}:{target_profile_id}"
    cache_set(key, True, ttl=duration_minutes * 60)
    return True

def remove_user_live(room_id, target_profile_id):
    """Removes a user from a live stream"""
    # Mark as left in viewers table and optionally block from re-joining
    safe_update("chain_live_viewers", {"left_at": _utcnow_iso()}, eq={"room_id": room_id, "profile_id": target_profile_id})
    from services.redis_service import cache_set
    key = f"live_ban:{room_id}:{target_profile_id}"
    cache_set(key, True, ttl=3600) # 1 hour ban
    return True

def get_live_room_analytics(room_id):
    """Returns analytics for a live room session"""
    room = get_room(room_id)
    if not room: return None
    
    return {
        "peak_viewers": room.get("viewer_count", 0), # Simplified
        "total_gifts": room.get("gift_total", 0) or room.get("total_gift_coins", 0),
        "comment_count": safe_count("chain_live_comments", filters={"room_id": room_id}),
        "unique_viewers": safe_count("chain_live_viewers", filters={"room_id": room_id}),
        "duration": (datetime.now(timezone.utc) - _parse_dt(room.get("created_at"))).total_seconds() / 60 if room.get("is_live") else room.get("duration_seconds", 0) / 60
    }

def _parse_dt(value):
    if isinstance(value, datetime): return value
    try: return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except: return datetime.now(timezone.utc)

def end_live(room_id):
    try:
        ended_at = _utcnow_iso()
        if safe_update("chain_live_rooms", {"status": "ended", "ended_at": ended_at}, eq={"id": room_id}) is None:
            safe_update("chain_live_rooms", {"is_live": False, "ended_at": ended_at}, eq={"id": room_id})
        _invalidate_homepage_cache()
    except Exception as error:
        print(f"[live_service] end_live failed: {error}")
