import uuid
import os
import time
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query
from services.redis_service import cache_get, cache_set, cache_delete, publish
from services.request_cache import build_request_key, request_memoize
from services.socketio_service import broadcast_notification
from services.logging_service import log_info, log_error

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
    # Dedup check: skip if same notification sent in the last 10 seconds
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
            # Mark as sent for dedup
            cache_set(dedup_key, True, ttl=10)
            
            # Invalidate unread count cache in Redis
            cache_delete(f"notif_unread_{recipient_profile_id}")
            
            # Realtime emit
            broadcast_notification(recipient_profile_id, res[0])
            publish(f"notifications:{recipient_profile_id}", {"event": "notification:new", "payload": res[0]})
            
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
    return fast_query(sql, (profile_id, limit), timeout_ms=1000)

def unread_count(profile_id):
    """Returns the count of unread notifications, with optimized caching."""
    if not profile_id:
        return 0
    
    cache_key = f"notif_unread_{profile_id}"
    
    # 1. Try Redis cache first (5-minute TTL by default in mark_read/create)
    cached = cache_get(cache_key)
    if cached is not None:
        return int(cached)

    # 2. Per-request memoization to avoid multiple DB hits for the same profile in one request
    # This is critical if multiple parts of the UI call this in one page load
    req_key = f"req_unread_{profile_id}"
    
    def _fetch_count():
        # Optimization: use a faster COUNT query
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
    
    # 3. Cache back to Redis with jittered TTL (60-90 seconds) to prevent stampedes
    # We use a shorter TTL here than in mark_read to ensure eventual consistency
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
