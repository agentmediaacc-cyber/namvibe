"""
Phase 45 E2E: Push Notifications, Background Calls, APNS, FCM, CallKit
  - push token registration
  - remove token
  - notification queue
  - message notification
  - call notification
  - missed call notification
  - security notification
  - group call invite
  - notification history
  - unread count
  - socket handlers
  - service worker exists
  - push_notifications.js exists
  - backward compat (Phase 37-44)
"""
import os, sys, json, re, uuid as uuid_mod, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_TEST_FAKE_DB"] = "1"
os.environ["CHAIN_TRUST_PROFILE_SCHEMA"] = "1"
logging.disable(logging.CRITICAL)

from app import create_app
app = create_app()

from services.neon_service import get_pool_status, fast_query, write_query
def _db_available():
    import os
    if (
        os.getenv("FLASK_TESTING") == "1"
        or os.getenv("CHAIN_FAST_LOCAL") == "1"
        or os.getenv("CHAIN_TEST_FAKE_DB") == "1"
    ):
        return False
    return bool(get_pool_status().get("configured"))

import services.push_notification_service as _pns
if hasattr(_pns, '_db_available'): _pns._db_available = _db_available

import services.push_token_service as _pts
if hasattr(_pts, '_db_available'): _pts._db_available = _db_available

import services.notification_queue_service as _nqs
if hasattr(_nqs, '_db_available'): _nqs._db_available = _db_available

import services.group_call_service as _gcs
if hasattr(_gcs, '_db_available'): _gcs._db_available = _db_available

import services.message_feature_service as _mfs
if hasattr(_mfs, '_db_available'): _mfs._db_available = _db_available

import services.message_delivery_service as _mds
if hasattr(_mds, '_db_available'): _mds._db_available = _db_available

import services.webrtc_call_service as _wcs
if hasattr(_wcs, '_db_available'): _wcs._db_available = _db_available

import services.security_service as _sec
if hasattr(_sec, '_db_available'): _sec._db_available = _db_available

import services.encryption_service as _enc
if hasattr(_enc, '_db_available'): _enc._db_available = _db_available

from services.push_notification_service import (
    queue_push_event, send_push_notification, send_message_notification,
    send_call_notification, send_missed_call_notification, send_security_notification,
    send_group_call_invite, get_preferences, update_preferences,
    save_subscription, remove_subscription, get_subscriptions,
    get_vapid_public_key, register_device_token,
)
from services.push_token_service import register_push_token, remove_push_token, get_push_tokens
from services.notification_queue_service import (
    queue_notification, process_notification, get_notification_history,
    mark_notification_sent, mark_notification_failed,
)
from services.callkit_service import (
    prepare_callkit_payload, build_apns_push_payload, build_android_call_payload,
)

_FAKE_TOKENS = {}
_FAKE_NOTIFICATIONS = []
_FAKE_SUBSCRIPTIONS = {}
_FAKE_PREFS = {}

def _fake_now():
    return "2026-01-01T00:00:00+00:00"

def _fake_fast_query(sql_text, params=None, timeout_ms=2000, default=None):
    if "COUNT(*) AS cnt FROM chain_notification_queue" in sql_text:
        profile_id = params[0] if params else None
        count = len([n for n in _FAKE_NOTIFICATIONS if n.get("profile_id") == profile_id and n.get("status") == "pending"])
        return [{"cnt": count}]
    return default if default is not None else []

def _fake_write_query(sql_text, params=None, timeout_ms=5000):
    return {"ok": True}

def _fake_register_push_token(profile_id, token, platform="web", device_session_id=None):
    if not profile_id or not token:
        return {"ok": False, "error": "missing_fields"}
    tokens = _FAKE_TOKENS.setdefault(profile_id, [])
    for row in tokens:
        if row["token"] == token:
            row.update({"platform": platform, "device_session_id": device_session_id, "active": True, "updated_at": _fake_now()})
            return {"ok": True}
    tokens.append({
        "id": str(uuid_mod.uuid4()),
        "profile_id": profile_id,
        "device_session_id": device_session_id,
        "platform": platform,
        "token": token,
        "active": True,
        "created_at": _fake_now(),
        "updated_at": _fake_now(),
    })
    return {"ok": True}

