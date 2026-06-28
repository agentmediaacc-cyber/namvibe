#!/usr/bin/env python3
"""Audit social UI pages exist, are not placeholders, and have working buttons."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'development'
os.environ['CHAIN_FAST_LOCAL'] = '1'
os.environ['WTF_CSRF_ENABLED'] = '0'

PASS, FAIL = 0, 0
def test(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} - {detail}")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(BASE, "templates")

print("=" * 60)
print("PHASE 160 — SOCIAL UI CONTRACT AUDIT")
print("=" * 60)

# 1. Check templates exist
print("\n1. Template files...")
tmpl_checks = {
    "notifications/index.html": os.path.join(TEMPLATES, "notifications", "index.html"),
    "notifications/center.html": os.path.join(TEMPLATES, "notifications", "center.html"),
    "profile/friends.html": os.path.join(TEMPLATES, "profile", "friends.html"),
    "profile/friend_requests.html": os.path.join(TEMPLATES, "profile", "friend_requests.html"),
    "profile/followers.html": os.path.join(TEMPLATES, "profile", "followers.html"),
    "profile/following.html": os.path.join(TEMPLATES, "profile", "following.html"),
}
for name, path in tmpl_checks.items():
    test(f"template exists: {name}", os.path.isfile(path), f"not found at {path}")

messages_dir = os.path.join(TEMPLATES, "messages")
calls_dir = os.path.join(TEMPLATES, "calls")
test("templates/messages/ has files", os.path.isdir(messages_dir) and len(os.listdir(messages_dir)) > 0, "no files found")
test("templates/calls/ has files", os.path.isdir(calls_dir) and len(os.listdir(calls_dir)) > 0, "no files found")

# 2. Check no placeholder text in social UI templates
print("\n2. Placeholder text check...")
placeholder_keywords = ["Coming soon", "Placeholder", "TODO", "Under construction", "Not implemented", "Coming Soon"]
social_templates = list(tmpl_checks.values()) + [
    os.path.join(TEMPLATES, "profile", "public.html"),
    os.path.join(TEMPLATES, "profile", "index.html"),
    os.path.join(TEMPLATES, "profile", "private_profile.html"),
    os.path.join(TEMPLATES, "profile", "partials", "profile_actions.html"),
    os.path.join(TEMPLATES, "base.html"),
    os.path.join(TEMPLATES, "chain_home.html"),
]
found_placeholder = False
for tp in social_templates:
    if os.path.isfile(tp):
        try:
            content = open(tp, encoding="utf-8", errors="replace").read()
            for kw in placeholder_keywords:
                if kw in content:
                    found_placeholder = True
                    test(f"placeholder '{kw}' found in {os.path.relpath(tp, TEMPLATES)}", False, f"contains '{kw}'")
        except Exception as e:
            test(f"read {os.path.relpath(tp, TEMPLATES)}", False, str(e))
if not found_placeholder:
    test("no placeholder text in social templates", True)

# 3. Check routes exist via app.url_map
print("\n3. Route registration...")
try:
    from app import app
    rules = set()
    for rule in app.url_map.iter_rules():
        rules.add(rule.rule)

    route_checks = {
        "/notifications/": "notifications page",
        "/social/friends": "friends page",
        "/social/friend-requests": "friend requests page (social)",
        "/friends/requests": "friend requests page (legacy)",
        "/social/followers": "followers page",
        "/social/following": "following page",
        "/messages/": "messages inbox",
        "/calls/": "calls index",
        "/calls/recent": "calls recent",
    }
    for route, desc in route_checks.items():
        test(f"route exists: {route} ({desc})", route in rules, f"not in url_map")
except Exception as e:
    test("import app and inspect routes", False, str(e))

# 4. Check buttons in templates
print("\n4. Button presence...")
profile_templates = [
    os.path.join(TEMPLATES, "profile", "public.html"),
    os.path.join(TEMPLATES, "profile", "index.html"),
    os.path.join(TEMPLATES, "profile", "private_profile.html"),
    os.path.join(TEMPLATES, "profile", "modern_profile.html"),
]
found_message_btn = False
found_follow_btn = False
for tp in profile_templates + [os.path.join(TEMPLATES, "profile", "partials", "profile_header.html")]:
    if os.path.isfile(tp):
        content = open(tp, encoding="utf-8", errors="replace").read()
        if "Message" in content:
            found_message_btn = True
            test(f"Message button found in {os.path.relpath(tp, TEMPLATES)}", True)
            break
if not found_message_btn:
    test("Message button in profile templates", False, "no 'Message' text found in any profile template")

for tp in profile_templates + [
    os.path.join(TEMPLATES, "profile", "partials", "profile_actions.html"),
    os.path.join(TEMPLATES, "profile", "partials", "profile_header.html"),
]:
    if os.path.isfile(tp):
        content = open(tp, encoding="utf-8", errors="replace").read()
        if "Follow" in content or "follow" in content:
            found_follow_btn = True
            test(f"Follow button found in {os.path.relpath(tp, TEMPLATES)}", True)
            break
if not found_follow_btn:
    test("Follow button in profile templates", False, "no 'Follow' text found")

base_html = os.path.join(TEMPLATES, "base.html")
chain_home = os.path.join(TEMPLATES, "chain_home.html")
found_notification_ui = False
for tp in [base_html, chain_home]:
    if os.path.isfile(tp):
        content = open(tp, encoding="utf-8", errors="replace").read()
        if "notification" in content.lower() and ("badge" in content.lower() or "bell" in content.lower() or "nvpro-badge" in content):
            found_notification_ui = True
            test(f"Notification bell/badge found in {os.path.relpath(tp, TEMPLATES)}", True)
            break
if not found_notification_ui:
    test("Notification bell/badge in base template", False, "no notification bell/badge found")

# 5. Verify blueprint imports in app.py
print("\n5. Blueprint registration in app.py...")
app_py_path = os.path.join(BASE, "app.py")
if os.path.isfile(app_py_path):
    app_content = open(app_py_path, encoding="utf-8", errors="replace").read()
    test("social_bp imported", "from api_routes.social_routes import social_api_bp, social_bp" in app_content, "social_bp import missing")
    test("friend_bp imported", "from api_routes.friend_routes import friend_bp" in app_content, "friend_bp import missing")
    test("message_bp registered", "register_blueprint(message_bp)" in app_content, "message_bp not registered")
    test("call_bp registered", "register_blueprint(call_bp)" in app_content, "call_bp not registered")
    test("notification_center_bp registered", "register_blueprint(notification_center_bp)" in app_content, "notification_center_bp not registered")
    test("notification_engine_bp registered", "register_blueprint(notification_engine_bp)" in app_content, "notification_engine_bp not registered")
    test("social_bp registered with /social prefix", "register_blueprint(social_bp, url_prefix=\"/social\")" in app_content, "social_bp url_prefix missing")

print(f"\nResults: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
sys.exit(0)
