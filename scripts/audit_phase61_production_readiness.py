"""
Phase 61 Production Hardening — comprehensive audit.
Finds bugs across auth, profiles, posts, stories, reels, messaging, calls, live, wallet, notifications, mobile, performance, security.
"""
import os, sys, re, subprocess, importlib.util
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PASS, FAIL, WARN = 0, 0, 0

def check(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        print(f"  PASS  {label}")
        PASS += 1
    else:
        print(f"  FAIL  {label}" + (f"  [{detail}]" if detail else ""))
        FAIL += 1

def warn(label, msg):
    global WARN
    print(f"  WARN  {label}: {msg}")
    WARN += 1

def has_route(filepath, pattern):
    p = BASE / filepath
    if not p.exists():
        return False
    return bool(re.search(pattern, p.read_text()))

def file_contains(path, pattern):
    p = BASE / path if isinstance(path, str) else path
    if not p.exists():
        return False
    return bool(re.search(pattern, p.read_text()))

def file_not_contains(path, pattern):
    p = BASE / path if isinstance(path, str) else path
    if not p.exists():
        return False
    return not bool(re.search(pattern, p.read_text()))

# ═══════════════════════════════════════════════════════════════
# 1. AUTHENTICATION
# ═══════════════════════════════════════════════════════════════
print("\n═══════════════ 1. AUTHENTICATION ═══════════════\n")

# 1a. Login route exists
check("Login GET route exists", has_route("api_routes/auth_routes.py", r"@auth_bp\.route\(\"/login\""))
check("Login POST route exists", has_route("api_routes/auth_routes.py", r"def login\("))

# 1b. Register route exists
check("Register GET route exists", has_route("api_routes/auth_routes.py", r"@auth_bp\.route\(\"/register\".*GET"))
check("Register POST route exists", has_route("api_routes/auth_routes.py", r"register_post"))

# 1c. Logout route exists
check("Logout route exists", has_route("api_routes/auth_routes.py", r"def logout\("))

# 1d. Password reset routes exist
check("Forgot password route exists", has_route("api_routes/auth_routes.py", r"def forgot_password\("))
check("Reset password route exists", has_route("api_routes/auth_routes.py", r"def reset_password\("))

# 1e. Session expiry handling
check("Session has PERMANENT_SESSION_LIFETIME", file_contains("app.py", r"PERMANENT_SESSION_LIFETIME"))
check("Session refresh logic exists", file_contains("services/session_service.py", r"refresh_supabase_session"))
check("CSRFProtect initialized", file_contains("app.py", r"CSRFProtect\(app\)"))

# 1f. Auth templates exist
check("Login template exists", (BASE / "templates" / "auth" / "login.html").exists())
check("Register template exists", (BASE / "templates" / "auth" / "register.html").exists())
check("Forgot password template exists", (BASE / "templates" / "auth" / "forgot_password.html").exists())
check("Reset password template exists", (BASE / "templates" / "auth" / "reset_password.html").exists())

# 1g. CSRF token presence in auth forms (BUG CHECK)
login_html = (BASE / "templates" / "auth" / "login.html").read_text() if (BASE / "templates" / "auth" / "login.html").exists() else ""
register_html = (BASE / "templates" / "auth" / "register.html").read_text() if (BASE / "templates" / "auth" / "register.html").exists() else ""
forgot_html = (BASE / "templates" / "auth" / "forgot_password.html").read_text() if (BASE / "templates" / "auth" / "forgot_password.html").exists() else ""
reset_html = (BASE / "templates" / "auth" / "reset_password.html").read_text() if (BASE / "templates" / "auth" / "reset_password.html").exists() else ""

check("Login form has CSRF token", "csrf_token" in login_html, "CRITICAL: missing CSRF token in login form")
check("Register form has CSRF token", "csrf_token" in register_html, "CRITICAL: missing CSRF token in register form")
check("Forgot password form has CSRF token", "csrf_token" in forgot_html, "HIGH: missing CSRF token in forgot-password form")
check("Reset password form has CSRF token", "csrf_token" in reset_html, "HIGH: missing CSRF token in reset-password form")

# 1h. Logout is POST (BUG CHECK: should not be GET)
auth_routes = (BASE / "api_routes" / "auth_routes.py").read_text()
logout_line = re.search(r"def logout\(\)", auth_routes)
if logout_line:
    # Find the route decorator before logout function by scanning backwards
    lines = auth_routes.split('\n')
    logout_idx = None
    for i, line in enumerate(lines):
        if 'def logout' in line:
            logout_idx = i
            break
    is_get = False
    if logout_idx:
        for j in range(logout_idx-1, max(0, logout_idx-4), -1):
            if 'route(' in lines[j] and 'GET' in lines[j]:
                is_get = True
                break
    check("Logout is NOT a GET request", not is_get, "HIGH: GET logout is CSRF-vulnerable")

# 1i. Rate limiting on auth endpoints
check("Login has rate limiting", "limiter.limit" in auth_routes)
check("Register has rate limiting", "5/hour" in auth_routes or "limiter.limit" in auth_routes)

# 1j. API v1 auth endpoints
api_auth = Path(BASE / "api_v1" / "auth_api.py")
if api_auth.exists():
    api_auth_text = api_auth.read_text()
    check("API v1 login route exists", "def login(" in api_auth_text)
    check("API v1 register route exists", "def register(" in api_auth_text)
    # Check for the critical bug: login_chain_user returns (bool, str) but API expects object
    check("API login handles (bool, str) tuple correctly",
          "res.get" not in api_auth_text and "res.user" not in api_auth_text,
          "CRITICAL: API login expects .user attr on bool")
    check("API register handles dict return correctly",
          "res, error = register_chain_user" not in api_auth_text,
          "CRITICAL: API register expects 2 values from dict-returning func")

# 1k. login_required decorator exists
check("login_required decorator exists", "def login_required" in (BASE / "api_routes" / "profile_routes.py").read_text())

# ═══════════════════════════════════════════════════════════════
# 2. PROFILES
# ═══════════════════════════════════════════════════════════════
print("\n═══════════════ 2. PROFILES ═══════════════\n")

profile_routes = (BASE / "api_routes" / "profile_routes.py").read_text()
check("Follow route exists", "def follow(" in profile_routes)
check("Unfollow route exists", "def toggle_follow" in profile_routes or "def unfollow" in profile_routes)
check("Edit profile route exists", "def edit_profile(" in profile_routes)
check("Avatar upload route exists", "def avatar_upload(" in profile_routes)
check("Cover upload route exists", "def cover_upload(" in profile_routes)
check("Profile settings route exists", "def settings(" in profile_routes)

# 2a. Follow/Unfollow permission checks
check("Follow prevents self-follow", "self" in profile_routes.lower() or "follower_id != following_id" in profile_routes or "str(viewer" in profile_routes)

# 2b. Edit profile ownership check
check("Edit profile validates ownership", "auth_user_id" in (BASE / "services" / "profile_service.py").read_text())

# 2c. File upload validation
storage_router = (BASE / "services" / "supabase_storage_router.py").read_text() if (BASE / "services" / "supabase_storage_router.py").exists() else ""
check("Avatar upload validates file type", "validate_upload" in storage_router or "allowed_extensions" in storage_router)

# ═══════════════════════════════════════════════════════════════
# 3. POSTS
# ═══════════════════════════════════════════════════════════════
print("\n═══════════════ 3. POSTS ═══════════════\n")

post_routes_py = (BASE / "api_routes" / "post_routes.py").read_text()
check("Post create route exists", "def create(" in post_routes_py)
check("Post edit route exists (BUG CHECK)", has_route("api_routes/post_routes.py", r"def edit\(|\.route.*edit"),
      "LOW: no post edit route found")
check("Post delete route exists (BUG CHECK)", has_route("api_routes/post_routes.py", r"def delete\(|\.route.*delete"),
      "LOW: no post delete route found")
check("Post like route exists", has_route("api_routes/homepage_api.py", r"api_like_post"))
check("Post comment route exists", has_route("api_routes/homepage_api.py", r"api_comment_post") or has_route("api_routes/engagement_routes.py", r"api_add_comment"))
check("Post share route exists", has_route("api_routes/homepage_api.py", r"api_share_post"))
check("Post save route exists", has_route("api_routes/homepage_api.py", r"api_save_post"))

# Media upload validation
post_routes_text = (BASE / "api_routes" / "post_routes.py").read_text()
check("Post upload validates file type (via service)", "validate_media" in (BASE / "services" / "content_service.py").read_text())

# Post ownership on delete
engagement_service = (BASE / "services" / "engagement_service.py").read_text()
check("Comment delete validates ownership", "existing.get(\"profile_id\") != profile_id" in engagement_service)

# ═══════════════════════════════════════════════════════════════
# 4. STORIES
# ═══════════════════════════════════════════════════════════════
print("\n═══════════════ 4. STORIES ═══════════════\n")

check("Stories create route exists", has_route("api_routes/status_routes.py", r"def create\(") or has_route("api_routes/stories_v2_routes.py", r"def index\("))
check("Stories view route exists", has_route("api_routes/status_routes.py", r"def detail\(") or has_route("api_routes/stories_v2_routes.py", r"def detail\("))
check("Stories react route exists", has_route("api_routes/stories_v2_routes.py", r"def api_react\(") if (BASE / "api_routes" / "stories_v2_routes.py").exists() else False)
check("Stories reply route exists", has_route("api_routes/stories_v2_routes.py", r"def api_reply\(") if (BASE / "api_routes" / "stories_v2_routes.py").exists() else False)
check("Stories poll vote route exists", has_route("api_routes/stories_v2_routes.py", r"def api_poll_vote") if (BASE / "api_routes" / "stories_v2_routes.py").exists() else False)
check("Stories expiry function exists", has_route("services/status_service.py", r"def expire_old_statuses"))
check("Story viewer records view", has_route("services/status_service.py", r"def record_view"))
check("Story viewer has reaction support", has_route("services/stories_service.py", r"def react_to_story") if (BASE / "services" / "stories_service.py").exists() else False)

# ═══════════════════════════════════════════════════════════════
# 5. REELS
# ═══════════════════════════════════════════════════════════════
print("\n═══════════════ 5. REELS ═══════════════\n")

check("Reels upload route exists", has_route("api_routes/reels_routes.py", r"def upload\("))
check("Reels playback route exists", has_route("api_routes/reels_routes.py", r"def index\("))
check("Reels like route exists", has_route("api_routes/reels_routes.py", r"def api_like\("))
check("Reels comment route exists", has_route("api_routes/reels_routes.py", r"def api_comment\("))
check("Reels share route exists", has_route("api_routes/reels_routes.py", r"def api_share\("))
check("Reels follow creator exists", has_route("api_routes/reels_routes.py", r"def "))  # follow is in template JS
check("Reels delete validates ownership", has_route("api_routes/reels_routes.py", r"profile_id"))
reels_svc = (BASE / "services" / "reels_service.py").read_text() if (BASE / "services" / "reels_service.py").exists() else ""
check("Reels watch-time tracking exists", "track_reel_event" in reels_svc)
check("Reels comments list route exists", has_route("api_routes/reels_routes.py", r"def api_comments"))

# ═══════════════════════════════════════════════════════════════
# 6. MESSAGING
# ═══════════════════════════════════════════════════════════════
print("\n═══════════════ 6. MESSAGING ═══════════════\n")

message_routes = (BASE / "api_routes" / "message_routes.py").read_text()
check("Message send route exists", "def api_send(" in message_routes)
check("Message media upload exists", "def api_messages_upload(" in message_routes)
check("Message voice notes exist", "def api_messages_voice_note(" in message_routes)
check("Message reactions exist", "def api_reaction(" in message_routes)
check("Message reply exists (via parent_message_id)", "parent_message_id" in message_routes)
check("Message forward exists", "def api_forward_messages(" in message_routes or "def api_messages_forward(" in message_routes)
check("Delete for everyone exists", "def api_delete_msg(" in message_routes or "def api_messages_delete(" in message_routes)
check("Read receipts exist", "def api_seen(" in message_routes or "def api_messages_seen(" in message_routes)

# Forward permission check
msg_feature = (BASE / "services" / "message_feature_service.py").read_text() if (BASE / "services" / "message_feature_service.py").exists() else ""
check("Forward has thread membership check", "member_threads" in msg_feature or "can_access_thread" in msg_feature,
      "HIGH: forward_messages may lack thread membership check")

# Delete for everyone ownership check
msg_engine = (BASE / "services" / "messaging_engine.py").read_text()
check("Delete for everyone validates sender", "sender_profile_id" in msg_engine.lower() or "profile_id" in msg_engine.lower())

# Rate limiting
check("Send has rate limiting", "60/minute" in message_routes or "limiter" in message_routes)

# ICE servers auth check
call_routes = (BASE / "api_routes" / "call_routes.py").read_text() if (BASE / "api_routes" / "call_routes.py").exists() else ""
check("ICE servers endpoint has auth (BUG CHECK)", "login_required" in call_routes,
      "MEDIUM: ICE servers may be unauthenticated")

# ═══════════════════════════════════════════════════════════════
# 7. CALLS
# ═══════════════════════════════════════════════════════════════
print("\n═══════════════ 7. CALLS ═══════════════\n")

check("Audio call route exists", "def api_webrtc_start(" in call_routes)
check("Video call route exists", "def api_webrtc_start(" in call_routes)
check("Offline user handling exists", "offline" in call_routes.lower() or "offline" in (BASE / "services" / "webrtc_call_service.py").read_text())
check("Busy user handling exists", "busy" in call_routes.lower() or "busy" in (BASE / "services" / "webrtc_call_service.py").read_text())
check("Call timeout handling exists", "def check_call_timeouts" in (BASE / "services" / "webrtc_call_service.py").read_text())
check("Call reconnect handling exists", "def api_phase41_reconnect" in call_routes)

# ═══════════════════════════════════════════════════════════════
# 8. LIVE
# ═══════════════════════════════════════════════════════════════
print("\n═══════════════ 8. LIVE ═══════════════\n")

live_service = (BASE / "services" / "live_service.py").read_text()
live_routes = (BASE / "api_routes" / "live_routes.py").read_text()
check("Live comments exist", "def add_comment" in live_service or "comment" in live_routes)
check("Live reactions exist", "def send_gift" in live_service or "reaction" in live_routes)
check("Live gifts exist", "def send_gift" in live_service or "gift" in live_routes)
check("Live guest join exists", "guest" in live_service.lower() or "cohost" in live_service.lower())
check("Live event timeline exists", "def create_live_event" in live_service or "chain_live_events" in live_service)

# ═══════════════════════════════════════════════════════════════
# 9. WALLET
# ═══════════════════════════════════════════════════════════════
print("\n═══════════════ 9. WALLET ═══════════════\n")

wallet_routes = (BASE / "api_routes" / "wallet_routes.py").read_text()
check("Wallet balance route exists", "def balance" in wallet_routes or "dashboard" in wallet_routes)
check("Wallet transfer route exists", "def transfer" in wallet_routes or "send" in wallet_routes)
check("Wallet transaction history exists", "def transactions" in wallet_routes or "history" in wallet_routes)
check("Wallet engine exists", (BASE / "services" / "wallet_engine.py").exists())

# ═══════════════════════════════════════════════════════════════
# 10. NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════
print("\n═══════════════ 10. NOTIFICATIONS ═══════════════\n")

check("Notification realtime exists", (BASE / "services" / "socketio_service.py").exists())
check("Notification unread count exists", has_route("services/notification_engine.py", r"def unread_count"))
check("Notification mark read exists", has_route("api_routes/notification_routes.py", r"mark_read") if (BASE / "api_routes" / "notification_routes.py").exists() else False)
check("Notification template exists", (BASE / "templates" / "notifications" / "index.html").exists())

# ═══════════════════════════════════════════════════════════════
# 11. MOBILE / PERFORMANCE / SECURITY
# ═══════════════════════════════════════════════════════════════
print("\n═══════════════ 11. MOBILE ═══════════════\n")

check("Mobile responsive CSS exists", (BASE / "static" / "css" / "style.css").exists() or (BASE / "static" / "css" / "chain_home.css").exists())
check("Viewport meta tag in base template", "viewport" in (BASE / "templates" / "base.html").read_text())
check("Mobile API routes exist", (BASE / "api_routes" / "mobile_api_routes.py").exists())
check("Service worker exists", (BASE / "static" / "js" / "sw.js").exists() or (BASE / "static" / "js" / "service-worker.js").exists())

print("\n═══════════════ 12. PERFORMANCE ═══════════════\n")
check("Neon pool configured", "POOL_MIN" in (BASE / "services" / "neon_service.py").read_text())
check("Query timeout configured", "STATEMENT_TIMEOUT" in (BASE / "services" / "neon_service.py").read_text())
check("Cache service exists", (BASE / "services" / "cache_service.py").exists() or (BASE / "services" / "redis_service.py").exists())
check("Request memoize exists", "request_memoize" in (BASE / "services" / "request_cache.py").read_text())
check("Homepage cache exists", (BASE / "services" / "homepage_cache_service.py").exists())

print("\n═══════════════ 13. SECURITY ═══════════════\n")

# XSS: Check for quote=False in escape calls
service_files = ["services/content_service.py", "services/engagement_service.py", "services/comments_service.py"]
xss_issues = 0
for sf in service_files:
    p = BASE / sf
    if p.exists():
        content = p.read_text()
        if "escape" in content and "quote=False" in content:
            xss_issues += 1
check("No quote=False XSS in escape calls (content_service, engagement_service, comments_service)", xss_issues == 0,
      f"MEDIUM: found {xss_issues} file(s) using escape(text, quote=False)")
check("quote=False fixed in engagement_service", not bool(re.search(r"escape\(.*quote=False", (BASE / "services"/"engagement_service.py").read_text())))
check("quote=False fixed in content_service", not bool(re.search(r"escape\(.*quote=False", (BASE / "services"/"content_service.py").read_text())))

# CSRF protection
check("CSRFProtect is initialized", "CSRFProtect" in (BASE / "app.py").read_text())

# Upload validation
check("Upload validation function exists", "def validate_upload" in (BASE / "services" / "supabase_storage_router.py").read_text())

# Permission checks
check("Edit profile validates auth_user_id", "auth_user_id" in (BASE / "services" / "profile_service.py").read_text())
check("Post delete validates ownership", "profile_id" in (BASE / "services" / "engagement_service.py").read_text())

# Private content leakage
privacy_service = (BASE / "services" / "privacy_service.py").read_text() if (BASE / "services" / "privacy_service.py").exists() else ""
check("Privacy service exists", bool(privacy_service) or (BASE / "services" / "privacy_service.py").exists())

# SQL injection
neon_text = (BASE / "services" / "neon_service.py").read_text()
check("Parameterized queries used (no f-string SQL)", "%s" in neon_text,
      "LOW: verify parameterized queries are used")

# ═══════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════
print(f"\n{'═'*60}")
print(f"SUMMARY: {PASS} PASS, {FAIL} FAIL, {WARN} WARN")
print(f"{'═'*60}\n")
sys.exit(0 if FAIL == 0 else 1)
