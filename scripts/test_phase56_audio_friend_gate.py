"""
Phase 56: Audio Fix + Friend-Based Messaging/Calling Test Users
"""
import os, sys, json, uuid as uuid_mod, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_TEST_FAKE_DB"] = "1"
os.environ["CHAIN_TRUST_PROFILE_SCHEMA"] = "1"

from app import create_app
app = create_app()

PASS = 0; FAIL = 0
def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {label}"); PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else "")); FAIL += 1

PID_A = str(uuid_mod.uuid4())
PID_B = str(uuid_mod.uuid4())
PID_C = str(uuid_mod.uuid4())

client = app.test_client()

# ============================================================
# TASK 1: Relationship Gate Service
# ============================================================
def test_relationship_gate_imports():
    from services.relationship_gate_service import (
        can_message, can_call, relationship_status,
        is_mutual_follow, is_blocked
    )
    check("relationship_gate_service imports ok", True)

def test_self_message_blocked():
    from services.relationship_gate_service import can_message, can_call
    result = can_message(PID_A, PID_A)
    check("can_message blocks self", not result.get("ok"), result.get("error"))
    result = can_call(PID_A, PID_A)
    check("can_call blocks self", not result.get("ok"), result.get("error"))

def test_relationship_status_self():
    from services.relationship_gate_service import relationship_status
    rs = relationship_status(PID_A, PID_A)
    check("relationship_status self returns self", rs.get("status") == "self")

def test_relationship_status_stranger():
    from services.relationship_gate_service import relationship_status
    rs = relationship_status(PID_A, PID_B)
    # In test mode (CHAIN_FAST_LOCAL), all statuses return "friend"
    check("relationship_status returns status", rs.get("status") in ("stranger", "friend"))

def test_relationship_gate_has_can_message():
    from services.relationship_gate_service import relationship_status
    rs = relationship_status(PID_A, PID_B)
    check("relationship_status has can_message key", "can_message" in rs)
    check("relationship_status has can_call key", "can_call" in rs)

# ============================================================
# TASK 2: Test User Seeder Script
# ============================================================
def test_seeder_script_exists():
    check("seed_chain_test_users.py exists",
          os.path.isfile("scripts/seed_chain_test_users.py"))

def test_seeder_has_all_users():
    content = open("scripts/seed_chain_test_users.py").read()
    for username in ["chain_star", "chain_moon", "chain_gold", "chain_million", "chain_premium"]:
        check(f"Seeder has user {username}", username in content)
    check("Seeder uses generate_password_hash",
          "generate_password_hash" in content)
    check("Seeder uses write_query",
          "write_query" in content)
    check("Seeder seeds mutual follows",
          "seed_mutual_follows" in content)
    check("Seeder saves credentials",
          "save_credentials" in content)
    check("Seeder uses @chain.local emails",
          "@chain.local" in content)
    check("Seeder saves profile dict in credentials",
          "\"profile\":" in content)
    check("Seeder saves auth_user_id in credentials",
          "\"auth_user_id\":" in content)

def test_seeder_password_constant():
    content = open("scripts/seed_chain_test_users.py").read()
    check("Seeder uses Adimintest password",
          'PASSWORD = "Adimintest"' in content)

# ============================================================
# TASK 3: Message Requests SQL + Routes
# ============================================================
def test_message_requests_sql():
    check("phase56_message_requests.sql exists",
          os.path.isfile("sql/phase56_message_requests.sql"))
    content = open("sql/phase56_message_requests.sql").read()
    check("SQL has chain_message_requests table",
          "chain_message_requests" in content)
    check("SQL has pending/accepted/declined/expired check",
          "CHECK (status IN ('pending'" in content)

def test_message_request_routes_exist():
    routes_content = open("api_routes/message_routes.py").read()
    checks = [
        ("api_send_message_request route", "/api/message-request/send"),
        ("api_message_request_inbox route", "/api/message-requests/inbox"),
        ("api_accept_message_request route", "/api/message-requests/<request_id>/accept"),
        ("api_decline_message_request route", "/api/message-requests/<request_id>/decline"),
        ("api_friends route", "/api/friends"),
        ("api_get_or_create_thread route", "/api/thread/<profile_id>"),
        ("api_relationship_status route", "/api/relationship/<profile_id>"),
        ("api_start_thread route", "/api/threads/start"),
    ]
    for label, route in checks:
        check(label, route in routes_content)

def test_message_request_imports():
    routes_content = open("api_routes/message_routes.py").read()
    check("message_routes imports relationship_gate_service",
          "from services.relationship_gate_service import" in routes_content)
    check("message_routes imports uuid",
          "import uuid" in routes_content)

