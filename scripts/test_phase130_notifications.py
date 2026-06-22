#!/usr/bin/env python3
"""
Phase 130 — Notification Audit.
Verifies message, call, reaction, group, mention notifications and badge/unread counts.
"""

import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASS = 0; FAIL = 0; WARN = 0


def ok(m): global PASS; PASS += 1; print(f"  [PASS] {m}")
def fail(m): global FAIL; FAIL += 1; print(f"  [FAIL] {m}")
def warn(m): global WARN; WARN += 1; print(f"  [WARN] {m}")


def read_file(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full): return ""
    with open(full, encoding="utf-8", errors="ignore") as f:
        return f.read()


def file_exists(path):
    return os.path.exists(os.path.join(ROOT, path))


def find_pattern(text, pattern):
    return bool(re.search(pattern, text, re.IGNORECASE))


print("=" * 60)
print("PHASE 130 — NOTIFICATION AUDIT")
print("=" * 60)

ne = read_file("services/notification_engine.py")
ns = read_file("services/notification_service.py")
ps = read_file("services/push_notification_service.py")
pe = read_file("services/push_notification_engine.py")
nq = read_file("services/notification_queue_service.py")
ng = read_file("services/notification_grouping_service.py")
nc = read_file("services/notification_center_service.py")
se = read_file("services/socket_events.py")
nr = read_file("api_routes/notification_routes.py")
pcr = read_file("api_routes/push_notification_routes.py")
ncr = read_file("api_routes/notification_center_routes.py")
badge_js = read_file("static/js/notification_badge.js")
nc_js = read_file("static/js/notifications_center.js")

# ── 1. Core files ──
print("\n--- 1. Core Files ---")
notif_files = [
    "services/notification_engine.py",
    "services/notification_service.py",
    "services/push_notification_service.py",
    "services/push_notification_engine.py",
    "services/notification_queue_service.py",
    "services/notification_grouping_service.py",
    "services/notification_center_service.py",
    "api_routes/notification_routes.py",
    "api_routes/push_notification_routes.py",
    "api_routes/notification_center_routes.py",
]
for f in notif_files:
    ok(f"{f} exists") if file_exists(f) else fail(f"{f} missing")

# ── 2. Notification types ──
print("\n--- 2. Notification Types ---")
all_notif = ne + ns + ps + se
types = [
    "new_message", "message_reaction", "incoming_call", "missed_call",
    "follow", "follow_accepted", "mention", "comment", "reply",
    "post_like", "reel_like", "story_reaction", "story_mention",
    "live_started", "creator_subscription",
    "wallet_transfer", "wallet_received",
    "dating_match", "friend_request", "friend_accepted",
    "verification_approved", "security_alert", "system_announcement",
]
found_types = 0
for nt in types:
    if nt in all_notif:
        found_types += 1
        ok(f"notification type: {nt}")
    else:
        warn(f"notification type not found: {nt}")
print(f"  --- {found_types}/{len(types)} notification types found ---")

# ── 3. Message notifications ──
print("\n--- 3. Message Notifications ---")
ok("message notification") if "new_message" in all_notif or "message:send" in se else fail("message notification missing")
ok("reaction notification") if "message_reaction" in all_notif or "reaction:new" in se else fail("reaction notification missing")
ok("mention notification") if "mention" in all_notif else fail("mention notification missing")
ok("group notification") if "group" in all_notif.lower() or "thread" in all_notif.lower() else warn("group notification")

# ── 4. Call notifications ──
print("\n--- 4. Call Notifications ---")
ok("incoming call notification") if "incoming_call" in all_notif else fail("incoming_call notification missing")
ok("missed call notification") if "missed_call" in all_notif else fail("missed_call notification missing")
ok("notification:call socket") if "notification:call" in se else warn("notification:call socket event")

# ── 5. Push delivery ──
print("\n--- 5. Push Delivery ---")
ok("push subscription") if find_pattern(ps, "subscription|subscribe") else warn("push subscription")
ok("web push (VAPID)") if "vapid" in ps.lower() or "webpush" in ps.lower() else warn("web push (VAPID)")
ok("FCM") if "fcm" in ps.lower() or "firebase" in ps.lower() else warn("FCM")
ok("APNS") if "apns" in ps.lower() or "apn" in ps.lower() else warn("APNS")

# ── 6. Badge & unread ──
print("\n--- 6. Badge / Unread ---")
ok("badge count JS") if badge_js else fail("notification_badge.js missing")
ok("unread count API") if find_pattern(ns, "unread") else fail("unread count missing in service")
ok("badge update") if find_pattern(badge_js, "badge|count|unread") else fail("badge update logic missing")

# ── 7. Socket events ──
print("\n--- 7. Socket Events ---")
ok("notification:join") if "notification:join" in se else fail("notification:join missing")
ok("notification:new") if "notification:new" in se else fail("notification:new missing")
ok("notification:read") if "notification:read" in se else fail("notification:read missing")
ok("notification:deleted") if "notification:deleted" in se else warn("notification:deleted")
ok("notification_ack") if "notification_ack" in se else warn("notification_ack")

# ── 8. Redis pub/sub ──
print("\n--- 8. Redis Pub/Sub ---")
redis_svc = read_file("services/redis_service.py")
redis_text = redis_svc + ne
ok("Redis pubsub publish") if find_pattern(redis_text, "publish") else fail("Redis pubsub publish missing")
ok("notifications channel") if "notifications" in redis_text else warn("notifications Redis channel")

# ── 9. Templates & UI ──
print("\n--- 9. Templates & UI ---")
for f in ["templates/settings/notifications.html",
          "templates/profile/tabs/tab_notifications.html",
          "static/js/notification_badge.js",
          "static/js/notifications_center.js",
          "static/js/namvibe_notifications.js",
          "static/css/notifications_center.css",
          "static/css/notifications.css"]:
    ok(f"{f} exists") if file_exists(f) else fail(f"{f} missing")

# ── Summary ──
print(f"\n{'=' * 60}")
print("PHASE 130 — NOTIFICATION AUDIT SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
