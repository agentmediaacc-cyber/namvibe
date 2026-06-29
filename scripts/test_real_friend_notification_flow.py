#!/usr/bin/env python3
"""
Verify the real friend-request notification flow against production services.
"""
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_ENV", "production")
os.environ.setdefault("CHAIN_FAST_LOCAL", "0")

from services.neon_service import fast_query, write_query, prime_neon_runtime
from services.profile_service import get_profile_by_id
from services.social_relationship_service import send_friend_request, accept_friend_request
from services.friendship_service import are_friends, require_friendship_or_403


PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"PASS [{name}] {detail}")
    else:
        FAIL += 1
        print(f"FAIL [{name}] {detail}")


def _uuid():
    return str(uuid.uuid4())


def find_profile(*usernames):
    for username in usernames:
        rows = fast_query(
            """
            SELECT id, auth_user_id, username, display_name, avatar_url
            FROM chain_profiles
            WHERE LOWER(username) = LOWER(%s) AND deleted_at IS NULL
            LIMIT 1
            """,
            (username,),
            default=[],
        )
        if rows:
            return rows[0]
    return None


def create_test_profile(username, display_name):
    profile_id = _uuid()
    auth_user_id = _uuid()
    email = f"{username}@test.local"
    try:
        rows = write_query(
            """
            INSERT INTO chain_profiles (
                id, auth_user_id, username, display_name, email, profile_visibility,
                who_can_message, who_can_call, profile_completed, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, 'public', 'friends', 'friends', TRUE, now(), now())
            ON CONFLICT DO NOTHING
            RETURNING id, auth_user_id, username, display_name, avatar_url
            """,
            (profile_id, auth_user_id, username, display_name, email),
        )
        return rows[0] if rows else find_profile(username)
    except Exception:
        return None


def find_or_create_profiles():
    alpha = find_profile("alpha", "alpha_messenger", "alpha_social_test")
    beta = find_profile("beta", "beta_messenger", "beta_social_test")
    created = []
    if not alpha:
        alpha = create_test_profile("alpha_social_test", "Alpha Social Test")
        created.append(alpha and alpha.get("username"))
    if not beta:
        beta = create_test_profile("beta_social_test", "Beta Social Test")
        created.append(beta and beta.get("username"))
    return alpha, beta, [name for name in created if name]


def cleanup(alpha_id, beta_id):
    write_query(
        """
        DELETE FROM chain_notifications
        WHERE recipient_profile_id IN (%s, %s)
           OR actor_profile_id IN (%s, %s)
        """,
        (alpha_id, beta_id, alpha_id, beta_id),
    )
    write_query(
        """
        DELETE FROM chain_friend_requests
        WHERE sender_profile_id IN (%s, %s)
           OR recipient_profile_id IN (%s, %s)
        """,
        (alpha_id, beta_id, alpha_id, beta_id),
    )
    write_query(
        """
        DELETE FROM chain_friends
        WHERE (profile_id_1 = %s AND profile_id_2 = %s)
           OR (profile_id_1 = %s AND profile_id_2 = %s)
        """,
        (alpha_id, beta_id, beta_id, alpha_id),
    )
    write_query(
        """
        DELETE FROM chain_thread_members
        WHERE profile_id IN (%s, %s)
        """,
        (alpha_id, beta_id),
    )
    write_query(
        """
        DELETE FROM chain_message_threads
        WHERE thread_type = 'direct'
          AND (
            created_by_profile_id IN (%s, %s)
            OR id IN (
                SELECT tm.thread_id
                FROM chain_thread_members tm
                WHERE tm.profile_id IN (%s, %s)
            )
          )
        """,
        (alpha_id, beta_id, alpha_id, beta_id),
    )