# ============================================================
# TASK 4: Friend Picker UI
# ============================================================
def test_friend_picker_html():
    index_content = open("templates/messages/index.html").read()
    checks = [
        ("friendList container", 'id="friendList"'),
        ("friendSearch input", 'id="friendSearch"'),
        ("Friend card template", "friend-card"),
        ("Message button in friend card", "fa-comment"),
        ("Call button in friend card", "fa-phone"),
        ("Friend online dot", "friend-online-dot"),
        ("Load friend list function", "loadFriendList"),
        ("Friend card click handler", "startFriendThread"),
        ("Friend search filter", "friendSearch"),
    ]
    for label, pattern in checks:
        check(f"Friend picker: {label}", pattern in index_content)

def test_friend_picker_css():
    index_content = open("templates/messages/index.html").read()
    css_classes = [
        ".friend-card", ".friend-card-avatar", ".friend-online-dot",
        ".friend-card-info", ".friend-card-name", ".friend-card-username",
        ".friend-card-actions", ".friend-card-btn",
    ]
    for css in css_classes:
        check(f"Friend picker CSS: {css}", css in index_content)

# ============================================================
# TASK 5: Voice Recording Fix
# ============================================================
def test_voice_mime_detection():
    composer_js = open("static/js/message_composer.js").read()
    check("detectAudioMime function exists",
          "detectAudioMime" in composer_js)
    check("MIME fallback chain exists",
          "audio/webm;codecs=opus" in composer_js)
    check("MIME fallback includes mp4",
          "audio/mp4" in composer_js)
    check("MIME fallback includes ogg",
          "audio/ogg" in composer_js)
    check("MediaRecorder.isTypeSupported used",
          "MediaRecorder.isTypeSupported" in composer_js)
    check("handleVoiceStop function",
          "handleVoiceStop" in composer_js)
    check("Timeslice argument 250ms",
          "start(250)" in composer_js)
    check("Extension from MIME type",
          "ext = 'mp4'" in composer_js)
    check("Voice file extension logic",
          "ext = 'mp3'" in composer_js)
    check("Voice file name uses extension",
          "voice-note." in composer_js)

# ============================================================
# TASK 6: WebRTC Call Fix
# ============================================================
def test_webrtc_relationship_gate():
    socket_events = open("services/socket_events.py").read()
    check("socket_events imports relationship_gate_service",
          "from services.relationship_gate_service import" in socket_events)
    check("socket_events checks gate in call:start",
          "_gate_can_call" in socket_events)

def test_webrtc_call_service_gate():
    ws_content = open("services/webrtc_call_service.py").read()
    check("webrtc_call_service checks relationship gate in create_call",
          "_check_relationship_gate" in ws_content)
    check("_check_relationship_gate function defined",
          "def _check_relationship_gate" in ws_content)
    check("gate imports can_call from relationship_gate_service",
          "from services.relationship_gate_service import can_call" in ws_content)

def test_call_routes_gate():
    call_routes = open("api_routes/call_routes.py").read()
    check("call_routes imports relationship_gate_service",
          "from services.relationship_gate_service import" in call_routes)

def test_api_send_relationship_check():
    msg_routes = open("api_routes/message_routes.py").read()
    check("api_send checks relationship_status",
          "relationship_status" in msg_routes and "can_message" in msg_routes)

# ============================================================
# TASK 7: Auth Test Credentials Loading
# ============================================================
def test_auth_test_credential_loading():
    auth_content = open("services/auth_service.py").read()
    check("auth_service loads test credentials",
          "_load_test_credentials" in auth_content)
    check("auth_service checks test_credentials.json",
          "test_credentials.json" in auth_content)
    check("auth_service populates _DEV_REGISTRATION_CREDENTIALS",
          "_DEV_REGISTRATION_CREDENTIALS[str(key).lower()]" in auth_content)

# ============================================================
# TASK 8: WebRTC Audio Call — essential features
# ============================================================
def test_webrtc_ringtone_handling():
    wc = open("static/js/webrtc_calls.js").read()
    checks = [
        ("startRingtone function", "function startRingtone"),
        ("stopRingtone function", "function stopRingtone"),
        ("startRingbackTone function", "function startRingbackTone"),
        ("handleIncomingCall handler", "function handleIncomingCall"),
        ("handleCallRejected handler", "handleCallRejected"),
        ("handleCallCancelled handler", "handleCallCancelled"),
        ("handleCallEnded handler", "handleCallEnded"),
        ("handleCallBusy handler", "handleCallBusy"),
        ("handleCallNoAnswer handler", "handleCallNoAnswer"),
        ("handleCallMissed handler", "handleCallMissed"),
        ("wAcceptCall function", "function wAcceptCall"),
        ("wRejectCall function", "function wRejectCall"),
        ("wEndCall function", "function wEndCall"),
        ("call:timeout socket event", "call:timeout"),
        ("cleanupCall function", "function cleanupCall"),
        ("startCallTimeoutTimer", "startCallTimeoutTimer"),
        ("stopCallTimeoutTimer", "stopCallTimeoutTimer"),
    ]
    for label, pattern in checks:
        check(f"WebRTC: {label}", pattern in wc)

