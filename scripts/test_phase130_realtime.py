#!/usr/bin/env python3
"""
Phase 130 — Socket.IO Realtime Audit.
Verifies all required realtime events, room management, presence, and recovery.
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


print("=" * 60)
print("PHASE 130 — SOCKET.IO REALTIME AUDIT")
print("=" * 60)

se = read_file("services/socket_events.py")
si = read_file("services/socketio_service.py")

# ── 1. Core infrastructure ──
print("\n--- 1. Core Infrastructure ---")
for f in ["services/socket_events.py", "services/socketio_service.py",
          "services/realtime_service.py", "services/presence_service.py"]:
    ok(f"{f} exists") if file_exists(f) else fail(f"{f} missing")

ok("SocketIO init") if "SocketIO" in si and "socketio" in si else fail("SocketIO init missing")
ok("Redis message queue") if "message_queue" in si else fail("Redis message queue missing")
ok("CORS enabled") if "cors" in si.lower() else warn("CORS not found in socketio_service")
ok("event handlers defined") if len(se) > 5000 else fail("socket_events.py too short")

# ── 2. Connection lifecycle ──
print("\n--- 2. Connection Lifecycle ---")
ok("connect") if "def connect" in se or "'connect'" in se or '"connect"' in se else fail("connect handler missing")
ok("disconnect") if "def disconnect" in se or "'disconnect'" in se or '"disconnect"' in se or "handle_disconnect" in se else fail("disconnect handler missing")
ok("join_room") if "join_room" in se else fail("join_room missing")
ok("leave_room") if "leave_room" in se else fail("leave_room missing")
ok("join:thread") if "join:thread" in se or "join_thread" in se else fail("join:thread missing")
ok("leave:thread") if "leave:thread" in se or "leave_thread" in se else fail("leave:thread missing")
ok("presence heartbeat") if "heartbeat" in se or "presence" in se else warn("presence heartbeat")
ok("room dedup") if "dedup" in se or "_ignore_duplicate" in se else warn("room dedup not found")

# ── 3. Typing indicators ──
print("\n--- 3. Typing Indicators ---")
ok("typing:start") if "typing:start" in se or "typing_start" in se else fail("typing:start missing")
ok("typing:stop") if "typing:stop" in se or "typing_stop" in se else fail("typing:stop missing")
ok("typing rate limited") if "rate" in se.lower() and "typing" in se.lower() else warn("typing rate limit not found")

# ── 4. Message events ──
print("\n--- 4. Message Events ---")
ok("message:send") if "message:send" in se or "send_message" in se else fail("message:send missing")
ok("message:delivered") if "message:delivered" in se or "delivered" in se else fail("message:delivered missing")
ok("message:seen") if "message:seen" in se or "message_seen" in se or '"seen"' in se else fail("message:seen missing")
ok("message:reaction") if "message:reaction" in se or "reaction:new" in se else fail("message:reaction missing")
ok("message:delete") if "message:delete" in se or "message_deleted" in se else fail("message:delete missing")
ok("message:edited") if "message:edited" in se else fail("message:edited missing")
ok("message:recover") if "message:recover" in se or "reconnect_sync" in se else warn("message:recover")
ok("message:forwarded") if "message:forwarded" in se else warn("message:forwarded")
ok("message:draft") if "message:draft" in se else warn("message:draft")
ok("message:pinned") if "message:pinned" in se else warn("message:pinned")

# ── 5. Call signaling events ──
print("\n--- 5. Call Signaling ---")
ok("call:start") if "call:start" in se else fail("call:start missing")
ok("call:ringing") if "call:ringing" in se else fail("call:ringing missing")
ok("call:accept") if "call:accept" in se else fail("call:accept missing")
ok("call:reject") if "call:reject" in se else fail("call:reject missing")
ok("call:cancel") if "call:cancel" in se else fail("call:cancel missing")
ok("call:end") if "call:end" in se else fail("call:end missing")
ok("call:busy") if "call:busy" in se else fail("call:busy missing")
ok("call:offer") if "call:offer" in se else fail("call:offer missing")
ok("call:answer") if "call:answer" in se else fail("call:answer missing")
ok("call:ice-candidate") if "call:ice-candidate" in se else fail("call:ice-candidate missing")
ok("call:reconnect") if "call:reconnect" in se else fail("call:reconnect missing")
ok("call:media-state") if "call:media-state" in se else fail("call:media-state missing")
ok("call:participant events") if "call:participant-joined" in se else fail("call:participant events missing")

# ── 6. Group call events ──
print("\n--- 6. Group Call Events ---")
ok("group-call:create") if "group-call:create" in se else fail("group-call:create missing")
ok("group-call:join") if "group-call:join" in se else fail("group-call:join missing")
ok("group-call:leave") if "group-call:leave" in se else fail("group-call:leave missing")
ok("group-call:mute") if "group-call:mute" in se else warn("group-call:mute")
ok("group-call:raise-hand") if "group-call:raise-hand" in se else warn("group-call:raise-hand")

# ── 7. Notification events ──
print("\n--- 7. Notification Events ---")
ok("notification:new") if "notification:new" in se else fail("notification:new missing")
ok("notification:read") if "notification:read" in se else fail("notification:read missing")
ok("notification:join") if "notification:join" in se else fail("notification:join missing")
ok("notification:call") if "notification:call" in se else warn("notification:call")
ok("notification:message") if "notification:message" in se else warn("notification:message")
ok("notification:security") if "notification:security" in se else warn("notification:security")

# ── 8. Reconnection & recovery ──
print("\n--- 8. Reconnect & Recovery ---")
ok("reconnect_sync") if "reconnect_sync" in se else warn("reconnect_sync")
ok("offline recovery") if "reconnect" in se or "recover" in se else fail("offline recovery missing")
ok("message retry queue") if file_exists("services/message_delivery_service.py") and "retry" in read_file("services/message_delivery_service.py").lower() else warn("message retry queue")
ok("duplicate prevention") if "_ignore_duplicate" in se or "client_event_id" in se else warn("duplicate prevention missing")

# ── 9. Safety events ──
print("\n--- 9. Safety Events ---")
ok("safety:report") if "safety:report" in se else warn("safety:report")
ok("safety:restricted") if "safety:user-restricted" in se else warn("safety:user-restricted")

# ── 10. Encryption events ──
print("\n--- 10. Encryption Events ---")
ok("encryption:status") if "encryption:status" in se else warn("encryption:status")
ok("encryption:key-rotated") if "encryption:key-rotated" in se else warn("encryption:key-rotated")

# ── 11. Total event count ──
print("\n--- 11. Event Count ---")
event_count = len(re.findall(r"'([a-z_-]+:[a-z_-]+)'", se))
if event_count >= 30:
    ok(f"Socket event handlers: {event_count}+")
else:
    warn(f"Only {event_count} events found")

# ── Summary ──
print(f"\n{'=' * 60}")
print("PHASE 130 — SOCKET.IO REALTIME AUDIT SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}  FAIL: {FAIL}  WARN: {WARN}")
print(f"  safe_to_commit: {'YES' if FAIL == 0 else 'NO'}")
