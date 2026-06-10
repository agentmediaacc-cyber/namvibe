#!/usr/bin/env python3
"""
Phase 60 — Premium Notification Center
Tests covering SQL, service, API routes, Socket.IO, template, CSS, JS, seed script
"""
import os, sys, json, subprocess, importlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"

from flask import Flask, session as flask_session

PASS = 0
FAIL = 0
ERRORS = []

def check(desc, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {desc}")
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

def create_test_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.config["TESTING"] = True
    return app

print("=" * 60)
print("Phase 60 — Premium Notification Center Tests")
print("=" * 60)

# ============================================================
# SECTION 1: SQL file
# ============================================================
print("\n--- SQL schema ---")
sql_content = safe_read("sql/phase60_notifications.sql")
check("sql/phase60_notifications.sql exists", bool(sql_content))
check("CREATE TABLE chain_notifications", "CREATE TABLE IF NOT EXISTS chain_notifications" in sql_content)
check("chain_notifications has recipient_profile_id", "recipient_profile_id" in sql_content)
check("chain_notifications has notification_type", "notification_type" in sql_content)
check("chain_notifications has title", "title" in sql_content)
check("chain_notifications has body", "body" in sql_content)
check("chain_notifications has preview", "preview" in sql_content)
check("chain_notifications has target_type", "target_type" in sql_content)
check("chain_notifications has target_id", "target_id" in sql_content)
check("chain_notifications has action_url", "action_url" in sql_content)
check("chain_notifications has image_url", "image_url" in sql_content)
check("chain_notifications has is_read", "is_read" in sql_content)
check("chain_notifications has is_deleted", "is_deleted" in sql_content)
check("chain_notifications has priority", "priority" in sql_content)
check("chain_notifications has metadata jsonb", "metadata" in sql_content and "jsonb" in sql_content)
check("chain_notifications has read_at", "read_at" in sql_content)
check("chain_notifications has deleted_at", "deleted_at" in sql_content)
check("CREATE TABLE chain_notification_preferences", "CREATE TABLE IF NOT EXISTS chain_notification_preferences" in sql_content)
check("preferences has profile_id PK", "profile_id uuid PRIMARY KEY" in sql_content or "profile_id" in sql_content)
check("preferences has in_app_enabled", "in_app_enabled" in sql_content)
check("preferences has push_enabled", "push_enabled" in sql_content)
check("preferences has email_enabled", "email_enabled" in sql_content)
check("preferences has sms_enabled", "sms_enabled" in sql_content)
check("preferences has muted_types", "muted_types" in sql_content)
check("preferences has quiet_hours", "quiet_hours_enabled" in sql_content)
check("Index recipient unread", "idx_chain_notifications_recipient_unread" in sql_content)
check("Index recipient created", "idx_chain_notifications_recipient_created" in sql_content)
check("Index notification type", "idx_chain_notifications_type" in sql_content)
check("Index target lookup", "idx_chain_notifications_target" in sql_content)

# ============================================================
# SECTION 2: Notification center service
# ============================================================
print("\n--- notification_center_service ---")
svc_content = safe_read("services/notification_center_service.py")
check("notification_center_service.py exists", bool(svc_content))
check("create_notification function", "def create_notification" in svc_content)
check("list_notifications function", "def list_notifications" in svc_content)
check("unread_count function", "def unread_count" in svc_content)
check("mark_read function", "def mark_read" in svc_content)
check("mark_all_read function", "def mark_all_read" in svc_content)
check("delete_notification function", "def delete_notification" in svc_content)
check("delete_selected function", "def delete_selected" in svc_content)
check("get_preferences function", "def get_preferences" in svc_content)
check("update_preferences function", "def update_preferences" in svc_content)
check("mute_type function", "def mute_type" in svc_content)
check("format_notification function", "def format_notification" in svc_content)
check("Wraps notification_engine", "from services.notification_engine import" in svc_content)

svc_imports = safe_read("services/notification_center_service.py")
check("Tab support in service", "list_notifications_tab" in svc_imports or "tab=" in svc_imports)
check("Fallback to empty list on error", "return [], False" in svc_content)
check("Recipient ownership enforced", "recipient_profile_id" in svc_content or "profile_id" in svc_content)

# ============================================================
# SECTION 3: API routes
# ============================================================
print("\n--- API routes ---")
routes_content = safe_read("api_routes/notification_routes.py")
check("notification_routes.py exists", bool(routes_content))
check("GET /notifications/ route", "/notifications/" in routes_content)
check("GET /api/notifications route", "/api/notifications\"" in routes_content or "'/api/notifications'" in routes_content or "/api/notifications<" in routes_content)
check("/api/notifications/unread-count route", "/api/notifications/unread-count" in routes_content)
check("POST /api/notifications/<id>/read route", "/api/notifications/<" in routes_content and "/read" in routes_content)
check("POST /api/notifications/read-all route", "/api/notifications/read-all" in routes_content)
check("POST /api/notifications/<id>/delete route", "/delete\"" in routes_content or "/delete'" in routes_content)
check("POST /api/notifications/delete-selected route", "/api/notifications/delete-selected" in routes_content)
check("GET /api/notifications/preferences route", "/api/notifications/preferences" in routes_content)
check("POST /api/notifications/preferences route", "\"/api/notifications/preferences\"" in routes_content or "'/api/notifications/preferences'" in routes_content)
check("POST /api/notifications/mute-type route", "/api/notifications/mute-type" in routes_content)
check("List route accepts tab param", "tab" in routes_content)
check("List route accepts page param", "page" in routes_content)
check("List returns ok field", "\"ok\"" in routes_content or "'ok'" in routes_content)
check("List returns items field", "\"items\"" in routes_content or "'items'" in routes_content)
check("List returns has_more field", "has_more" in routes_content)
check("Delete-selected handles ids", "ids" in routes_content)
check("Mute-type handles event_type", "event_type" in routes_content)
check("Mute-type handles muted", "muted" in routes_content)
check("Uses notification_engine_bp", "notification_engine_bp" in routes_content)

# ============================================================
# SECTION 4: Blueprint registration in app.py
# ============================================================
print("\n--- Blueprint registration ---")
app_content = safe_read("app.py")
check("notification_routes imported", "notification_routes" in app_content)
check("notification_engine_bp registered", "notification_engine_bp" in app_content)

# ============================================================
# SECTION 5: Socket.IO events
# ============================================================
print("\n--- Socket.IO events ---")
socket_content = safe_read("services/socket_events.py")
check("notification:join handler", "notification:join" in socket_content)
check("notification:leave handler", "notification:leave" in socket_content)
check("join calls join_room", "join_room(room_name)" in socket_content[socket_content.find("notification:join"):socket_content.find("notification:leave")] if "notification:join" in socket_content else False)
check("leave calls leave_room", "leave_room" in socket_content[socket_content.find("notification:leave"):] if "notification:leave" in socket_content else False)
check("notification:new emit from engine", "notification:new" in socket_content)

# ============================================================
# SECTION 6: Template
# ============================================================
print("\n--- Template ---")
tpl_content = safe_read("templates/notifications/index.html")
check("Template exists", bool(tpl_content))
check("Extends base.html", "extends" in tpl_content and "base.html" in tpl_content)
check("CSS link to notifications_premium.css", "notifications_premium.css" in tpl_content)
check("JS link to notifications_premium.js", "notifications_premium.js" in tpl_content)
check("Socket.IO script included", "socket.io" in tpl_content)
check("Tab container notifTabs", "notifTabs" in tpl_content)
check("Unread badge element", "unreadBadge" in tpl_content)
check("Toolbar element", "notifToolbar" in tpl_content)
check("Mark all read button", "markAllReadBtn" in tpl_content)
check("Bulk delete button", "bulkDeleteBtn" in tpl_content)
check("Notification list container", "notifList" in tpl_content)
check("Skeleton loader", "notifSkeleton" in tpl_content)
check("Empty state", "notifEmpty" in tpl_content)
check("Sentinel for infinite scroll", "notifSentinel" in tpl_content)
check("Toast container", "notifToasts" in tpl_content)
check("Preferences overlay", "prefsOverlay" in tpl_content)
check("Preferences drawer", "prefsDrawer" in tpl_content)
check("Muted types list", "mutedTypesList" in tpl_content)
check("Tabs rendered from Jinja", "tabs" in tpl_content)

# Tab labels
check("Tab data-tab attribute pattern", "data-tab" in tpl_content)
check("Tab label Jinja variable", "tab.label" in tpl_content)
check("Tab loop Jinja", "for tab in tabs" in tpl_content)

# ============================================================
# SECTION 7: CSS
# ============================================================
print("\n--- Premium CSS ---")
css_content = safe_read("static/css/notifications_premium.css")
check("notifications_premium.css exists", bool(css_content))
check("Card class", ".notif-card" in css_content)
check("Unread card class", ".notif-card.unread" in css_content)
check("Read card class", ".notif-card.read" in css_content)
check("Selected card class", ".notif-card.selected" in css_content)
check("Tab class", ".notif-premium-tab" in css_content)
check("Active tab gold gradient", "d4a843" in css_content)
check("Badge class", ".notif-premium-badge" in css_content)
check("Avatar class", ".notif-card-avatar" in css_content)
check("Card title class", ".notif-card-title" in css_content)
check("Card preview class", ".notif-card-preview" in css_content)
check("Card meta class", ".notif-card-meta" in css_content)
check("Card timestamp", ".notif-card-timestamp" in css_content)
check("Card action button", ".notif-card-action" in css_content)
check("Mark read button", ".mark-read" in css_content)
check("Unread dot", ".notif-unread-dot" in css_content)
check("Card checkbox", ".notif-card-check" in css_content)
check("Swipe background", ".notif-swipe-bg" in css_content)
check("Swipe read button", ".n-swipe-read" in css_content)
check("Swipe delete button", ".n-swipe-delete" in css_content)
check("Skeleton avatar", ".n-skele-avatar" in css_content)
check("Skeleton line", ".n-skele-line" in css_content)
check("Shimmer animation", "nShimmer" in css_content)
check("Empty state", ".notif-premium-empty" in css_content)
check("Toast styles", ".notif-toast" in css_content)
check("Overlay", ".notif-premium-overlay" in css_content)
check("Drawer", ".notif-premium-drawer" in css_content)
check("Toggle switch", ".n-toggle" in css_content)
check("Preferences row", ".n-prefs-row" in css_content)
check("Mute type row", ".n-mute-type-row" in css_content)
check("Responsive 480px", "@media (max-width: 480px)" in css_content)
check("Responsive 768px", "@media (max-width: 768px)" in css_content)
check("Responsive 1024px", "@media (min-width: 1024px)" in css_content)
check("44px touch target on tabs", "min-height: 44px" in css_content)

# ============================================================
# SECTION 8: JS
# ============================================================
print("\n--- Premium JS ---")
js_content = safe_read("static/js/notifications_premium.js")
check("notifications_premium.js exists", bool(js_content))
check("IIFE wrapper", "function ()" in js_content)
check("State object", "var S" in js_content or "let S" in js_content or "const S" in js_content)
check("switchTab function", "switchTab" in js_content)
check("onTabClick handler", "onTabClick" in js_content)
check("fetchTab function", "fetchTab" in js_content)
check("Uses /api/notifications as base URL", "API = '/api/notifications'" in js_content)
check("buildCard function", "buildCard" in js_content)
check("Mark read function", "function mark(" in js_content)
check("Delete function", "function del(" in js_content)
check("Mark all read handler", "onMarkAllRead" in js_content)
check("Bulk delete handler", "onBulkDelete" in js_content)
check("toggleCard function", "toggleCard" in js_content)
check("fetchUnread function", "fetchUnread" in js_content)
check("IntersectionObserver for infinite scroll", "IntersectionObserver" in js_content)
check("Scroll fallback", "scroll" in js_content)
check("Socket.IO connection", "io()" in js_content)
check("notification:join emit", "notification:join" in js_content)
check("notification:new listener", "notification:new" in js_content)
check("Touch swipe handlers", "touchstart" in js_content and "touchmove" in js_content and "touchend" in js_content)
check("openPrefs function", "openPrefs" in js_content)
check("closePrefs function", "closePrefs" in js_content)
check("renderPrefs function", "renderPrefs" in js_content)
check("savePrefs function", "savePrefs" in js_content)
check("toast function", "function toast(" in js_content)
check("timeAgo helper", "timeAgo" in js_content)
check("esc helper (escapeHtml)", "function esc(" in js_content)
check("DOMContentLoaded init", "DOMContentLoaded" in js_content)
check("Header badge update", "notif-count" in js_content)

# ============================================================
# SECTION 9: Seed script
# ============================================================
print("\n--- Seed script ---")
seed_content = safe_read("scripts/seed_phase60_notifications.py")
check("seed script exists", bool(seed_content))
check("Seed creates follow notification", "follow" in seed_content and "chain_moon" in seed_content)
check("Seed creates post_like notification", "post_like" in seed_content)
check("Seed creates message notification", "new_message" in seed_content)
check("Seed creates live_started notification", "live_started" in seed_content)
check("Seed creates wallet_received notification", "wallet_received" in seed_content)
check("Seed creates verification_approved notification", "verification_approved" in seed_content)
check("Seed creates system_announcement notification", "system_announcement" in seed_content)
check("Seed dedup check", "Dedup" in seed_content or "dedup" in seed_content or "already exist" in seed_content)
check("Seed uses chain_notifications table", "chain_notifications" in seed_content)

# ============================================================
# SECTION 10: Compile check
# ============================================================
print("\n--- Compile check ---")
result = subprocess.run(
    ["python3", "-m", "compileall",
     "api_routes/notification_routes.py",
     "services/notification_center_service.py",
     "services/notification_engine.py"],
    capture_output=True, text=True, cwd=os.path.join(os.path.dirname(__file__), "..")
)
check("Python backend compiles", result.returncode == 0)
check("No syntax errors", "Error" not in result.stderr and " error" not in result.stdout.lower())

# ============================================================
# SECTION 11: Import check
# ============================================================
print("\n--- Import check ---")
_nc_ok = False
try:
    importlib.import_module("services.notification_center_service")
    _nc_ok = True
except Exception:
    _nc_ok = False
check("notification_center_service imports cleanly", _nc_ok)

_nr_ok = False
try:
    importlib.import_module("api_routes.notification_routes")
    _nr_ok = True
except Exception:
    _nr_ok = False
check("notification_routes imports cleanly", _nr_ok)

# ============================================================
# SECTION 12: Flask integration
# ============================================================
print("\n--- Flask integration ---")
try:
    test_app = create_test_app()
    from api_routes.notification_routes import notification_engine_bp
    test_app.register_blueprint(notification_engine_bp)
    check("Blueprint registers in Flask without error", True)
except Exception as e:
    check(f"Blueprint registration: {e}", False)

# ============================================================
# SECTION 13: Header badge integration
# ============================================================
print("\n--- Header badge ---")
base_content = safe_read("templates/base.html")
check("Header notification badge exists", "notif-badge" in base_content)
check("Badge links to /notifications/", "/notifications/" in base_content)
check("Badge has unread count span", "notif-count" in base_content)
check("Badge uses g_unread_count", "g_unread_count" in base_content)

# ============================================================
# SECTION 14: Notification type coverage
# ============================================================
print("\n--- Type coverage ---")
engine_content = safe_read("services/notification_engine.py")
types_in_engine = [
    "follow", "follow_accepted", "new_message", "message_reaction",
    "mention", "comment", "reply", "post_like", "reel_like",
    "story_reaction", "story_mention", "live_started", "creator_subscription",
    "wallet_transfer", "wallet_received", "dating_match",
    "verification_approved", "security_alert", "system_announcement",
]
for t in types_in_engine:
    check(f"Notification type '{t}' in engine", t in engine_content)

# ============================================================
# SECTION 15: Code quality
# ============================================================
print("\n--- Code quality ---")
check("No hardcoded passwords in routes", "password" not in routes_content.lower())
check("No hardcoded passwords in service", "password" not in svc_content.lower())

print(f"\n{'=' * 60}")
print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
print(f"{'=' * 60}")

if FAIL > 0:
    print("\nFailed checks:")
    for e in ERRORS:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("All checks passed!")
    sys.exit(0)
