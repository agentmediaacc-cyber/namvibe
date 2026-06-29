#!/usr/bin/env python3
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_ENV", "production")
os.environ.setdefault("CHAIN_FAST_LOCAL", "0")

from services.neon_service import fast_query, prime_neon_runtime
from services.profile_service import get_mutual_friends_summary
from services.social_action_policy import get_action_policy


def emit(ok, name, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} [{name}] {detail}")
    return ok


def find_pair():
    rows = fast_query(
        """
        SELECT fr.sender_profile_id AS alpha_id,
               fr.recipient_profile_id AS beta_id
        FROM chain_friend_requests fr
        WHERE fr.status = 'accepted'
        ORDER BY fr.updated_at DESC NULLS LAST, fr.created_at DESC NULLS LAST
        LIMIT 1
        """,
        (),
        default=[],
    )
    return rows[0] if rows else None


def load_profile(profile_id):
    rows = fast_query(
        """
        SELECT id, username, profile_visibility, who_can_message, who_can_call, is_page,
               account_type, profile_type, is_creator, is_premium, is_verified, verified
        FROM chain_profiles
        WHERE id = %s
        LIMIT 1
        """,
        (profile_id,),
        default=[],
    )
    return rows[0] if rows else None


def main():
    failures = 0
    try:
        prime_neon_runtime()
    except Exception as error:
        print(f"FAIL [db_runtime] {error}")
        return 1

    pair = find_pair()
    if not emit(bool(pair), "accepted_pair", str(pair)):
        return 1

    alpha_id = pair["alpha_id"]
    beta_id = pair["beta_id"]
    beta_profile = load_profile(beta_id)
    alpha_profile = load_profile(alpha_id)
    if not emit(bool(alpha_profile and beta_profile), "profile_lookup", f"alpha={alpha_profile} beta={beta_profile}"):
        return 1
    alpha_policy = get_action_policy(alpha_id, beta_profile)
    beta_policy = get_action_policy(beta_id, alpha_profile)

    if not emit(alpha_policy.get("can_chat") is True, "message_permission_alpha_to_beta", str(alpha_policy)):
        failures += 1
    if not emit(alpha_policy.get("can_call") is True, "call_permission_alpha_to_beta", str(alpha_policy)):
        failures += 1
    if not emit(beta_policy.get("can_chat") is True, "message_permission_beta_to_alpha", str(beta_policy)):
        failures += 1
    if not emit(beta_policy.get("can_call") is True, "call_permission_beta_to_alpha", str(beta_policy)):
        failures += 1

    try:
        mutual = get_mutual_friends_summary(alpha_id, beta_id, limit=3)
        if not emit(isinstance(mutual, dict) and isinstance(mutual.get("items", []), list), "mutual_friends_summary_safe", str(mutual)):
            failures += 1
    except Exception as error:
        print(f"FAIL [mutual_friends_summary_safe] {error}")
        failures += 1

    print("PASS" if failures == 0 else "FAIL")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
