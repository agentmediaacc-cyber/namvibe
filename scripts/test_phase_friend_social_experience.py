#!/usr/bin/env python3
import os
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_ENV", "production")
os.environ.setdefault("CHAIN_FAST_LOCAL", "0")

from services.env_service import load_project_env
from services.friendship_service import are_friends
from services.neon_service import fast_query, get_pool_status, prime_neon_runtime, write_query
from services.profile_service import get_mutual_friends_summary, get_profile_by_id
from services.social_relationship_service import accept_friend_request, send_friend_request


load_project_env()

SKIP_EXIT = 2
PREFERRED_USERNAME_TOKENS = ("alpha", "beta", "test", "demo", "final", "chain")


def emit(status, name, detail=""):
    print(f"{status} [{name}] {detail}")
    return status == "PASS"


def database_host():
    raw = (os.getenv("DATABASE_URL") or "").strip()
    if not raw:
        return None
    return urlparse(raw).hostname


def dns_diagnose(host):
    if not host:
        return False, "missing DATABASE_URL host"
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        addrs = sorted({info[4][0] for info in infos})
        return True, ", ".join(addrs[:3])
    except Exception as error:
        return False, str(error)


def db_ping():
    last_detail = "empty SELECT now() result"
    for attempt in range(1, 4):
        try:
            rows = fast_query("SELECT now() AS now", (), default=[])
            if rows and rows[0].get("now"):
                return True, f"{rows[0]['now']} (attempt {attempt})"
            last_detail = f"empty SELECT now() result (attempt {attempt})"
        except Exception as error:
            last_detail = f"{error} (attempt {attempt})"
        time.sleep(1.2)
    return False, last_detail


def fail_db_dependency(reason):
    emit("FAIL_DB_DEPENDENCY", "database", reason)
    return 1


def skip_db(reason):
    emit("SKIP_DB", "database", reason)
    return SKIP_EXIT


def find_profile_by_username(username):
    rows = fast_query(
        """
        SELECT id, username, display_name, avatar_url
        FROM chain_profiles
        WHERE LOWER(username) = LOWER(%s)
          AND deleted_at IS NULL
        LIMIT 1
        """,
        (username,),
        default=[],
    )
    return rows[0] if rows else None


def find_candidate_profiles(limit=40):
    rows = fast_query(
        """
        SELECT id, username, display_name, avatar_url, account_type, profile_type,
               COALESCE(is_creator, FALSE) AS is_creator,
               COALESCE(is_verified, FALSE) AS is_verified,
               COALESCE(verified, FALSE) AS verified,
               COALESCE(business_name, '') AS business_name
        FROM chain_profiles
        WHERE deleted_at IS NULL
          AND COALESCE(username, '') <> ''
          AND LOWER(COALESCE(account_type, '')) NOT IN ('admin', 'system', 'business', 'government', 'official')
          AND LOWER(COALESCE(profile_type, '')) NOT IN ('admin', 'system', 'business', 'government', 'official', 'page')
        ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
        LIMIT %s
        """,
        (limit,),
        default=[],
    )
    return rows or []


def score_candidate(profile):
    username = (profile.get("username") or "").lower()
    profile_type = (profile.get("profile_type") or "").lower()
    account_type = (profile.get("account_type") or "").lower()
    score = 0
    for token in PREFERRED_USERNAME_TOKENS:
        if token in username:
            score += 10
    if profile.get("business_name"):
        score -= 20
    if profile.get("is_creator"):
        score -= 5
    if profile.get("is_verified") or profile.get("verified"):
        score -= 5
    if account_type in {"business", "government", "official", "admin", "system"}:
        score -= 50
    if profile_type in {"business", "government", "official", "admin", "system", "page"}:
        score -= 50
    return score


def select_profiles():
    env_a = (os.getenv("SOCIAL_E2E_USER_A_USERNAME") or "").strip()
    env_b = (os.getenv("SOCIAL_E2E_USER_B_USERNAME") or "").strip()
    if env_a and env_b:
        a = find_profile_by_username(env_a)
        b = find_profile_by_username(env_b)
        return a, b, "env"

    candidates = find_candidate_profiles()
    ranked = sorted(candidates, key=lambda row: (score_candidate(row), row.get("username") or ""), reverse=True)
    picked = []
    seen = set()
    for row in ranked:
        profile_id = str(row.get("id") or "")
        if not profile_id or profile_id in seen:
            continue
        seen.add(profile_id)
        picked.append(row)
        if len(picked) == 2:
            break
    if len(picked) < 2:
        return None, None, "auto"
    return picked[0], picked[1], "auto"


