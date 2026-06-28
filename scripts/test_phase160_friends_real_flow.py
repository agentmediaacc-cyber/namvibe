#!/usr/bin/env python3
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'development'
os.environ['CHAIN_FAST_LOCAL'] = '1'
os.environ['ALLOW_LOCAL_AUTH_FALLBACK'] = 'true'
os.environ['WTF_CSRF_ENABLED'] = '0'

from app import app as flask_app
flask_app.config["WTF_CSRF_ENABLED"] = False
from services.neon_service import fast_query, write_query
from services.engagement_service import follow_profile, unfollow_profile
from services.social_relationship_service import relationship_summary
from services.friend_service import suggest_friends
from services.blocking_service import block_user, is_blocked_any

PASS, FAIL = 0, 0
def test(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} - {detail}")


def _uuid():
    return str(uuid.uuid4())


def _cleanup(profile_ids):
    for pid in profile_ids:
        if pid:
            write_query(
                "UPDATE chain_profiles SET deleted_at = now() WHERE id = %s AND deleted_at IS NULL",
                (pid,)
            )
            write_query(
                "UPDATE chain_follows SET deleted_at = now() WHERE (follower_profile_id = %s OR following_profile_id = %s) AND deleted_at IS NULL",
                (pid, pid)
            )
            write_query(
                "UPDATE chain_blocks SET deleted_at = now() WHERE (blocker_profile_id = %s OR blocked_profile_id = %s) AND deleted_at IS NULL",
                (pid, pid)
            )


print("=" * 60)
print("PHASE 160 - FRIENDS REAL FLOW (E2E)")
print("=" * 60)