def latest_friend_notification(recipient_id, actor_id):
    rows = fast_query(
        """
        SELECT id, event_type, title, body, actor_profile_id, entity_id, action_url, created_at
        FROM chain_notifications
        WHERE recipient_profile_id = %s
          AND actor_profile_id = %s
          AND deleted_at IS NULL
          AND event_type = 'friend_request'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (recipient_id, actor_id),
        default=[],
    )
    return rows[0] if rows else None


def main():
    print("=" * 72)
    print("REAL FRIEND NOTIFICATION FLOW")
    print("=" * 72)
    try:
        prime_neon_runtime()
    except Exception as error:
        check("prime_neon_runtime", False, str(error))
        print("\n" + "=" * 72)
        print(f"FAIL: {FAIL} checks failed, {PASS} passed")
        sys.exit(1)

    try:
        alpha, beta, created = find_or_create_profiles()
    except Exception as error:
        check("find_or_create_profiles", False, str(error))
        print("\n" + "=" * 72)
        print(f"FAIL: {FAIL} checks failed, {PASS} passed")
        sys.exit(1)
    check("alpha_profile", bool(alpha), str(alpha.get("username") if alpha else None))
    check("beta_profile", bool(beta), str(beta.get("username") if beta else None))
    if not alpha or not beta:
        print(f"\nFAIL: missing test profiles; created={created}")
        sys.exit(1)

    alpha_id = alpha["id"]
    beta_id = beta["id"]
    alpha_username = alpha.get("username")
    beta_username = beta.get("username")
    alpha_url = f"/profile/@{alpha_username}" if alpha_username else f"/profile/id/{alpha_id}"

    cleanup(alpha_id, beta_id)

    send_result = send_friend_request(alpha_id, beta_id)
    check("send_friend_request_ok", bool(send_result.get("ok")), str(send_result))
    request_id = send_result.get("request_id")
    check("send_friend_request_request_id", bool(request_id), str(request_id))

    request_rows = fast_query(
        """
        SELECT id, sender_profile_id, recipient_profile_id, status
        FROM chain_friend_requests
        WHERE id = %s
        LIMIT 1
        """,
        (request_id,),
        default=[],
    )
    request_row = request_rows[0] if request_rows else None
    check("friend_request_row_exists", bool(request_row), str(request_row))
    check(
        "friend_request_row_pending",
        bool(request_row and request_row.get("status") == "pending" and str(request_row.get("sender_profile_id")) == str(alpha_id) and str(request_row.get("recipient_profile_id")) == str(beta_id)),
        str(request_row),
    )

    notification = latest_friend_notification(beta_id, alpha_id)
    check("notification_exists", bool(notification), str(notification))
    check("notification_type", bool(notification and notification.get("event_type") == "friend_request"), str(notification))
    check("notification_request_entity", bool(notification and str(notification.get("entity_id")) == str(request_id)), str(notification))
    check("notification_action_url", bool(notification and notification.get("action_url") == alpha_url), str(notification))

    actor_profile = get_profile_by_id(notification.get("actor_profile_id")) if notification else None
    check("notification_actor_profile", bool(actor_profile and actor_profile.get("username") == alpha_username), str(actor_profile))
    check("notification_actor_avatar_real", bool(actor_profile is not None and actor_profile.get("avatar_url") == alpha.get("avatar_url")), str(actor_profile.get("avatar_url") if actor_profile else None))

    accept_result = accept_friend_request(beta_id, request_id)
    check("accept_friend_request_ok", bool(accept_result.get("ok")), str(accept_result))

    friends_rows = fast_query(
        """
        SELECT id, profile_id_1, profile_id_2, status
        FROM chain_friends
        WHERE ((profile_id_1 = %s AND profile_id_2 = %s) OR (profile_id_1 = %s AND profile_id_2 = %s))
          AND deleted_at IS NULL
        LIMIT 1
        """,
        (alpha_id, beta_id, beta_id, alpha_id),
        default=[],
    )
    friendship = friends_rows[0] if friends_rows else None
    check("friendship_row_exists", bool(friendship), str(friendship))
    check("friendship_status_friend", bool(friendship and friendship.get("status") == "friend"), str(friendship))
    check("are_friends_alpha_beta", are_friends(alpha_id, beta_id), "")
    check("are_friends_beta_alpha", are_friends(beta_id, alpha_id), "")

    _, message_allowed = require_friendship_or_403(alpha_id, beta_id, "message")
    _, call_allowed = require_friendship_or_403(alpha_id, beta_id, "call")
    check("message_permission_allowed", bool(message_allowed), "")
    check("call_permission_allowed", bool(call_allowed), "")

    accepted_rows = fast_query(
        """
        SELECT id, event_type, actor_profile_id, action_url
        FROM chain_notifications
        WHERE recipient_profile_id = %s
          AND actor_profile_id = %s
          AND deleted_at IS NULL
          AND event_type IN ('friend_accepted', 'friend_request_accepted')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (alpha_id, beta_id),
        default=[],
    )
    accepted_notification = accepted_rows[0] if accepted_rows else None
    beta_url = f"/profile/@{beta_username}" if beta_username else f"/profile/id/{beta_id}"
    check("accepted_notification_exists", bool(accepted_notification), str(accepted_notification))
    check("accepted_notification_action_url", bool(accepted_notification and accepted_notification.get("action_url") == beta_url), str(accepted_notification))

    print("\n" + "=" * 72)
    if FAIL:
        print(f"FAIL: {FAIL} checks failed, {PASS} passed")
        sys.exit(1)
    print(f"PASS: {PASS} checks passed")


if __name__ == "__main__":
    main()
