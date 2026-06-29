#!/usr/bin/env python3
import os
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_ENV", "production")
os.environ.setdefault("CHAIN_FAST_LOCAL", "0")

from services.env_service import load_project_env
from services.neon_service import fast_query, get_pool_status, prime_neon_runtime
from services.profile_service import get_mutual_friends_summary
from services.social_action_policy import get_action_policy


load_project_env()

SKIP_EXIT = 2


def emit(status, name, detail=""):
    print(f"{status} [{name}] {detail}")
    return status == "PASS"


def database_host():
    raw = (os.getenv("DATABASE_URL") or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    return parsed.hostname


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
    try:
        rows = fast_query("SELECT now() AS now", (), default=[])
        if rows and rows[0].get("now"):
            return True, str(rows[0]["now"])
        return False, "empty SELECT now() result"
    except Exception as error:
        return False, str(error)


def find_test_profile(*usernames):
    for username in usernames:
        rows = fast_query(
            """
            SELECT id, username, profile_visibility, who_can_message, who_can_call, is_page,
                   account_type, profile_type, is_creator, is_premium, is_verified, verified
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


def friendship_pair(alpha_id, beta_id):
    rows = fast_query(
        """
        SELECT profile_id_1, profile_id_2, status, updated_at, created_at
        FROM chain_friends
        WHERE ((profile_id_1 = %s AND profile_id_2 = %s)
            OR (profile_id_1 = %s AND profile_id_2 = %s))
          AND deleted_at IS NULL
        ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
        LIMIT 1
        """,
        (alpha_id, beta_id, beta_id, alpha_id),
        default=[],
    )
    return rows[0] if rows else None


def fail_db_dependency(reason):
    emit("FAIL_DB_DEPENDENCY", "database", reason)
    return 1


def skip_db(reason):
    emit("SKIP_DB", "database", reason)
    return SKIP_EXIT


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

    alpha = find_test_profile("alpha", "alpha_social_test", "alpha_messenger")
    beta = find_test_profile("beta", "beta_social_test", "beta_messenger")
    if not emit("PASS" if alpha else "FAIL", "alpha_profile", str(alpha)):
        return 1
    if not emit("PASS" if beta else "FAIL", "beta_profile", str(beta)):
        return 1

    friendship = friendship_pair(alpha["id"], beta["id"])
    if not emit("PASS" if friendship else "FAIL", "alpha_beta_friendship", str(friendship)):
        return 1
    if not emit("PASS" if friendship.get("status") == "friend" else "FAIL", "alpha_beta_friendship_status", str(friendship)):
        return 1

    alpha_policy = get_action_policy(alpha["id"], beta)
    beta_policy = get_action_policy(beta["id"], alpha)

    failures = 0
    for ok, name, detail in [
        (alpha_policy.get("can_chat") is True, "message_permission_alpha_to_beta", str(alpha_policy)),
        (alpha_policy.get("can_call") is True, "call_permission_alpha_to_beta", str(alpha_policy)),
        (beta_policy.get("can_chat") is True, "message_permission_beta_to_alpha", str(beta_policy)),
        (beta_policy.get("can_call") is True, "call_permission_beta_to_alpha", str(beta_policy)),
    ]:
        if not emit("PASS" if ok else "FAIL", name, detail):
            failures += 1

    try:
        mutual = get_mutual_friends_summary(alpha["id"], beta["id"], limit=3)
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
