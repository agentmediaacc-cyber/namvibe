"""Phase 82: homepage links point to real routes or safe redirects."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0


def check(name, condition):
    global PASS, FAIL
    if condition:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name}")
        FAIL += 1


def run():
    print("Phase 82: Home Links Static")
    tpl = open("templates/chain_home.html").read()
    app = open("app.py").read()
    js = open("static/js/home_real_actions.js").read()

    required = {
        "create post": "/posts/create",
        "story": "/status/create",
        "upload reel": "/reels/upload",
        "go live": "/live/studio",
        "messages": "/messages/",
        "calls": "/calls/",
        "wallet": "/wallet/",
        "dating": "/dating/",
        "profile": "/profile/",
        "security": "/security/privacy",
        "notifications": "/notifications/",
    }
    for label, path in required.items():
        check(f"{label} route wired", path in tpl or path in app)

    check("settings uses valid profile settings route", "/profile/settings" in tpl or "/profile/settings" in app)
    check("home includes real action JS", "home_real_actions.js" in tpl)
    check("home action JS handles data-action", "data-action" in js and "like" in js and "save" in js and "share" in js)
    check("home action JS shows toast on failures", "toast(error.message" in js)
    check("home action JS disables during request", "setBusy(button, true)" in js)

    print(f"\nPhase 82 Home Links: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
