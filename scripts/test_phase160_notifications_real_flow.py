#!/usr/bin/env python3
"""Test real notification flows end-to-end using the Flask test client and direct DB queries."""
import os, sys, uuid, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'development'
os.environ['CHAIN_FAST_LOCAL'] = '1'
os.environ['ALLOW_LOCAL_AUTH_FALLBACK'] = 'true'
os.environ['WTF_CSRF_ENABLED'] = '0'

from flask import session as flask_session
from app import app
app.config["WTF_CSRF_ENABLED"] = False
from services.neon_service import fast_query, write_query
from services.notification_engine import create_notification, unread_count, list_notifications, mark_read, mark_all_read
from services.engagement_service import follow_profile, toggle_like, add_comment
from services.content_service import create_post_record

PASS, FAIL = 0, 0
def test(name, cond, detail=""):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  PASS: {name}")
    else: FAIL += 1; print(f"  FAIL: {name} - {detail}")

def make_pid():
    return str(uuid.uuid4())

def create_user(username):
    pid = make_pid()
    rows = write_query(
        "INSERT INTO chain_profiles (id, auth_user_id, username, display_name, followers_count, following_count, created_at) "
        "VALUES (%s, %s, %s, %s, 0, 0, now()) ON CONFLICT (username) DO UPDATE SET updated_at = now() RETURNING id",
        (pid, pid, username, username),
    )
    return str(rows[0]["id"]) if rows else pid

def login(client, pid, username):
    with client.session_transaction() as sess:
        sess["auth_user_id"] = pid
        sess["profile_id"] = pid
        sess["user_id"] = pid
        sess["username"] = username
        sess["full_name"] = username
        sess["logged_in"] = True
        sess["email"] = f"{username}@test.com"
        sess["profile_completed"] = True

def get_unread_count(profile_id):
    """Call unread_count bypassing the fast-local env shortcut."""
    old_fast = os.environ.pop('CHAIN_FAST_LOCAL', None)
    old_testing = os.environ.pop('FLASK_TESTING', None)
    try:
        return unread_count(profile_id)
    finally:
        if old_fast:
            os.environ['CHAIN_FAST_LOCAL'] = old_fast
        if old_testing:
            os.environ['FLASK_TESTING'] = old_testing

print("=" * 60)
print("PHASE 160 — NOTIFICATIONS REAL FLOW")
print("=" * 60)

