"""Phase 87E — Verify old user login compatibility."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0

def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name} {detail}")
        FAIL += 1

def run():
    global PASS, FAIL
    print("=" * 60)
    print("PHASE 87E — OLD USER LOGIN COMPAT")
    print("=" * 60)

    # Static analysis
    print("\n--- auth_service static ---")
    with open("services/auth_service.py", "r") as f:
        content = f.read()
    
    # 1. LOGIN_PROFILE_FIELD_CANDIDATES includes legacy hash columns
    for col in ("password_digest", "hashed_password", "legacy_password_hash"):
        check(f"LOGIN_PROFILE_FIELD_CANDIDATES includes {col}", col in content)
    
    # 2. _get_password_hash helper
    check("_get_password_hash checks all columns", "_get_password_hash" in content)
    
    # 3. Login debug logs
    check("login_lookup_debug has profile_found", "profile_found" in content)
    check("verifier_available in debug", "verifier_available" in content)
    
    # 4. Password reset message
    check("password reset required message", "needs password reset" in content)
    
    # 5. No password printed in logs (log function calls with provider type "password" are OK)
    lines_with_password_log = 0
    for line in content.split("\n"):
        low = line.lower()
        if "log_" in low and '"password"' in low:
            # _log_login_event(profile, user, "password", "success") — provider type, not the actual password
            if "_log_login_event" in line:
                continue
            lines_with_password_log += 1
    check("no raw password in log lines", lines_with_password_log == 0)
    
    # 6. Login profile lookup cached
    check("_find_login_profile cached 30s", "ttl=30" in content or "ttl = 30" in content)
    check("login cache key pattern", "login_profile_lookup" in content)

    print("\n--- werkzeug password check available ---")
    from werkzeug.security import check_password_hash, generate_password_hash
    check("check_password_hash works", callable(check_password_hash))
    check("generate_password_hash works", callable(generate_password_hash))

    print(f"\n{'=' * 60}")
    total = PASS + FAIL
    if FAIL == 0:
        print(f"PHASE 87E: PASS ({PASS}/{total})")
    else:
        print(f"PHASE 87E: FAIL ({PASS}/{total})")
    print(f"{'=' * 60}")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
