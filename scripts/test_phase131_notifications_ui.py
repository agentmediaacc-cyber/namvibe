#!/usr/bin/env python3
"""
Phase 131 — Notification UX Test.
Verifies incoming call, missed call, group update, admin promote/demote, member removed, voice note, badge.
"""

import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PASS = 0; FAIL = 0; WARN = 0
def ok(m): global PASS; PASS += 1; print(f"  [PASS] {m}")
def fail(m): global FAIL; FAIL += 1; print(f"  [FAIL] {m}")
def warn(m): global WARN; WARN += 1; print(f"  [WARN] {m}")
def read_file(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full): return ""
    with open(full, encoding="utf-8", errors="ignore") as f: return f.read()

ne = read_file("services/notification_engine.py")
ns = read_file("services/notification_service.py")
ps = read_file("services/push_notification_service.py")
se = read_file("services/socket_events.py")
badge_js = read_file("static/js/notification_badge.js")

print("=" * 60)
print("PHASE 131 — NOTIFICATION UX TEST")
print("=" * 60)

all_notif = ne + ns + ps + se

print("\n--- 1. Call Notifications ---")
ok("incoming_call type") if "incoming_call" in all_notif else fail("incoming_call notification type missing")
ok("missed_call type") if "missed_call" in all_notif else fail("missed_call notification type missing")
ok("notification:call socket") if "notification:call" in se else warn("notification:call socket event")

print("\n--- 2. Group Notifications ---")
ok("group_update type") if "group_update" in ne else warn("group_update notification type")
ok("admin_promoted type") if "admin_promoted" in ne else warn("admin_promoted notification type")
ok("admin_demoted type") if "admin_demoted" in ne else warn("admin_demoted notification type")
ok("member_removed type") if "member_removed" in ne else warn("member_removed notification type")

print("\n--- 3. Voice Note Notifications ---")
ok("voice_note_received type") if "voice_note_received" in all_notif else warn("voice_note_received notification type")

print("\n--- 4. Badge Updates ---")
ok("badge JS exists") if badge_js else fail("notification_badge.js missing")
ok("badge update logic") if "badge" in badge_js or "count" in badge_js else fail("badge update logic missing")
ok("realtime badge") if "notification:new" in se else fail("notification:new socket event missing")

print("\n--- 5. Socket Notification Events ---")
ok("notification:new") if "notification:new" in se else fail("notification:new missing")
ok("notification:read") if "notification:read" in se else fail("notification:read missing")
ok("notification:join") if "notification:join" in se else fail("notification:join missing")
ok("notification:deleted") if "notification:deleted" in se else warn("notification:deleted")

print(f"\n{'=' * 60}")
print("PHASE 131 — NOTIFICATION UX TEST SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
