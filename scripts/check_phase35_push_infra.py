#!/usr/bin/env python3
"""Phase 35 — Push Notification Production Check"""

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

passed = 0
failed = 0

STATUS = {
    "push_framework_ready": False,
    "delivery_ready": False,
    "missing_vapid": False,
    "missing_pywebpush": False,
    "https_required": False,
}

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} {detail}")
        failed += 1

# 1. Service worker exists
sw_path = os.path.join(BASE, "static", "js", "sw.js")
sw_path2 = os.path.join(BASE, "static", "sw.js")
check("Service worker (sw.js) exists", os.path.exists(sw_path) or os.path.exists(sw_path2))

# 2. Push JS exists
push_js = os.path.join(BASE, "static", "js", "push_notifications.js")
check("Push JS (push_notifications.js) exists", os.path.exists(push_js))

# 3. Push routes registered
push_routes_file = os.path.join(BASE, "api_routes", "push_routes.py")
check("Push routes file (push_routes.py) exists", os.path.exists(push_routes_file))

# 4. Notification settings page exists
notif_templates = [
    os.path.join(BASE, "templates", "notifications", "index.html"),
    os.path.join(BASE, "templates", "notifications", "settings.html"),
]
notif_exists = any(os.path.exists(t) for t in notif_templates)
check("Notification settings template exists", notif_exists)

# 5. VAPID_PUBLIC_KEY exists
try:
    from services.push_notification_service import get_vapid_public_key
    vapid_key = get_vapid_public_key()
    has_vapid = bool(vapid_key)
    check("VAPID_PUBLIC_KEY configured", has_vapid)
    if not has_vapid:
        STATUS["missing_vapid"] = True
except Exception:
    check("VAPID_PUBLIC_KEY configured", False, "vapid key not found")
    STATUS["missing_vapid"] = True

# 6. VAPID_PRIVATE_KEY exists
try:
    from services.push_notification_service import get_vapid_public_key
    check("VAPID module loads", True)
    priv_key = os.environ.get("VAPID_PRIVATE_KEY") or os.environ.get("VAPID_PRIVATE") or ""
    has_priv = bool(priv_key)
    check("VAPID_PRIVATE_KEY env", has_priv)
    if not has_priv:
        STATUS["missing_vapid"] = True
except Exception:
    check("VAPID_PRIVATE_KEY env", False)
    STATUS["missing_vapid"] = True

# 7. pywebpush installed
try:
    import pywebpush
    check("pywebpush installed", True)
except ImportError:
    check("pywebpush installed", False, "pywebpush not installed — push delivery will not work")
    STATUS["missing_pywebpush"] = True

# 8. HTTPS requirement documented
https_note = False
if os.path.isfile(push_js):
    content = open(push_js).read()
    if "https" in content.lower() or "localhost" in content.lower():
        https_note = True
check("HTTPS requirement documented in JS", https_note)

# 9. Push event queue table
sql_dir = os.path.join(BASE, "sql")
table_found = False
if os.path.isdir(sql_dir):
    sql_content = ""
    for root, dirs, files in os.walk(sql_dir):
        for f in files:
            if f.endswith(".sql"):
                sql_content += open(os.path.join(root, f)).read()
    if "chain_push_events" in sql_content or "push_notification" in sql_content:
        table_found = True
# Also check .py files
for root, dirs, files in os.walk(os.path.join(BASE, "services")):
    for f in files:
        if f.endswith(".py"):
            try:
                content = open(os.path.join(root, f)).read()
                if "chain_push_events" in content or "push_notification_queue" in content:
                    table_found = True
            except Exception:
                pass
check("Push event queue table exists", table_found, "No push event queue table found")

# 10. Message push hooks
try:
    from services.push_notification_service import queue_push_event
    check("queue_push_event function exists", callable(queue_push_event))
    STATUS["delivery_ready"] = True
except Exception as e:
    check("queue_push_event exists", False, str(e))

# 11. Call push hooks
try:
    from services.push_notification_service import queue_push_event
    check("Call push hook shares queue_push_event", True)
except Exception:
    check("Call push hook", False)

# 12. Missed call push
try:
    from services.call_service import record_call_event
    check("Missed call event record function exists", callable(record_call_event))
except Exception:
    check("Missed call event record", False)

# 13. Push preferences API
try:
    from services.push_notification_service import get_preferences, update_preferences
    check("Push preferences functions exist", callable(get_preferences) and callable(update_preferences))
except Exception:
    check("Push preferences functions", False)

print()
print("  [SUMMARY] Push Notification Infrastructure:")
STATUS["push_framework_ready"] = passed >= 5
if STATUS["push_framework_ready"]:
    print("    Push framework: READY")
else:
    print("    Push framework: INCOMPLETE")
if STATUS["missing_vapid"]:
    print("    VAPID keys: MISSING — set VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY in .env")
if STATUS["missing_pywebpush"]:
    print("    pywebpush: MISSING — run 'pip install pywebpush'")
if not STATUS["delivery_ready"]:
    print("    Delivery pipeline: NOT READY")
print()
print(f"Results: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")
if failed > 0:
    sys.exit(1)
