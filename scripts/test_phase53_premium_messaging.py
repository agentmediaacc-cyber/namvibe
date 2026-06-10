"""
Phase 53 E2E: Premium Messaging — Voice Transcription, HD Media, Scheduled Messages,
Polls, Live Location, Wallet, AI Chat Tools, Thread Search, Disappearing Messages, UI/UX.
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
from services.neon_service import get_pool_status, fast_query, write_query

_MESSAGES = {}
_THREADS = {}
_KNOWN_MEMBERS = {}

def _db_true():
    return False
if hasattr(_mfs, '_db_available'): _mfs._db_available = _db_true
if hasattr(_mds, '_db_available'): _mds._db_available = _db_true

PASS = 0; FAIL = 0
def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {label}"); PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else "")); FAIL += 1

PID_A = str(uuid_mod.uuid4())
PID_B = str(uuid_mod.uuid4())
TID = None
MSG_ID = None

def setup():
    global TID, MSG_ID
    TID = str(uuid_mod.uuid4())
    _THREADS[TID] = {"id": TID, "members": [PID_A, PID_B]}
    mid = str(uuid_mod.uuid4())
    _MESSAGES[mid] = {"id": mid, "message_id": mid, "thread_id": TID,
        "sender_profile_id": PID_A, "body": "Phase 53 test",
        "delivery_status": "sent", "created_at": "2026-06-10T00:00:00Z",
        "message_type": "text", "media_url": None, "media_quality": "standard"}
    MSG_ID = mid

client = app.test_client()

# Patch DB availability for _safe_write/_safe_query
_mfs._db_available = lambda: False
if hasattr(_mds, '_db_available'):
    _mds._db_available = lambda: False

def _fake_fast_query(sql, params=None, timeout_ms=2000, default=None):
    # Membership check — return member row for known threads
    if params and len(params) >= 2 and "chain_thread_members" in sql and "profile_id" in sql:
        tid, pid = str(params[0]), str(params[1])
        if _KNOWN_MEMBERS.get((tid, pid)):
            return [{"profile_id": pid}]
    # Poll thread_id lookup — return known thread_id
    if params and "chain_message_polls" in sql and "thread_id" in str(sql) and "WHERE id" in str(sql):
        return [{"thread_id": TID}]
    # Live location ownership — return row for PID_A
    if params and "chain_live_location_shares" in sql and "sender_profile_id" in sql:
        if len(params) >= 2 and str(params[1]) == PID_A:
            return [{"id": str(params[0])}]
    return default if default is not None else []
_mfs.fast_query = _fake_fast_query
_tss.fast_query = _fake_fast_query

setup()
# Register PID_A as a member of the test thread
_KNOWN_MEMBERS[(TID, PID_A)] = True

# =========== TESTS ===========

with app.test_request_context('/', headers={"Cookie": "session=test"}):
    # Login simulation
    with client.session_transaction() as sess:
        sess["profile_id"] = PID_A
        sess["auth_user_id"] = "auth-" + PID_A

    print("\n=== PHASE 53 — PREMIUM MESSAGING ===\n")

    # 1. Route Audit — no duplicates
    print("--- 1. ROUTE AUDIT ---")
    from scripts.audit_chain_routes import audit
    result = audit()
    check("no duplicate routes", not result.get("duplicates"),
          str(result.get("duplicates", [])))
    check("no missing templates", not result.get("missing_templates"))
    check("no broken imports", not result.get("broken_imports"))

    # 2. Voice Transcription Button
    print("\n--- 2. VOICE TRANSCRIPTION ---")
    resp = client.post(f"/messages/api/messages/{MSG_ID}/transcribe")
    data = resp.get_json() or {}
    check("transcribe endpoint returns 200", resp.status_code == 200)
    check("transcribe response has transcript", data.get("transcript") is not None)

    # 3. HD Media Options
    print("\n--- 3. HD MEDIA ---")
    resp = client.post("/messages/api/messages/send-hd", json={
        "thread_id": TID, "media_url": "https://example.com/photo.jpg",
        "quality": "hd", "file_size": 2048576, "file_name": "photo.jpg"
    })
    data = resp.get_json() or {}
    check("send-hd endpoint returns 200", resp.status_code == 200)
    check("send-hd quality is hd", data.get("quality") == "hd")
    check("send-hd has message_id", bool(data.get("message_id")))

    resp = client.post("/messages/api/messages/send-hd", json={
        "thread_id": TID, "media_url": "https://example.com/video.mp4",
        "quality": "original", "file_size": 52428800, "file_name": "video.mp4"
    })
    data = resp.get_json() or {}
    check("send-hd original quality works", data.get("quality") == "original")

    resp = client.post("/messages/api/messages/send-hd", json={
        "thread_id": TID, "media_url": "https://example.com/img.jpg",
        "quality": "standard"
    })
    data = resp.get_json() or {}
    check("send-hd standard quality works", data.get("quality") == "standard")

    # 4. Scheduled Message UI + Migration
    print("\n--- 4. SCHEDULED MESSAGES ---")
    resp = client.post(f"/messages/api/threads/{TID}/schedule", json={
        "body": "Scheduled test", "scheduled_for": "2026-06-11T10:00:00Z"
    })
    data = resp.get_json() or {}
    check("schedule endpoint returns 200", resp.status_code == 200)
    check("schedule succeeded", data.get("ok") or data.get("success", False))

    # Check SQL migration file exists
    sql_path = os.path.join(os.path.dirname(__file__), "..", "sql", "phase53_premium_messaging.sql")
    check("SQL migration file exists", os.path.exists(sql_path))
    with open(sql_path) as f:
        sql_content = f.read()
        check("SQL has chain_scheduled_messages", "chain_scheduled_messages" in sql_content)
        check("SQL uses IF NOT EXISTS", "IF NOT EXISTS" in sql_content)

    # 5. Poll UI + Migration
    print("\n--- 5. POLL MESSAGES ---")
    resp = client.post("/messages/api/poll/create", json={
        "thread_id": TID, "question": "Best framework?",
        "options": ["React", "Vue", "Svelte", "Solid"],
        "allow_multiple": False
    })
    data = resp.get_json() or {}
    check("poll create returns 200", resp.status_code == 200)
    check("poll created ok", data.get("ok", False))
    check("poll has question", data.get("poll", {}).get("question") == "Best framework?")
    check("poll has 4 options", len(data.get("poll", {}).get("options", [])) == 4)

    POLL_ID = data.get("poll", {}).get("id", "")
    OPTION_ID = data.get("poll", {}).get("options", [{}])[0].get("id", "")

    resp = client.post(f"/messages/api/poll/{POLL_ID}/vote", json={
        "option_id": OPTION_ID
    })
    data = resp.get_json() or {}
    check("poll vote returns 200", resp.status_code == 200)

    resp = client.get(f"/messages/api/poll/{POLL_ID}/results")
    data = resp.get_json() or {}
    check("poll results returns 200", resp.status_code == 200)
    check("poll results have options", data.get("options") is not None)

    check("SQL has chain_message_polls", "chain_message_polls" in sql_content)
    check("SQL has chain_message_poll_options", "chain_message_poll_options" in sql_content)
    check("SQL has chain_message_poll_votes", "chain_message_poll_votes" in sql_content)

    # 6. Live Location Sharing
    print("\n--- 6. LIVE LOCATION SHARING ---")
    resp = client.post("/messages/api/location/share", json={
        "thread_id": TID, "latitude": 40.7128, "longitude": -74.0060,
        "duration_minutes": 15
    })
    data = resp.get_json() or {}
    check("location share returns 200", resp.status_code == 200)
    check("location share ok", data.get("ok", False))
    SHARE_ID = data.get("share_id", "")

    resp = client.post("/messages/api/location/stop", json={
        "share_id": SHARE_ID
    })
    data = resp.get_json() or {}
    check("location stop returns 200", resp.status_code == 200)
    check("location stop ok", data.get("ok", False))

    check("SQL has chain_live_location_shares", "chain_live_location_shares" in sql_content)

    # 7. Wallet Chat Actions
    print("\n--- 7. WALLET IN CHAT ---")
    resp = client.post("/messages/api/wallet/send", json={
        "thread_id": TID, "recipient_profile_id": PID_B,
        "amount": 100, "note": "Thanks!"
    })
    data = resp.get_json() or {}
    check("wallet send returns 200", resp.status_code == 200)
    check("wallet send safe disabled", data.get("error") is not None)

    resp = client.post("/messages/api/wallet/request", json={
        "thread_id": TID, "recipient_profile_id": PID_B,
        "amount": 50
    })
    data = resp.get_json() or {}
    check("wallet request returns 200", resp.status_code == 200)

    resp = client.post("/messages/api/wallet/tip", json={
        "thread_id": TID, "recipient_profile_id": PID_B,
        "amount": 25
    })
    data = resp.get_json() or {}
    check("wallet tip returns 200", resp.status_code == 200)

    resp = client.post("/messages/api/wallet/split", json={
        "thread_id": TID, "amount": 200
    })
    data = resp.get_json() or {}
    check("wallet split returns 200", resp.status_code == 200)

    # 8. AI Chat Tools
    print("\n--- 8. AI CHAT TOOLS ---")
    resp = client.post("/messages/api/chat/ai/summarize", json={
        "thread_id": TID
    })
    data = resp.get_json() or {}
    check("ai summarize returns 200", resp.status_code == 200)
    check("ai summarize has summary/note", data.get("summary") is not None or data.get("note") is not None)

    resp = client.post("/messages/api/chat/ai/find-important", json={
        "thread_id": TID
    })
    data = resp.get_json() or {}
    check("ai find-important returns 200", resp.status_code == 200)

    resp = client.post("/messages/api/chat/ai/suggest-reply", json={
        "thread_id": TID, "context": "Hello!"
    })
    data = resp.get_json() or {}
    check("ai suggest-reply returns 200", resp.status_code == 200)

    resp = client.post("/messages/api/chat/ai/translate", json={
        "message_id": MSG_ID, "target_language": "es"
    })
    data = resp.get_json() or {}
    check("ai translate returns 200", resp.status_code == 200)

    # 9. Thread Search
    print("\n--- 9. MESSAGE SEARCH ---")
    resp = client.get(f"/messages/api/thread/{TID}/search?q=test")
    data = resp.get_json() or {}
    check("thread search returns 200", resp.status_code == 200)
    check("thread search has messages", data.get("messages") is not None)

    # 10. Disappearing Messages UI
    print("\n--- 10. DISAPPEARING MESSAGES ---")
    resp = client.post(f"/messages/api/thread/{TID}/disappearing", json={
        "timer_seconds": 86400
    })
    data = resp.get_json() or {}
    check("disappearing set returns 200", resp.status_code == 200)
    check("disappearing set ok", data.get("ok", False))
    check("disappearing timer is 86400", data.get("timer_seconds") == 86400)
    check("disappearing enabled", data.get("enabled") == True)

    resp = client.post(f"/messages/api/thread/{TID}/disappearing", json={
        "timer_seconds": 0
    })
    data = resp.get_json() or {}
    check("disappearing off works", data.get("timer_seconds") == 0)
    check("disappearing disabled", data.get("enabled") == False)

    resp = client.get(f"/messages/api/thread/{TID}/disappearing/settings")
    data = resp.get_json() or {}
    check("disappearing settings returns 200", resp.status_code == 200)

    check("SQL has chain_thread_disappearing_settings",
          "chain_thread_disappearing_settings" in sql_content)

    # 11. UI/UX — Plus Menu elements exist
    print("\n--- 11. UI/UX CHECKS ---")
    try:
        with open(os.path.join(os.path.dirname(__file__), "..",
                  "templates", "messages", "thread.html")) as f:
            html = f.read()
        check("plus menu exists", "plus-menu" in html)
        check("poll creator exists", "poll-creator" in html)
        check("schedule picker exists", "schedule-picker" in html)
        check("wallet actions exist", "wallet-actions" in html)
        check("AI tools panel exists", "ai-tools-panel" in html)
        check("disappearing timer exists", "d-timer-menu" in html)
        check("thread search bar exists", "thread-search-bar" in html)
        check("HD selector exists", "hd-selector" in html)
        check("transcribe button exists", "transcribe-btn" in html)
        check("auto-reply templates exist", "auto-reply-btn" in html)
        # safe-area CSS lives in chat.css, verified in CSS checks below
        check("44px touch targets", "min-height: 44" in html or "44px" in html)
    except Exception as e:
        check("read thread.html", False, str(e))

    # 12. CSS checks
    print("\n--- 12. CSS CHECKS ---")
    try:
        with open(os.path.join(os.path.dirname(__file__), "..",
                  "static", "css", "chat.css")) as f:
            css = f.read()
        check("PHASE 53 CSS section exists", "PHASE 53" in css)
        check("plus-menu CSS", ".plus-menu" in css)
        check("poll-card CSS", ".poll-card" in css)
        check("d-timer-menu CSS", ".d-timer-menu" in css)
        check("live-location-card CSS", ".live-location-card" in css)
        check("wallet-action CSS", ".wallet-action" in css)
        check("ai-tools-grid CSS", ".ai-tools-grid" in css)
        check("hd-badge CSS", ".hd-badge" in css)
        check("hd-selector CSS", ".hd-selector" in css)
        check("transcribe-btn CSS", ".transcribe-btn" in css)
        check("thread-search-bar CSS", ".thread-search-bar" in css)
        check("schedule-picker CSS", ".schedule-picker" in css)
        check("safe-area CSS", "safe-area-inset-bottom" in css)
    except Exception as e:
        check("read chat.css", False, str(e))

    # 13. Socket events
    print("\n--- 13. SOCKET EVENTS ---")
    try:
        with open(os.path.join(os.path.dirname(__file__), "..",
                  "services", "socket_events.py")) as f:
            se = f.read()
        check("transcribe:voice socket event", "transcribe:voice" in se)
        check("live_location:update socket event", "live_location:update" in se)
        check("live_location:stop socket event", "live_location:stop" in se)
        check("poll:vote socket event", "poll:vote" in se)
        check("disappearing:set socket event", "disappearing:set" in se)
        check("chat:ai-summarize socket event", "chat:ai-summarize" in se)
        check("chat:ai-suggest socket event", "chat:ai-suggest" in se)
        check("PHASE 53 section in socket_events", "PHASE 53" in se)
    except Exception as e:
        check("read socket_events.py", False, str(e))

    # 14. API Routes exist
    print("\n--- 14. API ROUTES ---")
    try:
        with open(os.path.join(os.path.dirname(__file__), "..",
                  "api_routes", "message_routes.py")) as f:
            ar = f.read()
        check("/api/messages/<message_id>/transcribe route", "api_transcribe" in ar)
        check("/api/messages/send-hd route", "api_send_hd" in ar)
        check("/api/poll/create route", "api_poll_create" in ar)
        check("/api/poll/<poll_id>/vote route", "api_poll_vote" in ar)
        check("/api/poll/<poll_id>/results route", "api_poll_results" in ar)
        check("/api/location/share route", "api_location_share" in ar)
        check("/api/location/stop route", "api_location_stop" in ar)
        check("/api/wallet/send route", "api_wallet_send" in ar)
        check("/api/wallet/request route", "api_wallet_request" in ar)
        check("/api/wallet/tip route", "api_wallet_tip" in ar)
        check("/api/wallet/split route", "api_wallet_split" in ar)
        check("/api/chat/ai/summarize route", "api_ai_summarize" in ar)
        check("/api/chat/ai/find-important route", "api_ai_find_important" in ar)
        check("/api/chat/ai/suggest-reply route", "api_ai_suggest_reply" in ar)
        check("/api/chat/ai/translate route", "api_ai_translate" in ar)
        check("/api/thread/<thread_id>/disappearing route", "api_disappearing" in ar)
        check("/api/thread/<thread_id>/search route", "api_thread_search" in ar)
        check("PHASE 53 section in routes", "PHASE 53" in ar)
    except Exception as e:
        check("read message_routes.py", False, str(e))

    # 15. Feature service functions exist
    print("\n--- 15. BACKEND SERVICE ---")
    try:
        with open(os.path.join(os.path.dirname(__file__), "..",
                  "services", "message_feature_service.py")) as f:
            fs = f.read()
        check("transcribe_voice_note function", "transcribe_voice_note" in fs)
        check("send_hd_media function", "send_hd_media" in fs)
        check("create_poll function", "create_poll" in fs)
        check("vote_poll function", "vote_poll" in fs)
        check("get_poll_results function", "get_poll_results" in fs)
        check("share_live_location function", "share_live_location" in fs)
        check("stop_live_location function", "stop_live_location" in fs)
        check("wallet_send function", "wallet_send" in fs)
        check("wallet_request function", "wallet_request" in fs)
        check("wallet_tip function", "wallet_tip" in fs)
        check("wallet_split function", "wallet_split" in fs)
        check("ai_summarize function", "ai_summarize" in fs)
        check("ai_find_important function", "ai_find_important" in fs)
        check("ai_suggest_reply function", "ai_suggest_reply" in fs)
        check("ai_translate function", "ai_translate" in fs)
        check("set_disappearing_timer function", "set_disappearing_timer" in fs)
        check("search_thread_messages function", "search_thread_messages" in fs)
        check("get_disappearing_settings function", "get_disappearing_settings" in fs)
        check("PHASE 53 section in service", "PHASE 53" in fs)
    except Exception as e:
        check("read message_feature_service.py", False, str(e))

    print(f"\n=== SUMMARY ===")
    print(f"  PASS: {PASS}/{PASS+FAIL}  FAIL: {FAIL}/{PASS+FAIL}")
    if FAIL:
        print("  ❌ Some Phase 53 tests failed!")
    else:
        print("  ✅ All Phase 53 E2E tests passed!")
    raise SystemExit(0 if FAIL == 0 else 1)
