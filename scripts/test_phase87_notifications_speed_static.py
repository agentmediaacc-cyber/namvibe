"""Phase 87 — Notifications Speed Static Test."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0

def check(name, ok):
    global PASS, FAIL
    if ok:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name}")
        FAIL += 1

def run():
    global PASS, FAIL
    print("Phase 87: Notifications Speed Static")

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Check notification modules
    try:
        from services.notification_engine import (
            create_notification, list_notifications, unread_count,
            mark_read, mark_all_read, invalidate_unread_count,
        )
        check("notification_engine functions import", True)
    except ImportError as e:
        check(f"notification_engine import ({e})", False)

    # Check notification routes
    try:
        __import__("api_routes.notification_routes")
        check("notification_routes module loads", True)
    except Exception as e:
        check(f"notification_routes ({e})", False)

    # Check JS files
    js_files = [
        "static/js/namvibe_global_badges.js",
        "static/js/namvibe_notifications.js",
        "static/js/notifications_center.js",
        "static/js/notification_badge.js",
    ]
    for jf in js_files:
        path = os.path.join(root, jf)
        check(f"{jf} exists", os.path.isfile(path))

    # Check notification template
    notif_dir = os.path.join(root, "templates", "notifications")
    for t in ["index.html", "list.html"]:
        path = os.path.join(notif_dir, t) if os.path.isdir(notif_dir) else os.path.join(root, "templates", t)
        if os.path.isfile(path):
            check(f"notifications/{t} exists", True)

    print(f"\nPhase 87 Notifications Speed: {PASS} passed, {FAIL} failed")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
