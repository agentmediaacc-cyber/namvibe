"""Phase 87 — Profile Speed Static Test."""
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
    print("Phase 87: Profile Speed Static")

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_dir = os.path.join(root, "templates", "profile")

    key_templates = [
        "base_profile.html",
        "index.html",
        "edit.html",
        "security.html",
    ]
    for t in key_templates:
        path = os.path.join(template_dir, t)
        check(f"profile/{t} exists", os.path.isfile(path))

    js_path = os.path.join(root, "static", "js", "profile_command_center.js")
    check("profile_command_center.js exists", os.path.isfile(js_path))

    try:
        from services.relationship_privacy_service import (
            can_view_profile, can_view_posts, can_view_reels,
            can_view_followers, can_view_following,
        )
        check("privacy functions import", True)
    except ImportError as e:
        check(f"privacy functions import ({e})", False)

    print(f"\nPhase 87 Profile Speed: {PASS} passed, {FAIL} failed")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
