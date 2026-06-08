from datetime import datetime, timezone
import os
from engines.cache_engine import cache_key, delete_cache, get_cache, set_cache
from services.profile_service import get_current_profile
from services.supabase_safe import safe_count, safe_insert, safe_select, safe_update, table_exists


def normalize_notification(notification):
    if not notification:
        return {}

    normalized = dict(notification)
    normalized["body"] = normalized.get("body") or normalized.get("message") or ""
    normalized["type"] = normalized.get("type") or normalized.get("notification_type") or "info"
    normalized["target_url"] = normalized.get("target_url") or normalized.get("link_url")
    return normalized


def get_unread_notification_count(profile_id=None):
    current = None
    if not profile_id:
        current = get_current_profile()
        if not current:
            return 0
        profile_id = current["id"]

    key = cache_key("notif_unread", profile_id)
    cached_count = get_cache(key)
    if cached_count is not None:
        return cached_count

    count = 0
    if table_exists("chain_notification_events"):
        count += safe_count("chain_notification_events", filters={"profile_id": profile_id, "is_read": False})
    
    if table_exists("chain_notifications"):
        count += safe_count("chain_notifications", filters={"profile_id": profile_id, "is_read": False})
    
    set_cache(key, count, ttl=20)
    return count


def create_notification(profile_id=None, actor_profile_id=None, title="", body="", n_type="info", link_url=None):
    if not profile_id:
        return False
        
    payload = {
        "profile_id": profile_id,
        "actor_profile_id": actor_profile_id,
        "event_type": n_type or "info",
        "title": title or "Notification",
        "body": body or "",
        "target_url": link_url,
        "is_read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    if table_exists("chain_notification_events"):
        if safe_insert("chain_notification_events", payload) is not None:
            delete_cache(cache_key("notif_unread", profile_id))
            return True

    # Fallback to legacy
    legacy_payloads = [
        {
            "profile_id": profile_id,
            "title": title or "Notification",
            "message": body or "",
            "notification_type": n_type or "info",
            "target_url": link_url,
            "is_read": False,
        }
    ]
    for p in legacy_payloads:
        if safe_insert("chain_notifications", p) is not None:
            delete_cache(cache_key("notif_unread", profile_id))
            return True

    return False


def get_my_notifications(limit=30):
    if os.getenv("CHAIN_FAST_LOCAL") == "1" and os.getenv("FLASK_ENV", "development") != "production":
        return [], None, 0

    current = get_current_profile()
    if not current:
        return [], None, 0

    all_notifs = []
    if table_exists("chain_notification_events"):
        all_notifs.extend(safe_select("chain_notification_events", filters={"profile_id": current["id"]}, limit=limit))
        
    if table_exists("chain_notifications"):
        all_notifs.extend(safe_select("chain_notifications", filters={"profile_id": current["id"]}, limit=limit))
    
    # Sort by created_at
    all_notifs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    unread = get_unread_notification_count(current["id"])
    return [normalize_notification(item) for item in all_notifs[:limit]], current, unread


def mark_notification_read(notification_id):
    result = safe_update("chain_notifications", {"is_read": True}, eq={"id": notification_id})
    delete_cache(cache_key("notif_unread", (get_current_profile() or {}).get("id")))
    return result is not None


def mark_all_read():
    current = get_current_profile()
    if not current:
        return True

    result = safe_update(
        "chain_notifications",
        {"is_read": True},
        eq={"profile_id": current["id"]},
    )
    delete_cache(cache_key("notif_unread", current["id"]))
    return result is not None
