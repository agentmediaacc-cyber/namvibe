#!/usr/bin/env python3
"""
Test Part 1 – Notification grouping service.
"""
import sys, os, json, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask
from services.notification_grouping_service import (
    get_group_key, group_notifications, format_grouped_title,
    TYPES_THAT_NEVER_GROUP, TYPES_THAT_CAN_GROUP,
)

app = Flask(__name__)
app.config["TESTING"] = True

FAILED = False
def check(label, ok, detail=""):
    global FAILED
    if not ok: FAILED = True
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  | {detail}" if detail else ""))

with app.app_context():
    print("=" * 60)
    print("Part 1 – Notification Grouping Service")
    print("=" * 60)

    # 1. Never-group types return None key
    print("\n--- 1. Never-group types ---")
    for nt in TYPES_THAT_NEVER_GROUP:
        n = {"event_type": nt, "entity_type": "user", "entity_id": "123", "action_url": "/test"}
        key = get_group_key(n)
        check(f"{nt} does not group", key is None)

    # 2. Groupable types return a key
    print("\n--- 2. Groupable types ---")
    for nt in list(TYPES_THAT_CAN_GROUP)[:3]:
        n = {"event_type": nt, "entity_type": "post", "entity_id": "456", "action_url": "/post/456", "created_at": "2026-06-17T12:00:00Z"}
        key = get_group_key(n)
        check(f"{nt} returns group key", key is not None)

    # 3. Same key for same event + entity + date
    print("\n--- 3. Same key for same group ---")
    a = {"event_type": "post_like", "entity_type": "post", "entity_id": "789", "action_url": "/post/789", "created_at": "2026-06-17T10:00:00Z"}
    b = {"event_type": "post_like", "entity_type": "post", "entity_id": "789", "action_url": "/post/789", "created_at": "2026-06-17T11:00:00Z"}
    ka = get_group_key(a)
    kb = get_group_key(b)
    check("Same group key for same post", ka == kb)

    # 4. Different key for different entity
    print("\n--- 4. Different entity === different key ---")
    c = {"event_type": "post_like", "entity_type": "post", "entity_id": "999", "action_url": "/post/999", "created_at": "2026-06-17T10:00:00Z"}
    kc = get_group_key(c)
    check("Different entity_id different key", ka != kc)

    # 5. Single item stays ungrouped
    print("\n--- 5. Singleton remains flat ---")
    items = [{"id": "n1", "event_type": "post_like", "entity_type": "post", "entity_id": "1", "action_url": "/p/1", "created_at": "2026-06-17T10:00:00Z", "actor_profile_id": "p1", "actor_username": "alice", "title": "liked your post", "is_read": False}]
    result = group_notifications(items)
    check("Singleton not wrapped", len(result) == 1 and not result[0].get("grouped"))

    # 6. Two items with same key become grouped
    print("\n--- 6. Two items grouped ---")
    items2 = [
        {"id": "n1", "event_type": "post_like", "entity_type": "post", "entity_id": "1", "action_url": "/p/1", "created_at": "2026-06-17T10:00:00Z", "actor_profile_id": "p1", "actor_username": "alice", "actor_avatar": "/ava/a.jpg", "title": "liked your post", "is_read": False},
        {"id": "n2", "event_type": "post_like", "entity_type": "post", "entity_id": "1", "action_url": "/p/1", "created_at": "2026-06-17T11:00:00Z", "actor_profile_id": "p2", "actor_username": "bob", "actor_avatar": "/ava/b.jpg", "title": "liked your post", "is_read": False},
    ]
    result2 = group_notifications(items2)
    check("Two same -> one grouped item", len(result2) == 1 and result2[0].get("grouped"))
    check("Group count is 2", result2[0].get("group_count") == 2)
    check("Actor count is 2", result2[0].get("actor_count") == 2)
    check("Title mentions both", "alice" in result2[0]["title"] and "bob" in result2[0]["title"])

    # 7. Three items with same key
    print("\n--- 7. Three items grouped ---")
    items3 = items2 + [
        {"id": "n3", "event_type": "post_like", "entity_type": "post", "entity_id": "1", "action_url": "/p/1", "created_at": "2026-06-17T12:00:00Z", "actor_profile_id": "p3", "actor_username": "charlie", "actor_avatar": "/ava/c.jpg", "title": "liked your post", "is_read": False},
    ]
    result3 = group_notifications(items3)
    check("Three items grouped", len(result3) == 1 and result3[0].get("grouped"))
    check("Group count is 3", result3[0].get("group_count") == 3)
    check("Title: Alice, Bob and 1 other", "others" in result3[0].get("title", ""))

    # 8. Mixed groupable + never-group
    print("\n--- 8. Mixed items ---")
    items4 = items2 + [{"id": "n4", "event_type": "friend_request", "entity_type": "user", "entity_id": "456", "created_at": "2026-06-17T10:00:00Z", "actor_profile_id": "p4", "actor_username": "dave", "title": "sent you a friend request", "is_read": False}]
    result4 = group_notifications(items4)
    check("Mixed -> 2 items (1 grouped + 1 flat)", len(result4) == 2)
    has_grouped = any(r.get("grouped") for r in result4)
    has_flat = any(not r.get("grouped") for r in result4)
    check("Has grouped and flat items", has_grouped and has_flat)

    # 9. Format title helpers
    print("\n--- 9. Title formatting ---")
    t1 = format_grouped_title({"event_type": "post_like"}, ["Alice"])
    check("Single title", "Alice" in t1 and "liked" in t1)
    t2 = format_grouped_title({"event_type": "follow"}, ["Alice", "Bob"])
    check("Two actors", "Alice" in t2 and "Bob" in t2)
    t3 = format_grouped_title({"event_type": "post_like"}, ["Alice", "Bob", "Charlie"])
    check("Three+ actors", "others" in t3)

    # Summary
    print("\n" + "=" * 60)
    if FAILED:
        print("RESULT: SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("RESULT: ALL TESTS PASSED")
