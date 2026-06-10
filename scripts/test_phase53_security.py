"""
Phase 53 Security Hardening — Verify thread membership enforcement.
All thread-based API routes must return 403 for non-members.
"""
import os, sys, json, uuid as uuid_mod
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_TEST_FAKE_DB"] = "1"
os.environ["CHAIN_TRUST_PROFILE_SCHEMA"] = "1"

from app import create_app
app = create_app()
from api_routes.message_production_routes import message_production_bp
app.register_blueprint(message_production_bp)

import services.message_feature_service as _mfs
import services.message_delivery_service as _mds
import services.thread_security_service as _tss
from services.neon_service import fast_query, write_query

PID_A = str(uuid_mod.uuid4())
PID_B = str(uuid_mod.uuid4())
PID_EVE = str(uuid_mod.uuid4())  # Intruder — not in any thread
TID = str(uuid_mod.uuid4())
POLL_ID = str(uuid_mod.uuid4())
OPTION_ID = str(uuid_mod.uuid4())
SHARE_ID = str(uuid_mod.uuid4())

PASS = 0; FAIL = 0
def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {label}"); PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else "")); FAIL += 1

client = app.test_client()

_mfs._db_available = lambda: False
if hasattr(_mds, '_db_available'):
    _mds._db_available = lambda: False

_known_members = {}

def _fake_fast_query(sql, params=None, timeout_ms=2000, default=None):
    if params and len(params) >= 2:
        # chain_thread_members membership check
        if "chain_thread_members" in sql and "profile_id" in sql:
            tid, pid = params[0], params[1]
            if _known_members.get((str(tid), str(pid))):
                return [{"profile_id": str(pid)}]
            return default if default is not None else []
        # chain_message_polls thread_id lookup
        if "chain_message_polls" in sql and "thread_id" in sql and "WHERE id" in sql:
            return [{"thread_id": TID, "id": params[0]}]
        # poll options and votes — return empty
        if "chain_message_poll_options" in sql or "chain_message_poll_votes" in sql:
            return default if default is not None else []
        # live_location_shares ownership check
        if "chain_live_location_shares" in sql and "sender_profile_id" in sql:
            return default if default is not None else []
    return default if default is not None else []

_mfs.fast_query = _fake_fast_query
_tss.fast_query = _fake_fast_query

# Register PID_A and PID_B as members of TID
_known_members[(TID, PID_A)] = True
_known_members[(TID, PID_B)] = True

