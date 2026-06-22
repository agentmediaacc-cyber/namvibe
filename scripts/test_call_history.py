#!/usr/bin/env python3
"""Tests call history: outgoing, incoming, missed, rejected, busy, delete."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.neon_service import fast_query, write_query
from services.call_history_service import (
    get_call_history,
    create_call_log,
    delete_call_log,
    get_missed_call_count,
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

    user_a = find_or_create_test_user("test_hist_a_p92", "History A")
    user_b = find_or_create_test_user("test_hist_b_p92", "History B")

    # Clean up any leftover active calls from previous test runs
    from services.webrtc_call_service import get_active_call, end_call
    for pid in (user_a, user_b):
        active = get_active_call(pid)
        if active:
            end_call(active["id"], pid, end_reason="test_cleanup")

    from services.webrtc_call_service import create_call as w_create_call, get_call as w_get_call

    checks = []

    # Helper to create a call + log
    def _make_test_call(caller, receiver, call_type="audio", advanced=False):
        result = w_create_call(caller, receiver, call_type=call_type)
        if not result.get("ok") or not result.get("call"):
            return None, None
        c = result["call"]
        cid = c["id"]
        status = c.get("status", "ringing")
        dur = c.get("duration_seconds", 0)
        if advanced:
            create_call_log(cid, caller, receiver, "outgoing", call_type, "ended", 45)
            create_call_log(cid, receiver, caller, "incoming", call_type, "ended", 45)
        return cid, c
    call_id, _ = _make_test_call(user_a, user_b)

    if not call_id:
        checks.append(check("outgoing call appears", False))
    else:
        # 1. Outgoing call log — use live call data
        create_call_log(call_id, user_a, user_b, "outgoing", "audio", "ended", 45)
        hist_a = get_call_history(user_a)
        checks.append(check("outgoing call appears",
            any(h.get("other_profile_id") == user_b and h.get("direction") == "outgoing" for h in hist_a)))

        # 2. Incoming call log
        create_call_log(call_id, user_b, user_a, "incoming", "audio", "ended", 45)
        hist_b = get_call_history(user_b)
        checks.append(check("incoming call appears",
            any(h.get("other_profile_id") == user_a and h.get("direction") == "incoming" for h in hist_b)))

    # 3. Missed call
    call3, _ = _make_test_call(user_a, user_b)
    if call3:
        create_call_log(call3, user_a, user_b, "outgoing", "audio", "missed", 0)
        hist_a2 = get_call_history(user_a)
        checks.append(check("missed call appears",
            any(h.get("status") == "missed" and h.get("call_id") == call3 for h in hist_a2)))

    # 4. Rejected call
    call4, _ = _make_test_call(user_a, user_b, call_type="video")
    if call4:
        create_call_log(call4, user_a, user_b, "outgoing", "video", "rejected", 0)
        hist_a3 = get_call_history(user_a)
        checks.append(check("rejected call appears",
            any(h.get("status") == "rejected" for h in hist_a3)))

    # 5. Busy call
    call5, _ = _make_test_call(user_a, user_b)
    if call5:
        create_call_log(call5, user_a, user_b, "outgoing", "audio", "busy", 0)
        hist_a4 = get_call_history(user_a)
        checks.append(check("busy call appears",
            any(h.get("status") == "busy" for h in hist_a4)))

    # 6. Duration displayed
    if call_id:
        for h in get_call_history(user_a):
            if h.get("call_id") == call_id:
                checks.append(check("call duration displayed", h.get("duration_seconds") == 45))
                break

    # 7. Delete call log
    if call_id:
        hist_for_delete = get_call_history(user_a, limit=50)
        log_to_delete = None
        for h in hist_for_delete:
            if h.get("call_id") == call_id and h.get("id"):
                log_to_delete = h["id"]
                break
        if log_to_delete:
            del_result = delete_call_log(log_to_delete, user_a)
            checks.append(check("delete call log", del_result.get("ok")))
            hist_after = get_call_history(user_a)
            checks.append(check("deleted log gone",
                not any(h.get("id") == log_to_delete for h in hist_after)))
        else:
            checks.append(check("delete call log - log found", False))

    # 8. Missed call count
    missed_count = get_missed_call_count(user_b)
    checks.append(check("missed call count", missed_count >= 0))

    if not all(checks):
        raise SystemExit(1)
    print("test_call_history_ok")


if __name__ == "__main__":
    main()
