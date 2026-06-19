"""Phase 87 — Terminal Log Clean Test."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    print("Phase 87: Terminal Log Clean")

    # Check log rate limit service works
    from services.log_rate_limit_service import sql_fingerprint, should_log, reset_rate_limits

    check("sql_fingerprint exists", callable(sql_fingerprint))
    check("should_log exists", callable(should_log))
    check("reset_rate_limits exists", callable(reset_rate_limits))

    fp1 = sql_fingerprint("SELECT 1 FROM chain_friends WHERE profile_id_1 = %s AND profile_id_2 = %s LIMIT 1")
    fp2 = sql_fingerprint("SELECT 1 FROM chain_friends WHERE profile_id_1 = %s AND profile_id_2 = %s LIMIT 1")
    check("same SQL → same fingerprint", fp1 == fp2)

    fp3 = sql_fingerprint("SELECT 1 FROM chain_follows WHERE follower_profile_id = %s")
    check("different SQL → different fingerprint", fp1 != fp3)

    reset_rate_limits()
    check("first call should_log True", should_log(fp1))
    check("second immediate call should_log False", not should_log(fp1))

    reset_rate_limits()
    check("after reset should_log True", should_log(fp1))

    # Check neon_service imports rate limit
    from services.neon_service import log_warning as neon_log_warning
    check("neon_service uses log_warning", callable(neon_log_warning))

    print(f"\nPhase 87 Terminal Log Clean: {PASS} passed, {FAIL} failed")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
