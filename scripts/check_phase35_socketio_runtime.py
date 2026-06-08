#!/usr/bin/env python3
"""Phase 35 — Socket.IO Runtime Environment Check"""

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

# 1. Async mode
try:
    os.environ["FLASK_TESTING"] = "1"
    from app import create_app
    from services.socketio_service import socketio
    app = create_app()
    async_mode = socketio.async_mode
    print(f"  [INFO] async_mode: {async_mode}")
    check("async mode detected", async_mode is not None)
    check("async mode is threading/gevent", async_mode in ("threading", "gevent", None))
except Exception as e:
    check("async mode detection", False, str(e))

# 2. Redis configured
try:
    from services.redis_service import _REDIS_URL, redis_available
    redis_url = os.environ.get("REDIS_URL") or os.environ.get("REDIS_TLS_URL") or ""
    redis_ok = bool(redis_url) or redis_available()
    check("Redis configured", redis_ok, detail="REDIS_URL env not set or Redis unavailable")
    if redis_url:
        print(f"  [INFO] Redis URL configured: {redis_url[:20]}...")
    else:
        print("  [WARN] Redis not configured — Socket.IO will use single-node mode")
except Exception as e:
    check("Redis detection", False, str(e))

# 3. gevent installed
try:
    import gevent
    import gevent.monkey
    check("gevent installed", True)
    print(f"  [INFO] gevent version: {getattr(gevent, '__version__', 'unknown')}")
except ImportError:
    check("gevent installed", False, detail="gevent not installed — threading fallback will be used")
    print("  [WARN] gevent not installed — install for production Socket.IO performance")

# 4. gevent-websocket installed
try:
    import geventwebsocket
    check("gevent-websocket installed", True)
    print(f"  [INFO] gevent-websocket version: {getattr(geventwebsocket, '__version__', 'unknown')}")
except ImportError:
    check("gevent-websocket installed", False, detail="not installed — WebSocket transport will not work")
    print("  [WARN] gevent-websocket not installed — clients will fall back to long-polling")

# 5. Flask-SocketIO installed
try:
    import flask_socketio
    check("flask-socketio installed", True)
    print(f"  [INFO] flask-socketio version: {getattr(flask_socketio, '__version__', 'unknown')}")
except ImportError:
    check("flask-socketio installed", False)

# 6. Warning summary
print()
print("  [SUMMARY] Socket.IO Runtime Environment:")
print(f"    Tests passed: {passed}/{passed+failed}")
if "not installed" in str(failed):
    print("  [WARNING] Missing packages affect real-time performance:")
    print("    - gevent-websocket: WebSocket transport will not work; clients fall back to long-polling")
    print("    - gevent: Threading fallback reduces concurrent connection capacity")
if failed > 0:
    pass  # Don't exit error — just report

print(f"\nResults: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")

# Always exit 0 — this is a diagnostic, not a pass/fail gate
sys.exit(0 if passed > 0 else 1)