def hydrate_profile(profile_id):
    profile = get_profile_by_id(profile_id) or {}
    if not profile:
        return None
    profile.setdefault("id", profile_id)
    profile.setdefault("profile_visibility", profile.get("visibility") or "public")
    return profile


def channel_allowed_for_friends(profile, field_name):
    value = str(profile.get(field_name) or "").strip().lower()
    if not value:
        return True
    return value in {"everyone", "public", "friends", "friends_only"}


def cleanup_pair(profile_a_id, profile_b_id):
    write_query(
        """
        DELETE FROM chain_notifications
        WHERE (
            recipient_profile_id = %s AND actor_profile_id = %s
        ) OR (
            recipient_profile_id = %s AND actor_profile_id = %s
        )
        """,
        (profile_a_id, profile_b_id, profile_b_id, profile_a_id),
    )
    write_query(
        """
        DELETE FROM chain_friend_requests
        WHERE (sender_profile_id = %s AND recipient_profile_id = %s)
           OR (sender_profile_id = %s AND recipient_profile_id = %s)
        """,
        (profile_a_id, profile_b_id, profile_b_id, profile_a_id),
    )
    write_query(
        """
        DELETE FROM chain_friends
        WHERE (profile_id_1 = %s AND profile_id_2 = %s)
           OR (profile_id_1 = %s AND profile_id_2 = %s)
        """,
        (profile_a_id, profile_b_id, profile_b_id, profile_a_id),
    )


