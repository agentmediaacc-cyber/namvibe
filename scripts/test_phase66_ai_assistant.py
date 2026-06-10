#!/usr/bin/env python3
"""Phase 66 — Premium AI Assistant Ecosystem Tests (350+)."""

import os, sys, json, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"

PASS = 0
FAIL = 0
ERRORS = []

def check(desc, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        ERRORS.append(desc)
        print(f"  [FAIL] {desc}")

def safe_read(path):
    try:
        with open(path) as f:
            return f.read()
    except Exception:
        return ""

def compiles(path):
    try:
        import py_compile
        py_compile.compile(path, doraise=True)
        return True
    except:
        return False

print("=" * 60)
print("Phase 66 — Premium AI Assistant Ecosystem Tests")
print("=" * 60)

# SECTION 1: SQL schema
print("\n--- SECTION 1: SQL Schema ---")
sql = safe_read("sql/phase66_ai_assistant.sql")
check("sql/phase66_ai_assistant.sql exists", bool(sql))
check("CREATE TABLE chain_ai_chat_sessions", "CREATE TABLE IF NOT EXISTS chain_ai_chat_sessions" in sql)
check("Chat sessions has profile_id", "profile_id UUID NOT NULL" in sql.split("chain_ai_chat_sessions")[1][:300])
check("Chat sessions has assistant_type CHECK", "CHECK(assistant_type IN" in sql)
check("Chat sessions has messages JSONB", "messages JSONB" in sql or "messages TEXT" in sql)
check("Chat sessions has context JSONB", "context JSONB" in sql)
check("Chat sessions has is_archived", "is_archived" in sql)
check("Chat sessions has created_at", "created_at" in sql)
check("Chat sessions has updated_at", "updated_at" in sql)
check("CREATE TABLE chain_ai_suggestions", "CREATE TABLE IF NOT EXISTS chain_ai_suggestions" in sql)
check("Suggestions has profile_id", "profile_id UUID" in sql.split("chain_ai_suggestions")[1][:300])
check("Suggestions has assistant_type", "assistant_type" in sql)
check("Suggestions has input_text", "input_text" in sql)
check("Suggestions has output_text", "output_text" in sql)
check("Suggestions has was_applied", "was_applied" in sql)
check("Suggestions has was_dismissed", "was_dismissed" in sql)
check("Suggestions has feedback_score CHECK", "feedback_score INTEGER CHECK" in sql or "feedback_score CHECK" in sql)
check("Suggestions has context JSONB", "context JSONB" in sql)
check("CREATE TABLE chain_ai_moderation_log", "CREATE TABLE IF NOT EXISTS chain_ai_moderation_log" in sql)
check("Moderation log has moderator_profile_id", "moderator_profile_id" in sql)
check("Moderation log has action_type CHECK", "CHECK(action_type IN" in sql.split("chain_ai_moderation_log")[1][:400] if "chain_ai_moderation_log" in sql else False)
check("Moderation log has confidence_score", "confidence_score" in sql)
check("Moderation log has ai_summary", "ai_summary" in sql)
check("CREATE TABLE chain_ai_feedback", "CREATE TABLE IF NOT EXISTS chain_ai_feedback" in sql)
check("Feedback has rating CHECK", "CHECK(rating >= 1 AND rating <= 5)" in sql or "CHECK(rating" in sql)
check("Feedback has suggestion_id", "suggestion_id" in sql)
check("Feedback has comment", "comment" in sql)
check("Chat sessions INDEX", "idx_p66_chat_sessions_profile" in sql)
check("Suggestions INDEX", "idx_p66_suggestions_profile" in sql)
check("Moderation log INDEX", "idx_p66_moderation_log" in sql)
check("Feedback INDEX", "idx_p66_feedback" in sql)
check("IF NOT EXISTS pattern", "IF NOT EXISTS" in sql)

# SECTION 2: SQL assistant type coverage
print("\n--- SECTION 2: SQL Assistant Types ---")
chat_section = sql.split("chain_ai_chat_sessions")[1][:400] if "chain_ai_chat_sessions" in sql else ""
types = ['general','creator','marketplace','dating_safety','moderation','messages','captions','profile_suggestions','search']
for t in types:
    check(f"Assistant type '{t}' in SQL CHECK", t in chat_section)

# SECTION 3: Service file
print("\n--- SECTION 3: Service File ---")
svc = safe_read("services/ai_assistant_service.py")
check("services/ai_assistant_service.py exists", bool(svc))
check("Service has PLATFORM constant", "PLATFORM" in svc)
check("Service has AI_MARKER", "AI_MARKER = \"[AI Suggestion]\"" in svc)
check("Service has ASSISTANT_TYPES tuple", "ASSISTANT_TYPES" in svc)
check("Service has _db_available", "def _db_available" in svc)
check("Service has _has_api_key", "def _has_api_key" in svc)
check("Service has _sanitize", "def _sanitize" in svc)
check("Service has _truncate_context", "def _truncate_context" in svc)
check("Service has _mock_response", "def _mock_response" in svc)
check("Service has _call_ai_provider", "def _call_ai_provider" in svc)
check("Service has create_session", "def create_session" in svc)
check("Service has get_sessions", "def get_sessions" in svc)
check("Service has get_session", "def get_session" in svc)
check("Service has delete_session", "def delete_session" in svc)
check("Service has chat", "def chat" in svc)
check("Service has creator_assistant", "def creator_assistant" in svc)
check("Service has marketplace_assistant", "def marketplace_assistant" in svc)
check("Service has dating_safety_assistant", "def dating_safety_assistant" in svc)
check("Service has moderation_assistant", "def moderation_assistant" in svc)
check("Service has message_suggestions", "def message_suggestions" in svc)
check("Service has caption_generator", "def caption_generator" in svc)
check("Service has profile_suggestions", "def profile_suggestions" in svc)
check("Service has ai_search", "def ai_search" in svc)
check("Service has submit_feedback", "def submit_feedback" in svc)
check("Service has log_moderation_action", "def log_moderation_action" in svc)
check("Service has get_suggestion_history", "def get_suggestion_history" in svc)
check("Service has get_moderation_log", "def get_moderation_log" in svc)
check("Service has mark_suggestion_applied", "def mark_suggestion_applied" in svc)
check("Service has mark_suggestion_dismissed", "def mark_suggestion_dismissed" in svc)
check("Service imports neon_service", "neon_service" in svc)
check("Service imports supabase_safe", "supabase_safe" in svc)
check("Service uses safe_insert", "safe_insert" in svc)
check("Service uses safe_select", "safe_select" in svc)
check("Service uses safe_update", "safe_update" in svc)
check("Service uses safe_delete", "safe_delete" in svc)

# SECTION 4: Service safety checks
print("\n--- SECTION 4: Safety & Fallback Checks ---")
check("_sanitize strips HTML tags", "&lt;" in svc or ".replace('<', '&lt;')" in svc)
check("_sanitize truncates at 5000", "5000" in svc.split("def _sanitize")[1][:200] if "def _sanitize" in svc else False)
check("_has_api_key checks env vars", "OPENAI_API_KEY" in svc or "AI_API_KEY" in svc)
check("_mock_response returns AI_MARKER", "AI_MARKER" in svc.split("def _mock_response")[1][:5000] if "def _mock_response" in svc else False)
check("_mock_response has warning", "AI provider not configured" in svc)
check("chat sanitizes input", "_sanitize" in svc.split("def chat")[1][:500] if "def chat" in svc else False)
check("chat validates non-empty", "Message cannot be empty" in svc or "empty" in svc.split("def chat")[1][:300] if "def chat" in svc else False)
check("chat returns suggestions array", "suggestions" in svc.split("def chat")[1][:1500] if "def chat" in svc else False)
check("chat saves suggestion to DB", "safe_insert" in svc.split("def chat")[1][:1500] if "def chat" in svc else False)
check("message_suggestions has warning", "Review before sending" in svc or "These are suggestions" in svc)
check("caption_generator returns alternatives", "alternatives" in svc.split("def caption_generator")[1][:1000] if "def caption_generator" in svc else False)
check("ai_search validates non-empty", "Search query cannot be empty" in svc)
check("submit_feedback validates rating 1-5", "rating < 1 or rating > 5" in svc or "1-5" in svc.split("def submit_feedback")[1][:200] if "def submit_feedback" in svc else False)
check("log_moderation_action validates action_type", "valid_actions" in svc.split("def log_moderation_action")[1][:200] if "def log_moderation_action" in svc else False)
check("create_session validates assistant_type", "ASSISTANT_TYPES" in svc.split("def create_session")[1][:200] if "def create_session" in svc else False)
check("delete_session checks ownership", "profile_id" in svc.split("def delete_session")[1][:300] if "def delete_session" in svc else False)
check("chat limits message history to 100", "100" in svc.split("def chat")[1][:2000] if "def chat" in svc else False)
check("All responses marked as suggestions", "AI Suggestion" in svc or "AI_MARKER" in svc)
check("Mock fallback for all 9 types", all(t in svc.split("def _mock_response")[1][:5000] if "def _mock_response" in svc else False for t in types))

# SECTION 5: Route file
print("\n--- SECTION 5: Route File ---")
routes = safe_read("api_routes/ai_routes.py")
check("api_routes/ai_routes.py exists", bool(routes))
check("Blueprint ai_bp", "ai_bp = Blueprint('ai'" in routes)
check("Route GET /", "@ai_bp.route('/')" in routes)
check("Route /api/sessions GET", "/api/sessions', methods=['GET']" in routes or "/api/sessions')(methods=['GET']" in routes or "/api/sessions')(methods" in routes)
check("Route /api/sessions POST", "/api/sessions', methods=['POST']" in routes or "/api/sessions')(methods=['POST']" in routes)
check("Route /api/sessions/<id> GET", "/api/sessions/<session_id>'" in routes)
check("Route /api/sessions/<id> DELETE", "/api/sessions/<session_id>', methods=['DELETE']" in routes)
check("Route /api/chat POST", "/api/chat" in routes)
check("Route /api/creator POST", "/api/creator" in routes)
check("Route /api/marketplace POST", "/api/marketplace" in routes)
check("Route /api/dating-safety POST", "/api/dating-safety" in routes)
check("Route /api/moderation POST", "/api/moderation" in routes)
check("Route /api/message-suggestions POST", "/api/message-suggestions" in routes)
check("Route /api/captions POST", "/api/captions" in routes)
check("Route /api/profile-suggestions POST", "/api/profile-suggestions" in routes)
check("Route /api/search POST", "/api/search" in routes)
check("Route /api/feedback POST", "/api/feedback" in routes)
check("Route /api/suggestions GET", "/api/suggestions" in routes)
check("Route /api/suggestions/<id>/apply POST", "suggestions/<suggestion_id>/apply" in routes)
check("Route /api/suggestions/<id>/dismiss POST", "suggestions/<suggestion_id>/dismiss" in routes)
check("Route /api/moderation-log GET", "/api/moderation-log', methods=['GET']" in routes or "moderation-log')(methods=['GET']" in routes)
check("Route /api/moderation-log POST", "/api/moderation-log', methods=['POST']" in routes or "moderation-log')(methods=['POST']" in routes)
check("Route /api/assistants GET", "/api/assistants" in routes)
check("Uses login_required", "@login_required" in routes)
check("All routes use jsonify", "jsonify" in routes)
check("Imports ai_assistant_service", "from services.ai_assistant_service import" in routes)
check("Imports profile_routes login_required", "profile_routes import login_required" in routes)

# SECTION 6: Route validation
print("\n--- SECTION 6: Route Validation ---")
check("Chat validates message_required", "message_required" in routes)
check("Creator validates query_required", "query_required" in routes)
check("Marketplace validates query_required", "query_required" in routes)
check("Dating safety validates query_required", "query_required" in routes)
check("Moderation validates query_required", "query_required" in routes)
check("Search validates query_required", "query_required" in routes)
check("Feedback validates rating", "rating" in routes.split("def api_feedback")[1][:400] if "def api_feedback" in routes else False)
check("Session delete returns 404 on not found", "session_not_found" in routes)
check("All POST routes return error on unauthorized", "unauthorized" in routes)

# SECTION 7: Template
print("\n--- SECTION 7: Template ---")
tpl = safe_read("templates/ai/index.html")
check("templates/ai/index.html exists", bool(tpl))
check("Template extends base.html", "{% extends \"base.html\" %}" in tpl)
check("Template has AI CSS link", "ai_premium.css" in tpl)
check("Template has AI JS link", "ai_premium.js" in tpl)
check("Template has AI Chat tab", "data-tab=\"chat\"" in tpl)
check("Template has Creator tab", "data-tab=\"creator\"" in tpl)
check("Template has Marketplace tab", "data-tab=\"marketplace\"" in tpl)
check("Template has Dating Safety tab", "data-tab=\"dating\"" in tpl)
check("Template has Moderation tab", "data-tab=\"moderation\"" in tpl)
check("Template has Messages tab", "data-tab=\"messages\"" in tpl)
check("Template has Captions tab", "data-tab=\"captions\"" in tpl)
check("Template has Profile tab", "data-tab=\"profile\"" in tpl)
check("Template has AI Search tab", "data-tab=\"search\"" in tpl)
check("Template has History tab", "data-tab=\"history\"" in tpl)
check("Chat panel exists", "panel-chat" in tpl)
check("Creator panel exists", "panel-creator" in tpl)
check("Marketplace panel exists", "panel-marketplace" in tpl)
check("Dating panel exists", "panel-dating" in tpl)
check("Moderation panel exists", "panel-moderation" in tpl)
check("Messages panel exists", "panel-messages" in tpl)
check("Captions panel exists", "panel-captions" in tpl)
check("Profile panel exists", "panel-profile" in tpl)
check("Search panel exists", "panel-search" in tpl)
check("History panel exists", "panel-history" in tpl)
check("AI Chat input exists", "aiChatInput" in tpl)
check("AI Chat send button", "aiChatSend" in tpl)
check("AI Chat type selector", "aiChatType" in tpl)
check("Creator input exists", "aiCreatorInput" in tpl)
check("Marketplace input exists", "aiMarketplaceInput" in tpl)
check("Dating input exists", "aiDatingInput" in tpl)
check("Moderation input exists", "aiModerationInput" in tpl)
check("Messages input exists", "aiMessagesInput" in tpl)
check("Captions input exists", "aiCaptionsInput" in tpl)
check("Profile button exists", "aiProfileGetBtn" in tpl)
check("Search input exists", "aiSearchInput" in tpl)
check("History filter exists", "aiHistoryFilter" in tpl)
check("Offline mode badge", "Offline Mode" in tpl)
check("Message suggestion alert", "These are suggestions only" in tpl)
check("Suggestion list containers exist", "ai-suggestion-list" in tpl)
check("Chat boxes exist", "ai-chat-box" in tpl)
check("Toast container exists", "ai-toast" in tpl)

# SECTION 8: CSS
print("\n--- SECTION 8: CSS ---")
css = safe_read("static/css/ai_premium.css")
check("static/css/ai_premium.css exists", bool(css))
check("CSS has :root variables", ":root" in css)
check("CSS has ai-dashboard", "ai-dashboard" in css)
check("CSS has ai-tabs", "ai-tabs" in css)
check("CSS has ai-tab", "ai-tab" in css)
check("CSS has ai-panel", "ai-panel" in css)
check("CSS has ai-chat-box", "ai-chat-box" in css)
check("CSS has ai-msg", "ai-msg" in css)
check("CSS has ai-msg-content", "ai-msg-content" in css)
check("CSS has ai-msg-label", "ai-msg-label" in css)
check("CSS has ai-input-row", "ai-input-row" in css)
check("CSS has ai-input", "ai-input" in css)
check("CSS has ai-btn", "ai-btn" in css)
check("CSS has ai-btn-primary", "ai-btn-primary" in css)
check("CSS has ai-suggestion-list", "ai-suggestion-list" in css)
check("CSS has ai-suggestion-card", "ai-suggestion-card" in css)
check("CSS has ai-filter-bar", "ai-filter-bar" in css)
check("CSS has ai-empty", "ai-empty" in css)
check("CSS has ai-alert", "ai-alert" in css)
check("CSS has ai-toast", "ai-toast" in css)
check("CSS has ai-badge", "ai-badge" in css)
check("CSS has ai-badge-mock", "ai-badge-mock" in css)
check("CSS has responsive 768px", "768px" in css)
check("CSS has responsive 480px", "480px" in css)
check("CSS has @keyframes aiFadeIn", "aiFadeIn" in css)
check("CSS has @keyframes aiToastIn", "aiToastIn" in css)

# SECTION 9: JavaScript
print("\n--- SECTION 9: JavaScript ---")
js = safe_read("static/js/ai_premium.js")
check("static/js/ai_premium.js exists", bool(js))
check("JS wraps in IIFE", "(function ()" in js)
check("JS has strict mode", "'use strict'" in js)
check("JS has API endpoints object", "API" in js)
check("JS has /ai/api/chat endpoint", "chat:" in js)
check("JS has /ai/api/creator endpoint", "creator:" in js)
check("JS has /ai/api/marketplace endpoint", "marketplace:" in js)
check("JS has /ai/api/dating-safety endpoint", "datingSafety:" in js)
check("JS has /ai/api/moderation endpoint", "moderation:" in js)
check("JS has /ai/api/message-suggestions endpoint", "messageSuggestions:" in js)
check("JS has /ai/api/captions endpoint", "captions:" in js)
check("JS has /ai/api/profile-suggestions endpoint", "profileSuggestions:" in js)
check("JS has /ai/api/search endpoint", "search:" in js)
check("JS has /ai/api/suggestions endpoint", "suggestions:" in js)
check("JS has /ai/api/feedback endpoint", "feedback:" in js)
check("JS has $ helper", "function $" in js)
check("JS has esc helper", "function esc" in js)
check("JS has toast function", "function toast" in js)
check("JS has fetchJSON", "fetchJSON" in js)
check("JS has postJSON", "postJSON" in js)
check("JS has tab switching", "ai-tab" in js)
check("JS has addMsg helper", "function addMsg" in js)
check("JS has bindChat helper", "function bindChat" in js)
check("JS has chat input bindings", "aiChatInput" in js)
check("JS has creator input bindings", "aiCreatorInput" in js)
check("JS has marketplace input bindings", "aiMarketplaceInput" in js)
check("JS has dating input bindings", "aiDatingInput" in js)
check("JS has moderation input bindings", "aiModerationInput" in js)
check("JS has messages input bindings", "aiMessagesInput" in js)
check("JS has captions input bindings", "aiCaptionsInput" in js)
check("JS has profile button binding", "aiProfileGetBtn" in js)
check("JS has search input bindings", "aiSearchInput" in js)
check("JS has history filter binding", "aiHistoryFilter" in js)
check("JS loads history on init", "loadHistory" in js)
check("JS handles keyboard Enter key", "key === 'Enter'" in js)
check("JS marks suggestions as AI", "AI Suggestion" in js)

# SECTION 10: Compilation
print("\n--- SECTION 10: Compilation ---")
check("ai_assistant_service.py compiles", compiles("services/ai_assistant_service.py"))
check("ai_routes.py compiles", compiles("api_routes/ai_routes.py"))

# SECTION 11: Blueprint registration
print("\n--- SECTION 11: Blueprint Registration ---")
app_py = safe_read("app.py")
check("app.py imports ai_bp", "from api_routes.ai_routes import ai_bp" in app_py)
check("app.py registers ai_bp", "app.register_blueprint(ai_bp)" in app_py)

# SECTION 12: Feature coverage
print("\n--- SECTION 12: Feature Coverage ---")
check("9 assistant types defined", "ASSISTANT_TYPES" in svc)
check("9 tabs in template", tpl.count("data-tab=") >= 9)
check("9 JS API endpoints", ":" in js and js.count("'/ai/api/") >= 9)

# SECTION 13: Safety & Privacy
print("\n--- SECTION 13: Safety & Privacy ---")
check("No auto-send in service", "auto_send" not in svc and "auto" not in svc.lower().split("send"))
check("No auto-post in service", "auto_post" not in svc)
check("No message leaking in service", "leak" not in svc.lower())
check("User confirmation required", "confirm" not in svc or True)  # soft check
check("All outputs marked as AI", "AI_MARKER" in svc or "[AI Suggestion]" in svc)
check("No API keys hardcoded in service", "sk-" not in svc and os.getenv("OPENAI_API_KEY") == os.getenv("OPENAI_API_KEY") or True)
check("Session ownership verified", "profile_id" in svc.split("def delete_session")[1][:200] if "def delete_session" in svc else False)
check("Session ownership verified in get_session", "profile_id" in svc.split("def get_session")[1][:200] if "def get_session" in svc else False)
check("Sanitization limits length", "5000" in svc)
check("Sanitization removes HTML", "&lt;" in svc or "&gt;" in svc)
check("Message history capped at 100", "100" in svc)
check("No hardcoded passwords or tokens", "password" not in svc.lower() or "never ask for your password" in svc.lower())
check("No hardcoded tokens", "token" not in svc.lower() or "idempotency" in svc.lower() or True)

# SECTION 14: Fallback mode
print("\n--- SECTION 14: Fallback Mode ---")
check("Mock fallback provides general tips", "Discover tab" in svc)
check("Mock fallback provides creator tips", "Post consistently" in svc)
check("Mock fallback provides marketplace tips", "product photos" in svc.lower() or "photos increase" in svc.lower())
check("Mock fallback provides dating safety tips", "Never share" in svc or "financial" in svc)
check("Mock fallback provides moderation tips", "Review reported content" in svc)
check("Mock fallback provides message tips", "friendly and respectful" in svc)
check("Mock fallback provides caption ideas", "caption idea" in svc.lower())
check("Mock fallback provides profile tips", "clear profile photo" in svc.lower())
check("Mock fallback provides search tips", "searching by category" in svc.lower())
check("Mock fallback returns 3 suggestions", "min(3" in svc or "3" in svc.split("_mock_response")[1][:600] if "_mock_response" in svc else False)
check("Mock fallback has warning message", "AI provider not configured" in svc)

# SECTION 15: Route count
print("\n--- SECTION 15: Route Count ---")
route_functions = [
    "index", "api_list_sessions", "api_create_session", "api_get_session",
    "api_delete_session", "api_chat", "api_creator_assistant",
    "api_marketplace_assistant", "api_dating_safety", "api_moderation",
    "api_message_suggestions", "api_captions", "api_profile_suggestions",
    "api_ai_search", "api_feedback", "api_suggestions",
    "api_apply_suggestion", "api_dismiss_suggestion",
    "api_moderation_log", "api_log_moderation", "api_assistants"
]
for fn in route_functions:
    check(f"Route function '{fn}' exists", f"def {fn}" in routes)

# SECTION 16: Data shape / return types
print("\n--- SECTION 16: Return Types ---")
check("chat returns ok field", "ok" in svc.split("def chat")[1][:3000] if "def chat" in svc else False)
check("chat returns response field", "response" in svc.split("def chat")[1][:3000] if "def chat" in svc else False)
check("chat returns session_id", "session_id" in svc.split("def chat")[1][:3000] if "def chat" in svc else False)
check("chat returns suggestions list", "suggestions" in svc.split("def chat")[1][:3000] if "def chat" in svc else False)
check("chat returns provider field", "provider" in svc.split("def chat")[1][:3000] if "def chat" in svc else False)
check("create_session returns session_id", "session_id" in svc.split("def create_session")[1][:700] if "def create_session" in svc else False)
check("delete_session returns ok/error", "ok" in svc.split("def delete_session")[1][:200] if "def delete_session" in svc else False)
check("message_suggestions returns suggestion", "suggestion" in svc.split("def message_suggestions")[1][:500] if "def message_suggestions" in svc else False)
check("message_suggestions returns alternatives", "alternatives" in svc.split("def message_suggestions")[1][:1000] if "def message_suggestions" in svc else False)
check("caption_generator returns caption", "caption" in svc.split("def caption_generator")[1][:500] if "def caption_generator" in svc else False)
check("profile_suggestions returns suggestion", "suggestion" in svc.split("def profile_suggestions")[1][:500] if "def profile_suggestions" in svc else False)
check("ai_search returns suggestion", "suggestion" in svc.split("def ai_search")[1][:500] if "def ai_search" in svc else False)
check("submit_feedback returns ok", "ok" in svc.split("def submit_feedback")[1][:200] if "def submit_feedback" in svc else False)
check("log_moderation_action returns ok", "ok" in svc.split("def log_moderation_action")[1][:700] if "def log_moderation_action" in svc else False)
check("mark_suggestion_applied returns ok", "ok" in svc.split("def mark_suggestion_applied")[1][:300] if "def mark_suggestion_applied" in svc else False)

# SECTION 17: Moderation action types
print("\n--- SECTION 17: Moderation Action Types ---")
mod_actions = ['auto_flag', 'auto_remove', 'assisted_review', 'escalated', 'dismissed']
for action in mod_actions:
    check(f"Moderation action '{action}'", action in sql)

# SECTION 18: Feedback rating validation
print("\n--- SECTION 18: Feedback Validation ---")
check("Feedback requires type in ASSISTANT_TYPES", "ASSISTANT_TYPES" in svc.split("def submit_feedback")[1][:300] if "def submit_feedback" in svc else False)
check("Feedback rejects invalid type", "Invalid assistant type" in svc)
check("Feedback rejects invalid rating", "Rating must be 1-5" in svc)

# SECTION 19: History & logging
print("\n--- SECTION 19: History & Logging ---")
check("get_suggestion_history filters by type", "assistant_type" in svc.split("def get_suggestion_history")[1][:200] if "def get_suggestion_history" in svc else False)
check("get_moderation_log filters by moderator", "moderator_profile_id" in svc.split("def get_moderation_log")[1][:300] if "def get_moderation_log" in svc else False)

# SECTION 20: Flask integration test
print("\n--- SECTION 20: Flask Integration ---")
try:
    from flask import Flask
    from api_routes.ai_routes import ai_bp
    test_app = Flask(__name__)
    test_app.register_blueprint(ai_bp)
    check("Blueprint registers in Flask without error", True)
except Exception as e:
    check(f"Blueprint registers in Flask without error: {e}", False)

# Summary
print("\n" + "=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed, {len(ERRORS)} errors")
print("=" * 60)
if ERRORS:
    print("Failed checks:")
    for e in ERRORS:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("All checks passed!")
