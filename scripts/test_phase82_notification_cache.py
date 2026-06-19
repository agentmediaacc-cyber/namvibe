"""Phase 82: notification unread count uses shared Redis cache key."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0


def check(name, condition):
    global PASS, FAIL
    if condition:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name}")
        FAIL += 1


def run():
    print("Phase 82: Notification Cache")
    engine = open("services/notification_engine.py").read()
    routes = open("api_routes/notification_routes.py").read()
    homepage = open("services/homepage_service.py").read()

    check("uses required notif unread cache key", "notif:unread:{profile_id}" in engine)
    check("has invalidation helper", "def invalidate_unread_count" in engine)
    check("create invalidates unread count", "invalidate_unread_count(recipient_profile_id)" in engine)
    check("mark read invalidates unread count", "invalidate_unread_count(profile_id)" in engine)
    check("unread count TTL 60", "cache_set(cache_key, count, ttl=60)" in engine)
    check("route calls unread_count service", "count = unread_count(profile_id)" in routes)
    check("homepage uses same cache key", 'f"notif:unread:{profile_id}"' in homepage)

    print(f"\nPhase 82 Notification Cache: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