with app.test_request_context('/', headers={"Cookie": "session=test"}):
    with client.session_transaction() as sess:
        sess["profile_id"] = PID_EVE
        sess["auth_user_id"] = "auth-" + PID_EVE

    print("\n=== PHASE 53 — SECURITY HARDENING ===\n")

    print("--- 1. POLL SECURITY ---")

    resp = client.post("/messages/api/poll/create", json={
        "thread_id": TID, "question": "Test?", "options": ["A", "B"]
    })
    check("unauthorized poll create blocked", resp.status_code == 403, str(resp.status_code))

    resp = client.post(f"/messages/api/poll/{POLL_ID}/vote", json={
        "option_id": OPTION_ID
    })
    check("unauthorized poll vote blocked", resp.status_code == 403, str(resp.status_code))

    resp = client.get(f"/messages/api/poll/{POLL_ID}/results")
    check("unauthorized poll results blocked", resp.status_code == 403, str(resp.status_code))

    print("--- 2. LOCATION SECURITY ---")

    resp = client.post("/messages/api/location/share", json={
        "thread_id": TID, "latitude": 40.71, "longitude": -74.01
    })
    check("unauthorized location share blocked", resp.status_code == 403, str(resp.status_code))

    resp = client.post("/messages/api/location/stop", json={
        "share_id": SHARE_ID
    })
    check("unauthorized location stop blocked", resp.status_code == 403, str(resp.status_code))

    print("--- 3. DISAPPEARING MESSAGES ---")

    resp = client.post(f"/messages/api/thread/{TID}/disappearing", json={
        "timer_seconds": 86400
    })
    check("unauthorized disappearing timer blocked", resp.status_code == 403, str(resp.status_code))

    resp = client.get(f"/messages/api/thread/{TID}/disappearing/settings")
    check("unauthorized disappearing settings blocked", resp.status_code == 403, str(resp.status_code))

    print("--- 4. THREAD SEARCH ---")

    resp = client.get(f"/messages/api/thread/{TID}/search?q=hello")
    check("unauthorized thread search blocked", resp.status_code == 403, str(resp.status_code))

    print("--- 5. AI TOOLS ---")

    resp = client.post("/messages/api/chat/ai/summarize", json={
        "thread_id": TID
    })
    check("unauthorized AI summarize blocked", resp.status_code == 403, str(resp.status_code))

    resp = client.post("/messages/api/chat/ai/find-important", json={
        "thread_id": TID
    })
    check("unauthorized AI find-important blocked", resp.status_code == 403, str(resp.status_code))

    resp = client.post("/messages/api/chat/ai/suggest-reply", json={
        "thread_id": TID, "context": "Hi"
    })
    check("unauthorized AI suggest-reply blocked", resp.status_code == 403, str(resp.status_code))

    print("--- 6. HD MEDIA ---")

    resp = client.post("/messages/api/messages/send-hd", json={
        "thread_id": TID, "media_url": "https://example.com/img.jpg"
    })
    check("unauthorized send-hd blocked", resp.status_code == 403, str(resp.status_code))

    print("--- 7. AUTHORIZED ACCESS ALLOWED ---")

    # Now test that PID_A (a member) gets 200, not 403
    with client.session_transaction() as sess:
        sess["profile_id"] = PID_A
        sess["auth_user_id"] = "auth-" + PID_A

    # HD media — should succeed since PID_A is a member
    resp = client.post("/messages/api/messages/send-hd", json={
        "thread_id": TID, "media_url": "https://example.com/img.jpg"
    })
    check("authorized send-hd returns 200", resp.status_code == 200, str(resp.status_code))

    # Poll create — should succeed
    resp = client.post("/messages/api/poll/create", json={
        "thread_id": TID, "question": "Test?", "options": ["A", "B"]
    })
    check("authorized poll create returns 200", resp.status_code == 200, str(resp.status_code))

    # Location share — should succeed
    resp = client.post("/messages/api/location/share", json={
        "thread_id": TID, "latitude": 40.71, "longitude": -74.01
    })
    check("authorized location share returns 200", resp.status_code == 200, str(resp.status_code))

    # Disappearing — should succeed
    resp = client.post(f"/messages/api/thread/{TID}/disappearing", json={
        "timer_seconds": 86400
    })
    check("authorized disappearing returns 200", resp.status_code == 200, str(resp.status_code))

    # Thread search — should succeed
    resp = client.get(f"/messages/api/thread/{TID}/search?q=hello")
    check("authorized thread search returns 200", resp.status_code == 200, str(resp.status_code))

    # AI summarize — should succeed
    resp = client.post("/messages/api/chat/ai/summarize", json={
        "thread_id": TID
    })
    check("authorized AI summarize returns 200", resp.status_code == 200, str(resp.status_code))

    # AI suggest-reply — should succeed
    resp = client.post("/messages/api/chat/ai/suggest-reply", json={
        "thread_id": TID, "context": "Hi"
    })
    check("authorized AI suggest-reply returns 200", resp.status_code == 200, str(resp.status_code))

    # Disappearing settings — should succeed
    resp = client.get(f"/messages/api/thread/{TID}/disappearing/settings")
    check("authorized disappearing settings returns 200", resp.status_code == 200, str(resp.status_code))

    print("\n=== SUMMARY ===")
    print(f"  PASS: {PASS}/{PASS+FAIL}  FAIL: {FAIL}/{PASS+FAIL}")
    if FAIL:
        print("  ❌ Some security tests failed!")
    else:
        print("  ✅ All Phase 53 security hardening tests passed!")
    sys.exit(FAIL)
