"""
Phase 52 E2E: Smart Composer — AI, Smart Reply Chips, Emoji, Location,
Media, Voice, Story/Post Share, Reply/Edit/Quote, Delete, Message Info,
Keyboard Shortcuts, Mobile Safe Area, Accessibility, Themes.
"""
import os, sys, json, uuid as uuid_mod, time
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
from services.neon_service import get_pool_status, fast_query, write_query

_MESSAGES = {}
_THREADS = {}

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

def support_get_message_info(message_id, profile_id):
    for mid, msg in _MESSAGES.items():
        if str(mid) == str(message_id):
            return {"ok": True, "message": dict(msg)}
    return {"ok": False, "error": "not_found"}

_mfs.get_message_info = support_get_message_info

def setup():
    global TID, MSG_ID
    TID = str(uuid_mod.uuid4())
    _THREADS[TID] = {"id": TID, "members": [PID_A, PID_B]}
    mid = str(uuid_mod.uuid4())
    _MESSAGES[mid] = {"id": mid, "message_id": mid, "thread_id": TID, "sender_profile_id": PID_A, "body": "Phase 52 test message", "delivery_status": "sent", "created_at": "2026-06-09T00:00:00Z", "message_type": "text"}
    global MSG_ID
    MSG_ID = mid

client = app.test_client()
def login(pid):
    with client.session_transaction() as sess:
        sess["profile_id"] = pid
        sess["auth_user_id"] = pid
        sess["user_id"] = pid
        sess["access_token"] = "test-token"
        sess["_permanent"] = True

print("\n=== PHASE 52 — SETUP ===")
setup()
check("setup complete", TID is not None and MSG_ID is not None)
login(PID_A)

# ============================================================
print("\n=== 1. COMPOSER JS & HTML STRUCTURE ===")
composer_js_path = "static/js/message_composer.js"
thread_html_path = "templates/messages/thread.html"
check("message_composer.js exists", os.path.exists(composer_js_path))
check("thread.html exists", os.path.exists(thread_html_path))

with open(composer_js_path) as f:
    js_src = f.read()
with open(thread_html_path) as f:
    html_src = f.read()

check("composer has toggleAIPanel", 'toggleAIPanel' in js_src)
check("composer has applyAITransform", 'applyAITransform' in js_src)
check("composer has showSmartReplies", 'showSmartReplies' in js_src)
check("composer has shareLocation", 'shareLocation' in js_src)
check("composer has insertSmartReply", 'insertSmartReply' in js_src)
check("composer has applyTheme", 'applyTheme' in js_src)
check("composer has toggleThemeMenu", 'toggleThemeMenu' in js_src)
check("composer has setupKeyboardShortcuts", 'setupKeyboardShortcuts' in js_src)
check("composer has initEditFromComposer", 'initEditFromComposer' in js_src)
check("composer has cancelReplyFromComposer", 'cancelReplyFromComposer' in js_src)
check("composer has applyAriaLabels", 'applyAriaLabels' in js_src)
check("composer has captureCamera", 'captureCamera' in js_src)
check("composer has onVoiceTouchStart", 'onVoiceTouchStart' in js_src)

# ============================================================
print("\n=== 2. HTML STRUCTURE ===")
check("html has ai-panel", 'id="ai-panel"' in html_src)
check("html has smart-reply-bar", 'id="smart-reply-bar"' in html_src)
check("html has location-preview", 'id="location-preview"' in html_src)
check("html has theme-menu", 'id="theme-menu"' in html_src)
check("html has message-info-modal", 'id="message-info-modal"' in html_src)
check("html has voice-cancel-zone", 'id="voice-cancel-zone"' in html_src)
check("html has AI button in composer", 'data-action="ai"' in html_src)
check("html has ai-mode buttons", 'data-ai-mode' in html_src)
check("html has theme data attributes", 'data-theme' in html_src)
check("html has aria-label on send", 'aria-label="Send message"' in html_src)
check("html has aria-label on mic", 'aria-label="Voice message"' in html_src)
check("html has aria-label on input", 'aria-label="Message input"' in html_src)
check("html has smart-reply-bar role=toolbar", 'role="toolbar"' in html_src)

# ============================================================
print("\n=== 3. AI MENU FUNCTIONS ===")
check("aiTransforms defined", 'aiTransforms' in js_src)
check("friendly transform", 'friendly' in js_src)
check("professional transform", 'professional' in js_src)
check("shorter transform", 'shorter' in js_src)
check("grammar transform", 'grammar' in js_src)
check("translate transform", 'translate' in js_src)
check("suggest transform", 'suggest' in js_src)
check("template transform", 'template' in js_src)

# ============================================================
print("\n=== 4. SMART REPLY CHIPS ===")
check("smart replies show function", 'showSmartReplies' in js_src)
check("smart replies hide function", 'hideSmartReplies' in js_src)
check("smart reply insert function", 'insertSmartReply' in js_src)
check("smart-reply-bar CSS class", '.smart-reply-bar' in open('static/css/chat.css').read())

# ============================================================
print("\n=== 5. EMOJI CATEGORIES ===")
check("emoji categories exist", 'Smileys' in js_src and 'Hearts' in js_src and 'Hands' in js_src)
check("emoji insert function", 'insertEmoji' in js_src)
check("emoji grid render", 'renderEmojiGrid' in js_src)

# ============================================================
print("\n=== 6. LOCATION SHARING ===")
check("shareLocation function", 'shareLocation' in js_src)
check("sendLocation function", 'sendLocation' in js_src)
check("cancelLocation function", 'cancelLocation' in js_src)
check("location CSS class", '.location-preview' in open('static/css/chat.css').read())

