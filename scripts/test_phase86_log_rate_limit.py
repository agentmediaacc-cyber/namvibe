"""Verify log_rate_limit_service exists and functions work."""

import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0

def check(name, condition):
    global PASS, FAIL
    if condition:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name}")
        FAIL += 1

print("Phase 86: Log Rate Limit")

try:
    from services.log_rate_limit_service import sql_fingerprint, should_log, reset_rate_limits
    check("log_rate_limit_service imports", True)
    check("sql_fingerprint exists", callable(sql_fingerprint))
    check("should_log exists", callable(should_log))
    check("reset_rate_limits exists", callable(reset_rate_limits))
    
    fp = sql_fingerprint("SELECT 1 FROM chain_friends WHERE id = %s")
    check("fingerprint returns a string", isinstance(fp, str))
    check("fingerprint is 32 chars (md5)", len(fp) == 32)
    
    reset_rate_limits()
    first = should_log(fp)
    check("first call should_log returns True", first is True)
    
    second = should_log(fp)
    check("second immediate call should_log returns False", second is False)
    
    reset_rate_limits()
    reset = should_log(fp)
    check("after reset, should_log returns True again", reset is True)
    
except ImportError as e:
    check(f"module import failed: {e}", False)
except Exception as e:
    check(f"test error: {e}", False)

# Check neon_service integration
with open("services/neon_service.py") as f:
    ns = f.read()
check("neon_service uses should_log", "should_log" in ns)
check("neon_service uses sql_fingerprint", "sql_fingerprint" in ns)

print(f"\nPhase 86 Log Rate Limit: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
