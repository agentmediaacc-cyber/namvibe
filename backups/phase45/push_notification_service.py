import json
import os
import time
from datetime import datetime, timezone

from services.neon_service import fast_query, write_query, get_pool_status
from services.request_cache import request_get, request_set, request_memoize, build_request_key
from engines.cache_engine import cache_key, get_cache, set_cache

VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_CLAIM_EMAIL = os.getenv("VAPID_CLAIM_EMAIL", "push@chain.app")
_WEB_PUSH_AVAILABLE = None


def _vapid_available():
    global _WEB_PUSH_AVAILABLE
    if _WEB_PUSH_AVAILABLE is not None:
        return _WEB_PUSH_AVAILABLE
    _WEB_PUSH_AVAILABLE = bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)
    return _WEB_PUSH_AVAILABLE


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def get_vapid_public_key():
    return VAPID_PUBLIC_KEY


def save_subscription(profile_id, endpoint, p256dh, auth_key, user_agent="", device_type="web"):
    if not profile_id or not endpoint:
        return {"ok": False, "error": "missing_fields"}
    try:
        if _db_available():
            existing = fast_query(
                "SELECT id FROM chain_push_subscriptions WHERE profile_id = %s AND endpoint = %s LIMIT 1",
                (profile_id, endpoint),
                timeout_ms=500,
                default=[],
            )
            if existing:
                write_query(
                    "UPDATE chain_push_subscriptions SET p256dh = %s, auth = %s, user_agent = %s, device_type = %s, is_active = true, last_seen_at = now(), updated_at = now() WHERE id = %s",
                    (p256dh, auth_key, user_agent, device_type, existing[0]["id"]),
                    timeout_ms=500,
                )
            else:
                write_query(
                    "INSERT INTO chain_push_subscriptions (profile_id, endpoint, p256dh, auth, user_agent, device_type) VALUES (%s, %s, %s, %s, %s, %s)",
                    (profile_id, endpoint, p256dh, auth_key, user_agent, device_type),
                    timeout_ms=500,
                )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def remove_subscription(profile_id, endpoint):
    if not profile_id or not endpoint:
        return {"ok": False, "error": "missing_fields"}
    try:
        if _db_available():
            write_query(
                "UPDATE chain_push_subscriptions SET is_active = false WHERE profile_id = %s AND endpoint = %s",
                (profile_id, endpoint),
                timeout_ms=500,
            )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_subscriptions(profile_id):
    if not profile_id:
        return []
    try:
        if _db_available():
            return fast_query(
                "SELECT id, endpoint, p256dh, auth, user_agent, device_type FROM chain_push_subscriptions WHERE profile_id = %s AND is_active = true",
                (profile_id,),
                timeout_ms=500,
                default=[],
            )
        return []
    except Exception:
        return []


def get_preferences(profile_id):
    if not profile_id:
        return _default_preferences()
    cache_hit = get_cache(cache_key("push_prefs", profile_id))
    if cache_hit is not None:
        return cache_hit
    try:
        if _db_available():
            rows = fast_query(
                "SELECT * FROM chain_notification_preferences WHERE profile_id = %s LIMIT 1",
                (profile_id,),
                timeout_ms=500,
                default=[],
            )
            if rows:
                prefs = dict(rows[0])
                prefs.pop("id", None)
                prefs.pop("created_at", None)
                prefs.pop("updated_at", None)
                set_cache(cache_key("push_prefs", profile_id), prefs, ttl=120)
                return prefs
    except Exception:
        pass
    return _default_preferences()


def _default_preferences():
    return {
        "messages": True,
        "calls": True,
        "live": True,
        "groups": True,
        "wallet": True,
        "safety": True,
        "creator_updates": True,
    }


def update_preferences(profile_id, prefs):
    if not profile_id:
        return {"ok": False, "error": "missing_profile"}
    allowed = {"messages", "calls", "live", "groups", "wallet", "safety", "creator_updates"}
    clean = {k: bool(v) for k, v in prefs.items() if k in allowed}
    if not clean:
        return {"ok": False, "error": "no_valid_keys"}
    try:
        columns = ", ".join(clean.keys())
        placeholders = ", ".join(["%s"] * len(clean))
        updates = ", ".join(f"{k} = %s" for k in clean.keys())
        if _db_available():
            write_query(
                f"INSERT INTO chain_notification_preferences (profile_id, {columns}) VALUES (%s, {placeholders}) ON CONFLICT (profile_id) DO UPDATE SET {updates}, updated_at = now()",
                (profile_id, *clean.values(), *clean.values()),
                timeout_ms=500,
            )
        delete_cache(cache_key("push_prefs", profile_id))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def queue_push_event(profile_id, event_type, title="", body="", payload=None):
    if not profile_id or not event_type:
        return {"ok": False, "error": "missing_fields"}
    prefs = get_preferences(profile_id)
    event_type_to_pref = {
        "message_received": "messages",
        "incoming_call": "calls",
        "missed_call": "calls",
        "live_started": "live",
        "group_invite": "groups",
        "group_join_request": "groups",
        "creator_gift": "creator_updates",
        "wallet_update": "wallet",
        "safety_alert": "safety",
    }
    pref_key = event_type_to_pref.get(event_type)
    if pref_key and not prefs.get(pref_key, True):
        return {"ok": False, "error": "disabled_by_user"}
    try:
        if _db_available():
            write_query(
                "INSERT INTO chain_push_events (profile_id, event_type, title, body, payload, provider_missing) VALUES (%s, %s, %s, %s, %s::jsonb, %s)",
                (profile_id, event_type, title, body, json.dumps(payload or {}), not _vapid_available()),
                timeout_ms=500,
            )
        if _vapid_available():
            _send_web_push(profile_id, title, body, payload)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _send_web_push(profile_id, title, body, payload=None):
    subscriptions = get_subscriptions(profile_id)
    if not subscriptions:
        return False
    sent = 0
    for sub in subscriptions:
        try:
            result = _web_push_send(sub["endpoint"], sub["p256dh"], sub["auth"], title, body, payload)
            if result.get("ok"):
                sent += 1
        except Exception:
            pass
    return sent > 0


def _web_push_send(endpoint, p256dh, auth_key, title, body, payload=None):
    if not _vapid_available():
        return {"ok": False, "error": "provider_missing"}
    try:
        import pywebpush
        data = json.dumps({
            "title": title or "CHAIN",
            "body": body or "",
            "data": payload or {},
            "icon": "/static/img/icon-192.png",
            "badge": "/static/img/icon-192.png",
        })
        try:
            response = pywebpush.webpush(
                endpoint,
                data,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{VAPID_CLAIM_EMAIL}"},
                timeout=5,
            )
            if response and response.status_code == 201:
                return {"ok": True}
        except Exception as e:
            err_str = str(e)
            if "410" in err_str or "gone" in err_str.lower() or "unsubscribe" in err_str.lower():
                remove_subscription(None, endpoint)
            return {"ok": False, "error": err_str}
        return {"ok": True}
    except ImportError:
        return {"ok": False, "error": "pywebpush_not_installed"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def send_push_notification(profile_id, title, body, data=None):
    return queue_push_event(profile_id, "message_received", title, body, data)


def register_device_token(profile_id, token, platform="fcm"):
    return {"ok": True}
