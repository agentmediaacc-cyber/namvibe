"""
Phase 77 — Realtime Foundation Fix tests.

Verifies:
  1. Socket.IO async_mode detects gevent-websocket
  2. /system/socketio-status includes websocket_supported + transports
  3. handle_disconnect accepts *args
  4. presence_service.py exists and exports hot-path functions
  5. notification unread count uses Redis cache with 60s TTL
  6. Migration SQL files exist with proper indexes
  7. namvibe_socket_manager.js exists with reconnect banner
  8. socket_events.py imports from presence_service not presence_engine

Run:
  python3 scripts/test_phase77_realtime_foundation.py
"""

import os, sys, re

PASS = 0
FAIL = 0

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)

def ok(name, detail=""):
    global PASS
    PASS += 1
    msg = f"  OK {name}"
    if detail:
        msg += f"  ({detail})"
    print(msg)

def fail(name, detail=""):
    global FAIL
    FAIL += 1
    msg = f"  FAIL {name}"
    if detail:
        msg += f"  ({detail})"
    print(msg)

def readf(path):
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return None

print("=" * 70)
print("  Phase 77: Realtime Foundation Fix")
print("=" * 70)

# ─── 1. Socket.IO async_mode detection ───
print("\n--- 1. Socket.IO async_mode ---")
sid = readf("services/socketio_service.py") or ""
if "import geventwebsocket" in sid and "async_mode = 'gevent'" in sid:
    ok("gevent-websocket detection", "try/except import with fallback to threading")
else:
    fail("gevent-websocket detection", "import geventwebsocket not found in init_socketio")
if "async_mode = 'threading'" in sid:
    ok("threading fallback", "present when gevent-websocket missing")
else:
    fail("threading fallback", "not found")

# ─── 2. /system/socketio-status endpoints ───
print("\n--- 2. /system/socketio-status ---")
app = readf("app.py") or ""
if "websocket_supported" in app:
    ok("websocket_supported field", "in /system/socketio-status")
else:
    fail("websocket_supported field", "missing from /system/socketio-status")
if "transports" in app:
    ok("transports field", "in /system/socketio-status")
else:
    fail("transports field", "missing from /system/socketio-status")

# ─── 3. handle_disconnect accepts *args ───
print("\n--- 3. disconnect handler ---")
sev = readf("services/socket_events.py") or ""
if "def handle_disconnect(*args):" in sev:
    ok("handle_disconnect(*args)", "accepts extra disconnect reason")
else:
    fail("handle_disconnect(*args)", "still has empty parens")

# ─── 4. presence_service.py ───
print("\n--- 4. presence_service.py ---")
ps = readf("services/presence_service.py") or ""
if not ps:
    fail("services/presence_service.py", "file does not exist")
else:
    ok("services/presence_service.py exists", "file created")
    for fn in ["set_online", "set_offline", "heartbeat", "get_presence", "set_typing", "emit_presence_update"]:
        if f"def {fn}(" in ps:
            ok(f"  presence_service.{fn}()", "exported")
        else:
            fail(f"  presence_service.{fn}()", "missing")
    if "set_json" in ps:
        ok("Uses set_json/get_json (Redis)", "Redis-backed")
    else:
        fail("Uses set_json/get_json", "may not use Redis")
    if "enqueue_job" in ps:
        ok("Enqueues Neon sync via background job", "non-blocking")
    else:
        fail("Enqueues Neon sync", "missing")

# ─── 5. socket_events.py imports from presence_service ───
print("\n--- 5. socket_events.py import swap ---")
if "from services.presence_service import" in sev:
    ok("socket_events imports from presence_service", "hot path swapped")
else:
    fail("socket_events imports from presence_service", "still imports from presence_engine")

# ─── 6. notification unread count Redis TTL ───
print("\n--- 6. notification unread cache ---")
ne = readf("services/notification_engine.py") or ""
if "cache_set(cache_key, count, ttl=60)" in ne:
    ok("unread_count TTL=60s", "Redis cache extended from 15s to 60s")
else:
    fail("unread_count TTL=60s", "not found (may still be 15s)")
if "cache_get(cache_key)" in ne:
    ok("unread_count reads from Redis cache first", "cache_get before DB query")
else:
    fail("unread_count reads from Redis cache", "missing")
if "request_memoize" in ne:
    ok("request_memoize per-request dedup", "second layer of caching")
else:
    fail("request_memoize", "missing")

# ─── 7. Migration files ───
print("\n--- 7. Migrations ---")
for path, label in [
    ("migrations/001_notifications_indexes.sql", "notifications indexes"),
    ("migrations/002_messages_indexes.sql", "messages indexes"),
]:
    content = readf(path)
    if content:
        ok(f"migrations/{label}", "exists")
        if "CREATE INDEX CONCURRENTLY" in content:
            ok(f"  {label}: CONCURRENTLY", "safe for production")
        else:
            fail(f"  {label}: CONCURRENTLY", "missing (may lock table)")
    else:
        fail(f"migrations/{label}", "MISSING")

# ─── 8. namvibe_socket_manager.js ───
print("\n--- 8. Socket manager JS ---")
sm_js = readf("static/js/namvibe_socket_manager.js") or ""
if not sm_js:
    fail("static/js/namvibe_socket_manager.js", "file does not exist")
else:
    ok("static/js/namvibe_socket_manager.js", "exists")
    checks = [
        ("window.chainSocket", "exposes chainSocket global"),
        ("reconnectionDelay", "configures reconnection delay"),
        ("reconnectionAttempts", "configures reconnection attempts"),
        ("transports", "specifies transports"),
        ("reconnect-banner", "reconnect banner element"),
    ]
    for marker, desc in checks:
        if marker in sm_js:
            ok(f"  {desc}", marker)
        else:
            fail(f"  {desc}", f"{marker} missing")

# ─── 9. presence_engine.py still intact ───
print("\n--- 9. presence_engine.py intact ---")
pe = readf("services/presence_engine.py") or ""
if pe:
    ok("presence_engine.py still exists", "kept for sync_presence_to_neon job")
else:
    fail("presence_engine.py", "missing")

# ─── RESULTS ───
print("\n" + "=" * 70)
print(f"  Phase 77 Results: {PASS} passed, {FAIL} failed")
print("=" * 70)
sys.exit(0 if FAIL == 0 else 1)
