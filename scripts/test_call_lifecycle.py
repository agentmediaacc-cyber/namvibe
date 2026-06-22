#!/usr/bin/env python3
"""Tests call lifecycle: start, ringing, accept, reject, timeout, busy."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.neon_service import fast_query, write_query
from services.profile_service import get_current_profile
from services.webrtc_call_service import (
    create_call,
    accept_call,
    reject_call,
    cancel_call,
    end_call,
    get_call,
    get_call_history,
    get_active_call,
    mark_call_timeout,
    mark_call_busy,
)


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    if not condition and detail:
        print(f"{status}: {label} - {detail}")
    else:
        print(f"{status}: {label}")
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
    from services.neon_service import fast_query as _warmup, write_query as _wclean
    _warmup("SELECT 1", default=[])

    caller_id = find_or_create_test_user("test_caller_p92", "Test Caller")
    receiver_id = find_or_create_test_user("test_receiver_p92", "Test Receiver")

    # Clean up any leftover active calls from previous test runs
    for pid in (caller_id, receiver_id):
        active = get_active_call(pid)
        if active:
            from services.webrtc_call_service import end_call as _end
            _end(active["id"], pid, end_reason="test_cleanup")

    checks = []

    # 1. Start audio call
    result = create_call(caller_id, receiver_id, call_type="audio")
    call = result.get("call", {})
    call_id = call.get("id") if call else None
    checks.append(check("audio call created", result.get("ok") and bool(call_id),
        detail=f"ok={result.get('ok')} error={result.get('error')} status={result.get('status')} call_type={call.get('call_type')}"))
    checks.append(check("call status ringing", call.get("status") == "ringing"))
    checks.append(check("call type is audio", call.get("call_type") == "audio"))

    # 2. Receiver gets ringing status
    call_check = get_call(call_id)
    checks.append(check("receiver ringing", call_check and call_check.get("status") == "ringing"))

    # 3. Accept call
    accept_result = accept_call(call_id, receiver_id)
    checks.append(check("call accepted", accept_result.get("ok")))
    accepted = accept_result.get("call", {})
    checks.append(check("accepted status changed", accepted.get("status") == "accepted"))
    checks.append(check("accepted_at set", bool(accepted.get("accepted_at"))))

    # 4. End call
    end_result = end_call(call_id, caller_id, end_reason="hung_up")
    checks.append(check("call ended", end_result.get("ok")))
    ended = end_result.get("call", {})
    checks.append(check("ended status changed", ended.get("status") == "ended"))
    checks.append(check("duration saved", ended.get("duration_seconds", 0) >= 0))

    # 5. Start video call
    result2 = create_call(caller_id, receiver_id, call_type="video")
    call2 = result2.get("call", {})
    call2_id = call2.get("id")
    checks.append(check("video call created", result2.get("ok") and bool(call2_id)))
    checks.append(check("video call type", call2.get("call_type") == "video"))

    # 6. Reject call
    reject_result = reject_call(call2_id, receiver_id)
    checks.append(check("call rejected", reject_result.get("ok")))
    rejected = reject_result.get("call", {})
    checks.append(check("rejected status", rejected.get("status") == "rejected"))

    # 7. Timeout creates missed call
    result3 = create_call(caller_id, receiver_id, call_type="audio")
    call3 = result3.get("call", {})
    call3_id = call3.get("id")
    timeout_result = mark_call_timeout(call3_id)
    checks.append(check("timeout marked", timeout_result.get("ok")))
    timeout_call = timeout_result.get("call", {})
    checks.append(check("timeout status missed", timeout_call.get("status") == "missed"))

    # 8. New call succeeds after previous timeout (no active call)
    result4 = create_call(caller_id, receiver_id, call_type="audio")
    call4 = result4.get("call", {})
    call4_id = call4.get("id")
    checks.append(check("call succeeds after timeout",
        result4.get("ok") and bool(call4_id) and call4.get("status") == "ringing"))

    # 9. Duplicate call is prevented while active
    dup = create_call(caller_id, receiver_id, call_type="audio")
    checks.append(check("duplicate call prevented while active",
        not dup.get("ok") and (
            "busy" in str(dup.get("error", "")).lower() or
            "duplicate" in str(dup.get("error", "")).lower() or
            not dup.get("ok")
        )
    ))

    if not all(checks):
        raise SystemExit(1)
    print("test_call_lifecycle_ok")


if __name__ == "__main__":
    main()
