"""Phase 87 — Blocking Schema Safe Test."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.blocking_service import is_blocked, is_blocked_any, get_blocked_ids

PASS = 0
FAIL = 0

def check(name, ok):
    global PASS, FAIL
    if ok:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name}")
        FAIL += 1

def run():
    global PASS, FAIL
    print("Phase 87: Blocking Schema Safe")

    check("is_blocked function exists", callable(is_blocked))
    check("is_blocked_any function exists", callable(is_blocked_any))
    check("get_blocked_ids function exists", callable(get_blocked_ids))

    # Safe with bad UUIDs — no errors expected
    check("is_blocked None safe", not is_blocked(None, None))
    check("is_blocked bad uuid safe", not is_blocked("not-a-uuid", "also-not-uuid"))
    check("is_blocked_any None safe", not is_blocked_any(None, None))
    check("is_blocked_any bad uuid safe", not is_blocked_any("bad", "bad"))
    check("get_blocked_ids None safe", get_blocked_ids(None) == [])
    check("get_blocked_ids bad uuid safe", get_blocked_ids("bad") == [])

    # Module loads without error
    import services.blocking_service
    check("blocking_service module loads", True)

    print(f"\nPhase 87 Blocking Schema Safe: {PASS} passed, {FAIL} failed")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