def latest_notification(recipient_id, actor_id, event_type):
    rows = fast_query(
        """
        SELECT id, event_type, actor_profile_id, entity_id, action_url, created_at
        FROM chain_notifications
        WHERE recipient_profile_id = %s
          AND actor_profile_id = %s
          AND event_type = %s
          AND deleted_at IS NULL
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (recipient_id, actor_id, event_type),
        default=[],
    )
    return rows[0] if rows else None


def friendship_row(profile_a_id, profile_b_id):
    rows = fast_query(
        """
        SELECT id, profile_id_1, profile_id_2, status, created_at, updated_at
        FROM chain_friends
        WHERE ((profile_id_1 = %s AND profile_id_2 = %s)
            OR (profile_id_1 = %s AND profile_id_2 = %s))
          AND deleted_at IS NULL
        ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
        LIMIT 1
        """,
        (profile_a_id, profile_b_id, profile_b_id, profile_a_id),
        default=[],
    )
    return rows[0] if rows else None


def main():
    host = database_host()
    emit("PASS" if host else "FAIL", "database_host", host or "DATABASE_URL missing")

    dns_ok, dns_detail = dns_diagnose(host)
    emit("PASS" if dns_ok else "FAIL", "dns_resolution", dns_detail)

    pool_before = get_pool_status()
    emit("PASS" if pool_before.get("configured") else "FAIL", "pool_status_before", str(pool_before))

    if not host:
        return fail_db_dependency("DATABASE_URL is not configured")
    if not dns_ok:
        return skip_db(f"DNS resolution failed for {host}: {dns_detail}")

    try:
        prime_neon_runtime()
        emit("PASS", "prime_neon_runtime", "submitted")
    except Exception as error:
        return fail_db_dependency(f"prime_neon_runtime failed: {error}")

    pool_after = get_pool_status()
    emit("PASS" if pool_after.get("configured") else "FAIL", "pool_status_after", str(pool_after))

    ping_ok, ping_detail = db_ping()
    emit("PASS" if ping_ok else "FAIL", "db_ping", ping_detail)
    if not ping_ok:
        return skip_db(f"DB ping failed: {ping_detail}")

    user_a, user_b, selection_mode = select_profiles()
    if not emit("PASS" if user_a else "FAIL", "user_a_selected", f"{selection_mode}:{user_a.get('username') if user_a else None}"):
        return 1
    if not emit("PASS" if user_b else "FAIL", "user_b_selected", f"{selection_mode}:{user_b.get('username') if user_b else None}"):
        return 1
    if not emit("PASS" if str(user_a.get('id')) != str(user_b.get('id')) else "FAIL", "selected_profiles_distinct", f"{user_a.get('username')} -> {user_b.get('username')}"):
        return 1
    print(f"SELECTED_USERNAMES {user_a.get('username')} {user_b.get('username')}")

    user_a_full = hydrate_profile(user_a["id"])
    user_b_full = hydrate_profile(user_b["id"])
    if not emit("PASS" if user_a_full else "FAIL", "user_a_profile_full", str(user_a_full)):
        return 1
    if not emit("PASS" if user_b_full else "FAIL", "user_b_profile_full", str(user_b_full)):
        return 1

    cleanup_pair(user_a["id"], user_b["id"])

    send_result = send_friend_request(user_a["id"], user_b["id"]) or {}
    request_id = send_result.get("request_id")
    if not emit("PASS" if send_result.get("ok") else "FAIL", "send_friend_request", str(send_result)):
        return 1
    if not emit("PASS" if request_id else "FAIL", "friend_request_id", str(request_id)):
        return 1

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
    if not emit("PASS" if request_row else "FAIL", "friend_request_row_exists", str(request_row)):
        return 1

    friend_request_notification = latest_notification(user_b["id"], user_a["id"], "friend_request")
    expected_a_url = f"/profile/@{user_a.get('username')}" if user_a.get("username") else f"/profile/id/{user_a['id']}"
    if not emit("PASS" if friend_request_notification else "FAIL", "friend_request_notification_exists", str(friend_request_notification)):
        return 1
    if not emit(
        "PASS" if friend_request_notification and str(friend_request_notification.get("entity_id")) == str(request_id) else "FAIL",
        "friend_request_notification_request_id",
        str(friend_request_notification),
    ):
        return 1
    if not emit(
        "PASS" if friend_request_notification and friend_request_notification.get("action_url") == expected_a_url else "FAIL",
        "friend_request_notification_action_url",
        str(friend_request_notification),
    ):
        return 1

    accept_result = accept_friend_request(user_b["id"], request_id) or {}
    if not emit("PASS" if accept_result.get("ok") else "FAIL", "accept_friend_request", str(accept_result)):
        return 1

    friendship = friendship_row(user_a["id"], user_b["id"])
    if not emit("PASS" if friendship else "FAIL", "friendship_row_exists", str(friendship)):
        return 1
    if not emit("PASS" if friendship and friendship.get("status") == "friend" else "FAIL", "friendship_status", str(friendship)):
        return 1
    if not emit("PASS" if are_friends(user_a["id"], user_b["id"]) else "FAIL", "are_friends_a_to_b", ""):
        return 1
    if not emit("PASS" if are_friends(user_b["id"], user_a["id"]) else "FAIL", "are_friends_b_to_a", ""):
        return 1

    failures = 0
    can_message_a = are_friends(user_a["id"], user_b["id"]) and channel_allowed_for_friends(user_b_full, "who_can_message")
    can_call_a = are_friends(user_a["id"], user_b["id"]) and channel_allowed_for_friends(user_b_full, "who_can_call")
    can_message_b = are_friends(user_b["id"], user_a["id"]) and channel_allowed_for_friends(user_a_full, "who_can_message")
    can_call_b = are_friends(user_b["id"], user_a["id"]) and channel_allowed_for_friends(user_a_full, "who_can_call")
    for ok, name, detail in [
        (can_message_a is True, "message_permission_a_to_b", str(can_message_a)),
        (can_call_a is True, "call_permission_a_to_b", str(can_call_a)),
        (can_message_b is True, "message_permission_b_to_a", str(can_message_b)),
        (can_call_b is True, "call_permission_b_to_a", str(can_call_b)),
    ]:
        if not emit("PASS" if ok else "FAIL", name, detail):
            failures += 1

    expected_b_url = f"/profile/@{user_b.get('username')}" if user_b.get("username") else f"/profile/id/{user_b['id']}"
    accepted_notification = latest_notification(user_a["id"], user_b["id"], "friend_accepted") or latest_notification(user_a["id"], user_b["id"], "friend_request_accepted")
    if not emit("PASS" if accepted_notification else "FAIL", "friend_accepted_notification_exists", str(accepted_notification)):
        failures += 1
    elif not emit(
        "PASS" if accepted_notification.get("action_url") == expected_b_url else "FAIL",
        "friend_accepted_notification_action_url",
        str(accepted_notification),
    ):
        failures += 1

    try:
        mutual = get_mutual_friends_summary(user_a["id"], user_b["id"], limit=3)
        if not emit(
            "PASS" if isinstance(mutual, dict) and isinstance(mutual.get("items", []), list) else "FAIL",
            "mutual_friends_summary_safe",
            str(mutual),
        ):
            failures += 1
    except Exception as error:
        emit("FAIL", "mutual_friends_summary_safe", str(error))
        failures += 1

    print("PASS" if failures == 0 else "FAIL")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
