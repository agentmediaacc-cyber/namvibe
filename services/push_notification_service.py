import json
import os
from datetime import datetime, timezone

from services.neon_service import fast_query, write_query, get_pool_status
from services.request_cache import request_get, request_set, request_memoize, build_request_key
from engines.cache_engine import cache_key, get_cache, set_cache, delete_cache

VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_CLAIM_EMAIL = os.getenv("VAPID_CLAIM_EMAIL", "push@chain.app")
_WEB_PUSH_AVAILABLE = None

FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "")
APNS_KEY_ID = os.getenv("APNS_KEY_ID", "")
APNS_TEAM_ID = os.getenv("APNS_TEAM_ID", "")
APNS_KEY_PATH = os.getenv("APNS_KEY_PATH", "")
APNS_TOPIC = os.getenv("APNS_TOPIC", "app.chain")


def _vapid_available():
    global _WEB_PUSH_AVAILABLE
    if _WEB_PUSH_AVAILABLE is not None:
        return _WEB_PUSH_AVAILABLE
    _WEB_PUSH_AVAILABLE = bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)
    return _WEB_PUSH_AVAILABLE


def _fcm_available():
    return bool(FCM_SERVER_KEY)


def _apns_available():
    return bool(APNS_KEY_ID and APNS_TEAM_ID and APNS_KEY_PATH)


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
                default=[],
            )
            if existing:
                write_query(
                    "UPDATE chain_push_subscriptions SET p256dh = %s, auth = %s, user_agent = %s, device_type = %s, is_active = true, last_seen_at = now(), updated_at = now() WHERE id = %s",
                    (p256dh, auth_key, user_agent, device_type, existing[0]["id"]),
                )
            else:
                write_query(
                    "INSERT INTO chain_push_subscriptions (profile_id, endpoint, p256dh, auth, user_agent, device_type) VALUES (%s, %s, %s, %s, %s, %s)",
                    (profile_id, endpoint, p256dh, auth_key, user_agent, device_type),
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
                default=[],
            )
        return []
    except Exception:
        return []


def _log_notification(profile_id, notification_type, platform, status, provider_response=""):
    try:
        if _db_available():
            write_query(
                "INSERT INTO chain_notification_logs (profile_id, notification_type, platform, status, provider_response) VALUES (%s, %s, %s, %s, %s)",
                (profile_id, notification_type, platform, status, provider_response),
            )
    except Exception:
        pass


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
        "mentions": True,
        "security_alerts": True,
        "marketing": False,
    }


def update_preferences(profile_id, prefs):
    if not profile_id:
        return {"ok": False, "error": "missing_profile"}
    allowed = {"messages", "calls", "live", "groups", "wallet", "safety", "creator_updates", "mentions", "security_alerts", "marketing"}
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
        "call_invite": "calls",
        "group_call_invite": "groups",
        "live_started": "live",
        "group_invite": "groups",
        "group_join_request": "groups",
        "creator_gift": "creator_updates",
        "wallet_update": "wallet",
        "safety_alert": "safety",
        "security_alert": "security_alerts",
        "mention": "mentions",
        "marketing": "marketing",
    }
    pref_key = event_type_to_pref.get(event_type)
    if pref_key and not prefs.get(pref_key, True):
        return {"ok": False, "error": "disabled_by_user"}
    try:
        try:
            from services.job_queue_service import enqueue_unique_job
            enqueue_unique_job(
                "notification_delivery",
                {"profile_id": profile_id, "event_type": event_type},
                unique_key=f"notification:{profile_id}:{event_type}",
                priority=4,
                queue="notifications",
            )
        except Exception:
            pass
        if _db_available():
            write_query(
                "INSERT INTO chain_push_events (profile_id, event_type, title, body, payload, provider_missing) VALUES (%s, %s, %s, %s, %s::jsonb, %s)",
                (profile_id, event_type, title, body, json.dumps(payload or {}), not (_vapid_available() or _fcm_available())),
            )
        sent = False
        if _vapid_available():
            sent = _send_web_push(profile_id, title, body, payload) or sent
        if _fcm_available():
            sent = _send_fcm_push(profile_id, title, body, payload) or sent
        _log_notification(profile_id, event_type, "server", "sent" if sent else "queued")
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


def _send_fcm_push(profile_id, title, body, payload=None):
    if not _fcm_available():
        return False
    from services.push_token_service import get_active_push_tokens
    tokens = get_active_push_tokens(profile_id)
    android_tokens = [t for t in tokens if t.get("platform") in ("android", "fcm")]
    if not android_tokens:
        return False
    sent = 0
    for token in android_tokens:
        try:
            result = _fcm_send(token["token"], title, body, payload)
            if result.get("ok"):
                sent += 1
        except Exception:
            pass
    return sent > 0


def _fcm_send(token, title, body, payload=None):
    if not _fcm_available():
        return {"ok": False, "error": "provider_missing"}
    try:
        import requests
        message = {
            "to": token,
            "notification": {
                "title": title or "CHAIN",
                "body": body or "",
                "sound": "default",
                "badge": "1",
                "click_action": "FLUTTER_NOTIFICATION_CLICK",
            },
            "data": payload or {},
            "priority": "high",
        }
        headers = {
            "Authorization": f"key={FCM_SERVER_KEY}",
            "Content-Type": "application/json",
        }
        resp = requests.post("https://fcm.googleapis.com/fcm/send", json=message, headers=headers, timeout=10)
        if resp.status_code == 200:
            return {"ok": True}
        return {"ok": False, "error": resp.text}
    except ImportError:
        return {"ok": False, "error": "requests_not_installed"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def send_push_notification(profile_id, title, body, data=None):
    return queue_push_event(profile_id, "message_received", title, body, data)


def send_message_notification(profile_id, sender_name, message_preview, thread_id):
    return queue_push_event(
        profile_id,
        "message_received",
        sender_name or "New message",
        (message_preview or "")[:120],
        {"url": f"/messages/thread/{thread_id}"},
    )


def send_call_notification(profile_id, caller_name, call_type="audio"):
    return queue_push_event(
        profile_id,
        "incoming_call",
        "Incoming Call",
        f"{caller_name or 'Someone'} is calling ({call_type})",
        {"url": "/calls/recent", "call_type": call_type},
    )


def send_missed_call_notification(profile_id, caller_name):
    return queue_push_event(
        profile_id,
        "missed_call",
        "Missed Call",
        f"from {caller_name or 'Someone'}",
        {"url": "/calls/recent"},
    )


def send_security_notification(profile_id, event_type="security_alert", title="Security Alert", body="", payload=None):
    return queue_push_event(
        profile_id,
        "security_alert",
        title,
        body or "A security event was detected on your account.",
        payload or {"url": "/profile/settings"},
    )


def send_group_call_invite(profile_id, invited_by_name, call_id, room_name=""):
    return queue_push_event(
        profile_id,
        "group_call_invite",
        "Group Call Invitation",
        f"{invited_by_name or 'Someone'} invited you to {'a group call' if not room_name else room_name}",
        {"url": f"/calls/group/{call_id}", "call_id": call_id},
    )


def register_device_token(profile_id, token, platform="fcm"):
    from services.push_token_service import register_push_token
    return register_push_token(profile_id, token, platform=platform)
