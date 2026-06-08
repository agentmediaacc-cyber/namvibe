#!/usr/bin/env python3
"""Phase 35 — Socket.IO Connection Test (static verification)"""

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_DISABLE_PREWARM"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"

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

# 1. socket_events.py loads without error
try:
    import services.socket_events
    check("socket_events.py loads", True)
except Exception as e:
    check("socket_events.py loads", False, str(e))

# 2. socketio module loads and has required attributes
try:
    from services.socketio_service import socketio, init_socketio
    check("socketio object exists", socketio is not None)
    check("init_socketio callable", callable(init_socketio))
except Exception as e:
    check("socketio_service imports", False, str(e))

# 3. Required event handlers exist in socket_events
try:
    import services.socket_events as se
    events_to_check = [
        "handle_connect",
        "handle_disconnect",
        "handle_message_send",
        "handle_typing_start",
        "handle_message_seen",
        "handle_call_offer",
        "handle_call_answer",
        "handle_call_end",
        "handle_join_live",
        "handle_live_chat",
    ]
    for handler in events_to_check:
        check(f"Handler {handler} defined", hasattr(se, handler), f"Not found in socket_events")
except Exception as e:
    check("socket_events handler check", False, str(e))

# 4. Read socket_events.py source and confirm event name registrations
try:
    src = open(os.path.join(BASE, "services", "socket_events.py")).read()
    required_events = [
        ('"connect"', "connect event"),
        ('"disconnect"', "disconnect event"),
        ('"message:send"', "message:send event"),
        ('"message:seen"', "message:seen event"),
        ('"call:offer"', "call:offer event"),
        ('"call:answer"', "call:answer event"),
        ('"call:end"', "call:end event"),
        ('"join_live_room"', "join_live_room event"),
        ('"live_chat_message"', "live_chat_message event"),
        ('"presence:heartbeat"', "presence:heartbeat event"),
        ('"call:reject"', "call:reject event"),
        ('"call:ice-candidate"', "call:ice-candidate event"),
        ('"typing:start"', "typing:start event"),
        ('"typing:stop"', "typing:stop event"),
        ('"call:media-state"', "call:media-state event"),
        ('"call:reconnect"', "call:reconnect event"),
        ('"call:signal"', "call:signal event"),
        ('"call:status"', "call:status event"),
        ('"call:quality"', "call:quality event"),
        ('"call:waiting"', "call:waiting event"),
    ]
    for event_str, label in required_events:
        check(f"Socket event {label} registered", event_str in src, f"'{event_str}' not found")
except Exception as e:
    check("socket_events.py readable", False, str(e))

# 5. Socket.IO server is initialized via init_socketio
try:
    from services.socketio_service import socketio
    check("socketio.init_app available", hasattr(socketio, "init_app"))
    check("socketio.emit available", hasattr(socketio, "emit"))
    check("socketio.on available", hasattr(socketio, "on"))
except Exception as e:
    check("socketio interface OK", False, str(e))

# 6. Redis manager optional fallback works
try:
    from services.redis_service import redis_available
    check("redis_available function exists", callable(redis_available))
except Exception as e:
    check("redis_available importable", False, str(e))

# 7. Test mode skips Redis manager
try:
    from services.socketio_service import init_socketio
    from flask import Flask
    test_app = Flask(__name__)
    test_app.config["TESTING"] = True
    sio = init_socketio(test_app)
    check("init_socketio creates socketio in test mode", sio is not None)
    check("async_mode in test mode", sio.async_mode in (None, "threading", "gevent"))
except Exception as e:
    check("init_socketio test mode OK", False, str(e))

# 8. No gevent-websocket hard crash in test mode
try:
    import gevent
    check("gevent installed", True)
except ImportError:
    check("gevent installed (optional)", False, "gevent not installed — threading fallback OK")
try:
    import geventwebsocket
    check("gevent-websocket installed", True)
except ImportError:
    check("gevent-websocket installed (optional)", False, "not installed — will use long-polling fallback")

# 9. App socketio ready endpoint
try:
    from app import create_app
    ta = create_app()
    with ta.test_client() as c:
        r = c.get("/")
        check("GET / root accessible", r.status_code in (200, 302))
except Exception as e:
    check("root endpoint accessible", False, str(e))

print(f"\nResults: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")
if failed > 0:
    sys.exit(1)