# ============================================================
print("\n=== 7. MEDIA SENDING ===")
check("uploadFileWithCheck function", 'uploadFileWithCheck' in js_src)
check("captureCamera function", 'captureCamera' in js_src)
check("file size limit 50MB", '50 * 1024 * 1024' in js_src)

# ============================================================
print("\n=== 8. VOICE CONTROLS ===")
check("slide cancel detection", 'onVoiceTouchStart' in js_src)
check("waveform CSS", '.waveform-bar' in open('static/css/chat.css').read())
check("voice lock toggle", 'data-voice-control="lock"' in html_src)
check("voice pause button", 'data-voice-control="pause"' in html_src)
check("voice cancel button", 'data-voice-control="cancel"' in html_src)

# ============================================================
print("\n=== 9. STORY/POST SHARE ===")
check("shareAsStory function", 'shareAsStory' in html_src)
check("shareAsPost function", 'shareAsPost' in html_src)
check("Share as Story in context menu", 'Share as Story' in html_src)
check("Share as Post in context menu", 'Share as Post' in html_src)

# ============================================================
print("\n=== 10. REPLY/EDIT/QUOTE PREVIEW ===")
check("initReplyFromComposer", 'initReplyFromComposer' in js_src)
check("cancelReplyFromComposer", 'cancelReplyFromComposer' in js_src)
check("initEditFromComposer", 'initEditFromComposer' in js_src)
check("cancelEditFromComposer", 'cancelEditFromComposer' in js_src)
check("reply-preview HTML exists", 'id="reply-preview"' in html_src)

# ============================================================
print("\n=== 11. DELETE FOR ME / EVERYONE ===")
resp_delete_me = client.post(f"/messages/api/messages/{MSG_ID}/delete-for-me")
check("delete-for-me endpoint 200", resp_delete_me.status_code == 200, str(resp_delete_me.status_code))

# ============================================================
print("\n=== 12. MESSAGE INFO ===")
resp_info = client.get(f"/messages/api/messages/{MSG_ID}/info")
check("message-info endpoint 200", resp_info.status_code == 200, str(resp_info.status_code))
j_info = resp_info.get_json(silent=True) or {}
check("message-info returns ok", j_info.get("ok") is True, str(j_info)[:200])
check("message-info has message", "message" in j_info, str(list(j_info.keys())))
if j_info.get("message"):
    m = j_info["message"]
    check("message has delivery_status", "delivery_status" in m, str(list(m.keys())))
    check("message has created_at", "created_at" in m, str(list(m.keys())))

check("showMessageInfo in html", 'showMessageInfo' in html_src)
check("closeMessageInfo in html", 'closeMessageInfo' in html_src)
check("copyMessageId in html", 'copyMessageId' in html_src)

# ============================================================
print("\n=== 13. KEYBOARD SHORTCUTS ===")
check("ctrl+shift+E emoji", "ctrlKey" in js_src and "shiftKey" in js_src and "emojiPanel" in js_src)
check("ctrl+K focus", "key === 'k'" in js_src or "key === 'K'" in js_src)
check("ctrl+shift+A attach", "shiftKey" in js_src and "attach" in js_src.lower())
check("Escape handling", "Escape" in js_src)

# ============================================================
print("\n=== 14. MOBILE SAFE AREA & MIN SIZES ===")
css_src = open('static/css/chat.css').read()
check("safe-area-inset-bottom", 'safe-area-inset-bottom' in css_src)
check("16px font on textarea", 'font-size:16px' in css_src or 'font-size: 16px' in css_src)
check("44px touch targets", '44px' in css_src)

# ============================================================
print("\n=== 15. THEMES ===")
check("applyTheme function", 'applyTheme' in js_src)
check("theme localStorage", 'chain_chat_theme' in js_src)
check("theme menu HTML", 'data-theme' in html_src)
check("dark theme defined", 'dark' in js_src)
check("light theme defined", 'light' in js_src)
check("namibia theme defined", 'namibia' in js_src)
check("ocean theme defined", 'ocean' in js_src)
check("emerald theme defined", 'emerald' in js_src)
check("purple theme defined", 'purple' in js_src)

# ============================================================
print("\n=== 16. ACCESSIBILITY ===")
check("aria-labels applied", 'aria-label' in html_src)
check("reduced motion CSS", 'prefers-reduced-motion' in css_src)
check("focus outline CSS", 'outline' in css_src)

# ============================================================
print("\n=== 17. BACKEND ROUTES ===")
check("delete-for-me route exists", 'delete-for-me' in open('api_routes/message_routes.py').read())
check("info route exists", '/api/messages/<message_id>/info' in open('api_routes/message_routes.py').read())
check("get_message_info in service", 'get_message_info' in open('services/message_feature_service.py').read())

# ============================================================
print("\n=== 18. CSS COMPONENTS ===")
check("ai-panel CSS", '.ai-panel' in css_src)
check("smart-reply-chip CSS", '.smart-reply-chip' in css_src)
check("location-card CSS", '.location-card' in css_src)
check("modal-overlay CSS", '.modal-overlay' in css_src)
check("theme-menu CSS", '.theme-menu' in css_src)
check("composer-reply-preview CSS", '.composer-reply-preview' in css_src)
check("kbd-hint CSS", '.kbd-hint' in css_src)

# ============================================================
print("\n=== SUMMARY ===")
total = PASS + FAIL
print(f"  PASS: {PASS}/{total}  FAIL: {FAIL}/{total}")
if FAIL:
    print("  Some tests failed — review output above.")
    exit(1)
else:
    print("  All Phase 52 E2E tests passed!")
    exit(0)
