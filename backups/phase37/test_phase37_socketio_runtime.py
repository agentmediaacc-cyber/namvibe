"""
Phase 37 E2E: Socket.IO handler validation — handlers exist, no import errors.
"""
import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "0"
os.environ["CHAIN_TRUST_PROFILE_SCHEMA"] = "1"

PASS = 0; FAIL = 0
def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {label}"); PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else "")); FAIL += 1

# 1. Module imports without error
try:
    from services.socket_events import socketio
    check("socket_events module imports", True)
except Exception as e:
    check("socket_events module imports", False, str(e))

# 2. Check required handlers exist
socket_path = os.path.join(os.path.dirname(__file__), "..", "services", "socket_events.py")
with open(socket_path) as f:
    src = f.read()

required = [
    ("message:send", "send_message"),
    ("message:seen", "message_seen"),
    ("call:offer", "call_offer"),
    ("call:answer", "call_answer"),
    ("call:end", "call_end"),
    ("call:reject", "call_reject"),
    ("call:signal", "call_signal"),
    ("call:status", "call_status"),
]

for event, hint in required:
    found = re.search(rf'@socketio\.on\(["\']{event}["\']\)', src)
    check(f"Handler for '{event}'", bool(found))

# 3. Redis / Socket.IO config
try:
    from app import create_app
    app = create_app()
    check("create_app with socketio", app is not None)
except Exception as e:
    check("create_app with socketio", False, str(e))

# 4. Verify socketio imported cleanly
try:
    from services.socketio_service import socketio as sio, emit_to_profile, emit_to_thread
    check("socketio_service imports", True)
except Exception as e:
    check("socketio_service imports", False, str(e))

# 5. Check for WebRTC / call signal handlers
try:
    from services.webrtc_turn_service import get_webrtc_ice_config
    cfg = get_webrtc_ice_config()
    check("webrtc_turn_service imports and returns config", isinstance(cfg, dict))
except Exception as e:
    check("webrtc_turn_service imports and returns config", False, str(e))

print(f"\nResults: {PASS}/{PASS+FAIL} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