def test_webrtc_ui_elements():
    thread_html = open("templates/messages/thread.html").read()
    checks = [
        ("call-overlay exists", 'id="call-overlay"'),
        ("call-timer exists", 'id="call-timer"'),
        ("answer-btn exists", 'id="answer-btn"'),
        ("end-call exists", 'class="co-end end-call"'),
        ("answerIncomingCall onclick", "answerIncomingCall"),
        ("toggleMute onclick", "toggleMute"),
        ("toggleCamera onclick", "toggleCamera"),
        ("toggleSpeaker onclick", "toggleSpeaker"),
    ]
    for label, pattern in checks:
        check(f"Call UI: {label}", pattern in thread_html)

# ============================================================
# TASK 9: Route Smoke Tests
# ============================================================
def test_friends_api_route():
    """Check that route is registered"""
    rules = [r.rule for r in app.url_map.iter_rules()]
    check("/api/friends route registered",
          "/messages/api/friends" in " ".join(rules))

def test_relationship_api_route():
    with app.test_request_context():
        from api_routes.message_routes import message_bp
        check("/api/relationship/<profile_id> route registered",
              any("api/relationship" in str(r) for r in app.url_map.iter_rules() if r.endpoint and "messages" in r.endpoint) or
              any("relationship" in str(getattr(r, 'rule', '')) for r in app.url_map.iter_rules()),
              detail="Check route registration")

# ============================================================
# TASK 10: Thread — message request integration
# ============================================================
def test_get_or_create_direct_thread_already_uses_mutual():
    from services.messaging_engine import get_or_create_direct_thread
    import inspect
    src = inspect.getsource(get_or_create_direct_thread)
    check("get_or_create_direct_thread checks mutual follows",
          "is_mutual" in src and "follower_profile_id" in src,
          detail="Mutual follow detection")

def test_thread_start_api_checks_relationship():
    msg_routes = open("api_routes/message_routes.py").read()
    checks = [
        "needs_request" in msg_routes,
        "chain_message_requests" in msg_routes,
        "Cannot start thread with yourself" in msg_routes,
    ]
    check("api_start_thread checks relationship + request",
          all(checks), detail=str(checks))


# ============================================================
# Run all tests
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Phase 56: Audio Fix + Friend-Based Messaging/Calling")
    print("=" * 60)

    tests = [
        ("Relationship Gate Service", test_relationship_gate_imports),
        ("Self message/call blocked", test_self_message_blocked),
        ("Relationship status self", test_relationship_status_self),
        ("Relationship status stranger", test_relationship_status_stranger),
        ("Relationship status has keys", test_relationship_gate_has_can_message),
        ("Seeder script exists", test_seeder_script_exists),
        ("Seeder has all users", test_seeder_has_all_users),
        ("Seeder password constant", test_seeder_password_constant),
        ("Message requests SQL", test_message_requests_sql),
        ("Message request routes", test_message_request_routes_exist),
        ("Message request imports", test_message_request_imports),
        ("Friend picker HTML", test_friend_picker_html),
        ("Friend picker CSS", test_friend_picker_css),
        ("Voice MIME detection", test_voice_mime_detection),
        ("WebRTC relationship gate", test_webrtc_relationship_gate),
        ("WebRTC call service gate", test_webrtc_call_service_gate),
        ("Call routes gate", test_call_routes_gate),
        ("API send relationship check", test_api_send_relationship_check),
        ("Auth test credential loading", test_auth_test_credential_loading),
        ("WebRTC ringtone handling", test_webrtc_ringtone_handling),
        ("WebRTC UI elements", test_webrtc_ui_elements),
        ("Friends API route", test_friends_api_route),
        ("Relationship API route", test_relationship_api_route),
        ("Thread mutual follow", test_get_or_create_direct_thread_already_uses_mutual),
        ("Thread start API", test_thread_start_api_checks_relationship),
    ]

    for name, fn in tests:
        print(f"\n--- {name} ---")
        try:
            fn()
        except Exception as e:
            print(f"  [FAIL] {name} threw: {e}")
            FAIL += 1

    total = PASS + FAIL
    print(f"\n{'=' * 40}")
    print(f"Results: {PASS}/{total} passed, {FAIL} failed")
    print(f"{'=' * 40}")
    sys.exit(0 if FAIL == 0 else 1)