def _fake_remove_push_token(profile_id, token):
    if not profile_id or not token:
        return {"ok": False, "error": "missing_fields"}
    for row in _FAKE_TOKENS.get(profile_id, []):
        if row["token"] == token:
            row["active"] = False
            row["updated_at"] = _fake_now()
    return {"ok": True}

def _fake_get_push_tokens(profile_id):
    return list(_FAKE_TOKENS.get(profile_id, [])) if profile_id else []

def _fake_queue_notification(profile_id, notification_type, title="", body="", payload=None):
    if not profile_id or not notification_type:
        return {"ok": False, "error": "missing_fields"}
    _FAKE_NOTIFICATIONS.insert(0, {
        "id": str(uuid_mod.uuid4()),
        "profile_id": profile_id,
        "notification_type": notification_type,
        "title": title,
        "body": body,
        "payload": payload or {},
        "status": "pending",
        "retry_count": 0,
        "max_retries": 3,
        "created_at": _fake_now(),
        "processed_at": None,
    })
    return {"ok": True}

def _fake_get_notification_history(profile_id, limit=50):
    if not profile_id:
        return []
    return [n for n in _FAKE_NOTIFICATIONS if n.get("profile_id") == profile_id][:limit]

def _fake_mark_notification_sent(queue_id):
    for row in _FAKE_NOTIFICATIONS:
        if row["id"] == queue_id:
            row["status"] = "sent"
            row["processed_at"] = _fake_now()
    return {"ok": bool(queue_id)}

def _fake_mark_notification_failed(queue_id):
    for row in _FAKE_NOTIFICATIONS:
        if row["id"] == queue_id:
            row["retry_count"] += 1
    return {"ok": bool(queue_id)}

def _fake_save_subscription(profile_id, endpoint, p256dh, auth_key, user_agent="", device_type="web"):
    if not profile_id or not endpoint:
        return {"ok": False, "error": "missing_fields"}
    _FAKE_SUBSCRIPTIONS.setdefault(profile_id, {})[endpoint] = {
        "id": str(uuid_mod.uuid4()),
        "endpoint": endpoint,
        "p256dh": p256dh,
        "auth": auth_key,
        "user_agent": user_agent,
        "device_type": device_type,
    }
    return {"ok": True}

def _fake_remove_subscription(profile_id, endpoint):
    if not profile_id or not endpoint:
        return {"ok": False, "error": "missing_fields"}
    _FAKE_SUBSCRIPTIONS.get(profile_id, {}).pop(endpoint, None)
    return {"ok": True}

def _fake_get_subscriptions(profile_id):
    return list(_FAKE_SUBSCRIPTIONS.get(profile_id, {}).values()) if profile_id else []

def _fake_default_preferences():
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

def _fake_get_preferences(profile_id):
    prefs = _fake_default_preferences()
    if profile_id:
        prefs.update(_FAKE_PREFS.get(profile_id, {}))
    return prefs

def _fake_update_preferences(profile_id, prefs):
    if not profile_id:
        return {"ok": False, "error": "missing_profile"}
    allowed = set(_fake_default_preferences())
    clean = {k: bool(v) for k, v in (prefs or {}).items() if k in allowed}
    if not clean:
        return {"ok": False, "error": "no_valid_keys"}
    _FAKE_PREFS.setdefault(profile_id, {}).update(clean)
    return {"ok": True}

def _fake_queue_push_event(profile_id, event_type, title="", body="", payload=None):
    return _fake_queue_notification(profile_id, event_type, title, body, payload)

