import uuid
import json
import os
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query
from services.socketio_service import emit_to_profile
from engines.cache_engine import cache_key, get_cache, set_cache

_ACTIVITY_TYPES = frozenset({
    "friend_request_sent", "friend_request_accepted",
    "message_sent", "message_reacted", "message_edited", "message_deleted",
    "call_started", "call_ended", "call_missed",
    "profile_viewed", "gallery_viewed",
    "story_created", "post_liked", "post_commented", "reel_watched",
    "user_online", "user_offline",
    "upload_started", "upload_completed", "upload_failed",
})

_ACTIVITY_TABLE = "chain_activity_events"


def _table_exists():
    try:
        rows = fast_query(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s) AS exists",
            (_ACTIVITY_TABLE,), default=[{"exists": False}]
        )
        return rows and rows[0].get("exists", False)
    except Exception:
        return False


TABLE_EXISTS = _table_exists()


def _now():
    return datetime.now(timezone.utc)


def safe_activity_metadata(metadata):
    if not metadata:
        return {}
    safe = {}
    allowed_keys = {"preview", "thread_id", "call_id", "post_id", "reel_id", "story_id",
                    "gallery_id", "upload_id", "filename", "mime_type", "size_bytes", "duration_seconds"}
    for k, v in metadata.items():
        if k in allowed_keys and isinstance(v, (str, int, float, bool)):
            safe[k] = v
    return safe


def emit_activity(actor_profile_id, event_type, target_type=None, target_id=None,
                  recipient_profile_id=None, metadata=None, visibility="private"):
    if not actor_profile_id:
        return None
    if event_type not in _ACTIVITY_TYPES:
        return None

    activity_id = str(uuid.uuid4())
    safe_meta = safe_activity_metadata(metadata) if metadata else {}

    if TABLE_EXISTS:
        try:
            write_query(
                f"""INSERT INTO {_ACTIVITY_TABLE}
                   (id, actor_profile_id, recipient_profile_id, event_type, target_type, target_id, metadata, visibility, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)""",
                (activity_id, actor_profile_id, recipient_profile_id, event_type,
                 target_type, target_id, json.dumps(safe_meta), visibility, _now())
            )
        except Exception:
            return None

    activity = {
        "id": activity_id,
        "actor_profile_id": actor_profile_id,
        "recipient_profile_id": recipient_profile_id,
        "event_type": event_type,
        "target_type": target_type,
        "target_id": target_id,
        "metadata": safe_meta,
        "visibility": visibility,
        "created_at": _now().isoformat(),
    }

    emit_socket_activity(activity)

    if recipient_profile_id:
        from services.notification_center_service import invalidate_notification_feed_cache
        invalidate_notification_feed_cache(recipient_profile_id)

    return activity_id


def emit_socket_activity(activity):
    payload = {
        "id": activity["id"],
        "event_type": activity["event_type"],
        "actor_profile_id": activity["actor_profile_id"],
        "target_type": activity.get("target_type"),
        "target_id": activity.get("target_id"),
        "metadata": activity.get("metadata", {}),
        "created_at": activity.get("created_at"),
    }
    recipient = activity.get("recipient_profile_id")
    if recipient:
        emit_to_profile(recipient, "activity:new", payload)

    actor = activity.get("actor_profile_id")
    if actor:
        emit_to_profile(actor, "activity:new", payload)


def get_recent_activity(profile_id, limit=20):
    if not profile_id:
        return []
    if not TABLE_EXISTS:
        return []
    try:
        rows = fast_query(
            f"""SELECT id, actor_profile_id, recipient_profile_id, event_type,
                       target_type, target_id, metadata, visibility, created_at
                FROM {_ACTIVITY_TABLE}
                WHERE (recipient_profile_id = %s OR actor_profile_id = %s)
                  AND deleted_at IS NULL
                ORDER BY created_at DESC LIMIT %s""",
            (profile_id, profile_id, limit),
            default=[]
        )
        result = []
        for r in rows:
            meta = r.get("metadata")
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            created = r.get("created_at")
            if hasattr(created, "isoformat"):
                created = created.isoformat()
            result.append({
                "id": str(r["id"]),
                "actor_profile_id": str(r["actor_profile_id"]),
                "recipient_profile_id": str(r["recipient_profile_id"]) if r.get("recipient_profile_id") else None,
                "event_type": r["event_type"],
                "target_type": r.get("target_type"),
                "target_id": str(r["target_id"]) if r.get("target_id") else None,
                "metadata": meta or {},
                "visibility": r.get("visibility", "private"),
                "created_at": created,
            })
        return result
    except Exception:
        return []


def get_activity_summary(profile_id):
    if not profile_id or not TABLE_EXISTS:
        return {}
    try:
        rows = fast_query(
            f"""SELECT event_type, COUNT(*) as cnt
                FROM {_ACTIVITY_TABLE}
                WHERE recipient_profile_id = %s AND deleted_at IS NULL
                GROUP BY event_type ORDER BY cnt DESC LIMIT 10""",
            (profile_id,), default=[]
        )
        summary = {}
        for r in rows:
            summary[r["event_type"]] = r["cnt"]
        return summary
    except Exception:
        return {}
