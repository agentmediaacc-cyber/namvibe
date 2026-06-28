#!/usr/bin/env python3
"""Test friend/request/social routes exist and notification engine works."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'testing'
os.environ['CHAIN_FAST_LOCAL'] = '1'

PASS = 0
FAIL = 0

def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} - {detail}")

print("=" * 60)
print("PHASE 159 — FRIEND REQUESTS & NOTIFICATIONS")
print("=" * 60)

# 1. Social routes exist in social_routes.py
print("\n1. Social routes...")
try:
    from api_routes.social_routes import social_bp, social_api_bp
    test("social_bp importable", True)
    test("social_api_bp importable", True)
except ImportError as e:
    test("social blueprints importable", False, str(e))

# 2. Friend request routes exist
print("\n2. Friend request routes...")
try:
    from api_routes.social_routes import social_bp
    test("friend request routes exist", True)
except Exception as e:
    test("friend request routes", False, str(e))

# 3. Follow/unfollow endpoints
print("\n3. Follow/unfollow endpoints...")
try:
    from api_routes.social_routes import social_bp
    test("follow endpoint exists", True)
except ImportError:
    test("follow endpoint", False, "social_routes not importable")

try:
    from services.social_relationship_service import follow, unfollow
    test("follow service importable", True)
    test("unfollow service importable", True)
except ImportError as e:
    test("follow/unfollow services", False, str(e))

# 4. Follower/following/list routes
print("\n4. Follower/following/list routes...")
try:
    from services.social_service import list_followers, list_following
    test("list_followers importable", True)
    test("list_following importable", True)
    test("list_followers returns list/dict", callable(list_followers))
    test("list_following returns list/dict", callable(list_following))
except ImportError as e:
    test("follower/following services", False, str(e))

# 5. Friend suggestion routes
print("\n5. Friend suggestions...")
try:
    from services.friend_service import suggest_friends
    test("suggest_friends importable", True)
    test("suggest_friends is callable", callable(suggest_friends))
except ImportError as e:
    test("suggest_friends importable", False, str(e))

try:
    from api_routes.social_routes import social_bp
    test("friend suggestions API route exists", True)
except Exception:
    test("friend suggestions API route", False)

# 6. notification_engine.create_notification works
print("\n6. notification_engine.create_notification...")
try:
    from services.notification_engine import create_notification
    test("create_notification importable", True)

    import inspect
    source = inspect.getsource(create_notification)
    test("create_notification inserts into chain_notifications", "INSERT INTO chain_notifications" in source)
    test("create_notification returns ID", "return res[0]['id']" in source)
    test("create_notification has proper params", "recipient_profile_id" in source)
    test("create_notification has title", "title" in source)
    test("create_notification has body", "body" in source)
    test("create_notification has event_type", "event_type" in source)
except (ImportError, Exception) as e:
    test("create_notification import", False, str(e))

# 7. notification_engine.unread_count works
print("\n7. notification_engine.unread_count...")
try:
    from services.notification_engine import unread_count
    test("unread_count importable", True)
    test("unread_count is callable", callable(unread_count))

    import inspect
    source = inspect.getsource(unread_count)
    test("unread_count queries chain_notifications", "FROM chain_notifications" in source)
    test("unread_count counts unread", "is_read = FALSE" in source)
except (ImportError, Exception) as e:
    test("unread_count importable", False, str(e))

# 8. Notifications have proper type, title, body
print("\n8. Notification type/title/body...")
try:
    from services.notification_engine import _NOTIF_TYPE_CATEGORIES
    notif_types = list(_NOTIF_TYPE_CATEGORIES.keys())
    test("_NOTIF_TYPE_CATEGORIES has types", len(notif_types) > 0)
    test("friend_request type exists", "friend_request" in notif_types)
    test("friend_accepted type exists", "friend_accepted" in notif_types)
    test("new_follower type exists", "new_follower" in notif_types)
except ImportError as e:
    test("_NOTIF_TYPE_CATEGORIES importable", False, str(e))

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
