"""Phase 87H — static checks for local auth credential schema migration."""

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
    print("PHASE 87H — LOCAL AUTH SCHEMA")
    print("=" * 60)

    path = os.path.join(ROOT, "scripts", "phase87h_local_auth_schema.py")
    check("schema migration exists", os.path.exists(path))
    with open(path) as f:
        src = f.read()
    low = src.lower()

    check("creates chain_local_auth_credentials", "create table if not exists chain_local_auth_credentials" in low)
    for column in ("id uuid primary key", "profile_id uuid not null", "username text", "email text", "password_hash text not null", "last_used_at timestamptz"):
        check(f"schema has {column}", column in low)
    check("profile_id unique constraint", "unique (profile_id)" in low)
    check("username lower index", "lower(username)" in low)
    check("email lower index", "lower(email)" in low)
    check("uses write_query", "write_query" in src)

    total = PASS + FAIL
    print(f"\nPHASE 87H LOCAL AUTH SCHEMA: {'PASS' if FAIL == 0 else 'FAIL'} ({PASS}/{total})")
    return FAIL == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
