"""Phase 87F — Verify dev password reset script exists and is safe."""

import sys, os
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
    global PASS, FAIL
    print("=" * 60)
    print("PHASE 87F — DEV PASSWORD RESET")
    print("=" * 60)

    script = os.path.join(ROOT, "scripts", "dev_reset_user_password.py")

    print("\n--- Script exists ---")
    check("scripts/dev_reset_user_password.py exists", os.path.exists(script))

    with open(script) as f:
        src = f.read()

    print("\n--- Safety checks ---")
    check("is development-only (FLASK_ENV=development or CHAIN_ALLOW_DEV_PASSWORD_RESET)",
          "FLASK_ENV" in src or "CHAIN_ALLOW_DEV_PASSWORD_RESET" in src)
    check("does NOT print password to stdout",
          "print(password" not in src and 'print(f"{' not in src or '"password"' not in src)
    check("updates password hash using werkzeug",
          "generate_password_hash" in src)
    check("does not touch Supabase auth",
          "supabase" not in src.lower())
    check("outputs password_reset_local_ok",
          "password_reset_local_ok" in src)
    check("uses argparse for --username and --password",
          "argparse" in src and "--username" in src and "--password" in src)

    print(f"\n{'=' * 60}")
    total = PASS + FAIL
    if FAIL == 0:
        print(f"PHASE 87F DEV PASSWORD RESET: PASS ({PASS}/{total})")
    else:
        print(f"PHASE 87F DEV PASSWORD RESET: FAIL ({PASS}/{total})")
    print(f"{'=' * 60}")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
