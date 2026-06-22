#!/usr/bin/env python3
"""
Phase 130 — Group Chat Audit.
Verifies group creation, member management, admin controls, realtime, and unread counters.
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
print("PHASE 130 — GROUP CHAT AUDIT")
print("=" * 60)

thread_svc = read_file("services/message_thread_service.py")
msg_engine = read_file("services/messaging_engine.py")
msg_routes = read_file("api_routes/message_routes.py")
se = read_file("services/socket_events.py")
nv_js = read_file("static/js/namvike_messages_pro.js") or read_file("static/js/namvibe_messages_pro.js")

# ── 1. Database support ──
print("\n--- 1. Database Support ---")
sql_dir = os.path.join(ROOT, "sql")
sql_all = ""
if os.path.isdir(sql_dir):
    for f in os.listdir(sql_dir):
        if f.endswith(".sql"):
            sql_all += read_file(f"sql/{f}")
for tbl in ["chain_message_threads", "chain_thread_members"]:
    ok(f"table: {tbl}") if tbl in sql_all else fail(f"{tbl} not found in SQL")

# ── 2. Group CRUD ──
print("\n--- 2. Group CRUD ---")
ok("create group") if find_pattern(thread_svc, "create.*group|create.*thread|new.*group") else warn("create group not found")
ok("rename group") if find_pattern(thread_svc, "rename|update.*name|edit.*name") else warn("rename group not found")
ok("delete group") if find_pattern(thread_svc, "delete.*group|remove.*group|archive") else warn("delete group not found")

# ── 3. Member management ──
print("\n--- 3. Member Management ---")
ok("add member") if find_pattern(thread_svc, "add.*member|add.*participant|invite") else warn("add member not found")
ok("remove member") if find_pattern(thread_svc, "remove.*member|kick|remove.*participant") else warn("remove member not found")
ok("leave group") if find_pattern(thread_svc, "leave.*group|leave.*thread|exit") else warn("leave group not found")
ok("group avatar") if find_pattern(thread_svc, "avatar|group.*photo|group.*image") else warn("group avatar not found")

# ── 4. Admin controls ──
print("\n--- 4. Admin Controls ---")
ok("admin") if find_pattern(thread_svc, "admin|is_admin|role") else warn("admin role not found")
ok("promote/demote") if find_pattern(thread_svc, "promote|demote|make.*admin") else warn("promote/demote not found")

# ── 5. Realtime ──
print("\n--- 5. Realtime Events ---")
ok("group realtime messages") if "message:send" in se or "send_message" in se else fail("group messages not realtime")
ok("group typing") if "typing:start" in se else fail("group typing missing")
ok("group reactions") if "message:reaction" in se else fail("group reactions missing")
ok("group thread events") if "join:thread" in se or "leave:thread" in se else fail("group thread events missing")

# ── 6. Unread counters ──
print("\n--- 6. Unread Counters ---")
ok("unread count") if find_pattern(msg_engine + msg_routes, "unread") else fail("unread count missing")
ok("thread pin") if "thread:pin" in se else warn("thread pin not in socket events")

# ── 7. Group call integration ──
print("\n--- 7. Group Call Integration ---")
grp_call_svc = read_file("services/group_call_service.py")
grp_call_rt = read_file("api_routes/group_call_routes.py")
ok("group call service") if grp_call_svc else fail("group call service missing")
ok("group call routes") if grp_call_rt else fail("group call routes missing")

# ── Summary ──
print(f"\n{'=' * 60}")
print("PHASE 130 — GROUP CHAT AUDIT SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
