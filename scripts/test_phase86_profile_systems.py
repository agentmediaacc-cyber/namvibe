"""
Phase 86 — NamVibe Profile Systems Tests
Posts/Reels/Followers/Following/Friends managers
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
print("Phase 86 — Profile Systems Tests")
print("=" * 70)

# Test 1: Schema migration script
print("\n--- 1. Schema migration script ---")
check("apply_phase86 schema script exists",
      os.path.exists("scripts/apply_phase86_profile_systems_schema.py"))
if os.path.exists("scripts/apply_phase86_profile_systems_schema.py"):
    with open("scripts/apply_phase86_profile_systems_schema.py") as f:
        content = f.read()
    check("Has chain_friend_requests table", "chain_friend_requests" in content)
    check("Has chain_friends table", "chain_friends" in content)
    check("Has chain_post_settings table", "chain_post_settings" in content)
    check("Has chain_reel_settings table", "chain_reel_settings" in content)
    check("Has chain_profile_privacy table", "chain_profile_privacy" in content)
    check("Has 5 tables total", content.count("CREATE TABLE IF NOT EXISTS") == 5)
    check("Has 9 indexes total", content.count("CREATE INDEX IF NOT EXISTS") == 9)
    check("Uses IF NOT EXISTS (idempotent)", "IF NOT EXISTS" in content)

# Test 2: New service functions
print("\n--- 2. Service functions ---")
try:
    from services.friend_service import mark_close_friend, mark_best_friend
    check("mark_close_friend exists", callable(mark_close_friend))
    check("mark_best_friend exists", callable(mark_best_friend))
except Exception as e:
    check("friend_service imports (Phase 86)", False, str(e))

try:
    from services.profile_service import toggle_reel_sharing
    check("toggle_reel_sharing exists", callable(toggle_reel_sharing))
except Exception as e:
    check("toggle_reel_sharing import", False, str(e))

# Test 3: New routes exist
print("\n--- 3. Routes exist ---")
try:
    from flask import Flask
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"
    from api_routes.profile_routes import profile_bp
    app.register_blueprint(profile_bp)
    endpoints = set()
    for rule in app.url_map.iter_rules():
        endpoints.add(rule.endpoint)
    check("/profile/api/reels/<reel_id>/share-toggle route exists", "profile.api_reel_share_toggle" in endpoints)
    check("/profile/api/friends/<friend_id>/close route exists", "profile.api_friend_close" in endpoints)
    check("/profile/api/friends/<friend_id>/best route exists", "profile.api_friend_best" in endpoints)
except Exception as e:
    check("Route registration (Phase 86)", False, str(e))

# Test 4: Templates (5 manager pages rewritten)
print("\n--- 4. Templates exist ---")
tpl_dir = "templates/profile"
for tpl in ["posts.html", "reels.html", "followers.html", "following.html", "friends.html"]:
    path = os.path.join(tpl_dir, tpl)
    check(f"templates/profile/{tpl} exists", os.path.exists(path))

print("\n--- 4B. Template features ---")
for tpl_name in ["posts.html", "reels.html", "followers.html", "following.html", "friends.html"]:
    tpl_path = os.path.join(tpl_dir, tpl_name)
    if os.path.exists(tpl_path):
        with open(tpl_path) as f:
            tpl = f.read()
        check(f"{tpl_name}: extends base_profile", "extends \"profile/base_profile.html\"" in tpl or "extends 'profile/base_profile.html'" in tpl)
        check(f"{tpl_name}: has data-action attributes", "data-action=" in tpl)
        check(f"{tpl_name}: has load-more button", "load-more" in tpl)
        check(f"{tpl_name}: has next_cursor support", "next_cursor" in tpl)
        check(f"{tpl_name}: calls Phase86.init()", "Phase86.init()" in tpl)
        check(f"{tpl_name}: has empty state", "manager-empty" in tpl)
        check(f"{tpl_name}: uses profile variable", "profile." in tpl)

# Test 5: profile_systems.js
print("\n--- 5. profile_systems.js ---")
js_path = "static/js/profile_systems.js"
if os.path.exists(js_path):
    with open(js_path) as f:
        js = f.read()
    checks = [
        ("Phase86 namespace", "window.Phase86" in js or "Phase86." in js),
        ("toggleComments", "toggleComments" in js),
        ("toggleSharing", "toggleSharing" in js),
        ("togglePin", "togglePin" in js),
        ("toggleArchive", "toggleArchive" in js),
        ("deleteItem", "deleteItem" in js),
        ("showVisibilityModal", "showVisibilityModal" in js),
        ("saveVisibility", "saveVisibility" in js),
        ("showReelAnalytics", "showReelAnalytics" in js),
        ("followUser", "followUser" in js),
        ("unfollowUser", "unfollowUser" in js),
        ("removeFollower", "removeFollower" in js),
        ("blockUser", "blockUser" in js),
        ("muteUser", "muteUser" in js),
        ("sendFriendRequest", "sendFriendRequest" in js),
        ("acceptFriendRequest", "acceptFriendRequest" in js),
        ("declineFriendRequest", "declineFriendRequest" in js),
        ("cancelFriendRequest", "cancelFriendRequest" in js),
        ("removeFriend", "removeFriend" in js),
        ("toggleCloseFriend", "toggleCloseFriend" in js),
        ("toggleBestFriend", "toggleBestFriend" in js),
        ("loadMoreFollowers", "loadMoreFollowers" in js),
        ("loadMoreFollowing", "loadMoreFollowing" in js),
        ("init function", "Phase86.init" in js),
        ("data-action listener registration", "data-action" in js),
        ("DOMContentLoaded listener", "DOMContentLoaded" in js or "document.readyState" in js),
        ("Toast notification", "sysToast" in js or "toast(" in js),
        ("Confirm before delete", "confirmAction" in js),
    ]
    for label, cond in checks:
        check(f"JS: {label}", cond)
else:
    check("profile_systems.js exists", False)

# Test 6: profile_systems.css
print("\n--- 6. profile_systems.css ---")
css_path = "static/css/profile_systems.css"
if os.path.exists(css_path):
    with open(css_path) as f:
        css = f.read()
    checks = [
        (".profile-manager-shell", ".profile-manager-shell" in css),
        (".people-list", ".people-list" in css),
        (".people-card", ".people-card" in css),
        (".manager-grid", ".manager-grid" in css),
        (".manager-card", ".manager-card" in css),
        (".filter-chip", ".filter-chip" in css),
        (".load-more-btn", ".load-more-btn" in css),
        (".load-more-wrap", ".load-more-wrap" in css),
        (".manager-empty", ".manager-empty" in css),
        (".vis-modal-overlay", ".vis-modal-overlay" in css),
        (".vis-modal", ".vis-modal" in css),
        (".sys-toast", ".sys-toast" in css),
        (".following-group", ".following-group" in css),
        (".action-btn styles", ".action-btn" in css),
        (".people-avatar styles", ".people-avatar" in css),
        ("Skeleton loading", "skeleton" in css),
        ("Responsive (768px)", "@media (max-width: 768px)" in css),
        ("Animations", "@keyframes" in css),
    ]
    for label, cond in checks:
        check(f"CSS: {label}", cond)
else:
    check("profile_systems.css exists", False)

# Test 7: base_profile loads Phase 86 assets
print("\n--- 7. base_profile.html asset registration ---")
base_path = "templates/profile/base_profile.html"
if os.path.exists(base_path):
    with open(base_path) as f:
        base = f.read()
    check("loads profile_systems.css", "profile_systems.css" in base)
    check("loads profile_systems.js", "profile_systems.js" in base)
    check("loads profile_command_center.css", "profile_command_center.css" in base)
    check("loads profile_command_center.js", "profile_command_center.js" in base)

# Test 8: Friend service has all Phase 84-86 functions
print("\n--- 8. Complete friend service ---")
try:
    from services.friend_service import (
        send_friend_request, accept_friend_request, decline_friend_request,
        cancel_friend_request, remove_friend, list_friends, list_friend_requests,
        are_friends, get_mutual_friends, suggest_friends, get_friend_status,
        mark_close_friend, mark_best_friend,
    )
    all_callable = all(callable(fn) for fn_name in [
        "send_friend_request", "accept_friend_request", "decline_friend_request",
        "cancel_friend_request", "remove_friend", "list_friends", "list_friend_requests",
        "are_friends", "get_mutual_friends", "suggest_friends", "get_friend_status",
        "mark_close_friend", "mark_best_friend",
    ] for fn_name in dir() if not fn_name.startswith("_"))
    if "mark_close_friend" in dir() and "mark_best_friend" in dir():
        check("All 13 friend service functions", callable(mark_close_friend) and callable(mark_best_friend))
except Exception as e:
    check("Complete friend service", False, str(e))

# Test 9: Templates use cursor pagination (not page-based)
print("\n--- 9. Cursor pagination ---")
for tpl_name in ["posts.html", "reels.html", "followers.html", "following.html", "friends.html"]:
    tpl_path = os.path.join(tpl_dir, tpl_name)
    if os.path.exists(tpl_path):
        with open(tpl_path) as f:
            tpl = f.read()
        check(f"{tpl_name}: uses cursor-based next_cursor", "next_cursor" in tpl)
        check(f"{tpl_name}: loads 20 per page (limit=20)", "limit=20" in tpl or "limit=20" in tpl)

# Test 10: Specific template features
print("\n--- 10. Template-specific features ---")

# posts.html: toggle-comments, toggle-sharing, toggle-pin, toggle-archive, show-visibility, delete-item
posts_path = os.path.join(tpl_dir, "posts.html")
if os.path.exists(posts_path):
    with open(posts_path) as f:
        p = f.read()
    check("posts: has toggle-comments data-action", 'data-action="toggle-comments"' in p)
    check("posts: has toggle-sharing data-action", 'data-action="toggle-sharing"' in p)
    check("posts: has toggle-pin data-action", 'data-action="toggle-pin"' in p)
    check("posts: has toggle-archive data-action", 'data-action="toggle-archive"' in p)
    check("posts: has show-visibility data-action", 'data-action="show-visibility"' in p)
    check("posts: has delete-item data-action", 'data-action="delete-item"' in p)

# reels.html: 7 filter chips, reel-analytics
reels_path = os.path.join(tpl_dir, "reels.html")
if os.path.exists(reels_path):
    with open(reels_path) as f:
        r = f.read()
    chip_count = r.count("filter-chip")
    check("reels: has 7 filter chips", chip_count >= 7)
    check("reels: has reel-analytics data-action", 'data-action="reel-analytics"' in r)
    check("reels: has My Reels filter", "My Reels" in r or "filter=my" in r)

# followers.html: follow, remove-follower, block
followers_path = os.path.join(tpl_dir, "followers.html")
if os.path.exists(followers_path):
    with open(followers_path) as f:
        fw = f.read()
    check("followers: has follow data-action", 'data-action="follow"' in fw)
    check("followers: has remove-follower data-action", 'data-action="remove-follower"' in fw)
    check("followers: has block data-action", 'data-action="block"' in fw)

# following.html: unfollow, mute, send-friend-request
following_path = os.path.join(tpl_dir, "following.html")
if os.path.exists(following_path):
    with open(following_path) as f:
        fg = f.read()
    check("following: has unfollow data-action", 'data-action="unfollow"' in fg)
    check("following: has mute data-action", 'data-action="mute"' in fg)
    check("following: has send-friend-request data-action", 'data-action="send-friend-request"' in fg)
    check("following: has type filter chips", "type=" in fg)

# friends.html: accept/decline/cancel/remove, close/best friend toggles
friends_path = os.path.join(tpl_dir, "friends.html")
if os.path.exists(friends_path):
    with open(friends_path) as f:
        fr = f.read()
    check("friends: has accept-friend data-action", 'data-action="accept-friend"' in fr)
    check("friends: has decline-friend data-action", 'data-action="decline-friend"' in fr)
    check("friends: has cancel-friend-request data-action", 'data-action="cancel-friend-request"' in fr)
    check("friends: has remove-friend data-action", 'data-action="remove-friend"' in fr)
    check("friends: has close-friend data-action", 'data-action="close-friend"' in fr)
    check("friends: has best-friend data-action", 'data-action="best-friend"' in fr)
    check("friends: shows pending requests section", "Pending Requests" in fr)
    check("friends: shows sent requests section", "Sent Requests" in fr)

# Test 11: No placeholder/fake data
print("\n--- 11. No placeholder content ---")
for tpl_name in ["posts.html", "reels.html", "followers.html", "following.html", "friends.html"]:
    tpl_path = os.path.join(tpl_dir, tpl_name)
    if os.path.exists(tpl_path):
        with open(tpl_path) as f:
            tpl = f.read()
        has_loop = "{% for" in tpl or "{% if" in tpl
        has_data = "{{ " in tpl
        check(f"{tpl_name} uses real data (loop + template vars)", has_loop and has_data)

print(f"\n{'=' * 70}")
print(f"RESULTS: {PASS} passed, {FAIL} failed out of {PASS + FAIL} tests")
if ERRORS:
    print(f"ERRORS:\n" + "\n".join(f"  - {e}" for e in ERRORS))
print(f"{'=' * 70}")
sys.exit(0 if FAIL == 0 else 1)
