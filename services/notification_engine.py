import uuid
import os
import time
import json
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query
from services.redis_service import cache_get, cache_set, cache_delete, publish
from services.request_cache import build_request_key, request_memoize
from services.socketio_service import broadcast_notification
from services.logging_service import log_info, log_error

_NOTIF_TYPE_CATEGORIES = {
    "follow": "activity",
    "follow_accepted": "activity",
    "mention": "mentions",
    "comment": "activity",
    "reply": "activity",
    "post_like": "activity",
    "reel_like": "activity",
    "story_reaction": "activity",
    "story_mention": "mentions",
    "live_started": "activity",
    "creator_subscription": "activity",
    "wallet_transfer": "activity",
    "wallet_received": "activity",
    "dating_match": "activity",
    "verification_approved": "system",
    "security_alert": "system",
    "system_announcement": "system",
    "new_message": "messages",
    "message_reaction": "messages",
}

_NOTIF_ICONS = {
    "follow": "fa-user-plus",
    "follow_accepted": "fa-check-double",
    "mention": "fa-at",
    "comment": "fa-comment",
    "reply": "fa-reply",
    "post_like": "fa-heart",
    "reel_like": "fa-heart",
    "story_reaction": "fa-smile",
    "story_mention": "fa-at",
    "live_started": "fa-video",
    "creator_subscription": "fa-crown",
    "wallet_transfer": "fa-paper-plane",
    "wallet_received": "fa-wallet",
    "dating_match": "fa-heart",
    "verification_approved": "fa-check-circle",
    "security_alert": "fa-shield-alt",
    "system_announcement": "fa-bullhorn",
    "new_message": "fa-envelope",
    "message_reaction": "fa-reply",
}

def _notif_category(event_type):
    return _NOTIF_TYPE_CATEGORIES.get(event_type, "activity")

def _notif_icon(event_type):
    return _NOTIF_ICONS.get(event_type, "fa-bell")

def _enrich_with_profiles(rows):
    if not rows:
        return []
    profile_ids = set()
    for r in rows:
        if r.get("actor_profile_id"):
            profile_ids.add(r["actor_profile_id"])
    if not profile_ids:
        return rows
    ids_list = list(profile_ids)
    placeholders = ",".join(["%s"] * len(ids_list))
    sql = f"SELECT id, username, avatar_url, display_name FROM chain_profiles WHERE id IN ({placeholders})"
    try:
        profiles = fast_query(sql, tuple(ids_list), timeout_ms=500, default=[])
    except Exception:
        profiles = []
    pmap = {p["id"]: p for p in profiles}
    enriched = []
    for r in rows:
        d = dict(r)
        actor = pmap.get(r.get("actor_profile_id"))
        if actor:
            d["actor_username"] = actor.get("username") or d.get("actor_username")
            d["actor_avatar"] = actor.get("avatar_url") or d.get("actor_avatar")
            d["actor_display_name"] = actor.get("display_name")
        d["category"] = _notif_category(r.get("event_type", ""))
        d["icon"] = _notif_icon(r.get("event_type", ""))
        enriched.append(d)
    return enriched

def create_notification(
    recipient_profile_id,
    event_type,
    title,
    body=None,
    actor_profile_id=None,
    entity_type=None,
    entity_id=None,
    action_url=None
):
    """Creates a new notification in Neon and emits realtime event with deduplication."""
    dedup_key = f"notif_dedup:{recipient_profile_id}:{actor_profile_id or 'sys'}:{event_type}:{entity_id or 'none'}"
    if cache_get(dedup_key):
        return None

    sql = """
        INSERT INTO chain_notifications (
            id, recipient_profile_id, actor_profile_id, event_type, 
            title, body, entity_type, entity_id, action_url, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
        RETURNING *
    """
    params = (
        str(uuid.uuid4()), recipient_profile_id, actor_profile_id, event_type,
        title, body, entity_type, entity_id, action_url
    )
    try:
        res = write_query(sql, params)
        if res:
            cache_set(dedup_key, True, ttl=10)
            cache_delete(f"notif_unread_{recipient_profile_id}")
            enriched = _enrich_with_profiles(res)
            broadcast_notification(recipient_profile_id, enriched[0] if enriched else res[0])
            publish(f"notifications:{recipient_profile_id}", {"event": "notification:new", "payload": enriched[0] if enriched else res[0]})
            log_info("notification_created", recipient_id=recipient_profile_id, type=event_type)
            return res[0]['id']
        return None
    except Exception as e:
        log_error("notification_creation_failed", error=e)
        return None

