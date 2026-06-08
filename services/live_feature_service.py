import os
import uuid
from datetime import datetime, timezone
import json

from services.neon_service import fast_query, get_pool_status, write_query
from services.socketio_service import emit_to_live_room

_ROOMS = {}
_VIEWERS = {}
_COMMENTS = {}
_GUEST_REQUESTS = {}
_POLLS = {}
_BATTLES = {}
_MODERATION = {}
_REPLAYS = {}
_CLIPS = {}
_SHOPPING = {}
_LEADERBOARD = {}
_STREAM_SETTINGS = {}


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


def _invalidate_homepage_cache():
    try:
        from services.homepage_cache_service import invalidate_homepage_cache
        invalidate_homepage_cache()
    except Exception:
        pass


def start_live(profile_id, title, host_name=None, allow_comments=True, allow_gifts=True):
    profile_id = _uuid(profile_id)
    room_id = str(uuid.uuid4())
    room = {
        "id": room_id,
        "profile_id": profile_id,
        "host_profile_id": profile_id,
        "title": (title or "Live on CHAIN").strip(),
        "host_name": host_name or "Creator",
        "status": "live",
        "is_live": True,
        "viewer_count": 0,
        "allow_comments": bool(allow_comments),
        "allow_gifts": bool(allow_gifts),
        "created_at": _now(),
    }
    try:
        rows = _write(
            "INSERT INTO chain_live_rooms (id, profile_id, host_profile_id, title, host_name, status, is_live, viewer_count, allow_comments, allow_gifts) VALUES (%s, %s, %s, %s, %s, 'live', TRUE, 0, %s, %s) RETURNING *",
            (room_id, profile_id, profile_id, room["title"], room["host_name"], room["allow_comments"], room["allow_gifts"]),
        )
        room = rows[0] if rows else room
    except Exception:
        _ROOMS[room_id] = room
    _invalidate_homepage_cache()
    emit_to_live_room(room_id, "live:started", room)
    return {"ok": True, "room": room}


def list_live_rooms(limit=20):
    if _db_available():
        rows = fast_query("SELECT * FROM chain_live_rooms WHERE status = 'live' OR is_live = TRUE ORDER BY created_at DESC LIMIT %s", (int(limit),), timeout_ms=700, default=[])
        if rows:
            return rows
    return [room for room in _ROOMS.values() if room.get("status") == "live"][:int(limit)]


def join_live(room_id, profile_id=None, display_name=None):
    room_id = _uuid(room_id)
    profile_id = _uuid(profile_id) if profile_id else None
    try:
        _write("INSERT INTO chain_live_viewers (room_id, profile_id, display_name, joined_at) VALUES (%s, %s, %s, now())", (room_id, profile_id, display_name))
        rows = fast_query("SELECT COUNT(*) AS count FROM chain_live_viewers WHERE room_id = %s AND left_at IS NULL", (room_id,), timeout_ms=500, default=[])
        count = int(rows[0]["count"]) if rows else 1
        _write("UPDATE chain_live_rooms SET viewer_count = %s WHERE id = %s", (count, room_id), timeout_ms=500)
    except Exception:
        _VIEWERS.setdefault(room_id, set()).add(profile_id or display_name or str(uuid.uuid4()))
        count = len(_VIEWERS[room_id])
        if room_id in _ROOMS:
            _ROOMS[room_id]["viewer_count"] = count
    emit_to_live_room(room_id, "live:viewers", {"room_id": room_id, "count": count})
    return {"ok": True, "viewer_count": count}


def comment_live(room_id, profile_id, body, display_name=None):
    room_id = _uuid(room_id)
    profile_id = _uuid(profile_id) if profile_id else None
    comment = {"id": str(uuid.uuid4()), "room_id": room_id, "profile_id": profile_id, "display_name": display_name, "body": body or "", "created_at": _now()}
    try:
        rows = _write("INSERT INTO chain_live_comments (room_id, profile_id, display_name, body) VALUES (%s, %s, %s, %s) RETURNING *", (room_id, profile_id, display_name, body))
        comment = rows[0] if rows else comment
    except Exception:
        _COMMENTS.setdefault(room_id, []).append(comment)
    emit_to_live_room(room_id, "live:comment", comment)
    return {"ok": True, "comment": comment}