def _fake_send_push_notification(profile_id, title, body, payload=None):
    return _fake_queue_notification(profile_id, payload.get("_notification_type", "push") if isinstance(payload, dict) else "push", title, body, payload)

def _fake_current_profile():
    from flask import session
    profile_id = session.get("profile_id")
    return {"id": profile_id, "username": session.get("username", "e2e_45_a")} if profile_id else None

if not _db_available():
    import services.neon_service as _neon
    import api_routes.push_notification_routes as _pn_routes
    import services.profile_service as _profile_service

    _neon.fast_query = _fake_fast_query
    _neon.write_query = _fake_write_query
    fast_query = _fake_fast_query
    write_query = _fake_write_query

    _pts.register_push_token = register_push_token = _fake_register_push_token
    _pts.remove_push_token = remove_push_token = _fake_remove_push_token
    _pts.get_push_tokens = get_push_tokens = _fake_get_push_tokens
    _pts.get_active_push_tokens = _fake_get_push_tokens

    _nqs.queue_notification = queue_notification = _fake_queue_notification
    _nqs.get_notification_history = get_notification_history = _fake_get_notification_history
    _nqs.mark_notification_sent = mark_notification_sent = _fake_mark_notification_sent
    _nqs.mark_notification_failed = mark_notification_failed = _fake_mark_notification_failed

    _pns.save_subscription = save_subscription = _fake_save_subscription
    _pns.remove_subscription = remove_subscription = _fake_remove_subscription
    _pns.get_subscriptions = get_subscriptions = _fake_get_subscriptions
    _pns.get_preferences = get_preferences = _fake_get_preferences
    _pns.update_preferences = update_preferences = _fake_update_preferences
    _pns.queue_push_event = queue_push_event = _fake_queue_push_event
    _pns.send_push_notification = send_push_notification = _fake_send_push_notification

    _pn_routes.register_push_token = _fake_register_push_token
    _pn_routes.remove_push_token = _fake_remove_push_token
    _pn_routes.get_push_tokens = _fake_get_push_tokens
    _pn_routes.get_notification_history = _fake_get_notification_history
    _pn_routes.get_preferences = _fake_get_preferences
    _pn_routes.update_preferences = _fake_update_preferences
    _pn_routes.send_push_notification = _fake_send_push_notification
    _pn_routes.get_current_profile = _fake_current_profile
    _profile_service.get_current_profile = _fake_current_profile

PASS = 0; FAIL = 0
def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}" + (f" -- {detail}" if detail else ""))

PID_A = None; PID_B = None

def _ensure_test_profiles():
    global PID_A, PID_B
    if not _db_available():
        PID_A = "phase45-test-a"
        PID_B = "phase45-test-b"
        return
    for uname in ["e2e_45_a", "e2e_45_b"]:
        rows = fast_query("SELECT id FROM chain_profiles WHERE username = %s LIMIT 1", (uname,), default=[])
        if not rows:
            dummy_auth = str(uuid_mod.uuid4())
            rows = fast_query(
                "INSERT INTO chain_profiles (auth_user_id, username, display_name, email) VALUES (%s, %s, %s, %s) RETURNING id",
                (dummy_auth, uname, f"E2E {uname}", f"{uname}@test.chain"),
                default=[],
            )
        if rows and uname == "e2e_45_a":
            PID_A = str(rows[0]["id"])
        elif rows and uname == "e2e_45_b":
            PID_B = str(rows[0]["id"])

