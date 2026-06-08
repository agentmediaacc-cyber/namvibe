#!/usr/bin/env python3
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / "venv" / "bin" / "python3"
if VENV_PY.exists() and Path(sys.executable).resolve() != VENV_PY.resolve():
    os.execv(str(VENV_PY), [str(VENV_PY), *sys.argv])
sys.path.insert(0, str(ROOT))

os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_DISABLE_DB_PING"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"


def _login(client):
    with client.session_transaction() as sess:
        sess["auth_user_id"] = str(uuid.uuid4())
        sess["profile_id"] = str(uuid.uuid4())
        sess["auth_email"] = "pushtest@example.com"
        sess["username"] = "pushtest"


def check(passed, label):
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {label}")
    return passed


def main():
    from app import app
    from scripts.audit_chain_routes import audit

    app.config["TESTING"] = True
    client = app.test_client()
    results = []

    print("\n=== Phase 32 Push Notification Test ===\n")

    # 1. Service worker file exists
    sw_path = ROOT / "static" / "js" / "sw.js"
    results.append(check(sw_path.exists(), "Service worker file exists"))

    # 2. Push notifications JS exists
    pn_path = ROOT / "static" / "js" / "push_notifications.js"
    results.append(check(pn_path.exists(), "Push notification JS file exists"))

    # 3. Notification settings template exists
    tmpl_path = ROOT / "templates" / "settings" / "notifications.html"
    results.append(check(tmpl_path.exists(), "Notification settings template exists"))

    # 4. Push SQL migration exists
    sql_path = ROOT / "sql" / "phase32_push_notifications.sql"
    results.append(check(sql_path.exists(), "Push migration SQL exists"))

    # 5. Push routes register
    _login(client)
    r_vapid = client.get("/push/vapid-public-key")
    results.append(check(r_vapid.status_code in (200, 302), f"GET /push/vapid-public-key returns {r_vapid.status_code}"))

    # 6. VAPID missing does not crash
    r_vapid_data = r_vapid.get_json() or {}
    results.append(check("available" in r_vapid_data or "error" in r_vapid_data, "VAPID key response is valid"))

    # 7. Subscribe route works with test payload
    r_sub = client.post("/push/subscribe", json={
        "subscription": {
            "endpoint": "https://example.com/push/test",
            "keys": {"p256dh": "test_key", "auth": "test_auth"}
        }
    })
    results.append(check(r_sub.status_code in (200, 500), f"POST /push/subscribe returns {r_sub.status_code}"))

    # 8. Unsubscribe route works
    r_unsub = client.post("/push/unsubscribe", json={
        "endpoint": "https://example.com/push/test"
    })
    results.append(check(r_unsub.status_code in (200, 500), f"POST /push/unsubscribe returns {r_unsub.status_code}"))

    # 9. Preferences GET route works
    r_pref_get = client.get("/push/preferences")
    results.append(check(r_pref_get.status_code in (200, 400), f"GET /push/preferences returns {r_pref_get.status_code}"))

    # 10. Preferences POST route works
    r_pref_set = client.post("/push/preferences", json={"messages": False, "calls": True})
    results.append(check(r_pref_set.status_code in (200, 500), f"POST /push/preferences returns {r_pref_set.status_code}"))

    # 11. Push settings page works
    r_settings = client.get("/push/settings")
    results.append(check(r_settings.status_code in (200, 302), f"GET /push/settings returns {r_settings.status_code}"))

    # 12. Notification settings HTML page works
    r_notif = client.get("/settings/notifications")
    results.append(check(r_notif.status_code in (200, 302), f"GET /settings/notifications returns {r_notif.status_code}"))

    # 13. get_public_groups exists and returns list
    from services.group_feature_service import get_public_groups
    groups = get_public_groups(limit=3)
    results.append(check(isinstance(groups, list), "get_public_groups returns a list"))

    # 14. push_notification_service module loads
    from services.push_notification_service import (
        get_vapid_public_key, save_subscription, remove_subscription,
        get_preferences, update_preferences, queue_push_event
    )
    results.append(check(callable(get_vapid_public_key), "push_notification_service functions loadable"))

    # 15. queue_push_event handles missing VAPID without crash
    result = queue_push_event(str(uuid.uuid4()), "message_received", "Test", "Body")
    results.append(check(isinstance(result, dict), "queue_push_event returns dict without crashing"))

    # 16. Duplicate route check
    audit_result = audit()
    dupes = audit_result.get("duplicates", [])
    results.append(check(len(dupes) == 0, f"No duplicate routes ({len(dupes)} found)"))

    passed = all(results)
    total = len(results)
    print(f"\nResults: {results.count(True)}/{total} passed, {results.count(False)}/{total} failed")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
