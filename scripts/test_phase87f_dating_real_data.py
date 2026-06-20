"""Phase 87F — Verify dating page has no hardcoded data, real API wiring."""

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
    print("PHASE 87F — DATING REAL DATA")
    print("=" * 60)

    dating_tpl = os.path.join(ROOT, "templates", "dating", "index.html")
    discover_tpl = os.path.join(ROOT, "templates", "dating", "discover.html")
    dating_routes = os.path.join(ROOT, "api_routes", "dating_routes.py")

    print("\n--- Hardcoded data check ---")
    with open(discover_tpl) as f:
        disc = f.read()
    check("NO hardcoded age '24' fallback", "'24" not in disc,
          "age fallback found")

    with open(discover_tpl) as f:
        disc = f.read()
    check("NO hardcoded location 'Windhoek'", "'Windhoek'" not in disc,
          "location fallback found")

    check("NO hardcoded distance loop.index", "loop.index * 3" not in disc,
          "fake distance found")

    print("\n--- API wiring ---")
    with open(discover_tpl) as f:
        disc = f.read()
    check("swipe buttons wired to /dating/api/like", '/dating/api/like' in disc)
    check("swipe buttons wired to /dating/api/pass", '/dating/api/pass' in disc)
    check("swipe buttons wired to /dating/api/super-like", '/dating/api/super-like' in disc)
    check("CSRF token in swipe fetch", 'getCsrfToken' in disc or 'csrf' in disc)

    print("\n--- Backend routes ---")
    with open(dating_routes) as f:
        routes = f.read()
    check("/dating/api/like POST exists", '/api/like' in routes)
    check("/dating/api/pass POST exists", '/api/pass' in routes)
    check("/dating/api/super-like POST exists", '/api/super-like' in routes)
    check("/dating/discover GET exists", '/discover' in routes)

    print("\n--- Empty state ---")
    with open(dating_tpl) as f:
        index = f.read()
    has_empty = "No more" in index or "No matches" in index or "No dating" in index
    check("empty state present", has_empty)

    print(f"\n{'=' * 60}")
    total = PASS + FAIL
    if FAIL == 0:
        print(f"PHASE 87F DATING REAL DATA: PASS ({PASS}/{total})")
    else:
        print(f"PHASE 87F DATING REAL DATA: FAIL ({PASS}/{total})")
    print(f"{'=' * 60}")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
