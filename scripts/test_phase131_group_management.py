#!/usr/bin/env python3
"""
Phase 131 — Group Chat Management Test.
Verifies rename, avatar, promote/demote, remove, leave with realtime.
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

mts = read_file("services/message_thread_service.py")
se = read_file("services/socket_events.py")
ne = read_file("services/notification_engine.py")

print("=" * 60)
print("PHASE 131 — GROUP MANAGEMENT TEST")
print("=" * 60)

print("\n--- 1. Backend Functions ---")
ok("rename_group") if "def rename_group" in mts else fail("rename_group missing")
ok("update_group_avatar") if "def update_group_avatar" in mts else fail("update_group_avatar missing")
ok("promote_admin") if "def promote_admin" in mts else fail("promote_admin missing")
ok("demote_admin") if "def demote_admin" in mts else fail("demote_admin missing")
ok("remove_group_member admin check") if "not_admin" in mts else fail("remove_group_member admin check missing")
ok("leave_group") if "def leave_group" in mts else fail("leave_group missing")

print("\n--- 2. Socket Events ---")
ok("group:rename") if "group:rename" in se else fail("group:rename socket event missing")
ok("group:name-updated") if "group:name-updated" in se else fail("group:name-updated socket event missing")
ok("group:avatar") if "group:avatar" in se else fail("group:avatar socket event missing")
ok("group:avatar-updated") if "group:avatar-updated" in se else fail("group:avatar-updated socket event missing")
ok("group:promote") if "group:promote" in se else fail("group:promote socket event missing")
ok("group:admin-promoted") if "group:admin-promoted" in se else fail("group:admin-promoted socket event missing")
ok("group:demote") if "group:demote" in se else fail("group:demote socket event missing")
ok("group:admin-demoted") if "group:admin-demoted" in se else fail("group:admin-demoted socket event missing")
ok("group:remove-member") if "group:remove-member" in se else fail("group:remove-member socket event missing")
ok("group:member-removed") if "group:member-removed" in se else fail("group:member-removed socket event missing")
ok("group:leave") if "group:leave" in se else fail("group:leave socket event missing")
ok("group:member-left") if "group:member-left" in se else fail("group:member-left socket event missing")

print("\n--- 3. Notification Types ---")
ok("group_update") if "group_update" in ne else warn("group_update notification type")
ok("admin_promoted") if "admin_promoted" in ne else warn("admin_promoted notification type")
ok("admin_demoted") if "admin_demoted" in ne else warn("admin_demoted notification type")
ok("member_removed") if "member_removed" in ne else warn("member_removed notification type")

print("\n--- 4. DB Schema ---")
sql_all = ""
sql_dir = os.path.join(ROOT, "sql")
if os.path.isdir(sql_dir):
    for f in os.listdir(sql_dir):
        if f.endswith(".sql"):
            sql_all += read_file(f"sql/{f}")
ok("chain_message_threads avatar_url") if "avatar_url" in sql_all else warn("avatar_url column in chain_message_threads")
ok("chain_thread_members role") if "chain_thread_members" in sql_all else warn("chain_thread_members table")

print(f"\n{'=' * 60}")
print("PHASE 131 — GROUP MANAGEMENT TEST SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