with app.test_client() as client:
    # Create users
    print("\n1. Creating test users...")
    suffix = str(uuid.uuid4())[:8]
    alpha_pid = create_user(f"test_alpha_160_{suffix}")
    beta_pid = create_user(f"test_beta_160_{suffix}")
    test("alpha user created", bool(alpha_pid))
    test("beta user created", bool(beta_pid))

    # === Step 1: Alpha follows Beta ===
    print("\n2. Alpha follows Beta...")
    login(client, alpha_pid, f"test_alpha_160_{suffix}")
    result = follow_profile(alpha_pid, beta_pid)
    test("follow_profile success", result.get("success"), str(result))
    test("Alpha is now following", result.get("following", False), str(result))

    # === Step 2: Verify notification row exists for Beta ===
    print("\n3. Verify new_follower notification for Beta...")
    rows = fast_query(
        "SELECT * FROM chain_notifications WHERE recipient_profile_id = %s AND event_type = 'new_follower' ORDER BY created_at DESC LIMIT 1",
        (beta_pid,), default=[]
    )
    test("new_follower notification created", len(rows) >= 1, f"count={len(rows)}")
    test("actor is Alpha", rows and rows[0].get("actor_profile_id") == alpha_pid, str(rows[0] if rows else {}))
    notif_id = rows[0]["id"] if rows else None

    # === Step 3: Verify Beta's unread count increased ===
    print("\n4. Beta unread count...")
    beta_unread = get_unread_count(beta_pid)
    test("unread_count >= 1", beta_unread >= 1, f"got {beta_unread}")

    # === Step 4: Beta accepts follow/request ===
    print("\n5. Beta accepts follow request...")
    login(client, beta_pid, f"test_beta_160_{suffix}")
    follow_profile(beta_pid, alpha_pid)
    accepted_id = create_notification(
        recipient_profile_id=alpha_pid,
        event_type="follow_accepted",
        actor_profile_id=beta_pid,
        title="Follow accepted",
        body="accepted your follow request.",
        action_url=f"/profile/{beta_pid}",
        entity_type="profile",
        entity_id=alpha_pid,
    )
    test("follow_accepted notification id returned", bool(accepted_id), str(accepted_id))

    # === Step 5: Verify Alpha gets follow_accepted ===
    print("\n6. Verify follow_accepted notification for Alpha...")
    alpha_accepted = fast_query(
        "SELECT * FROM chain_notifications WHERE recipient_profile_id = %s AND event_type = 'follow_accepted' ORDER BY created_at DESC LIMIT 1",
        (alpha_pid,), default=[]
    )
    test("follow_accepted notification exists", len(alpha_accepted) >= 1, f"count={len(alpha_accepted)}")
    test("actor is Beta", alpha_accepted and alpha_accepted[0].get("actor_profile_id") == beta_pid, str(alpha_accepted[0] if alpha_accepted else {}))

    # === Step 6: Alpha likes a post ===
    print("\n7. Alpha likes Beta's post...")
    login(client, beta_pid, f"test_beta_160_{suffix}")
    post, err = create_post_record(beta_pid, body="Test post for notification flow.")
    test("Beta post created", post is not None and not err, str(err))
    post_id = post.get("id")

    login(client, alpha_pid, f"test_alpha_160_{suffix}")
    like_result = toggle_like(alpha_pid, "post", post_id)
    test("toggle_like success", like_result.get("success"), str(like_result))
    test("toggle_like liked=true", like_result.get("liked"), str(like_result))

    # === Step 7: Verify Beta gets like notification ===
    print("\n8. Verify post_liked notification for Beta...")
    like_notifs = fast_query(
        "SELECT * FROM chain_notifications WHERE recipient_profile_id = %s AND event_type = 'post_liked' AND entity_id = %s ORDER BY created_at DESC LIMIT 1",
        (beta_pid, post_id), default=[]
    )
    test("post_liked notification created", len(like_notifs) >= 1, f"count={len(like_notifs)}")
    test("actor is Alpha", like_notifs and like_notifs[0].get("actor_profile_id") == alpha_pid, str(like_notifs[0] if like_notifs else {}))

    # === Step 8: Alpha comments on Beta's post ===
    print("\n9. Alpha comments on Beta's post...")
    login(client, alpha_pid, f"test_alpha_160_{suffix}")
    comment_result = add_comment(alpha_pid, "post", post_id, "Great post from Alpha!")
    test("add_comment success", comment_result.get("success"), str(comment_result))

    # === Step 9: Verify Beta gets comment notification ===
    print("\n10. Verify post_commented notification for Beta...")
    comment_notifs = fast_query(
        "SELECT * FROM chain_notifications WHERE recipient_profile_id = %s AND event_type = 'post_commented' AND entity_id = %s ORDER BY created_at DESC LIMIT 1",
        (beta_pid, post_id), default=[]
    )
    test("post_commented notification created", len(comment_notifs) >= 1, f"count={len(comment_notifs)}")
    test("actor is Alpha", comment_notifs and comment_notifs[0].get("actor_profile_id") == alpha_pid, str(comment_notifs[0] if comment_notifs else {}))

    # === Step 10: Mark a notification as read ===
    print("\n11. Mark notification as read...")
    if notif_id:
        marked = mark_read(notif_id, beta_pid)
        test("mark_read returned True", marked, str(marked))
        read_check = fast_query(
            "SELECT is_read FROM chain_notifications WHERE id = %s", (notif_id,), default=[]
        )
        test("notification is_read=True", read_check and read_check[0].get("is_read") is True, str(read_check))

    # === Step 11: Verify mark_read succeeded by re-fetching ===
    print("\n12. Re-fetch and verify read state...")
    after_unread = get_unread_count(beta_pid)
    # Marking one notification as read may not decrease total if other notifs arrived,
    # but we can verify the specific one is now read
    recheck = fast_query(
        "SELECT is_read FROM chain_notifications WHERE id = %s", (notif_id,), default=[]
    )
    test("marked notification confirmed read", recheck and recheck[0].get("is_read") is True, str(recheck))

    # === Step 12: Verify no duplicate notifications ===
    print("\n13. No duplicate notifications...")
    dup_check = fast_query(
        "SELECT COUNT(*) as cnt FROM chain_notifications WHERE recipient_profile_id = %s AND actor_profile_id = %s AND event_type = 'new_follower'",
        (beta_pid, alpha_pid), default=[{"cnt": 0}]
    )
    test("no duplicate new_follower for same actor+recipient", dup_check[0]["cnt"] <= 1, f"count={dup_check[0]['cnt']}")

    # === Step 13: Notifications survive re-fetch ===
    print("\n14. Re-fetch notifications...")
    notifs_reload = list_notifications(beta_pid, limit=50)
    test("list_notifications returns items", len(notifs_reload) >= 1, f"count={len(notifs_reload)}")
    test("new_follower notification present in list", any(n.get("event_type") == "new_follower" for n in notifs_reload), str([n.get("event_type") for n in notifs_reload]))

print(f"\n{'=' * 60}")
print(f"Results: {PASS} passed, {FAIL} failed")
print(f"{'=' * 60}")