def end_live(room_id, host_profile_id=None):
    room_id = _uuid(room_id)
    try:
        _write("UPDATE chain_live_rooms SET status = 'ended', is_live = FALSE, ended_at = now() WHERE id = %s", (room_id,))
    except Exception:
        if room_id in _ROOMS:
            _ROOMS[room_id]["status"] = "ended"
            _ROOMS[room_id]["is_live"] = False
            _ROOMS[room_id]["ended_at"] = _now()
    _invalidate_homepage_cache()
    emit_to_live_room(room_id, "live:ended", {"room_id": room_id})
    return {"ok": True}


def set_comments(room_id, allow_comments):
    room_id = _uuid(room_id)
    try:
        _write("UPDATE chain_live_rooms SET allow_comments = %s WHERE id = %s", (bool(allow_comments), room_id))
    except Exception:
        if room_id in _ROOMS:
            _ROOMS[room_id]["allow_comments"] = bool(allow_comments)
    return {"ok": True, "allow_comments": bool(allow_comments)}


def request_guest(room_id, profile_id, note=None):
    room_id = _uuid(room_id)
    profile_id = _uuid(profile_id)
    record = {"id": str(uuid.uuid4()), "room_id": room_id, "profile_id": profile_id, "status": "pending", "note": note}
    try:
        _write("INSERT INTO chain_live_guest_requests (id, room_id, profile_id, status, note) VALUES (%s, %s, %s, 'pending', %s)", (record["id"], room_id, profile_id, note))
    except Exception:
        _GUEST_REQUESTS[record["id"]] = record
    emit_to_live_room(room_id, "live:guest_request", record)
    return {"ok": True, "guest_request": record}


def update_guest_request(request_id, status):
    request_id = _uuid(request_id)
    status = status if status in {"accepted", "rejected", "pending"} else "pending"
    try:
        _write("UPDATE chain_live_guest_requests SET status = %s, updated_at = now() WHERE id = %s", (status, request_id))
    except Exception:
        _GUEST_REQUESTS.setdefault(request_id, {"id": request_id})["status"] = status
    return {"ok": True, "status": status}


def create_poll(room_id, profile_id, question, options):
    room_id = _uuid(room_id)
    profile_id = _uuid(profile_id)
    options = list(options or [])
    record = {"id": str(uuid.uuid4()), "room_id": room_id, "profile_id": profile_id, "question": question, "options": options, "votes": {}, "status": "open"}
    try:
        _write("INSERT INTO chain_live_polls (id, room_id, profile_id, question, options) VALUES (%s, %s, %s, %s, %s::jsonb)", (record["id"], room_id, profile_id, question, json.dumps(options)))
    except Exception:
        _POLLS[record["id"]] = record
    emit_to_live_room(room_id, "live:poll", record)
    return {"ok": True, "poll": record}


def vote_poll(poll_id, profile_id, option):
    poll_id = _uuid(poll_id)
    profile_id = _uuid(profile_id)
    try:
        rows = fast_query("SELECT votes FROM chain_live_polls WHERE id = %s LIMIT 1", (poll_id,), timeout_ms=500, default=[]) if _db_available() else []
        votes = rows[0].get("votes") if rows else {}
        votes = votes if isinstance(votes, dict) else {}
        votes[profile_id] = option
        _write("UPDATE chain_live_polls SET votes = %s::jsonb, updated_at = now() WHERE id = %s", (json.dumps(votes), poll_id))
    except Exception:
        _POLLS.setdefault(poll_id, {"id": poll_id, "votes": {}}).setdefault("votes", {})[profile_id] = option
    return {"ok": True}


def create_battle(room_id, host_profile_id=None, challenger_room_id=None, challenger_profile_id=None):
    room_id = _uuid(room_id)
    host_profile_id = _uuid(host_profile_id) if host_profile_id else None
    challenger_room_id = _uuid(challenger_room_id) if challenger_room_id else None
    challenger_profile_id = _uuid(challenger_profile_id) if challenger_profile_id else None
    record = {"id": str(uuid.uuid4()), "room_id": room_id, "host_profile_id": host_profile_id, "challenger_room_id": challenger_room_id, "challenger_profile_id": challenger_profile_id, "status": "invited"}
    try:
        _write("INSERT INTO chain_live_battles (id, room_id, challenger_room_id, host_profile_id, challenger_profile_id, status) VALUES (%s, %s, %s, %s, %s, 'invited')", (record["id"], room_id, challenger_room_id, host_profile_id, challenger_profile_id))
    except Exception:
        _BATTLES[record["id"]] = record
    emit_to_live_room(room_id, "live:battle", record)
    return {"ok": True, "battle": record}


