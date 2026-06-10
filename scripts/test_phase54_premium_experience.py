"""
Phase 54 Premium Experience regression checks.

Audits the messaging/calls UI, safe fallback routes, migration file,
thread-security gates, cleanup script, and duplicate Flask routes.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_TEST_FAKE_DB"] = "1"
os.environ["CHAIN_TRUST_PROFILE_SCHEMA"] = "1"

PASS = 0
FAIL = 0


def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {label}")
        PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" - {detail}" if detail else ""))
        FAIL += 1


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


print("\n=== PHASE 54 — PREMIUM MESSAGING, CALLS, WALLET, AI ===\n")

thread_html = read("templates/messages/thread.html")
chat_css = read("static/css/chat.css")
webrtc_js = read("static/js/webrtc_calls.js")
group_call = read("templates/calls/group_call.html")
message_routes = read("api_routes/message_routes.py")
message_service = read("services/message_feature_service.py")
call_service = read("services/webrtc_call_service.py")
socket_events = read("services/socket_events.py")

print("--- 1. UI FEATURES ---")
check("voice transcript UI exists", all(s in thread_html for s in ["Transcribe", "Copy transcript", "Hide/show transcript", "Transcription not available yet"]))
check("translation UI exists", all(s in thread_html for s in ["translateMessage", "English", "Oshiwambo", "Afrikaans", "Portuguese", "French", "Replace the message text"]))
check("scheduled full UX exists", all(s in thread_html for s in ["Schedule", "Scheduled messages", "Edit time", "Cancel", "scheduled-preview"]))
check("HD media selector exists", all(s in thread_html for s in ["Standard", "HD", "Original", "Estimated", "Warning: above 50MB"]))
check("wallet chat cards exist", all(s in thread_html for s in ["Send money", "Request money", "Tip creator", "Split bill", "Wallet transfer route not connected yet"]))
check("AI message search exists", all(s in thread_html for s in ["Find location", "Find money", "Find photos", "Find voice notes", "Find links", "search-highlight"]))
check("unread summary UI exists", "Summarize unread messages" in thread_html and "unread-summary" in thread_html)
check("share as story/post exists", "shareAsStory" in thread_html and "shareAsPost" in thread_html)
check("quote selected message exists", "Quote selected message" in thread_html and "Copy selected message quote" in thread_html)

print("\n--- 2. CALL UX ---")
call_text = webrtc_js + "\n" + thread_html + "\n" + group_call + "\n" + chat_css
check("PiP call UI exists", "picture-in-picture" in call_text and "toggleCallPiP" in call_text)
check("network quality indicator exists", all(s in call_text for s in ["Good", "Weak", "Reconnecting", "Failed", "phase54-network-quality"]))
check("reconnect overlay exists", "reconnecting-overlay" in call_text or "gc-reconnect-overlay" in call_text)
check("call duration and controls exist", all(s in call_text for s in ["call-timer", "toggleMute", "toggleCamera", "toggleSpeaker", "End this call?"]))
check("missed call reasons exist", all(s in call_service for s in ["not_answered", "busy", "offline", "cancelled", "failed", "MISSED_CALL_REASONS"]))

print("\n--- 3. BACKEND ROUTES AND HELPERS ---")
check("scheduled list route exists", "/api/threads/<thread_id>/scheduled" in message_routes)
check("scheduled cancel route exists", "/api/scheduled/<scheduled_id>/cancel" in message_routes)
check("scheduled edit route exists", "/api/scheduled/<scheduled_id>/edit" in message_routes)
check("unread summary route exists", "/api/chat/ai/unread-summary" in message_routes)
check("share route exists", "/api/messages/<message_id>/share/<surface>" in message_routes)
check("translation route is gated", "api_ai_translate" in message_routes and "can_access_thread(profile_id, thread_id)" in message_routes)
check("wallet actions are safe disabled", "Wallet transfer route not connected yet." in message_service)
check("disappearing cleanup helper exists", all(s in message_service for s in ["find_expired_disappearing_messages", "mark_disappearing_messages_expired", "run_disappearing_message_cleanup"]))
check("disappearing cleanup script exists", os.path.isfile("scripts/run_disappearing_message_cleanup.py"))

print("\n--- 4. SQL AND SECURITY ---")
sql_path = "sql/phase54_premium_messaging_calls.sql"
check("phase54 SQL exists", os.path.isfile(sql_path))
sql = read(sql_path)
check("phase54 SQL idempotent", "IF NOT EXISTS" in sql)
check("SQL has transcript fields", "transcript" in sql and "transcript_available" in sql)
check("SQL has scheduled cancel fields", "cancelled_at" in sql and "cancelled_by_profile_id" in sql and "cancel_reason" in sql)
check("SQL has disappearing expired fields", "expired_at" in sql and "deletion_reason" in sql)
check("SQL has call quality fields", "network_quality" in sql and "missed_reason" in sql)
check("SQL has useful indexes", all(s in sql for s in ["idx_phase54_scheduled_pending", "idx_phase54_messages_expiring", "idx_phase54_live_location_active", "idx_phase54_messages_search"]))
check("thread security used", "from services.thread_security_service import can_access_thread" in message_routes and message_routes.count("can_access_thread") >= 12)
check("socket call quality still present", "call:quality" in socket_events and "call:reconnecting" in socket_events)

print("\n--- 5. ROUTE AUDIT ---")
from app import create_app

app = create_app()
seen = {}
duplicates = []
for rule in app.url_map.iter_rules():
    key = (rule.rule, tuple(sorted(rule.methods - {"HEAD", "OPTIONS"})))
    if key in seen:
        duplicates.append((rule.rule, seen[key], rule.endpoint))
    else:
        seen[key] = rule.endpoint
check("no duplicate routes", not duplicates, str(duplicates[:5]))

print("\n=== SUMMARY ===")
total = PASS + FAIL
print(f"  PASS: {PASS}/{total}  FAIL: {FAIL}/{total}")
if FAIL:
    print("  Phase 54 premium experience checks failed.")
sys.exit(FAIL)
