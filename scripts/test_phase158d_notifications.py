#!/usr/bin/env python3
"""Test notification types for social actions, verification, reports."""
import sys
import os
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
print("PHASE 158D - NOTIFICATIONS")
print("=" * 60)

try:
    from services.notification_engine import (
        create_notification, list_notifications, unread_count,
        mark_read, mark_all_read, delete_notification,
        list_notifications_tab, get_notification_preferences,
        update_notification_preferences, mute_notification_type
    )
    test("notification_engine full imports", True)
except ImportError as e:
    test("notification_engine full imports", False, str(e))

# Verify new notification types exist in category mapping
try:
    from services.notification_engine import _NOTIF_TYPE_CATEGORIES, _NOTIF_ICONS
    new_types = ["new_follower", "profile_viewed", "verification_rejected", 
                 "verification_needs_info", "report_received"]
    for nt in new_types:
        test(f"notification type '{nt}' in categories", nt in _NOTIF_TYPE_CATEGORIES, f"Missing from _NOTIF_TYPE_CATEGORIES")
        test(f"notification type '{nt}' has icon", nt in _NOTIF_ICONS, f"Missing from _NOTIF_ICONS")
except ImportError as e:
    test("notification type categories", False, str(e))

# Test notification creation
nid = create_notification(
    "test_recipient", "new_follower",
    "New Follower", "Someone followed you",
    actor_profile_id="test_actor",
    action_url="/profile/test_actor"
)
test("create_notification returns ID or None", nid is None or isinstance(nid, str))

test("list_notifications callable", callable(list_notifications))
test("unread_count callable", callable(unread_count))
test("mark_read callable", callable(mark_read))
test("mark_all_read callable", callable(mark_all_read))
test("delete_notification callable", callable(delete_notification))
test("list_notifications_tab callable", callable(list_notifications_tab))
test("get_notification_preferences callable", callable(get_notification_preferences))
test("update_notification_preferences callable", callable(update_notification_preferences))
test("mute_notification_type callable", callable(mute_notification_type))

# Test notification routes
try:
    from api_routes.notification_routes import notification_engine_bp
    test("notification_engine_bp imported", True)
except ImportError as e:
    test("notification_engine_bp imported", False, str(e))

try:
    from api_routes.notification_center_routes import notification_center_bp
    test("notification_center_bp imported", True)
except ImportError as e:
    test("notification_center_bp imported", False, str(e))

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
