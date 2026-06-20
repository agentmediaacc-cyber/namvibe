"""Phase 87H — static checks for local auth login fallback."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
    print("=" * 60)
    print("PHASE 87H — LOGIN LOCAL AUTH FALLBACK")
    print("=" * 60)

    path = os.path.join(ROOT, "services", "auth_service.py")
    with open(path) as f:
        src = f.read()
    low = src.lower()

    check("has local auth lookup helper", "def _get_local_auth_credential" in src)
    check("uses Neon table existence check", "neon_table_exists(\"chain_local_auth_credentials\")" in src)
    check("looks up by profile_id", "WHERE profile_id = %s" in src)
    check("verifies local hash", "check_password_hash(local_hash, password)" in src)
    check("stores same login session on success", "_store_login_session(login_profile" in src)
    check("updates last_used_at", "last_used_at = now()" in src)
    check("debug checked flag", "local_auth_table_checked" in src)
    check("debug found flag", "local_auth_found" in src)
    check("debug success flag", "local_auth_success" in src)
    check("missing local row is password reset required", "password_reset_required" in src)
    check("wrong local auth password remains invalid", "Password is incorrect." in src)
    check("does not bypass password checks", "local_auth_success\"] = True" in src and "check_password_hash(local_hash, password)" in src)
    check("does not print raw password", "print(password" not in src and "print(f\"{password" not in src)
    check("does not alter Supabase sign-in", "sign_in_with_password" in src)
    check("no plaintext local auth storage", "password_hash text" not in low)

    total = PASS + FAIL
    print(f"\nPHASE 87H LOGIN LOCAL AUTH FALLBACK: {'PASS' if FAIL == 0 else 'FAIL'} ({PASS}/{total})")
    return FAIL == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
