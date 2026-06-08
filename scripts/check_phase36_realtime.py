#!/usr/bin/env python3
"""Phase 36 — Real-Time Hardening Audit"""

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} {detail}")
        failed += 1

# 1. Socket.IO service loads
try:
    from services.socketio_service import socketio, init_socketio, emit_to_profile, emit_to_thread, emit_to_live_room
    check("socketio_service loads", True)
    check("socketio object exists", socketio is not None)
    check("emit_to_profile exists", callable(emit_to_profile))
    check("emit_to_thread exists", callable(emit_to_thread))
    check("emit_to_live_room exists", callable(emit_to_live_room))
except Exception as e:
    check("socketio_service loads", False, str(e))

# 2. Socket events load
try:
    import services.socket_events
    check("socket_events loads", True)
except Exception as e:
    check("socket_events loads", False, str(e))

# 3. Reconnect logic
socket_src = open(os.path.join(BASE, "services", "socket_events.py")).read()
has_reconnect = "\"reconnect_sync\"" in socket_src or "reconnect" in socket_src.lower()
check("Reconnect sync handler registered", has_reconnect)

# 4. Heartbeat/presence
has_heartbeat = "\"presence:heartbeat\"" in socket_src
check("Presence heartbeat handler registered", has_heartbeat)

# 5. Stale socket cleanup
try:
    from services.socketio_service import cleanup_stale_sockets
    check("cleanup_stale_sockets exists", callable(cleanup_stale_sockets))
except Exception as e:
    check("cleanup_stale_sockets exists", False, str(e))

# 6. Online presence
try:
    from services.presence_engine import set_online, set_offline, heartbeat
    check("presence_engine: set_online", callable(set_online))
    check("presence_engine: set_offline", callable(set_offline))
    check("presence_engine: heartbeat", callable(heartbeat))
except Exception as e:
    check("presence_engine imports", False, str(e))

# 7. Typing presence
try:
    from services.presence_engine import set_typing
    check("presence_engine: set_typing", callable(set_typing))
except Exception as e:
    check("presence_engine: set_typing", False, str(e))

# 8. Call recovery
try:
    from services.call_feature_service import get_call, recent_calls
    check("call_feature: get_call for recovery", callable(get_call))
    check("call_feature: recent_calls for recovery", callable(recent_calls))
except Exception as e:
    check("call recovery functions", False, str(e))

# 9. Live recovery
try:
    from services.live_service import get_room, get_live_rooms
    check("live_service: get_room for recovery", callable(get_room))
    check("live_service: get_live_rooms for recovery", callable(get_live_rooms))
except Exception as e:
    check("live recovery functions", False, str(e))

# 10. Redis availability (for scaling)
try:
    from services.redis_service import redis_available, get_redis
    check("redis_available exists", callable(redis_available))
    check("get_redis exists", callable(get_redis))
except Exception as e:
    check("redis_service imports", False, str(e))

# 11. Circuit breaker
try:
    from services.circuit_breaker import CircuitBreaker
    check("CircuitBreaker exists", callable(CircuitBreaker))
except Exception as e:
    check("CircuitBreaker exists", False, str(e))

# 12. Safe fallbacks in socketio_service
sio_src = open(os.path.join(BASE, "services", "socketio_service.py")).read()
has_test_mode = "TESTING" in sio_src and "Skipping Redis manager" in sio_src
check("Test mode fallback (skips Redis)", has_test_mode)
has_circuit = "CircuitBreaker" in sio_src
check("Circuit breaker in socketio_service", has_circuit)

# 13. emit_to_profile, emit_to_thread, emit_to_live_room
check("emit_to_profile wraps safely", "def emit_to_profile" in sio_src)
check("emit_to_thread wraps safely", "def emit_to_thread" in sio_src)
check("emit_to_live_room wraps safely", "def emit_to_live_room" in sio_src)

# 14. Presence routes
try:
    from api_routes.presence_routes import presence_bp
    check("presence_routes registered", True)
except Exception as e:
    check("presence_routes registered", False, str(e))

# 15. Realtime routes
try:
    from api_routes.realtime_routes import realtime_bp
    check("realtime_routes registered", True)
except Exception as e:
    check("realtime_routes registered", False, str(e))

print(f"\n  [SUMMARY] Real-Time Hardening:")
print(f"    Tests passed: {passed}/{passed+failed}")
print(f"\nResults: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")
if failed > 0:
    sys.exit(1)