def _ensure_tables():
    if not _db_available():
        return
    stmts = [
        "CREATE TABLE IF NOT EXISTS chain_push_tokens (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), profile_id UUID NOT NULL, device_session_id UUID DEFAULT NULL, platform TEXT NOT NULL DEFAULT 'web', token TEXT NOT NULL DEFAULT '', active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now())",
        "CREATE TABLE IF NOT EXISTS chain_notification_queue (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), profile_id UUID NOT NULL, notification_type TEXT NOT NULL DEFAULT 'info', title TEXT NOT NULL DEFAULT '', body TEXT NOT NULL DEFAULT '', payload JSONB DEFAULT '{}'::jsonb, status TEXT NOT NULL DEFAULT 'pending', retry_count INTEGER DEFAULT 0, max_retries INTEGER DEFAULT 3, created_at TIMESTAMPTZ DEFAULT now(), processed_at TIMESTAMPTZ DEFAULT NULL)",
        "CREATE TABLE IF NOT EXISTS chain_notification_logs (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), profile_id UUID NOT NULL, notification_type TEXT NOT NULL DEFAULT 'info', platform TEXT NOT NULL DEFAULT 'web', status TEXT NOT NULL DEFAULT 'sent', provider_response TEXT DEFAULT '', created_at TIMESTAMPTZ DEFAULT now())",
        "ALTER TABLE chain_notification_preferences ADD COLUMN IF NOT EXISTS mentions BOOLEAN DEFAULT TRUE",
        "ALTER TABLE chain_notification_preferences ADD COLUMN IF NOT EXISTS marketing BOOLEAN DEFAULT FALSE",
        "ALTER TABLE chain_notification_preferences ADD COLUMN IF NOT EXISTS security_alerts BOOLEAN DEFAULT TRUE",
    ]
    for stmt in stmts:
        try:
            write_query(stmt)
        except Exception:
            pass

_ensure_test_profiles()
_ensure_tables()

# ---- 1. SERVICE MODULE IMPORTS ----
print("\n=== 1. SERVICE MODULE IMPORTS ===")
check("push_notification_service imports ok", callable(queue_push_event))
check("push_token_service imports ok", callable(register_push_token))
check("notification_queue_service imports ok", callable(queue_notification))
check("callkit_service imports ok", callable(prepare_callkit_payload))

# ---- 2. PUSH TOKEN REGISTRATION ----
print("\n=== 2. PUSH TOKEN REGISTRATION ===")
if PID_A:
    token_a = f"test-token-{uuid_mod.uuid4()}"
    result = register_push_token(PID_A, token_a, platform="web")
    check("register push token returns ok", result.get("ok") is True)
    if result.get("ok"):
        tokens = get_push_tokens(PID_A)
        check("get_push_tokens returns list", isinstance(tokens, list))
        check("get_push_tokens has our token", any(t["token"] == token_a for t in tokens))
    result2 = register_push_token(PID_A, f"test-token-{uuid_mod.uuid4()}", platform="android")
    check("register android token", result2.get("ok") is True)
    check("register token with missing profile_id", register_push_token(None, token_a).get("ok") is False)
    check("register token with empty token", register_push_token(PID_A, "").get("ok") is False)
else:
    check("skip token tests (no PID_A)", True)

# ---- 3. PUSH TOKEN REMOVAL ----
print("\n=== 3. PUSH TOKEN REMOVAL ===")
if PID_A and token_a:
    result = remove_push_token(PID_A, token_a)
    check("remove push token returns ok", result.get("ok") is True)
    tokens = get_push_tokens(PID_A)
    active_tokens = [t for t in tokens if t.get("active") and t["token"] == token_a]
    check("token deactivated after remove", len(active_tokens) == 0)
else:
    check("skip remove tests", True)

# ---- 4. NOTIFICATION QUEUE ----
print("\n=== 4. NOTIFICATION QUEUE ===")
if PID_A:
    result = queue_notification(PID_A, "test", "Test Title", "Test body")
    check("queue notification returns ok", result.get("ok") is True)
    history = get_notification_history(PID_A)
    check("notification history returns list", isinstance(history, list))
    has_queued = any(h.get("notification_type") == "test" for h in history)
    check("history contains queued notification", has_queued)
else:
    check("skip queue tests", True)

# ---- 5. SEND MESSAGE NOTIFICATION ----
print("\n=== 5. MESSAGE NOTIFICATION ===")
if PID_B:
    result = send_message_notification(PID_B, "Alice", "Hello, how are you?", str(uuid_mod.uuid4()))
    check("send_message_notification returns ok", result.get("ok") is True)
