"""Phase 87 — Home Speed Static Test."""
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
    print("Phase 87: Home Speed Static")

    # Check common patterns exist
    try:
        from services.homepage_service import build_homepage_payload
        check("build_homepage_payload exists", True)
    except (ImportError, Exception) as e:
        check(f"build_home exists ({e})", False)

    try:
        from services.smart_suggestion_service import get_smart_suggestions, build_recommendation_cards
        check("get_smart_suggestions exists", True)
        check("build_recommendation_cards exists", True)
    except (ImportError, Exception) as e:
        check(f"smart suggestion imports ({e})", False)

    # Check JS files exist
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js_files = [
        "static/js/reels_autoplay_engine.js",
        "static/js/status_autoplay_engine.js",
        "static/js/home_real_actions.js",
        "static/js/namvibe_global_badges.js",
    ]
    for jf in js_files:
        path = os.path.join(root, jf)
        check(f"{jf} exists", os.path.isfile(path))

    print(f"\nPhase 87 Home Speed: {PASS} passed, {FAIL} failed")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
