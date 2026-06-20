"""Phase 87H — verify dev reset writes local auth fallback safely."""

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
    print("PHASE 87H — DEV RESET LOCAL AUTH")
    print("=" * 60)

    path = os.path.join(ROOT, "scripts", "dev_reset_user_password.py")
    with open(path) as f:
        src = f.read()
    low = src.lower()

    check("still requires local/dev opt-in", "flask_env" in low and "chain_allow_dev_password_reset" in low)
    check("uses werkzeug hash", "generate_password_hash" in src)
    check("keeps existing chain_profiles password-column path", "UPDATE chain_profiles SET password_hash" in src)
    check("falls back to local auth table", "chain_local_auth_credentials" in src)
    check("upserts by profile_id", "ON CONFLICT (profile_id)" in src)
    check("stores only password_hash", "password_hash = EXCLUDED.password_hash" in src)
    check("no longer exits no_password_column_found", "no_password_column_found" not in src)
    check("prints success marker", "password_reset_local_ok" in src)
    check("does not touch Supabase auth", "supabase" not in low)
    check("does not print raw password", "print(args.password" not in src and "print(password" not in src)

    total = PASS + FAIL
    print(f"\nPHASE 87H DEV RESET LOCAL AUTH: {'PASS' if FAIL == 0 else 'FAIL'} ({PASS}/{total})")
    return FAIL == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
