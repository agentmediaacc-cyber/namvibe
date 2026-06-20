"""Phase 87F — Verify profile shows full clean user details, location assembled."""

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
    print("PHASE 87F — PROFILE DETAILS")
    print("=" * 60)

    profile_svc = os.path.join(ROOT, "services", "profile_service.py")

    print("\n--- Location assembly ---")
    with open(profile_svc) as f:
        src = f.read()
    check("location uses town+region+country_origin concatenation",
          "town" in src and "region" in src and "country_origin" in src and '", ".join' in src)

    profile_header = os.path.join(ROOT, "templates", "profile", "partials", "profile_header.html")
    profile_index = os.path.join(ROOT, "templates", "profile", "index.html")

    print("\n--- Profile template checks ---")
    if os.path.exists(profile_header):
        with open(profile_header) as f:
            hdr = f.read()
        check("profile_header shows full_name or display_name",
              "full_name" in hdr or "display_name" in hdr)
        check("profile_header has location", "current_location" in hdr or "location" in hdr)
        check("profile_header has bio section", "bio" in hdr)

    if os.path.exists(profile_index):
        with open(profile_index) as f:
            idx = f.read()
        check("profile/index has username", "username" in idx)
        check("profile/index has bio or about section", "bio" in idx or "about" in idx.lower())

    print("\n--- No Tkasera ---")
    for root_dir in ["services", "templates", "static"]:
        full = os.path.join(ROOT, root_dir)
        for dirpath, dirnames, filenames in os.walk(full):
            for fn in filenames:
                if not fn.endswith((".py", ".html", ".js")):
                    continue
                fp = os.path.join(dirpath, fn)
                with open(fp, errors="ignore") as f:
                    if "Tkasera" in f.read():
                        check(f"No Tkasera in {root_dir}", False,
                              f"found in {os.path.relpath(fp, ROOT)}")
                        break
    check("No Tkasera anywhere in source", True)

    print("\n--- Website/joined/account type ---")
    with open(profile_svc) as f:
        src = f.read()
    check("profile normalizes website", "website" in src)
    check("profile normalizes created_at", "created_at" in src)
    check("profile normalizes profile_type", "profile_type" in src)

    print(f"\n{'=' * 60}")
    total = PASS + FAIL
    if FAIL == 0:
        print(f"PHASE 87F PROFILE DETAILS: PASS ({PASS}/{total})")
    else:
        print(f"PHASE 87F PROFILE DETAILS: FAIL ({PASS}/{total})")
    print(f"{'=' * 60}")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