def moderation_action(room_id, moderator_profile_id, action_type, target_profile_id=None, reason=None):
    room_id = _uuid(room_id)
    moderator_profile_id = _uuid(moderator_profile_id) if moderator_profile_id else None
    target_profile_id = _uuid(target_profile_id) if target_profile_id else None
    record = {"id": str(uuid.uuid4()), "room_id": room_id, "moderator_profile_id": moderator_profile_id, "target_profile_id": target_profile_id, "action_type": action_type, "reason": reason}
    try:
        _write("INSERT INTO chain_live_moderation_actions (id, room_id, moderator_profile_id, target_profile_id, action_type, reason) VALUES (%s, %s, %s, %s, %s, %s)", (record["id"], room_id, moderator_profile_id, target_profile_id, action_type, reason))
    except Exception:
        _MODERATION[record["id"]] = record
    emit_to_live_room(room_id, "live:moderation", record)
    return {"ok": True, "moderation": record}


def save_replay(room_id, profile_id=None, replay_url=None, duration_seconds=0, **metadata):
    return _insert_live_record("chain_live_replays", _REPLAYS, room_id, profile_id, {"replay_url": replay_url, "duration_seconds": float(duration_seconds or 0), "metadata": metadata}, "replay")


def create_clip(room_id, profile_id, clip_url=None, start_seconds=0, duration_seconds=0, title=None, **metadata):
    return _insert_live_record("chain_live_clips", _CLIPS, room_id, profile_id, {"clip_url": clip_url, "start_seconds": float(start_seconds or 0), "duration_seconds": float(duration_seconds or 0), "title": title, "metadata": metadata}, "clip")


def add_shopping_item(room_id, profile_id, title, price_coins=0, url=None):
    return _insert_live_record("chain_live_shopping_items", _SHOPPING, room_id, profile_id, {"title": title, "price_coins": float(price_coins or 0), "url": url}, "shopping_item")


def upsert_leaderboard(room_id, profile_id, score=0, rank=None, **metadata):
    room_id = _uuid(room_id)
    profile_id = _uuid(profile_id)
    record = {"id": str(uuid.uuid4()), "room_id": room_id, "profile_id": profile_id, "score": float(score or 0), "rank": rank, "metadata": metadata}
    try:
        _write("INSERT INTO chain_live_leaderboard (id, room_id, profile_id, score, rank, metadata) VALUES (%s, %s, %s, %s, %s, %s::jsonb)", (record["id"], room_id, profile_id, record["score"], rank, json.dumps(metadata)))
    except Exception:
        _LEADERBOARD[(room_id, profile_id)] = record
    return {"ok": True, "leaderboard": record}


def save_stream_settings(room_id, profile_id, **settings):
    room_id = _uuid(room_id)
    profile_id = _uuid(profile_id)
    record = {
        "room_id": room_id,
        "profile_id": profile_id,
        "webrtc_enabled": bool(settings.get("webrtc_enabled", True)),
        "rtmp_enabled": bool(settings.get("rtmp_enabled", False)),
        "rtmp_stream_key": settings.get("rtmp_stream_key"),
        "turn_required": bool(settings.get("turn_required", False)),
        "settings": settings,
    }
    try:
        _write(
            """
            INSERT INTO chain_live_stream_settings
            (room_id, profile_id, webrtc_enabled, rtmp_enabled, rtmp_stream_key, turn_required, settings)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (room_id, profile_id, record["webrtc_enabled"], record["rtmp_enabled"], record["rtmp_stream_key"], record["turn_required"], json.dumps(settings)),
        )
    except Exception:
        _STREAM_SETTINGS[(room_id, profile_id)] = record
    return {"ok": True, "stream_settings": record}


def _insert_live_record(table, store, room_id, profile_id, data, key):
    room_id = _uuid(room_id)
    profile_id = _uuid(profile_id) if profile_id else None
    record = {"id": str(uuid.uuid4()), "room_id": room_id, "profile_id": profile_id, **data}
    try:
        columns = ["id", "room_id", "profile_id", *data.keys()]
        placeholders = []
        params = []
        for column in columns:
            value = record[column]
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
                placeholders.append("%s::jsonb")
            else:
                placeholders.append("%s")
            params.append(value)
        _write(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})", tuple(params))
    except Exception:
        store[record["id"]] = record
    emit_to_live_room(room_id, f"live:{key}", record)
    return {"ok": True, key: record}
