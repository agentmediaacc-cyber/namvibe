"""Phase 87E — Verify homepage speed guards are in place."""

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
    print("PHASE 87E — HOMEPAGE SPEED STATIC")
    print("=" * 60)

    with open("services/homepage_service.py", "r") as f:
        content = f.read()

    # 1. Time budget functions
    check("_time_budget helper exists", "_time_budget" in content)
    check("per-section budget checks (800ms)", "budget_800" in content)
    check("per-section budget checks (1000ms)", "budget_1000" in content)

    # 2. Cached popular_towns
    check("popular_towns cached 10min", "ttl=600" in content or "ttl = 600" in content)

    # 3. Slow log warning
    check("slow build warning >3s", "elapsed > 3000" in content or "slow:" in content)

    # 4. build_tiktok_home_payload is wrapped
    check("build_tiktok_home_payload has try/except", 
          "try:" in content and "build_tiktok_home_payload error" in content)

    # 5. Home route in app.py has shell fallback
    with open("app.py", "r") as f:
        app_content = f.read()
    check("home route uses try/except shell", "shell" in app_content)
    check("home route populates safe defaults", 
          all(k in app_content for k in ["reels_feed", "suggested_creators", "recommendation_cards"]))

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
