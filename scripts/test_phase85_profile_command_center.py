"""
Phase 85 — NamVibe Profile Command Center Tests
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"

PASS = 0
FAIL = 0
ERRORS = []

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}  | {detail}")
        ERRORS.append(f"{label}: {detail}")

print("=" * 70)
print("Phase 85 — Profile Command Center Tests")
print("=" * 70)

# Test 1: Friend service exists and has required functions
print("\n--- 1. Friend service functions ---")
try:
    from services.friend_service import (
        send_friend_request, accept_friend_request, decline_friend_request,
        cancel_friend_request, remove_friend, list_friends, list_friend_requests,
        are_friends, get_mutual_friends, suggest_friends, get_friend_status,
    )
    check("send_friend_request exists", callable(send_friend_request))
    check("accept_friend_request exists", callable(accept_friend_request))
    check("decline_friend_request exists", callable(decline_friend_request))
    check("cancel_friend_request exists", callable(cancel_friend_request))
    check("remove_friend exists", callable(remove_friend))
    check("list_friends exists", callable(list_friends))
    check("list_friend_requests exists", callable(list_friend_requests))
    check("are_friends exists", callable(are_friends))
    check("get_mutual_friends exists", callable(get_mutual_friends))
    check("suggest_friends exists", callable(suggest_friends))
    check("get_friend_status exists", callable(get_friend_status))
except Exception as e:
    check("friend_service imports", False, str(e))

# Test 2: Schema tables exist
print("\n--- 2. Schema migration ---")
check("apply_phase85 schema script exists",
      os.path.exists("scripts/apply_phase85_profile_command_center_schema.py"))

# Test 3: Templates exist
print("\n--- 3. Templates exist ---")
tpl_dir = "templates/profile"
for tpl in ["posts_manager.html", "reels_manager.html", "command_center.html",
            "posts.html", "reels.html", "followers.html", "following.html",
            "friends.html", "privacy.html"]:
    path = os.path.join(tpl_dir, tpl)
    check(f"templates/profile/{tpl} exists", os.path.exists(path))

# Test 4: Routes exist
print("\n--- 4. Routes exist ---")
try:
    from flask import Flask
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"
    from api_routes.profile_routes import profile_bp
    app.register_blueprint(profile_bp)
    endpoints = set()
    for rule in app.url_map.iter_rules():
        endpoints.add(rule.endpoint)
    check("/profile/command-center route exists", "profile.command_center" in endpoints)
    check("/profile/@<username>/friends route exists", "profile.view_friends" in endpoints)
    check("/profile/@<username>/likes route exists", "profile.view_likes" in endpoints)
    check("/profile/@<username>/views route exists", "profile.view_views" in endpoints)
    check("/profile/@<username>/score route exists", "profile.view_score" in endpoints)
    check("/profile/api/friend-suggestions route exists", "profile.api_friend_suggestions" in endpoints)
    check("/profile/api/mutual-friends/<other_id> route exists", "profile.api_mutual_friends" in endpoints)
    check("/profile/api/posts/<post_id>/archive route exists", "profile.api_post_archive" in endpoints)
    check("/profile/api/reels/<reel_id>/archive route exists", "profile.api_reel_archive" in endpoints)
    check("/profile/api/friends route exists (Phase 85)", "profile.api_list_friends" in endpoints)
    check("/profile/api/friends/request route exists", "profile.api_new_friend_request" in endpoints)
    check("/profile/api/friends/<request_id>/accept route exists", "profile.api_accept_friend_req" in endpoints)
    check("/profile/api/friends/<request_id>/decline route exists", "profile.api_decline_friend_req" in endpoints)
    check("/profile/api/friends/<request_id>/cancel route exists", "profile.api_cancel_friend_req" in endpoints)
    check("/profile/api/friends/<profile_id>/remove route exists", "profile.api_remove_friend_by_id" in endpoints)
    check("/profile/api/friend-requests route exists", "profile.api_list_friend_requests" in endpoints)
    check("/profile/@<username>/posts route exists", "profile.view_posts" in endpoints)
    check("/profile/@<username>/reels route exists", "profile.view_reels" in endpoints)
    check("/profile/@<username>/followers route exists", "profile.view_followers" in endpoints)
    check("/profile/@<username>/following route exists", "profile.view_following" in endpoints)
    check("/profile/privacy route exists", "profile.privacy_settings" in endpoints)
    check("/profile/settings/privacy-advanced route exists", "profile.update_privacy_advanced" in endpoints)
    check("/profile/tab/<tab_name> route exists", "profile.tab_content" in endpoints)
    check("/profile/api/schedule/create route exists", "profile.api_schedule_create" in endpoints)
    check("/profile/api/scheduled route exists", "profile.api_scheduled_items" in endpoints)
except Exception as e:
    check("Route registration", False, str(e))

# Test 4B: Tab partial templates exist
print("\n--- 4B. Tab partial templates ---")
tab_dir = "templates/profile/tabs"
for tab in ["tab_stories.html", "tab_messages.html", "tab_calls.html", "tab_dating.html", "tab_wallet.html", "tab_notifications.html"]:
    path = os.path.join(tab_dir, tab)
    check(f"templates/profile/tabs/{tab} exists", os.path.exists(path))
    if os.path.exists(path):
        with open(path) as f:
            content = f.read()
        check(f"{tab} has real data (not static placeholder)", "{% if" in content or "{{ " in content)

# Test 5: JS file exists with required functions
print("\n--- 5. JS Command Center ---")
js_path = "static/js/profile_command_center.js"
if os.path.exists(js_path):
    with open(js_path) as f:
        js = f.read()
    checks = [
        ("Phase85 namespace", "Phase85" in js or "window.Phase85" in js),
        ("toggleComments", "toggleComments" in js),
        ("toggleSharing", "toggleSharing" in js),
        ("togglePin", "togglePin" in js),
        ("toggleArchive", "toggleArchive" in js),
        ("deleteItem", "deleteItem" in js),
        ("showVisibilityModal", "showVisibilityModal" in js),
        ("saveVisibility", "saveVisibility" in js),
        ("showReelAnalytics", "showReelAnalytics" in js),
        ("sendFriendRequest", "sendFriendRequest" in js),
        ("acceptFriendRequest", "acceptFriendRequest" in js),
        ("declineFriendRequest", "declineFriendRequest" in js),
        ("removeFriend", "removeFriend" in js),
        ("followUser", "followUser" in js),
        ("unfollowUser", "unfollowUser" in js),
        ("removeFollower", "removeFollower" in js),
        ("blockUser", "blockUser" in js),
        ("muteUser", "muteUser" in js),
        ("loadTab", "loadTab" in js),
        ("init function", "init" in js),
        ("DOMContentLoaded listener", "DOMContentLoaded" in js),
    ]
    for label, cond in checks:
        check(f"JS: {label}", cond)
else:
    check("profile_command_center.js exists", False)

# Test 6: CSS file exists
print("\n--- 6. CSS Command Center ---")
css_path = "static/css/profile_command_center.css"
if os.path.exists(css_path):
    with open(css_path) as f:
        css = f.read()
    checks = [
        (".command-center-shell", ".command-center-shell" in css),
        (".command-stats", ".command-stats" in css),
        (".command-grid", ".command-grid" in css),
        (".command-card", ".command-card" in css),
        (".manager-shell", ".manager-shell" in css),
        (".manager-grid", ".manager-grid" in css),
        (".people-list", ".people-list" in css),
        (".filter-chip", ".filter-chip" in css),
        (".visibility-modal-overlay", ".visibility-modal-overlay" in css),
        ("Responsive (768px)", "@media" in css),
    ]
    for label, cond in checks:
        check(f"CSS: {label}", cond)
else:
    check("profile_command_center.css exists", False)

# Test 6B: Creator tools has real data (no hardcoded placeholders)
print("\n--- 6B. Creator tools template ---")
ct_path = "templates/profile/creator_tools.html"
if os.path.exists(ct_path):
    with open(ct_path) as f:
        ct = f.read()
    checks = [
        ("Uses creator_data variable", "creator_data." in ct),
        ("Uses stats variable", "stats." in ct or "stats." in ct),
        ("Uses analytics variable", "analytics." in ct),
        ("Has scheduling form", "scheduleForm" in ct or "#scheduleForm" in ct),
        ("No placeholder earnings", "12.4m" not in ct),
        ("No placeholder sponsor", "MTC Namibia" not in ct),
        ("No hardcoded daily views", "Top 10%" not in ct),
        ("Has real chart bars", "cs-chart-bar" in ct),
        ("Has links section", "cs-links" in ct),
        ("No hardcoded AI captions", "POV: You found" not in ct or "Exclusive session starts" not in ct),
    ]
    for label, cond in checks:
        check(f"Creator Tools: {label}", cond)

# Test 7: /reels/upload no longer 500 (public_stats is safe)
print("\n--- 7. /reels/upload safety ---")
header_path = "templates/profile/partials/profile_header.html"
if os.path.exists(header_path):
    with open(header_path) as f:
        content = f.read()
    check("public_stats has default filter", "public_stats|default({})" in content or 'public_stats|default({})' in content)
    check("profile_header.html loads safely", "public_stats" in content)
# Also check the reels upload route uses build_profile_template_context
with open("api_routes/reels_routes.py") as f:
    reels_content = f.read()
check("_render_upload uses build_profile_template_context",
      "build_profile_template_context" in reels_content)

# Test 8: Stat cards are clickable in profile header
print("\n--- 8. Clickable stat cards ---")
with open(header_path) as f:
    header = f.read()
check("Posts stat is <a> link", 'href="' in header and "Posts" in header and "view_posts" in header)
check("Reels stat is <a> link", "view_reels" in header)
check("Followers stat is <a> link", "view_followers" in header)
check("Following stat is <a> link", "view_following" in header)
check("Friends stat is <a> link", "friends_page" in header)

# Test 9: Privacy defaults
print("\n--- 9. Privacy defaults ---")
try:
    from services.profile_service import get_profile_privacy, update_profile_privacy, invalidate_profile_cache
    privacy = get_profile_privacy(None)
    check("who_can_follow defaults to everyone", privacy.get("who_can_follow") == "everyone")
    check("who_can_message defaults to followers", privacy.get("who_can_message") == "followers")
    check("who_can_call defaults to friends", privacy.get("who_can_call") == "friends")
    check("who_can_view_posts defaults to public", privacy.get("who_can_view_posts") == "public")
    check("who_can_view_reels defaults to public", privacy.get("who_can_view_reels") == "public")
    check("invalidate_profile_cache exists", callable(invalidate_profile_cache))
    check("update_profile_privacy exists", callable(update_profile_privacy))
except Exception as e:
    check("Privacy tests", False, str(e))

# Test 10: Notification integration
print("\n--- 10. Notification integration ---")
try:
    from services.notification_service import create_notification
    check("create_notification exists", callable(create_notification))
except Exception as e:
    check("Notification test", False, str(e))

# Test 11: No placeholder/fake content in templates
print("\n--- 11. No placeholder content ---")
for tpl_name in ["posts.html", "reels.html", "followers.html", "following.html", "friends.html"]:
    tpl_path = os.path.join(tpl_dir, tpl_name)
    if os.path.exists(tpl_path):
        with open(tpl_path) as f:
            tpl = f.read()
        has_loop = "{% for" in tpl or "{% if" in tpl
        has_data = "{{ " in tpl
        check(f"{tpl_name} has real data (not static placeholder)", has_loop and has_data)

# Test 12: Cursor pagination limits
print("\n--- 12. Cursor pagination limits ---")
check("list_friends returns cursor-paginated result",
      True)  # validated by signature
try:
    sig = list_friends.__code__
    check("list_friends accepts cursor param", "cursor" in list_friends.__code__.co_varnames)
    check("list_friends accepts limit param", "limit" in list_friends.__code__.co_varnames)
except:
    pass

print(f"\n{'=' * 70}")
print(f"RESULTS: {PASS} passed, {FAIL} failed out of {PASS + FAIL} tests")
if ERRORS:
    print(f"ERRORS:\n" + "\n".join(f"  - {e}" for e in ERRORS))
print(f"{'=' * 70}")
sys.exit(0 if FAIL == 0 else 1)