def list_notifications(profile_id, limit=30):
    """Lists notifications for a specific profile."""
    sql = """
        SELECT n.*, p.username as actor_username, p.avatar_url as actor_avatar
        FROM chain_notifications n
        LEFT JOIN chain_profiles p ON n.actor_profile_id = p.id
        WHERE n.recipient_profile_id = %s AND n.deleted_at IS NULL
        ORDER BY n.created_at DESC
        LIMIT %s
    """
    rows = fast_query(sql, (profile_id, limit), timeout_ms=1000)
    return _enrich_with_profiles(rows)

def list_notifications_tab(profile_id, tab="all", page=1, limit=20):
    """Lists notifications by tab category with pagination."""
    offset = (page - 1) * limit
    conditions = ["n.recipient_profile_id = %s", "n.deleted_at IS NULL"]
    params = [profile_id]

    if tab == "unread":
        conditions.append("n.is_read = FALSE")
    elif tab == "mentions":
        mention_types = ["mention", "story_mention"]
        placeholders = ",".join(["%s"] * len(mention_types))
        conditions.append(f"n.event_type IN ({placeholders})")
        params.extend(mention_types)
    elif tab == "messages":
        msg_types = ["new_message", "message_reaction"]
        placeholders = ",".join(["%s"] * len(msg_types))
        conditions.append(f"n.event_type IN ({placeholders})")
        params.extend(msg_types)
    elif tab == "system":
        sys_types = ["verification_approved", "security_alert", "system_announcement"]
        placeholders = ",".join(["%s"] * len(sys_types))
        conditions.append(f"n.event_type IN ({placeholders})")
        params.extend(sys_types)
    elif tab == "activity":
        activity_types = [k for k, v in _NOTIF_TYPE_CATEGORIES.items() if v == "activity"]
        placeholders = ",".join(["%s"] * len(activity_types))
        conditions.append(f"n.event_type IN ({placeholders})")
        params.extend(activity_types)

    where_clause = " AND ".join(conditions)

    try:
        rows = fast_query(
            f"""
                SELECT n.*, p.username as actor_username, p.avatar_url as actor_avatar
                FROM chain_notifications n
                LEFT JOIN chain_profiles p ON n.actor_profile_id = p.id
                WHERE {where_clause}
                ORDER BY n.created_at DESC
                LIMIT %s OFFSET %s
            """,
            tuple(params + [limit + 1, offset]),
            timeout_ms=1000,
            default=[],
        )
    except Exception:
        return [], False

    has_more = len(rows) > limit
    items = rows[:limit]
    return _enrich_with_profiles(items), has_more

def unread_count(profile_id):
    """Returns the count of unread notifications, with optimized caching."""
    if not profile_id:
        return 0
    if os.getenv("FLASK_TESTING") == "1" or (os.getenv("CHAIN_FAST_LOCAL") == "1" and os.getenv("FLASK_ENV", "development") != "production"):
        return 0
    
    cache_key = f"notif_unread_{profile_id}"
    
    cached = cache_get(cache_key)
    if cached is not None:
        return int(cached)

    req_key = f"req_unread_{profile_id}"
    
    def _fetch_count():
        sql = """
            SELECT COUNT(*) as count 
            FROM chain_notifications 
            WHERE recipient_profile_id = %s 
              AND is_read = FALSE 
              AND deleted_at IS NULL
        """
        local_fast = os.getenv("CHAIN_FAST_LOCAL") == "1" and os.getenv("FLASK_ENV", "development") != "production"
        timeout_ms = 250 if local_fast else 1000
        try:
            res = fast_query(sql, (profile_id,), timeout_ms=timeout_ms, default=[])
            return res[0]['count'] if res else 0
        except Exception:
            return 0

    count = request_memoize(req_key, _fetch_count)
    
    jitter_ttl = 60 + (int(uuid.uuid4().int) % 30)
    cache_set(cache_key, count, ttl=jitter_ttl)
    
    return count

def mark_read(notification_id, profile_id):
    """Marks a single notification as read and invalidates cache."""
    sql = "UPDATE chain_notifications SET is_read = TRUE, read_at = now() WHERE id = %s AND recipient_profile_id = %s"
    try:
        write_query(sql, (notification_id, profile_id))
        cache_delete(f"notif_unread_{profile_id}")
        return True
    except Exception as e:
        log_error("notification_mark_read_failed", error=e, id=notification_id)
        return False

