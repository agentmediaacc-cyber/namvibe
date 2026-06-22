#!/usr/bin/env python3
"""Tests call security: auth, self-call, block, history isolation."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.neon_service import fast_query, write_query
from services.webrtc_call_service import (
    create_call, get_call, get_call_history,
)
from services.call_permission_service import (
    can_start_call, can_access_call_log,
)


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"{status}: {label}" + (f" - {detail}" if detail and not condition else ""))
    return bool(condition)


def find_or_create_test_user(username, display_name):
    rows = fast_query(
        "SELECT id FROM chain_profiles WHERE username = %s LIMIT 1",
        (username,), default=[]
    )
    if rows:
        return str(rows[0]["id"])
    import uuid
    pid = str(uuid.uuid4())
    write_query(
        "INSERT INTO chain_profiles (id, auth_user_id, username, display_name, created_at) VALUES (%s, %s, %s, %s, now()) ON CONFLICT DO NOTHING",
        (pid, pid, username, display_name),
    )
    return pid


def main():
    # Warm up DB pool before first real query
    from services.neon_service import fast_query as _warmup
    _warmup("SELECT 1", default=[])

    user_a = find_or_create_test_user("test_sec_a_p92", "Security A")
    user_b = find_or_create_test_user("test_sec_b_p92", "Security B")
    user_c = find_or_create_test_user("test_sec_c_p92", "Security C")

    # Clean up any leftover active calls from previous test runs
    from services.webrtc_call_service import get_active_call, end_call
    for pid in (user_a, user_b, user_c):
        active = get_active_call(pid)
        if active:
            end_call(active["id"], pid, end_reason="test_cleanup")

    checks = []

    # 1. User cannot call self
    perm = can_start_call(user_a, user_a)
    checks.append(check("cannot call self", not perm.get("ok") and "self_call" in perm.get("error", "")))

    # 2. Missing profile returns error
    perm = can_start_call(None, user_b)
    checks.append(check("missing caller rejected", not perm.get("ok")))

    # 3. Blocked check
    try:
        from services.neon_service import write_query
        write_query(
            "INSERT INTO chain_blocks (blocker_profile_id, blocked_profile_id, created_at) VALUES (%s, %s, now()) ON CONFLICT DO NOTHING",
            (user_b, user_a),
        )
    except Exception:
        pass
    perm = can_start_call(user_a, user_b)
    checks.append(check("blocked user cannot call",
        not perm.get("ok") and "blocked" in perm.get("error", "")))

    # 4. Invalid call_id rejected
    invalid = get_call("00000000-0000-0000-0000-000000000000")
    checks.append(check("invalid call_id returns none", invalid is None))

    # 5. Log access isolation
    call_result = create_call(user_a, user_c, call_type="audio")
    if call_result.get("ok"):
        from services.call_history_service import get_call_history as get_history
        import uuid
        from services.call_history_service import create_call_log
        create_call_log(
            call_result["call"]["id"], user_a, user_c,
            "outgoing", "audio", "ended", 30,
        )
        hist_a = get_history(user_a)
        hist_b = get_history(user_b)
        checks.append(check("user sees own history", any(
            h.get("other_profile_id") == user_c for h in hist_a
        )))
        checks.append(check("user cannot see other's history",
            not any(h.get("other_profile_id") == user_c for h in hist_b)
        ))

        is_creator = can_access_call_log(user_a, user_a)
        is_other = can_access_call_log(user_b, user_a)
        checks.append(check("owner can access log", is_creator))
        checks.append(check("non-owner cannot access log", not is_other))

    # 6. Non-participant cannot end (via permission check)
    from services.call_permission_service import can_end_call
    call_obj = call_result.get("call") if call_result.get("ok") else None
    if call_obj:
        checks.append(check("participant can end", can_end_call(call_obj, user_a)))
        checks.append(check("non-participant cannot end", not can_end_call(call_obj, "00000000-0000-0000-0000-000000000000")))

    if not all(checks):
        raise SystemExit(1)
    print("test_call_security_ok")


if __name__ == "__main__":
    main()