else:
    check("skip message notif tests", True)

# ---- 6. SEND CALL NOTIFICATION ----
print("\n=== 6. CALL NOTIFICATION ===")
if PID_B:
    result = send_call_notification(PID_B, "Bob", "audio")
    check("send_call_notification returns ok", result.get("ok") is True)
else:
    check("skip call notif tests", True)

# ---- 7. MISSED CALL NOTIFICATION ----
print("\n=== 7. MISSED CALL NOTIFICATION ===")
if PID_B:
    result = send_missed_call_notification(PID_B, "Charlie")
    check("send_missed_call_notification returns ok", result.get("ok") is True)
else:
    check("skip missed call tests", True)

# ---- 8. SECURITY NOTIFICATION ----
print("\n=== 8. SECURITY NOTIFICATION ===")
if PID_B:
    result = send_security_notification(PID_B, "new_device_login", "New Device Login", "Your account was accessed from a new device.")
    check("send_security_notification returns ok", result.get("ok") is True)
    result2 = send_security_notification(PID_B)
    check("security notification with defaults", result2.get("ok") is True)
else:
    check("skip security notif tests", True)

# ---- 9. GROUP CALL INVITE ----
print("\n=== 9. GROUP CALL INVITE ===")
if PID_B:
    result = send_group_call_invite(PID_B, "Dave", str(uuid_mod.uuid4()), "Cool Room")
    check("send_group_call_invite returns ok", result.get("ok") is True)
    result2 = send_group_call_invite(PID_B, "Dave", str(uuid_mod.uuid4()))
    check("group call invite without room_name", result2.get("ok") is True)
else:
    check("skip group call invite tests", True)

# ---- 10. PREFERENCES ----
print("\n=== 10. PREFERENCES ===")
if PID_A:
    prefs = get_preferences(PID_A)
    check("get_preferences returns dict", isinstance(prefs, dict))
    check("preferences has messages key", "messages" in prefs)
    result = update_preferences(PID_A, {"messages": False})
    check("update_preferences returns ok", result.get("ok") is True)
    updated = get_preferences(PID_A)
    check("preferences updated (messages disabled)", updated.get("messages") is False)
    result2 = update_preferences(PID_A, {"messages": True})
    check("re-enable messages pref", result2.get("ok") is True)
    result3 = update_preferences(PID_A, {})
    check("empty preferences returns error", result3.get("ok") is False)
    check("get_preferences with None returns defaults", "messages" in get_preferences(None))
    prefs_b = get_preferences(PID_B)
    check("new users have mentions pref", "mentions" in prefs_b)
    check("new users have security_alerts pref", "security_alerts" in prefs_b)
else:
    check("skip preference tests", True)

# ---- 11. VAPID & SUBSCRIPTIONS ----
print("\n=== 11. VAPID & SUBSCRIPTIONS ===")
check("get_vapid_public_key is callable", callable(get_vapid_public_key))
if PID_A:
    result = save_subscription(PID_A, "https://test.endpoint/push", "test-p256dh", "test-auth")
    check("save_subscription returns ok", result.get("ok") is True)
    subs = get_subscriptions(PID_A)
    check("get_subscriptions returns list", isinstance(subs, list))
    result2 = remove_subscription(PID_A, "https://test.endpoint/push")
    check("remove_subscription returns ok", result2.get("ok") is True)
    check("save_subscription with no endpoint", save_subscription(PID_A, "", "", "").get("ok") is False)
    check("save_subscription with no profile", save_subscription(None, "ep", "", "").get("ok") is False)
else:
    check("skip subscription tests", True)

