"""Phase 96 social relationship regression tests."""

import os
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("WTF_CSRF_ENABLED", "0")

from app import create_app
from services.neon_service import fast_query, write_query
from services.social_relationship_service import (
    accept_friend_request,
    follow,
    list_friend_requests,
    send_friend_request,
    unfollow,
)


PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS {name} {detail}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


def scalar(sql, params):
    rows = fast_query(sql, params, timeout_ms=15000, default=[])
    if not rows:
        return 0
    return rows[0].get("count", 0)


def create_profile(username):
    profile_id = str(uuid.uuid4())
    auth_id = str(uuid.uuid4())
    email = f"{username}@phase96.test"
    write_query(
        """
        INSERT INTO chain_profiles (
            id, auth_user_id, email, username, full_name, display_name,
            is_public, profile_visibility, followers_count, following_count,
            friends_count, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, TRUE, 'public', 0, 0, 0, now(), now())
        """,
        (profile_id, auth_id, email, username, username, username),
        timeout_ms=15000,
    )
    return {"id": profile_id, "auth_user_id": auth_id, "username": username}


def cleanup(ids):
    if not ids:
        return
    params = list(ids)
    placeholders = ", ".join(["%s"] * len(params))
    write_query(f"DELETE FROM chain_blocks WHERE blocker_profile_id IN ({placeholders}) OR blocked_profile_id IN ({placeholders})", params + params)
    write_query(f"DELETE FROM chain_follow_requests WHERE requester_profile_id IN ({placeholders}) OR target_profile_id IN ({placeholders})", params + params)
    write_query(f"DELETE FROM chain_follows WHERE follower_profile_id IN ({placeholders}) OR following_profile_id IN ({placeholders})", params + params)
    write_query(f"DELETE FROM chain_friend_requests WHERE sender_profile_id IN ({placeholders}) OR recipient_profile_id IN ({placeholders})", params + params)
    write_query(f"DELETE FROM chain_friends WHERE profile_id_1 IN ({placeholders}) OR profile_id_2 IN ({placeholders})", params + params)
    write_query(f"DELETE FROM chain_notifications WHERE recipient_profile_id IN ({placeholders}) OR actor_profile_id IN ({placeholders})", params + params)
    write_query(f"DELETE FROM chain_profiles WHERE id IN ({placeholders})", params)


def set_session(client, profile):
    with client.session_transaction() as sess:
        sess["profile_id"] = profile["id"]
        sess["auth_user_id"] = profile["auth_user_id"]
        sess["user_id"] = profile["auth_user_id"]


def run():
    print("Phase 96 social relationship tests")
    from scripts.phase96_fix_social_relationships import run as run_migration

    run_migration()

    suffix = uuid.uuid4().hex[:8]
    a = create_profile(f"phase96_a_{suffix}")
    b = create_profile(f"phase96_b_{suffix}")
    c = create_profile(f"phase96_c_{suffix}")
    ids = [a["id"], b["id"], c["id"]]

    try:
        res = follow(a["id"], b["id"])
        check("A follows B", res.get("ok") and res.get("state") == "following", str(res))

        res = follow(a["id"], b["id"])
        active_count = scalar(
            "SELECT COUNT(*) AS count FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s AND deleted_at IS NULL",
            (a["id"], b["id"]),
        )
        check("duplicate follow does not duplicate", res.get("ok") and active_count == 1, f"active_count={active_count}")

        res = unfollow(a["id"], b["id"])
        active_count = scalar(
            "SELECT COUNT(*) AS count FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s AND deleted_at IS NULL",
            (a["id"], b["id"]),
        )
        check("A unfollows B", res.get("ok") and active_count == 0, f"active_count={active_count}")

        res = send_friend_request(a["id"], b["id"])
        request_id = res.get("request_id")
        check("A sends friend request to B", res.get("ok") and res.get("state") == "friend_requested" and request_id, str(res))

        incoming = list_friend_requests(b["id"])
        check("B sees request", any(str(r.get("id")) == str(request_id) for r in incoming.get("incoming", [])), f"request_id={request_id}")

        res = accept_friend_request(b["id"], request_id)
        check("B accepts request", res.get("ok") and res.get("state") == "friends", str(res))
        friend_count = scalar(
            "SELECT COUNT(*) AS count FROM chain_friends WHERE profile_id_1 = LEAST(%s::uuid, %s::uuid) AND profile_id_2 = GREATEST(%s::uuid, %s::uuid) AND deleted_at IS NULL",
            (a["id"], b["id"], a["id"], b["id"]),
        )
        check("both become friends", friend_count == 1, f"friend_count={friend_count}")

        write_query(
            "INSERT INTO chain_blocks (blocker_profile_id, blocked_profile_id, created_at) VALUES (%s, %s, now())",
            (b["id"], c["id"]),
        )
        res = follow(c["id"], b["id"])
        check("blocked users cannot follow", not res.get("ok") and res.get("state") == "blocked", str(res))
        res = send_friend_request(c["id"], b["id"])
        check("blocked users cannot friend request", not res.get("ok") and res.get("state") == "blocked", str(res))

        app = create_app()
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        client = app.test_client()

        set_session(client, a)
        response = client.post(f"/api/social/follow/{c['id']}", json={})
        data = response.get_json() or {}
        check("Discovery follow endpoint returns ok JSON", response.status_code == 200 and data.get("ok") and data.get("state") == "following", str(data))

        response = client.post(f"/api/social/unfollow/{c['id']}", json={})
        data = response.get_json() or {}
        check("Discovery unfollow endpoint returns ok JSON", response.status_code == 200 and data.get("ok") and data.get("state") == "none", str(data))

        response = client.post(f"/api/social/friend-request/{c['id']}", json={})
        data = response.get_json() or {}
        check("Discovery friend endpoint returns ok JSON", response.status_code == 200 and data.get("ok") and data.get("state") == "friend_requested", str(data))

        response = client.get("/api/social/friend-requests")
        data = response.get_json() or {}
        check("outgoing requests endpoint returns JSON", response.status_code == 200 and data.get("ok") and "outgoing" in data, str(data.keys()))

    finally:
        cleanup(ids)

    print(f"Phase 96 results: {PASS} passed, {FAIL} failed")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    run()