with flask_app.app_context():
    alpha_id = _uuid()
    beta_id = _uuid()
    auth_id = _uuid()
    suffix = _uuid()[:8]
    test_ids = [alpha_id, beta_id]

    # 1. Create alpha and beta users in chain_profiles
    print("\n--- Step 1: Create test users ---")
    try:
        write_query(
            """INSERT INTO chain_profiles (id, auth_user_id, username, display_name, email,
               profile_visibility, followers_count, following_count)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (alpha_id, auth_id, f"alpha_{suffix}", "Alpha Tester", "alpha@test.local", "public", 0, 0)
        )
        test("Insert alpha profile", True)
    except Exception as e:
        test("Insert alpha profile", False, str(e))

    try:
        write_query(
            """INSERT INTO chain_profiles (id, auth_user_id, username, display_name, email,
               profile_visibility, followers_count, following_count)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (beta_id, _uuid(), f"beta_{suffix}", "Beta Tester", "beta@test.local", "public", 0, 0)
        )
        test("Insert beta profile", True)
    except Exception as e:
        test("Insert beta profile", False, str(e))

    # Verify profiles exist
    alpha_db = fast_query("SELECT id, username, followers_count, following_count FROM chain_profiles WHERE id = %s", (alpha_id,), default=[])
    beta_db = fast_query("SELECT id, username, followers_count, following_count FROM chain_profiles WHERE id = %s", (beta_id,), default=[])
    test("Alpha found in DB", bool(alpha_db))
    test("Beta found in DB", bool(beta_db))

    # 2. Set up Flask test client, login as alpha
    print("\n--- Step 2: Flask test client as alpha ---")
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess['auth_user_id'] = auth_id
        sess['user_id'] = auth_id
        sess['profile_id'] = alpha_id
        sess['access_token'] = 'test-token-alpha'
        sess['email'] = 'alpha@test.local'
        sess['username'] = f'alpha_{suffix}'
        sess['logged_in'] = True
        sess['age_verified'] = True
        sess['age_check_required'] = False
    test("Session configured for alpha", True)

    # 3. Alpha visits Beta's profile
    print("\n--- Step 3: Alpha visits Beta's profile ---")
    resp = client.get(f"/profile/@beta_{suffix}")
    test("GET /profile/@beta returns 200", resp.status_code == 200, f"status={resp.status_code}")

    # 4. Alpha sends follow request
    print("\n--- Step 4: Alpha follows Beta ---")
    resp = client.post(f"/social/follow/{beta_id}")
    follow_data = resp.get_json() if resp.is_json else {}
    test("POST /social/follow/{beta_id} returns ok", follow_data.get("ok") or follow_data.get("status") == "ok", str(follow_data))
    test("Follow response state is following", follow_data.get("state") == "following", str(follow_data))

    # 5. Verify chain_follows row exists
    print("\n--- Step 5: Verify chain_follows row ---")
    follows = fast_query(
        "SELECT id, follower_profile_id, following_profile_id FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s AND deleted_at IS NULL",
        (alpha_id, beta_id), default=[]
    )
    test("chain_follows row created", len(follows) > 0, f"rows={len(follows)}")

    # 6. Switch to Beta's session, verify Beta can see follower/follow request
    print("\n--- Step 6: Beta checks follower ---")
    beta_auth_id = _uuid()
    with client.session_transaction() as sess:
        sess['auth_user_id'] = beta_auth_id
        sess['user_id'] = beta_auth_id
        sess['profile_id'] = beta_id
        sess['access_token'] = 'test-token-beta'
        sess['email'] = 'beta@test.local'
        sess['username'] = f'beta_{suffix}'
        sess['logged_in'] = True
        sess['age_verified'] = True
        sess['age_check_required'] = False
    test("Session configured for beta", True)

    resp = client.get("/social/api/followers")
    followers_data = resp.get_json() if resp.is_json else {}
    follower_ids = [f.get("id") for f in (followers_data if isinstance(followers_data, list) else followers_data.get("followers", []))]
    test("Beta sees Alpha as follower", alpha_id in follower_ids, f"followers={follower_ids}")

    # Check relationship summary from Beta's perspective
    summary = relationship_summary(alpha_id, beta_id)
    test("Alpha relationship shows following",
         summary.get("state") in ("following",), str(summary))

    # 7. Beta accepts the request (in follow model there's no explicit accept, it's just a follow)
    # For friend request flow, we'd use the friend request API. Let's test both.
    print("\n--- Step 7: Beta sends friend request to Alpha ---")
    with client.session_transaction() as sess:
        sess['auth_user_id'] = beta_auth_id
        sess['user_id'] = beta_auth_id
        sess['profile_id'] = beta_id
        sess['access_token'] = 'test-token-beta'
        sess['email'] = 'beta@test.local'
        sess['username'] = 'beta'
        sess['logged_in'] = True
        sess['age_verified'] = True
        sess['age_check_required'] = False

    fr_resp = client.post(f"/api/social/friend-request/{alpha_id}")
    fr_data = fr_resp.get_json() if fr_resp.is_json else {}
    test("Beta sends friend request to Alpha",
         fr_data.get("ok") or (fr_data.get("state") == "friend_requested"),
         str(fr_data))

    # Switch to Alpha to accept
    print("\n--- Step 8: Alpha accepts friend request ---")
    with client.session_transaction() as sess:
        sess['auth_user_id'] = auth_id
        sess['user_id'] = auth_id
        sess['profile_id'] = alpha_id
        sess['access_token'] = 'test-token-alpha'
        sess['email'] = 'alpha@test.local'
        sess['username'] = 'alpha'
        sess['logged_in'] = True
        sess['age_verified'] = True
        sess['age_check_required'] = False

    # List friend requests to find the request ID
    req_resp = client.get("/api/social/friend-requests")
    req_data = req_resp.get_json() if req_resp.is_json else {}
    incoming = req_data.get("incoming", [])
    request_id = incoming[0].get("request_id") or incoming[0].get("id") if incoming else None
    test("Alpha sees incoming friend request from Beta", request_id is not None,
         f"incoming={incoming}")

    if request_id:
        accept_resp = client.post(f"/api/social/friend-request/{request_id}/accept")
        accept_data = accept_resp.get_json() if accept_resp.is_json else {}
        test("Alpha accepts friend request",
             accept_data.get("ok") or accept_data.get("state") == "friends",
             str(accept_data))

    # 9. Verify Alpha appears in Beta's followers list
    print("\n--- Step 9: Verify followers/following lists ---")
    with client.session_transaction() as sess:
        sess['auth_user_id'] = beta_auth_id
        sess['user_id'] = beta_auth_id
        sess['profile_id'] = beta_id
        sess['access_token'] = 'test-token-beta'
        sess['email'] = 'beta@test.local'
        sess['username'] = 'beta'
        sess['logged_in'] = True
        sess['age_verified'] = True
        sess['age_check_required'] = False

    resp = client.get("/social/api/followers")
    followers_data = resp.get_json() if resp.is_json else {}
    follower_ids = [f.get("id") for f in (followers_data if isinstance(followers_data, list) else followers_data.get("followers", []))]
    test("Alpha in Beta's followers list", alpha_id in follower_ids, str(follower_ids))

    # 10. Verify Beta appears in Alpha's following list
    with client.session_transaction() as sess:
        sess['auth_user_id'] = auth_id
        sess['user_id'] = auth_id
        sess['profile_id'] = alpha_id
        sess['access_token'] = 'test-token-alpha'
        sess['email'] = 'alpha@test.local'
        sess['username'] = 'alpha'
        sess['logged_in'] = True
        sess['age_verified'] = True
        sess['age_check_required'] = False

    resp = client.get("/social/api/following")
    following_data = resp.get_json() if resp.is_json else {}
    following_ids = [f.get("id") for f in (following_data if isinstance(following_data, list) else following_data.get("following", []))]
    test("Beta in Alpha's following list", beta_id in following_ids, str(following_ids))

    # 11. Verify counts match
    print("\n--- Step 11: Verify counts ---")
    alpha_profile = fast_query("SELECT followers_count, following_count FROM chain_profiles WHERE id = %s", (alpha_id,), default=[])
    beta_profile = fast_query("SELECT followers_count, following_count FROM chain_profiles WHERE id = %s", (beta_id,), default=[])
    if alpha_profile:
        test("Alpha following_count >= 1", alpha_profile[0].get("following_count", 0) >= 1,
             f"following_count={alpha_profile[0].get('following_count', 0)}")
    if beta_profile:
        test("Beta followers_count >= 1", beta_profile[0].get("followers_count", 0) >= 1,
             f"followers_count={beta_profile[0].get('followers_count', 0)}")

    # 12. Test unfollow: Alpha unfollows Beta
    print("\n--- Step 12: Alpha unfollows Beta ---")
    resp = client.post(f"/social/follow/{beta_id}")
    unfollow_data = resp.get_json() if resp.is_json else {}
    test("Unfollow response ok", unfollow_data.get("ok") or unfollow_data.get("status") == "ok", str(unfollow_data))
    test("Unfollow response state is none or not following",
         unfollow_data.get("state") in ("none",) or unfollow_data.get("state") != "following",
         str(unfollow_data.get("state")))

    # 13. Verify chain_follows has deleted_at set, counts decremented
    print("\n--- Step 13: Verify soft-delete and counts ---")
    follows = fast_query(
        "SELECT id, deleted_at FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s",
        (alpha_id, beta_id), default=[]
    )
    test("chain_follows row exists (soft-deleted)", len(follows) > 0, f"rows={len(follows)}")
    if follows:
        test("chain_follows has deleted_at set", follows[0].get("deleted_at") is not None,
             f"deleted_at={follows[0].get('deleted_at')}")

    alpha_profile = fast_query("SELECT followers_count, following_count FROM chain_profiles WHERE id = %s", (alpha_id,), default=[])
    beta_profile = fast_query("SELECT followers_count, following_count FROM chain_profiles WHERE id = %s", (beta_id,), default=[])
    if alpha_profile:
        test("Alpha following_count decremented to 0",
             alpha_profile[0].get("following_count", 1) == 0,
             f"following_count={alpha_profile[0].get('following_count', 0)}")
    if beta_profile:
        test("Beta followers_count decremented to 0",
             beta_profile[0].get("followers_count", 1) == 0,
             f"followers_count={beta_profile[0].get('followers_count', 0)}")

    # 14. Test suggestions exist and exclude already-followed users
    print("\n--- Step 14: Test suggestions ---")
    suggestions = suggest_friends(alpha_id, limit=10)
    test("suggest_friends returns list", isinstance(suggestions, list), str(type(suggestions)))
    suggestion_ids = [s.get("id") for s in suggestions if s.get("id")]
    test("Alpha not in suggestions", alpha_id not in suggestion_ids, str(suggestion_ids))

    # 15. Test block/unblock
    print("\n--- Step 15: Test block/unblock ---")
    block_res = block_user(alpha_id, beta_id)
    test("block_user returns ok", block_res.get("ok"), str(block_res))
    test("is_blocked_any returns True", is_blocked_any(alpha_id, beta_id) is True)

    # Verify suggestions exclude blocked
    suggestions_after_block = suggest_friends(alpha_id, limit=10)
    blocked_in_suggestions = any(s.get("id") == beta_id for s in suggestions_after_block)
    test("Blocked user excluded from suggestions", not blocked_in_suggestions,
         f"beta_id={beta_id} in suggestions={blocked_in_suggestions}")

    # Unblock
    from services.blocking_service import unblock_user
    unblock_res = unblock_user(alpha_id, beta_id)
    test("unblock_user returns ok", unblock_res.get("ok"), str(unblock_res))
    test("is_blocked_any returns False after unblock", is_blocked_any(alpha_id, beta_id) is False)

    # Cleanup
    print("\n--- Cleanup ---")
    _cleanup(test_ids)
    test("Cleanup completed", True)

    print(f"\nResults: {PASS} passed, {FAIL} failed")
    if FAIL > 0:
        sys.exit(1)
    sys.exit(0)
