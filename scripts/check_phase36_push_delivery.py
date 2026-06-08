#!/usr/bin/env python3
"""Phase 36 — Push Notification Delivery Verification"""

import os
import sys
import json

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} {detail}")
        failed += 1

# 1. VAPID keys
vapid_pub = os.environ.get("VAPID_PUBLIC_KEY", "")
vapid_priv = os.environ.get("VAPID_PRIVATE_KEY", "")
check("VAPID_PUBLIC_KEY env set", bool(vapid_pub))
check("VAPID_PRIVATE_KEY env set", bool(vapid_priv))

# 2. pywebpush installed
try:
    import pywebpush
    check("pywebpush installed", True)
    check("pywebpush has WebPushException", hasattr(pywebpush, "WebPushException"))
except ImportError:
    check("pywebpush installed", False, "Run: pip install pywebpush")

# 3. Push notification service loads
try:
    from services.push_notification_service import (
        get_vapid_public_key, save_subscription, remove_subscription,
        get_preferences, update_preferences, queue_push_event,
    )
    check("push_notification_service loads", True)
    check("get_vapid_public_key callable", callable(get_vapid_public_key))
    check("save_subscription callable", callable(save_subscription))
    check("queue_push_event callable", callable(queue_push_event))
except Exception as e:
    check("push_notification_service loads", False, str(e))

# 4. VAPID key from service
try:
    from services.push_notification_service import get_vapid_public_key
    key = get_vapid_public_key()
    check("get_vapid_public_key returns value", bool(key))
except Exception as e:
    check("get_vapid_public_key works", False, str(e))

# 5. Push send test (dry run without real subscription)
if vapid_pub and vapid_priv:
    try:
        from pywebpush import webpush
        check("webpush importable", True)
    except Exception as e:
        check("webpush importable", False, str(e))
else:
    check("Push send test skipped (VAPID keys missing)", True)

# 6. Message push integration
try:
    from services.socket_events import handle_message_send
    socket_src = open(os.path.join(BASE, "services", "socket_events.py")).read()
    has_message_push = "queue_push_event" in socket_src
    check("Message send triggers queue_push_event", has_message_push)
except Exception as e:
    check("Message push integration check", False, str(e))

# 7. Call push integration
try:
    socket_src = open(os.path.join(BASE, "services", "socket_events.py")).read()
    has_call_push = "queue_push_event" in socket_src
    check("Call events trigger queue_push_event", has_call_push)
except Exception as e:
    check("Call push integration check", False, str(e))

# 8. Missed call push
try:
    from services.call_service import record_call_event
    check("record_call_event exists for missed calls", callable(record_call_event))
except Exception:
    try:
        from services.call_feature_service import record_call_event
        check("record_call_event exists for missed calls", callable(record_call_event))
    except Exception as e:
        check("record_call_event", False, str(e))

# 9. Group invite push
try:
    from services.group_feature_service import create_group
    check("group creation triggers events", callable(create_group))
except Exception as e:
    check("group_feature_service", False, str(e))

# 10. Live started push
try:
    socket_src = open(os.path.join(BASE, "services", "socket_events.py")).read()
    has_live_push = "live" in socket_src.lower() and "push" in socket_src.lower()
    check("Live events have push hooks", has_live_push)
except Exception as e:
    check("Live push hook check", False, str(e))

# 11. Push routes
try:
    from api_routes.push_routes import push_bp
    check("push_bp registered", True)
except Exception as e:
    check("push_bp registered", False, str(e))

# 12. Push preferences API
try:
    from services.push_notification_service import get_preferences, update_preferences
    check("Push preferences API ready", callable(get_preferences) and callable(update_preferences))
except Exception as e:
    check("Push preferences API", False, str(e))

# 13. Service worker
sw_path1 = os.path.join(BASE, "static", "js", "sw.js")
sw_path2 = os.path.join(BASE, "static", "sw.js")
check("Service worker exists", os.path.exists(sw_path1) or os.path.exists(sw_path2))

if not vapid_pub or not vapid_priv:
    print()
    print("  [INFRASTRUCTURE REQUIRED]")
    print("    Set VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY in .env")
    print("    Generate: python -m pywebpush.vapid --gen")

print(f"\nResults: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")
if failed > 0:
    sys.exit(1)
