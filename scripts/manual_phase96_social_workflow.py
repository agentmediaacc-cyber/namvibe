"""Manual Phase 96 social workflow check via Flask API test client."""

import os
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("WTF_CSRF_ENABLED", "0")

from app import app
from services.neon_service import fast_query, write_query


def log(message):
    print(f"[phase96-manual] {message}")


def create_profile(label):
    pid = str(uuid.uuid4())
    auth_id = str(uuid.uuid4())
    username = f"phase96_manual_{label}_{uuid.uuid4().hex[:8]}"
    write_query(
        """
        INSERT INTO chain_profiles (
            id, auth_user_id, email, username, full_name, display_name,
            is_public, profile_visibility, followers_count, following_count,
            friends_count, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, TRUE, 'public', 0, 0, 0, now(), now())
        """,
        (pid, auth_id, f"{username}@phase96.test", username, username, username),
        timeout_ms=15000,
    )
    return {"id": pid, "auth_user_id": auth_id, "username": username}


def cleanup(ids):
    if not ids:
        return
    placeholders = ", ".join(["%s"] * len(ids))
    params = list(ids)
    write_query(f"DELETE FROM chain_blocks WHERE blocker_profile_id IN ({placeholders}) OR blocked_profile_id IN ({placeholders})", params + params)
    write_query(f"DELETE FROM chain_follow_requests WHERE requester_profile_id IN ({placeholders}) OR target_profile_id IN ({placeholders})", params + params)
    write_query(f"DELETE FROM chain_follows WHERE follower_profile_id IN ({placeholders}) OR following_profile_id IN ({placeholders})", params + params)
    write_query(f"DELETE FROM chain_friend_requests WHERE sender_profile_id IN ({placeholders}) OR recipient_profile_id IN ({placeholders})", params + params)
    write_query(f"DELETE FROM chain_friends WHERE profile_id_1 IN ({placeholders}) OR profile_id_2 IN ({placeholders})", params + params)
    write_query(f"DELETE FROM chain_notifications WHERE recipient_profile_id IN ({placeholders}) OR actor_profile_id IN ({placeholders})", params + params)
    write_query(f"DELETE FROM chain_profiles WHERE id IN ({placeholders})", params)


def client_for(profile):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["profile_id"] = profile["id"]
        sess["auth_user_id"] = profile["auth_user_id"]
        sess["user_id"] = profile["auth_user_id"]
    return client


def post_json(client, path):
    response = client.post(path, json={})
    data = response.get_json() or {}
    log(f"{path} -> {response.status_code} {data}")
    if response.status_code >= 400 or not data.get("ok"):
        raise AssertionError(f"{path} failed: {response.status_code} {data}")
    return data


def get_json(client, path):
    response = client.get(path)
    data = response.get_json() or {}
    log(f"{path} -> {response.status_code} {data}")
    if response.status_code >= 400 or not data.get("ok"):
        raise AssertionError(f"{path} failed: {response.status_code} {data}")
    return data


def counts(a_id, b_id):
    rows = fast_query(
        """
        SELECT
          (SELECT COUNT(*) FROM chain_follows WHERE follower_profile_id = %s AND deleted_at IS NULL) AS a_following,
          (SELECT COUNT(*) FROM chain_follows WHERE following_profile_id = %s AND deleted_at IS NULL) AS b_followers
        """,
        (a_id, b_id),
        timeout_ms=15000,
        default=[{"a_following": 0, "b_followers": 0}],
    )
    return rows[0] if rows else {"a_following": 0, "b_followers": 0}


def run():
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    a = create_profile("a")
    b = create_profile("b")
    c = create_profile("c")
    ids = [a["id"], b["id"], c["id"]]
    try:
        a_client = client_for(a)
        b_client = client_for(b)

        follow_data = post_json(a_client, f"/api/social/follow/{b['id']}")
        assert follow_data["state"] == "following"
        follow_counts = counts(a["id"], b["id"])
        assert int(follow_counts["a_following"]) == 1 and int(follow_counts["b_followers"]) == 1
        log(f"profile follower/following counts after follow: {follow_counts}")

        unfollow_data = post_json(a_client, f"/api/social/unfollow/{b['id']}")
        assert unfollow_data["state"] == "none"
        unfollow_counts = counts(a["id"], b["id"])
        assert int(unfollow_counts["a_following"]) == 0 and int(unfollow_counts["b_followers"]) == 0
        log(f"profile follower/following counts after unfollow: {unfollow_counts}")

        friend_data = post_json(a_client, f"/api/social/friend-request/{b['id']}")
        assert friend_data["state"] == "friend_requested"
        request_id = friend_data["request_id"]

        incoming = get_json(b_client, "/api/social/friend-requests")
        assert any(str(item["id"]) == str(request_id) for item in incoming["incoming"])
        log("view friend requests: incoming request visible")

        accept_data = post_json(b_client, f"/api/social/friend-request/{request_id}/accept")
        assert accept_data["state"] == "friends"
        summary = get_json(a_client, f"/api/social/relationship-summary?profile_id={b['id']}")
        assert summary["state"] == "friends"
        log("friends button state: relationship-summary reports friends")

        decline_req = post_json(a_client, f"/api/social/friend-request/{c['id']}")
        c_client = client_for(c)
        decline_data = post_json(c_client, f"/api/social/friend-request/{decline_req['request_id']}/decline")
        assert decline_data["state"] == "none"
        log("decline friend request: declined successfully")

        log("manual workflow PASS")
        return True
    finally:
        cleanup(ids)


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