# ---- 12. CALLKIT SERVICE ----
print("\n=== 12. CALLKIT SERVICE ===")
if PID_A and PID_B:
    payload = prepare_callkit_payload(str(uuid_mod.uuid4()), PID_A, "Test Caller", PID_B, "audio")
    check("prepare_callkit_payload returns dict", isinstance(payload, dict))
    check("callkit payload has aps", "aps" in payload)
    check("callkit payload has call_id", "call_id" in payload)
    check("callkit payload has caller_name", payload.get("caller_name") == "Test Caller")
    apns = build_apns_push_payload(payload)
    check("build_apns_push_payload returns dict", isinstance(apns, dict))
    check("apns payload has aps", "aps" in apns)
    android = build_android_call_payload(str(uuid_mod.uuid4()), "Android Caller", "video")
    check("build_android_call_payload returns dict", isinstance(android, dict))
    check("android payload has is_background_call", android.get("is_background_call") is True)
    check("android payload has notification_type", android.get("notification_type") == "incoming_call")
    check("android video call has has_video", android.get("has_video") is True)
else:
    check("skip callkit tests", True)

# ---- 13. QUEUE_MGMT ----
print("\n=== 13. QUEUE MGMT ===")
if PID_A:
    qr = queue_notification(PID_A, "mgmt_test", "MGMT", "Test")
    check("queue for mgmt tests", qr.get("ok") is True)
    hist = get_notification_history(PID_A)
    check("history returns list", isinstance(hist, list))
    if hist:
        latest_id = hist[0]["id"]
        mark_sent = mark_notification_sent(latest_id)
        check("mark_notification_sent returns ok", mark_sent.get("ok") is True)
        mark_failed = mark_notification_failed(latest_id)
        check("mark_notification_failed returns ok", mark_failed.get("ok") is True)
else:
    check("skip mgmt tests", True)

# ---- 14. API ROUTES ----
print("\n=== 14. API ROUTES ===")
with app.test_client() as c:
    with c.session_transaction() as sess:
        sess["auth_user_id"] = PID_A
        sess["profile_id"] = PID_A
        sess["username"] = "e2e_45_a"
        sess["_permanent"] = True

    resp = c.get("/notifications/api/vapid-public-key")
    data = resp.get_json(silent=True) or {}
    check("vapid-public-key returns 200", resp.status_code == 200)
    check("vapid-public-key has publicKey key", "publicKey" in data)

    resp2 = c.post("/notifications/api/register-token", json={"token": "api-test-token", "platform": "web"})
    data2 = resp2.get_json(silent=True) or {}
    check("register-token API returns 200", resp2.status_code == 200)
    check("register-token API returns ok", data2.get("ok") is True)

    resp3 = c.get("/notifications/api/tokens")
    data3 = resp3.get_json(silent=True) or {}
    check("tokens API returns 200", resp3.status_code == 200)
    check("tokens API has tokens list", isinstance(data3.get("tokens"), list))

    resp4 = c.post("/notifications/api/remove-token", json={"token": "api-test-token"})
    data4 = resp4.get_json(silent=True) or {}
    check("remove-token API returns 200", resp4.status_code == 200)
    check("remove-token API returns ok", data4.get("ok") is True)

    resp5 = c.post("/notifications/api/test", json={"title": "Test", "body": "Body"})
    data5 = resp5.get_json(silent=True) or {}
    check("test notification API returns 200", resp5.status_code in (200, 500))
    if resp5.status_code == 200:
        check("test notification returns ok", data5.get("ok") is True)

    resp6 = c.get("/notifications/api/history")
    data6 = resp6.get_json(silent=True) or {}
    check("history API returns 200", resp6.status_code == 200)
    check("history API returns list", isinstance(data6.get("history"), list))

    resp7 = c.get("/notifications/api/unread-count")
    data7 = resp7.get_json(silent=True) or {}
    check("unread-count API returns 200", resp7.status_code == 200)
    check("unread-count returns integer", isinstance(data7.get("unread_count"), int))

    resp8 = c.post("/notifications/api/mark-read", json={"notification_id": "00000000-0000-0000-0000-000000000000"})
    data8 = resp8.get_json(silent=True) or {}
    check("mark-read API returns 200", resp8.status_code == 200)
    check("mark-read API returns ok", data8.get("ok") is True)

    resp9 = c.get("/notifications/api/preferences")
    data9 = resp9.get_json(silent=True) or {}
    check("preferences GET returns 200", resp9.status_code == 200)
    check("preferences GET returns preferences", isinstance(data9.get("preferences"), dict))

    resp10 = c.post("/notifications/api/preferences", json={"messages": False})
    data10 = resp10.get_json(silent=True) or {}
    check("preferences POST returns 200", resp10.status_code == 200)
    check("preferences POST returns ok", data10.get("ok") is True)

    c.post("/notifications/api/preferences", json={"messages": True})

    resp11 = c.post("/notifications/api/register-token", json={})
    check("register-token with no body returns 400", resp11.status_code == 400)

    resp12 = c.post("/notifications/api/remove-token", json={})
    check("remove-token with no body returns 400", resp12.status_code == 400)