def mark_all_read(profile_id):
    """Marks all notifications for a profile as read and invalidates cache."""
    sql = "UPDATE chain_notifications SET is_read = TRUE, read_at = now() WHERE recipient_profile_id = %s AND is_read = FALSE"
    try:
        write_query(sql, (profile_id,))
        cache_delete(f"notif_unread_{profile_id}")
        return True
    except Exception as e:
        log_error("notification_mark_all_read_failed", error=e, profile_id=profile_id)
        return False

def delete_notification(notification_id, profile_id):
    """Soft-deletes a single notification."""
    sql = "UPDATE chain_notifications SET deleted_at = now() WHERE id = %s AND recipient_profile_id = %s"
    try:
        write_query(sql, (notification_id, profile_id))
        return True
    except Exception as e:
        log_error("notification_delete_failed", error=e, id=notification_id)
        return False

def delete_selected_notifications(notification_ids, profile_id):
    """Soft-deletes multiple notifications at once."""
    if not notification_ids:
        return False
    placeholders = ",".join(["%s"] * len(notification_ids))
    sql = f"UPDATE chain_notifications SET deleted_at = now() WHERE id IN ({placeholders}) AND recipient_profile_id = %s"
    try:
        params = tuple(notification_ids) + (profile_id,)
        write_query(sql, params)
        cache_delete(f"notif_unread_{profile_id}")
        return True
    except Exception as e:
        log_error("notifications_delete_selected_failed", error=e, count=len(notification_ids))
        return False

def mute_notification_type(profile_id, event_type, muted=True):
    """Mutes or unmutes a notification type for a profile using notification_preferences."""
    sql = """
        INSERT INTO chain_notification_preferences (profile_id, muted_types)
        VALUES (%s, %s::jsonb)
        ON CONFLICT (profile_id)
        DO UPDATE SET muted_types = (
            CASE WHEN %s THEN
                COALESCE(chain_notification_preferences.muted_types, '[]'::jsonb) || %s::jsonb
            ELSE
                (SELECT jsonb_agg(elem) FROM jsonb_array_elements_text(
                    COALESCE(chain_notification_preferences.muted_types, '[]'::jsonb)
                ) AS elem WHERE elem::text <> %s)
            END
        )
    """
    type_json = json.dumps([event_type])
    try:
        write_query(sql, (profile_id, type_json, muted, type_json, event_type))
        return True
    except Exception as e:
        log_error("notification_mute_failed", error=e, profile_id=profile_id, type=event_type)
        return False

def get_notification_preferences(profile_id):
    """Gets notification preferences for a profile."""
    sql = "SELECT * FROM chain_notification_preferences WHERE profile_id = %s"
    try:
        rows = fast_query(sql, (profile_id,), timeout_ms=500, default=[])
        if rows:
            prefs = dict(rows[0])
            if isinstance(prefs.get("muted_types"), str):
                prefs["muted_types"] = json.loads(prefs["muted_types"])
            return prefs
        return {"profile_id": profile_id, "muted_types": []}
    except Exception as e:
        log_error("notification_get_prefs_failed", error=e, profile_id=profile_id)
        return {"profile_id": profile_id, "muted_types": []}

def update_notification_preferences(profile_id, prefs_data):
    """Updates notification preferences."""
    muted_types = json.dumps(prefs_data.get("muted_types", []))
    sql = """
        INSERT INTO chain_notification_preferences (profile_id, muted_types, email_enabled, push_enabled, in_app_enabled, sms_enabled)
        VALUES (%s, %s::jsonb, %s, %s, %s, %s)
        ON CONFLICT (profile_id)
        DO UPDATE SET
            muted_types = EXCLUDED.muted_types,
            email_enabled = EXCLUDED.email_enabled,
            push_enabled = EXCLUDED.push_enabled,
            in_app_enabled = EXCLUDED.in_app_enabled,
            sms_enabled = EXCLUDED.sms_enabled,
            updated_at = now()
    """
    try:
        write_query(sql, (
            profile_id,
            muted_types,
            prefs_data.get("email_enabled", True),
            prefs_data.get("push_enabled", True),
            prefs_data.get("in_app_enabled", True),
            prefs_data.get("sms_enabled", False),
        ))
        return True
    except Exception as e:
        log_error("notification_update_prefs_failed", error=e, profile_id=profile_id)
        return False