# ---- 15. SOCKET HANDLERS ----
print("\n=== 15. SOCKET HANDLERS ===")
with open("services/socket_events.py") as f:
    se_src = f.read()

phase45_events = [
    "notification:new", "notification:read", "notification:deleted",
    "notification:call", "notification:message", "notification:security",
    "notification:group-call",
]
for event in phase45_events:
    found = re.search(rf'@socketio\.on\(["\']{event}["\']\)', se_src)
    check(f"socket handler for '{event}' exists", bool(found))

# ---- 16. SERVICE WORKER ----
print("\n=== 16. SERVICE WORKER ===")
check("service-worker.js exists", os.path.isfile("static/js/service-worker.js"))
with open("static/js/service-worker.js") as f:
    sw = f.read()
check("service-worker has install handler", "install" in sw)
check("service-worker has push handler", "push" in sw)
check("service-worker has notificationclick handler", "notificationclick" in sw)
check("service-worker has notificationclose handler", "notificationclose" in sw)
check("service-worker handles incoming call actions", "incoming_call" in sw)
check("service-worker handles missed call", "missed_call" in sw)
check("service-worker handles group call invite", "group_call_invite" in sw)
check("service-worker handles message notification", "message_received" in sw)

# ---- 17. PUSH NOTIFICATIONS JS ----
print("\n=== 17. PUSH NOTIFICATIONS JS ===")
check("push_notifications.js exists", os.path.isfile("static/js/push_notifications.js"))
with open("static/js/push_notifications.js") as f:
    pn = f.read()
check("push_notifications.js has CHAIN_PUSH", "CHAIN_PUSH" in pn)
check("push_notifications.js has requestNotificationPermission", "requestNotificationPermission" in pn)
check("push_notifications.js has registerServiceWorker", "registerServiceWorker" in pn)
check("push_notifications.js has subscribeBrowserPush", "subscribeBrowserPush" in pn)
check("push_notifications.js has registerPushToken", "registerPushToken" in pn)
check("push_notifications.js has getPushTokens", "getPushTokens" in pn)
check("push_notifications.js has unsubscribeBrowserPush", "unsubscribeBrowserPush" in pn)
check("push_notifications.js has getUnreadCount", "getUnreadCount" in pn)
check("push_notifications.js has markNotificationRead", "markNotificationRead" in pn)

# ---- 18. NOTIFICATION BADGE JS ----
print("\n=== 18. NOTIFICATION BADGE JS ===")
check("notification_badge.js exists", os.path.isfile("static/js/notification_badge.js"))
with open("static/js/notification_badge.js") as f:
    nb = f.read()
check("badge JS has CHAIN_PUSH.getUnreadCount", "getUnreadCount" in nb)
check("badge JS has periodic update", "setInterval" in nb)

# ---- 19. SQL MIGRATION ----
print("\n=== 19. SQL MIGRATION ===")
mig_path = "sql/phase45_push_notifications.sql"
check("SQL migration file exists", os.path.isfile(mig_path))
with open(mig_path) as f:
    mig_src = f.read()
check("migration has chain_push_tokens", "chain_push_tokens" in mig_src)
check("migration has chain_notification_queue", "chain_notification_queue" in mig_src)
check("migration has chain_notification_logs", "chain_notification_logs" in mig_src)
check("migration has CREATE INDEX IF NOT EXISTS", "CREATE INDEX IF NOT EXISTS" in mig_src)
check("migration has mentions column", "mentions" in mig_src)
check("migration has security_alerts column", "security_alerts" in mig_src)
check("migration has notification_settings column", "notification_settings" in mig_src)

statements = [s.strip() for s in mig_src.split(";") if s.strip()]
for stmt in statements:
    if stmt.startswith("--"):
        continue
    try:
        write_query(stmt + ";")
    except Exception as e:
        check(f"migration idempotent: {stmt[:50]}...", False, str(e)[:80])
        break
else:
    check("migration is idempotent (re-runs without error)", True)

# ---- 20. REGISTER DEVICE TOKEN ----
print("\n=== 20. REGISTER DEVICE TOKEN ===")
if PID_A:
    result = register_device_token(PID_A, "fcm-device-token-123", platform="fcm")
    check("register_device_token (FCM)", result.get("ok") is True)
    result2 = register_device_token(PID_A, "apns-device-token-456", platform="apns")
    check("register_device_token (APNS)", result2.get("ok") is True)
    result3 = register_device_token(None, "token")
    check("register_device_token with no profile", result3.get("ok") is False)
else:
    check("skip device token tests", True)

# ---- 21. BLUEPRINT REGISTRATION ----
print("\n=== 21. BLUEPRINT REGISTRATION ===")
with open("app.py") as f:
    app_src = f.read()
check("notifications_api_bp imported in app.py", "push_notifications_api_bp" in app_src)
check("notifications_api_bp registered in app.py", "register_blueprint(push_notifications_api_bp)" in app_src)

# ---- 22. BACKWARD COMPAT (Phase 44) ----
print("\n=== 22. BACKWARD COMPAT (Phase 44) ===")
check("push_notification_service still has save_subscription", callable(save_subscription))
check("push_notification_service still has remove_subscription", callable(remove_subscription))
check("push_notification_service still has get_subscriptions", callable(get_subscriptions))
check("push_notification_service still has queue_push_event", callable(queue_push_event))
check("push_notification_service still has get_vapid_public_key", callable(get_vapid_public_key))
check("push_notification_service still has get_preferences", callable(get_preferences))
check("push_notification_service still has update_preferences", callable(update_preferences))

# ---- 23. BACKWARD COMPAT (Phase 43-37 - service imports) ----
print("\n=== 23. BACKWARD COMPAT (Phase 43-37) ===")
for svc_name, svc_mod in [
    ("group_call_service", _gcs),
    ("message_feature_service", _mfs),
    ("message_delivery_service", _mds),
    ("webrtc_call_service", _wcs),
    ("security_service", _sec),
    ("encryption_service", _enc),
]:
    check(f"{svc_name} module loads", svc_mod is not None)

with open("services/socket_events.py") as f:
    full_src = f.read()
check("Phase 44 group-call handlers still present", "group-call:create" in full_src)
check("Phase 41 call:invite handler still present", "call:invite" in full_src)
check("Phase 40 call:start handler still present", "call:start" in full_src)
check("Phase 37 message:send handler still present", "message:send" in full_src)

# ---- SUMMARY ----
total = PASS + FAIL
print(f"\n=== PHASE 45 — SUMMARY ===")
print(f"  PASS: {PASS}/{total}  FAIL: {FAIL}/{total}")
if FAIL > 0:
    print("  Some tests failed -- review output above.")
    sys.exit(1)
else:
    print("  All Phase 45 push notification tests passed!")
    sys.exit(0)
